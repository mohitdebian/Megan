"""
Security Tool — AI interface to the network intelligence system.

Allows Megan to provide defensive LAN awareness, device inventory,
trust reports, and anomaly detection to the user.
"""

import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class SecurityTool(BaseTool):
    name = "network_security"
    description = (
        "Defensive cybersecurity tool for LAN awareness. "
        "Use when the user asks about network security, unknown devices, "
        "who's on the network, suspicious activity, or device trust. "
        "Actions: 'topology' (list all LAN devices with ports), "
        "'trust_report' (trust scores), 'scan' (trigger a fresh scan), "
        "'device_detail' (info on a specific IP)."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: topology, trust_report, scan, device_detail",
            "required": True,
        },
        "ip": {
            "type": "string",
            "description": "IP address for 'device_detail' action.",
        },
    }
    dangerous = False

    def __init__(self, network_intelligence) -> None:
        self.net_intel = network_intelligence

    async def execute(self, action: str, ip: str = "", **_) -> ToolResult:
        try:
            if action == "topology":
                nodes = self.net_intel.get_topology()
                if not nodes:
                    return ToolResult(success=True, output="No devices mapped yet. Run 'scan' first.")

                out = f"🗺️ Network Topology ({len(nodes)} devices):\n"
                for n in sorted(nodes, key=lambda x: x.trust_score, reverse=True):
                    trust_icon = "🟢" if n.trust_score >= 70 else "🟡" if n.trust_score >= 50 else "🔴"
                    ports = ", ".join(f"{p}/{n.services.get(p, '?')}" for p in n.open_ports) if n.open_ports else "none scanned"
                    out += (
                        f"\n{trust_icon} {n.ip} ({n.device_type})\n"
                        f"  MAC: {n.mac or 'unknown'} | Trust: {n.trust_score}/100\n"
                        f"  Ports: {ports}\n"
                        f"  First seen: {n.first_seen[:10] if n.first_seen else '?'}\n"
                    )
                return ToolResult(success=True, output=out)

            elif action == "trust_report":
                report = self.net_intel.get_trust_report()
                out = (
                    f"🛡️ Network Trust Report:\n"
                    f"  Total devices: {report['total_devices']}\n"
                    f"  🟢 Trusted: {report['trusted']}\n"
                    f"  🟡 Unknown: {report['unknown']}\n"
                    f"  🔴 Suspicious: {report['suspicious']}\n"
                )

                suspicious = [d for d in report['devices'] if d['trust_score'] < 30]
                if suspicious:
                    out += "\n⚠️ Suspicious Devices:\n"
                    for d in suspicious:
                        out += f"  • {d['ip']} (MAC: {d['mac']}, type: {d['device_type']})\n"

                return ToolResult(success=True, output=out)

            elif action == "scan":
                result = await self.net_intel.scan_network()
                out = (
                    f"🔍 Network scan complete.\n"
                    f"  Devices found: {result['total_devices']}\n"
                    f"  New devices: {result['new_devices']}\n"
                )
                if result['new_devices'] > 0:
                    out += "  ⚠️ New devices detected! Check the trust report for details."
                return ToolResult(success=True, output=out)

            elif action == "device_detail":
                if not ip:
                    return ToolResult(success=False, output="Provide an 'ip' address for device_detail.")

                node = self.net_intel.get_device_detail(ip)
                if not node:
                    return ToolResult(success=True, output=f"No data found for IP {ip}.")

                ports = "\n".join(f"    {p}: {node.services.get(p, 'unknown')}" for p in node.open_ports) if node.open_ports else "    none"
                out = (
                    f"🔎 Device Detail: {node.ip}\n"
                    f"  MAC: {node.mac or 'unknown'}\n"
                    f"  Type: {node.device_type}\n"
                    f"  Trust Score: {node.trust_score}/100\n"
                    f"  Known: {'Yes' if node.is_known else 'No'}\n"
                    f"  First seen: {node.first_seen}\n"
                    f"  Last seen: {node.last_seen}\n"
                    f"  Open ports:\n{ports}\n"
                )
                return ToolResult(success=True, output=out)

            else:
                return ToolResult(
                    success=False,
                    output=f"Unknown action: '{action}'. Use: topology, trust_report, scan, device_detail.",
                )

        except Exception as e:
            logger.error("security_tool_error", error=str(e))
            return ToolResult(success=False, output="", error=f"Security scan failed: {str(e)}")
