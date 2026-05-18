"""
Code Executor Tool — run Python/JS code in sandboxed subprocess.
Dangerous: requires confirmation.
"""

import asyncio
import tempfile
import os
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class CodeExecutorTool(BaseTool):
    name = "code_executor"
    description = (
        "Execute code snippets in a subprocess. Supports Python and JavaScript. "
        "Use this for calculations, data processing, testing code snippets, "
        "or running quick scripts. Code runs in a temporary file and the "
        "output (stdout + stderr) is returned."
    )
    parameters = {
        "code": {
            "type": "string",
            "description": "The code to execute",
            "required": True,
        },
        "language": {
            "type": "string",
            "enum": ["python", "javascript", "bash"],
            "description": "Programming language (default: python)",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (default: 30)",
        },
    }
    dangerous = True

    def __init__(self, settings) -> None:
        self._timeout = settings.safety.code_timeout

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
        **_,
    ) -> ToolResult:
        timeout = timeout or self._timeout

        lang_map = {
            "python": ("python3", ".py"),
            "javascript": ("node", ".js"),
            "bash": ("bash", ".sh"),
        }

        if language not in lang_map:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}",
            )

        interpreter, ext = lang_map[language]

        # Write to temp file, execute, clean up
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=ext, delete=False
            ) as f:
                f.write(code)
                tmp_path = f.name

            process = await asyncio.create_subprocess_exec(
                interpreter,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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

            if len(output) > 10000:
                output = output[:10000] + "\n... (output truncated)"

            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Code execution timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
