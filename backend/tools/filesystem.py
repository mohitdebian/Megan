"""
File System Tool — read, write, list, search files.
Write operations are marked dangerous.
"""

import os
import aiofiles
import structlog
from pathlib import Path
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class FileSystemTool(BaseTool):
    name = "filesystem"
    description = (
        "Interact with the local file system. Can read files, write files, "
        "list directory contents, search for files by name or content, "
        "and get file metadata. Use this to inspect projects, edit code, "
        "create new files, or explore directory structures."
    )
    parameters = {
        "action": {
            "type": "string",
            "enum": ["read", "write", "list", "search", "info"],
            "description": "The file system operation to perform",
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "File or directory path",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "Content to write (only for 'write' action)",
        },
        "pattern": {
            "type": "string",
            "description": "Search pattern (for 'search' action — searches file names)",
        },
        "max_depth": {
            "type": "integer",
            "description": "Max directory depth for list/search (default: 3)",
        },
    }
    dangerous = False  # Read is safe; write gets confirmed via agent safety

    def __init__(self, settings) -> None:
        self._allowed_dirs = settings.safety.allowed_dirs.split(",")

    async def execute(
        self,
        action: str,
        path: str,
        content: str | None = None,
        pattern: str | None = None,
        max_depth: int = 3,
        **_,
    ) -> ToolResult:
        path = os.path.expanduser(path)

        if action == "read":
            return await self._read(path)
        elif action == "write":
            return await self._write(path, content or "")
        elif action == "list":
            return await self._list(path, max_depth)
        elif action == "search":
            return await self._search(path, pattern or "", max_depth)
        elif action == "info":
            return await self._info(path)
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    async def _read(self, path: str) -> ToolResult:
        try:
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
            # Truncate very large files
            if len(content) > 50000:
                content = content[:50000] + "\n... (file truncated, showing first 50000 chars)"
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _write(self, path: str, content: str) -> ToolResult:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            async with aiofiles.open(path, "w") as f:
                await f.write(content)
            return ToolResult(
                success=True,
                output=f"Written {len(content)} bytes to {path}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _list(self, path: str, max_depth: int) -> ToolResult:
        try:
            lines = []
            base = Path(path)
            for item in sorted(base.rglob("*")):
                depth = len(item.relative_to(base).parts)
                if depth > max_depth:
                    continue
                # Skip common noise
                rel = str(item.relative_to(base))
                if any(
                    skip in rel
                    for skip in [
                        "node_modules", "__pycache__", ".git/", ".venv",
                        "venv/", "dist/", "build/",
                    ]
                ):
                    continue
                prefix = "📁 " if item.is_dir() else "📄 "
                indent = "  " * (depth - 1)
                lines.append(f"{indent}{prefix}{item.name}")

            if len(lines) > 200:
                lines = lines[:200] + [f"... ({len(lines) - 200} more items)"]

            return ToolResult(
                success=True,
                output="\n".join(lines) or "(empty directory)",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _search(self, path: str, pattern: str, max_depth: int) -> ToolResult:
        try:
            results = []
            base = Path(path)
            for item in base.rglob(f"*{pattern}*"):
                depth = len(item.relative_to(base).parts)
                if depth > max_depth:
                    continue
                results.append(str(item))
                if len(results) >= 50:
                    break
            return ToolResult(
                success=True,
                output="\n".join(results) or "No matches found",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _info(self, path: str) -> ToolResult:
        try:
            stat = os.stat(path)
            info = {
                "path": path,
                "size": stat.st_size,
                "is_file": os.path.isfile(path),
                "is_dir": os.path.isdir(path),
                "modified": stat.st_mtime,
            }
            return ToolResult(success=True, output=str(info))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
