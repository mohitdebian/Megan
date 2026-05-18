"""
LAN Monitor Service

Passively monitors the local network for devices using mDNS/Zeroconf.
Feeds discovered devices into the DeviceManager for persistent tracking.
"""

import asyncio
import structlog
from typing import Dict, Any

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from core.events import EventBus, Event, EventType
from services.device_manager import DeviceManager, DeviceRecord

logger = structlog.get_logger(__name__)


class LANMonitor:
    """Passively scans and tracks devices on the local network."""

    def __init__(self, event_bus: EventBus, device_manager: DeviceManager):
        self.event_bus = event_bus
        self.device_manager = device_manager
        self.aiozc: AsyncZeroconf | None = None
        self.browser: AsyncServiceBrowser | None = None

    async def start(self):
        """Start the async zeroconf browser."""
        logger.info("lan_monitor_starting")
        self.aiozc = AsyncZeroconf()

        # We are specifically looking for Chromecast / Google TV devices
        service_type = "_googlecast._tcp.local."

        self.browser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            service_type,
            handlers=[self._on_service_state_change],
        )
        logger.info("lan_monitor_started", service_type=service_type)

    async def stop(self):
        """Stop discovery and close zeroconf."""
        logger.info("lan_monitor_stopping")
        if self.aiozc:
            await self.aiozc.async_close()
            self.aiozc = None

    def _on_service_state_change(
        self, zeroconf, service_type, name, state_change
    ):
        """Callback from zeroconf when a service appears/disappears."""
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(self._resolve_and_register(service_type, name))
        elif state_change is ServiceStateChange.Removed:
            asyncio.create_task(self._handle_removed(name))

    async def _resolve_and_register(self, service_type: str, name: str):
        """Resolve the service info and register with DeviceManager."""
        if not self.aiozc:
            return

        info = AsyncServiceInfo(service_type, name)
        await info.async_request(self.aiozc.zeroconf, 3000)

        if info:
            # Parse useful metadata from TXT records
            properties = {}
            for k, v in info.properties.items():
                try:
                    properties[k.decode("utf-8")] = v.decode("utf-8")
                except Exception:
                    pass

            device_uuid = properties.get("id", name.split(".")[0])
            friendly_name = properties.get("fn", name.split(".")[0])
            model_name = properties.get("md", "Unknown Cast Device")
            manufacturer = properties.get("mf", "Google")
            ip_address = (
                ".".join(map(str, info.addresses[0])) if info.addresses else "Unknown"
            )

            record = DeviceRecord(
                uuid=device_uuid,
                ip=ip_address,
                port=info.port or 8009,
                hostname=name,
                friendly_name=friendly_name,
                manufacturer=manufacturer,
                model=model_name,
                device_type="chromecast",
                supported_protocols=["googlecast"],
                capabilities=["media_playback", "volume_control", "youtube"],
                metadata=properties,
            )

            await self.device_manager.register_device(record)
            logger.info(
                "lan_device_discovered",
                device=friendly_name,
                ip=ip_address,
                model=model_name,
            )

    async def _handle_removed(self, name: str):
        """Handle a device disappearing from mDNS."""
        # Try to find by hostname
        for device in self.device_manager.list_devices():
            if device.hostname == name:
                await self.device_manager.mark_offline(device.uuid)
                break
