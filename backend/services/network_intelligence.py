"""
Network Intelligence — Defensive LAN awareness and cybersecurity monitoring.

Provides passive network topology mapping, device fingerprinting,
trust scoring, and anomaly detection. DEFENSIVE ONLY — no exploit behavior.
"""

import os
import re
import json
import asyncio
import socket
import structlog
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path
from datetime import datetime, timezone

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


@dataclass
class NetworkNode:
    """A device discovered on the network."""

    ip: str
    mac: str = ""
    hostname: str = ""
    open_ports: list[int] = field(default_factory=list)
    services: dict[int, str] = field(default_factory=dict)  # port -> service name
    vendor: str = ""
    first_seen: str = ""
    last_seen: str = ""
    trust_score: int = 50  # 0-100, higher = more trusted
    is_known: bool = False
    device_type: str = "unknown"  # router, iot, phone, tv, laptop, etc.
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class NetworkIntelligence:
    """
    Defensive LAN intelligence system.

    - Passively monitors ARP table for device discovery
    - Scans common ports on discovered devices
    - Tracks trust scores and alerts on unknowns
    - Maintains historical snapshots
    """

    # Common ports to check (non-intrusive)
    COMMON_PORTS = {
        22: "SSH",
        53: "DNS",
        80: "HTTP",
        443: "HTTPS",
        548: "AFP",
        554: "RTSP",
        631: "IPP/CUPS",
        3000: "Dev Server",
        3389: "RDP",
        5000: "Flask",
        5353: "mDNS",
        7000: "AirPlay",
        8008: "Chromecast HTTP",
        8009: "Chromecast Cast",
        8080: "HTTP Alt",
        8443: "HTTPS Alt",
        9090: "Cockpit",
    }

    def __init__(self, event_bus: EventBus, data_dir: Path):
        self.event_bus = event_bus
        self._nodes: dict[str, NetworkNode] = {}  # keyed by IP
        self._known_macs: set[str] = set()  # MACs we've seen before
        self._snapshot_dir = data_dir / "network_snapshots"
        self._topology_path = data_dir / "network_topology.json"
        self._scan_task: asyncio.Task | None = None

        self._load_topology()

    def _load_topology(self):
        """Load known topology from disk."""
        if self._topology_path.exists():
            try:
                with open(self._topology_path, "r") as f:
                    data = json.load(f)
                for ip, node_data in data.get("nodes", {}).items():
                    self._nodes[ip] = NetworkNode(**node_data)
                self._known_macs = set(data.get("known_macs", []))
                logger.info("network_topology_loaded", nodes=len(self._nodes))
            except Exception as e:
                logger.warning("network_topology_load_failed", error=str(e))

    async def _save_topology(self):
        """Persist topology to disk."""
        try:
            import aiofiles
            self._topology_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self._topology_path, "w") as f:
                content = json.dumps(
                    {
                        "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
                        "known_macs": list(self._known_macs),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                )
                await f.write(content)
        except Exception as e:
            logger.warning("network_topology_save_failed", error=str(e))

    async def scan_network(self) -> dict:
        """
        Full network scan:
        1. Read ARP table for device discovery
        2. Port scan each device
        3. Update trust scores
        4. Alert on new unknown devices
        """
        now = datetime.now(timezone.utc).isoformat()
        new_devices = []

        # Step 1: Read ARP table
        arp_entries = await self._read_arp_table()

        for ip, mac in arp_entries.items():
            existing = self._nodes.get(ip)

            if existing:
                existing.last_seen = now
                existing.mac = mac or existing.mac
            else:
                # New device!
                node = NetworkNode(
                    ip=ip,
                    mac=mac,
                    first_seen=now,
                    last_seen=now,
                    is_known=mac in self._known_macs,
                    trust_score=70 if mac in self._known_macs else 30,
                )
                self._nodes[ip] = node

                if mac and mac not in self._known_macs:
                    new_devices.append(node)
                    self._known_macs.add(mac)

        # Step 2: Quick port scan on new/unknown devices
        for node in list(self._nodes.values()):
            if not node.is_known or not node.open_ports:
                await self._quick_port_scan(node)

        # Step 3: Alert on new unknown devices
        for node in new_devices:
            logger.info("new_unknown_device", ip=node.ip, mac=node.mac)
            await self.event_bus.emit(
                Event(
                    type=EventType.NEW_UNKNOWN_DEVICE,
                    data=node.to_dict(),
                )
            )

        await self._save_topology()

        return {
            "total_devices": len(self._nodes),
            "new_devices": len(new_devices),
            "scanned_at": now,
        }

    async def _read_arp_table(self) -> dict[str, str]:
        """Read the system ARP table. Returns {ip: mac}."""
        entries = {}
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "neigh", "show",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            output = stdout.decode()

            for line in output.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 5:
                    ip = parts[0]
                    # Find MAC address (looks like xx:xx:xx:xx:xx:xx)
                    mac = ""
                    for p in parts:
                        if re.match(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", p):
                            mac = p.lower()
                            break
                    if ip and not ip.startswith("fe80"):  # Skip IPv6 link-local
                        entries[ip] = mac
        except Exception as e:
            logger.warning("arp_table_read_failed", error=str(e))

        return entries

    async def _quick_port_scan(self, node: NetworkNode):
        """Non-intrusive port check on a device."""
        open_ports = []
        services = {}

        async def check_port(port: int, name: str):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(node.ip, port),
                    timeout=1.5,
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
                services[port] = name
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass

        # Check all common ports concurrently
        tasks = [check_port(port, name) for port, name in self.COMMON_PORTS.items()]
        await asyncio.gather(*tasks)

        node.open_ports = sorted(open_ports)
        node.services = services

        # Infer device type
        if 8009 in open_ports:
            node.device_type = "chromecast/tv"
            node.trust_score = max(node.trust_score, 80)
        elif 7000 in open_ports:
            node.device_type = "apple/airplay"
        elif 22 in open_ports and 80 not in open_ports:
            node.device_type = "server/laptop"
        elif 80 in open_ports or 443 in open_ports:
            node.device_type = "web_device"

    def get_topology(self) -> list[NetworkNode]:
        """Return all known nodes."""
        return list(self._nodes.values())

    def get_trust_report(self) -> dict:
        """Generate a trust report."""
        trusted = [n for n in self._nodes.values() if n.trust_score >= 70]
        unknown = [n for n in self._nodes.values() if n.trust_score < 50]
        suspicious = [n for n in self._nodes.values() if n.trust_score < 30]

        return {
            "total_devices": len(self._nodes),
            "trusted": len(trusted),
            "unknown": len(unknown),
            "suspicious": len(suspicious),
            "devices": [n.to_dict() for n in self._nodes.values()],
        }

    def get_device_detail(self, ip: str) -> NetworkNode | None:
        """Get detailed info about a specific device."""
        return self._nodes.get(ip)

    async def take_snapshot(self):
        """Save a timestamped snapshot of the current topology."""
        import aiofiles
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self._snapshot_dir / f"snapshot_{timestamp}.json"

        async with aiofiles.open(path, "w") as f:
            content = json.dumps(
                {k: v.to_dict() for k, v in self._nodes.items()},
                indent=2,
            )
            await f.write(content)
        logger.info("network_snapshot_saved", path=str(path))

    async def start_periodic_scan(self, interval: int = 300):
        """Start periodic background scanning (every 5 minutes)."""
        self._scan_task = asyncio.create_task(self._scan_loop(interval))

    async def stop_periodic_scan(self):
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

    async def _scan_loop(self, interval: int):
        """Periodic scan loop."""
        # Initial scan
        await self.scan_network()
        while True:
            await asyncio.sleep(interval)
            await self.scan_network()
