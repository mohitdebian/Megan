"""
Clipboard Tool — read/write system clipboard.
"""

import asyncio
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class ClipboardTool(BaseTool):
    name = "clipboard"
    description = (
        "Read from or write to the system clipboard. "
        "Use 'read' to get current clipboard contents, "
        "or 'write' to copy text to the clipboard."
    )
    parameters = {
        "action": {
            "type": "string",
            "enum": ["read", "write"],
            "description": "Whether to read or write the clipboard",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "Content to write to clipboard (only for 'write' action)",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        pass

    async def execute(
        self, action: str, content: str | None = None, **_
    ) -> ToolResult:
        try:
            if action == "read":
                proc = await asyncio.create_subprocess_exec(
                    "xclip", "-selection", "clipboard", "-o",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                text = stdout.decode("utf-8", errors="replace")
                return ToolResult(
                    success=True,
                    output=text or "(clipboard is empty)",
                )
            elif action == "write":
                proc = await asyncio.create_subprocess_exec(
                    "xclip", "-selection", "clipboard",
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate(input=(content or "").encode("utf-8"))
                return ToolResult(
                    success=True,
                    output=f"Copied {len(content or '')} chars to clipboard",
                )
            else:
                return ToolResult(
                    success=False, output="", error=f"Unknown action: {action}"
                )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="",
                error="xclip not installed. Install with: sudo apt install xclip",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
