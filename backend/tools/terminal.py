"""
Terminal Tool — execute shell commands.
Marked as dangerous: requires user confirmation.
"""

import asyncio
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class TerminalTool(BaseTool):
    name = "terminal"
    description = (
        "Execute a shell command on the user's system and return stdout/stderr. "
        "Use this for system operations, running scripts, installing packages, "
        "checking processes, git operations, etc. "
        "Commands run in the user's default shell with their permissions."
    )
    parameters = {
        "command": {
            "type": "string",
            "description": "The shell command to execute",
            "required": True,
        },
        "working_directory": {
            "type": "string",
            "description": "Working directory for the command (default: home directory)",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (default: 30)",
        },
    }
    dangerous = True

    def __init__(self, settings) -> None:
        self._timeout = settings.safety.command_timeout

    async def execute(
        self,
        command: str,
        working_directory: str | None = None,
        timeout: int | None = None,
        **_,
    ) -> ToolResult:
        timeout = timeout or self._timeout

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            output_parts = []
            if stdout_str:
                output_parts.append(stdout_str)
            if stderr_str:
                output_parts.append(f"[stderr] {stderr_str}")

            output = "\n".join(output_parts) or "(no output)"

            # Truncate very long output
            if len(output) > 10000:
                output = output[:10000] + "\n... (output truncated)"

            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
                metadata={"exit_code": process.returncode},
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
