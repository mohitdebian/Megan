"""
LAN Monitor Service

Passively monitors the local network for devices (specifically Google Cast)
using mDNS/Zeroconf. When a device is discovered or lost, it emits an event
to the EventBus.
"""

import asyncio
import structlog
from typing import Dict, Any

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


class LANMonitor:
    """Passively scans and tracks devices on the local network."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.aiozc: AsyncZeroconf | None = None
        self.browser: AsyncServiceBrowser | None = None
        
        # Track active devices: { device_name: { info } }
        self.active_devices: Dict[str, Dict[str, Any]] = {}

    async def start(self):
        """Start the async zeroconf browser."""
        logger.info("lan_monitor_starting")
        self.aiozc = AsyncZeroconf()
        
        # We are specifically looking for Chromecast / Google TV devices
        service_type = "_googlecast._tcp.local."
        
        self.browser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            service_type,
            handlers=[self._on_service_state_change]
        )
        logger.info("lan_monitor_started", service_type=service_type)

    async def stop(self):
        """Stop discovery and close zeroconf."""
        logger.info("lan_monitor_stopping")
        if self.aiozc:
            await self.aiozc.async_close()
            self.aiozc = None
        self.active_devices.clear()

    def _on_service_state_change(
        self, zeroconf, service_type, name, state_change
    ):
        """Callback from zeroconf when a service appears/disappears."""
        # This callback is synchronous, so we must schedule an async task to resolve
        if state_change is ServiceStateChange.Added:
            asyncio.create_task(self._resolve_and_emit(service_type, name))
        elif state_change is ServiceStateChange.Removed:
            asyncio.create_task(self._remove_and_emit(name))

    async def _resolve_and_emit(self, service_type: str, name: str):
        """Resolve the service info and emit DISCOVERED event."""
        if not self.aiozc:
            return
            
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(self.aiozc.zeroconf, 3000)
        
        if info:
            # Parse useful metadata
            properties = {}
            for k, v in info.properties.items():
                try:
                    properties[k.decode("utf-8")] = v.decode("utf-8")
                except:
                    pass
                    
            device_name = properties.get("fn", name.split(".")[0])
            model_name = properties.get("md", "Unknown Cast Device")
            ip_address = ".".join(map(str, info.addresses[0])) if info.addresses else "Unknown"
            
            device_data = {
                "id": name,
                "friendly_name": device_name,
                "model": model_name,
                "ip": ip_address,
                "port": info.port,
                "type": "chromecast"
            }
            
            self.active_devices[name] = device_data
            logger.info("lan_device_discovered", device=device_name, ip=ip_address, model=model_name)
            
            await self.event_bus.emit(
                Event(
                    type=EventType.NETWORK_DEVICE_DISCOVERED,
                    data=device_data
                )
            )

    async def _remove_and_emit(self, name: str):
        """Remove from tracking and emit LOST event."""
        if name in self.active_devices:
            device_data = self.active_devices.pop(name)
            logger.info("lan_device_lost", device=device_data["friendly_name"])
            
            # (Optional) You can define EventType.NETWORK_DEVICE_LOST in the future
            # if the UI needs to remove it from the screen.
