"""
Device Manager — Persistent Device Intelligence Registry.

The central nervous system for all device state. Tracks every device on the LAN
with rich metadata, health status, and persistent storage across restarts.
"""

import json
import asyncio
import structlog
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path
from datetime import datetime, timezone

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


@dataclass
class DeviceRecord:
    """Rich device profile for any LAN device."""

    uuid: str
    ip: str
    port: int = 8009
    hostname: str = ""
    friendly_name: str = "Unknown Device"
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    device_type: str = "unknown"  # chromecast, dlna, speaker, light, etc.
    supported_protocols: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    last_seen: str = ""
    first_seen: str = ""
    is_online: bool = True
    trust_level: str = "known"  # known, trusted, unknown, suspicious
    metadata: dict[str, Any] = field(default_factory=dict)

    # Connection cache key (not persisted)
    _connection: Any = field(default=None, repr=False)

    def touch(self):
        """Update last_seen to now."""
        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.is_online = True

    def to_dict(self) -> dict:
        """Serialize for JSON persistence (exclude private fields)."""
        d = asdict(self)
        d.pop("_connection", None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceRecord":
        data.pop("_connection", None)
        return cls(**data)


class DeviceManager:
    """
    Persistent device registry with health monitoring.

    Devices are discovered by LANMonitor and registered here.
    State is persisted to JSON so it survives restarts.
    """

    def __init__(self, event_bus: EventBus, data_dir: Path):
        self.event_bus = event_bus
        self._devices: dict[str, DeviceRecord] = {}  # keyed by uuid
        self._registry_path = data_dir / "device_registry.json"
        self._lock = asyncio.Lock()
        self._health_task: asyncio.Task | None = None

        # Load persisted state
        self._load_registry()

    def _load_registry(self):
        """Load device registry from disk."""
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r") as f:
                    data = json.load(f)
                for uuid_key, device_data in data.items():
                    record = DeviceRecord.from_dict(device_data)
                    record.is_online = False  # Mark all as offline until re-discovered
                    self._devices[uuid_key] = record
                logger.info("device_registry_loaded", count=len(self._devices))
            except Exception as e:
                logger.warning("device_registry_load_failed", error=str(e))

    def _save_registry(self):
        """Persist device registry to disk."""
        try:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._registry_path, "w") as f:
                json.dump(
                    {k: v.to_dict() for k, v in self._devices.items()},
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning("device_registry_save_failed", error=str(e))

    async def register_device(self, record: DeviceRecord) -> DeviceRecord:
        """Register or update a device. Returns the canonical record."""
        async with self._lock:
            existing = self._devices.get(record.uuid)

            if existing:
                # Update mutable fields
                was_offline = not existing.is_online
                existing.ip = record.ip
                existing.port = record.port
                existing.friendly_name = record.friendly_name or existing.friendly_name
                existing.model = record.model or existing.model
                existing.manufacturer = record.manufacturer or existing.manufacturer
                existing.device_type = record.device_type or existing.device_type
                existing.hostname = record.hostname or existing.hostname
                existing.metadata.update(record.metadata)
                existing.touch()
                self._save_registry()

                if was_offline:
                    logger.info("device_online", name=existing.friendly_name, ip=existing.ip)
                    await self.event_bus.emit(
                        Event(type=EventType.DEVICE_ONLINE, data=existing.to_dict())
                    )
                return existing
            else:
                # New device
                now = datetime.now(timezone.utc).isoformat()
                record.first_seen = now
                record.last_seen = now
                record.is_online = True
                self._devices[record.uuid] = record
                self._save_registry()

                logger.info(
                    "device_registered",
                    name=record.friendly_name,
                    ip=record.ip,
                    type=record.device_type,
                )
                await self.event_bus.emit(
                    Event(type=EventType.NETWORK_DEVICE_DISCOVERED, data=record.to_dict())
                )
                return record

    async def mark_offline(self, uuid: str):
        """Mark a device as offline."""
        async with self._lock:
            device = self._devices.get(uuid)
            if device and device.is_online:
                device.is_online = False
                device._connection = None
                self._save_registry()
                logger.info("device_offline", name=device.friendly_name)
                await self.event_bus.emit(
                    Event(type=EventType.DEVICE_OFFLINE, data=device.to_dict())
                )

    def get_device(self, name_or_ip: str = "") -> DeviceRecord | None:
        """
        Fuzzy lookup: match by friendly_name, model, uuid, or IP.
        If empty string, returns the first online device.
        """
        if not name_or_ip:
            # Return first online device
            for d in self._devices.values():
                if d.is_online:
                    return d
            return None

        target = name_or_ip.lower()
        for d in self._devices.values():
            if (
                target in d.friendly_name.lower()
                or target in d.model.lower()
                or target in d.uuid.lower()
                or target == d.ip
            ):
                return d
        return None

    def list_devices(
        self,
        device_type: str | None = None,
        online_only: bool = False,
    ) -> list[DeviceRecord]:
        """List devices with optional filters."""
        results = list(self._devices.values())
        if device_type:
            results = [d for d in results if d.device_type == device_type]
        if online_only:
            results = [d for d in results if d.is_online]
        return results

    def get_preferred_device(self, device_type: str = "chromecast") -> DeviceRecord | None:
        """Get the user's preferred device of a given type (first online match)."""
        online = [d for d in self._devices.values() if d.is_online and d.device_type == device_type]
        if online:
            # Prefer 'trusted' devices
            trusted = [d for d in online if d.trust_level == "trusted"]
            return trusted[0] if trusted else online[0]
        return None

    async def start_health_monitor(self, interval: int = 30):
        """Start periodic health checks."""
        self._health_task = asyncio.create_task(self._health_loop(interval))

    async def stop_health_monitor(self):
        """Stop health checks."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

    async def _health_loop(self, interval: int):
        """Periodic health check: ping known devices."""
        import socket

        while True:
            await asyncio.sleep(interval)
            for device in list(self._devices.values()):
                if not device.is_online:
                    continue
                try:
                    # Quick TCP connect to the device's cast port
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    result = sock.connect_ex((device.ip, device.port))
                    sock.close()

                    if result != 0:
                        await self.mark_offline(device.uuid)
                    else:
                        device.touch()
                except Exception:
                    await self.mark_offline(device.uuid)
