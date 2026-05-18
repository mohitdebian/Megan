"""
Network Intelligence Tool

Allows Megan to query active devices on the local network using the DeviceManager.
"""

import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class NetworkIntelligenceTool(BaseTool):
    name = "network_scan"
    description = (
        "List all smart devices discovered on the local network. "
        "Shows device names, models, IPs, types, and online/offline status. "
        "Use this when the user asks what devices are on the network, "
        "to find a TV name, or to check device health."
    )
    parameters = {
        "filter": {
            "type": "string",
            "description": "Optional filter: 'online', 'offline', 'chromecast', or leave empty for all devices.",
        }
    }
    dangerous = False

    def __init__(self, device_manager) -> None:
        self.device_manager = device_manager

    async def execute(self, filter: str = "", **_) -> ToolResult:
        try:
            if not self.device_manager:
                return ToolResult(success=False, output="Device manager is offline.")

            online_only = filter.lower() == "online" if filter else False
            device_type = None
            if filter and filter.lower() not in ("online", "offline"):
                device_type = filter.lower()

            devices = self.device_manager.list_devices(
                device_type=device_type,
                online_only=online_only,
            )

            if filter and filter.lower() == "offline":
                devices = [d for d in devices if not d.is_online]

            if not devices:
                return ToolResult(
                    success=True,
                    output="No devices found matching that filter.",
                )

            out = f"📡 Network Devices ({len(devices)} found):\n"
            for d in devices:
                status = "🟢 Online" if d.is_online else "🔴 Offline"
                out += (
                    f"\n• {d.friendly_name}\n"
                    f"  Model: {d.model} | Type: {d.device_type}\n"
                    f"  IP: {d.ip}:{d.port} | Status: {status}\n"
                    f"  Trust: {d.trust_level} | Last seen: {d.last_seen[:19] if d.last_seen else 'Never'}\n"
                )

            return ToolResult(success=True, output=out)
        except Exception as e:
            logger.error("network_tool_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to scan network: {str(e)}",
            )
