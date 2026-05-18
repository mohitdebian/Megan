"""
Network Intelligence Tool

Allows Megan to query active devices on the local network.
"""

import structlog
from typing import Any
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class NetworkIntelligenceTool(BaseTool):
    name = "network_scan"
    description = (
        "Scan the local network and list active smart devices (like TVs, Chromecasts, etc). "
        "Use this tool when the user asks what devices are on the network or to find a TV name. "
        "Do NOT use the terminal tool with avahi-browse. Use this tool instead."
    )
    parameters = {}
    dangerous = False

    def __init__(self, lan_monitor) -> None:
        self.lan_monitor = lan_monitor

    async def execute(self, **_) -> ToolResult:
        try:
            if not self.lan_monitor:
                return ToolResult(success=False, output="Network monitoring is offline.")
                
            devices = self.lan_monitor.active_devices
            if not devices:
                return ToolResult(success=True, output="No active smart devices found on the local network.")
                
            out = "Active Network Devices:\n"
            for d in devices.values():
                out += f"- {d['friendly_name']} (Model: {d['model']}, IP: {d['ip']}, Type: {d['type']})\n"
                
            return ToolResult(success=True, output=out)
        except Exception as e:
            logger.error("network_tool_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to scan network: {str(e)}",
            )
