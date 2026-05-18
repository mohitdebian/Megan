"""
System Info Tool — get system information.
"""

import platform
import psutil
from tools.base import BaseTool, ToolResult


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = (
        "Get system information: CPU, memory, disk, GPU, network, processes, OS details."
    )
    parameters = {
        "category": {
            "type": "string",
            "enum": ["all", "cpu", "memory", "disk", "network", "processes", "os"],
            "description": "Category of info to retrieve (default: all)",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        pass

    async def execute(self, category: str = "all", **_) -> ToolResult:
        try:
            info = {}
            if category in ("all", "os"):
                info["os"] = f"{platform.system()} {platform.release()} ({platform.machine()})"
            if category in ("all", "cpu"):
                info["cpu"] = f"{psutil.cpu_count()} cores, {psutil.cpu_percent(interval=0.5)}% used"
            if category in ("all", "memory"):
                m = psutil.virtual_memory()
                info["memory"] = f"{round(m.total/(1024**3),1)}GB total, {m.percent}% used"
            if category in ("all", "disk"):
                d = psutil.disk_usage("/")
                info["disk"] = f"{round(d.total/(1024**3),1)}GB total, {d.percent}% used"
            if category in ("all", "processes"):
                procs = []
                for p in sorted(
                    psutil.process_iter(["pid", "name", "cpu_percent"]),
                    key=lambda p: p.info.get("cpu_percent", 0) or 0,
                    reverse=True,
                )[:10]:
                    procs.append(f"  PID {p.info['pid']}: {p.info['name']} ({p.info['cpu_percent']}%)")
                info["top_processes"] = "\n".join(procs)

            lines = [f"{k}: {v}" for k, v in info.items()]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
