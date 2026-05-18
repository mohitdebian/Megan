"""
App Launcher Tool — open applications and files.
"""

import asyncio
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class AppLauncherTool(BaseTool):
    name = "app_launcher"
    description = (
        "Launch applications or open files/URLs with the system default handler. "
        "Can open apps by name (e.g., 'firefox', 'code'), open files in their "
        "default application, or open URLs in the browser."
    )
    parameters = {
        "target": {
            "type": "string",
            "description": "Application name, file path, or URL to open",
            "required": True,
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Additional arguments to pass to the application",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        pass

    async def execute(
        self, target: str, args: list[str] | None = None, **_
    ) -> ToolResult:
        args = args or []
        try:
            # Use xdg-open for files/URLs, direct binary for apps
            if target.startswith(("http://", "https://", "/")):
                cmd = ["xdg-open", target]
            else:
                cmd = [target] + args

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Don't wait for GUI apps to finish
            await asyncio.sleep(1)

            return ToolResult(
                success=True,
                output=f"Launched: {' '.join(cmd)}",
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="",
                error=f"Application not found: {target}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
