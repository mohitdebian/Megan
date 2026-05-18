"""
Codebase Tool — repository indexing, semantic code search, architecture analysis.
"""

import os
from pathlib import Path
from tools.base import BaseTool, ToolResult

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build", ".next", "target"}
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".css", ".html", ".json", ".yaml", ".yml", ".toml", ".md", ".sh"}


class CodebaseTool(BaseTool):
    name = "codebase"
    description = (
        "Analyze a code repository. Can map project structure, read files, "
        "search code content, find dependencies, and summarize architecture. "
        "Use this to understand unfamiliar codebases."
    )
    parameters = {
        "action": {
            "type": "string",
            "enum": ["structure", "search", "dependencies", "summary"],
            "description": "Analysis action to perform",
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "Root path of the repository",
            "required": True,
        },
        "query": {
            "type": "string",
            "description": "Search query (for 'search' action — searches file contents)",
        },
        "max_depth": {
            "type": "integer",
            "description": "Max directory depth (default: 4)",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        pass

    async def execute(self, action: str, path: str, query: str = "", max_depth: int = 4, **_) -> ToolResult:
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")

        if action == "structure":
            return self._structure(path, max_depth)
        elif action == "search":
            return self._search(path, query)
        elif action == "dependencies":
            return self._dependencies(path)
        elif action == "summary":
            return self._summary(path, max_depth)
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _structure(self, root: str, max_depth: int) -> ToolResult:
        lines = []
        base = Path(root)
        for item in sorted(base.rglob("*")):
            if any(s in item.parts for s in SKIP_DIRS):
                continue
            depth = len(item.relative_to(base).parts)
            if depth > max_depth:
                continue
            prefix = "📁 " if item.is_dir() else "📄 "
            indent = "  " * (depth - 1)
            lines.append(f"{indent}{prefix}{item.name}")
            if len(lines) > 300:
                lines.append("... (truncated)")
                break
        return ToolResult(success=True, output="\n".join(lines) or "(empty)")

    def _search(self, root: str, query: str) -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="Query required for search")
        results = []
        base = Path(root)
        for item in base.rglob("*"):
            if any(s in item.parts for s in SKIP_DIRS):
                continue
            if not item.is_file() or item.suffix not in CODE_EXTS:
                continue
            try:
                content = item.read_text(errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if query.lower() in line.lower():
                        results.append(f"{item.relative_to(base)}:{i}: {line.strip()}")
                        if len(results) >= 50:
                            return ToolResult(success=True, output="\n".join(results) + "\n... (50 max)")
            except Exception:
                continue
        return ToolResult(success=True, output="\n".join(results) or "No matches found")

    def _dependencies(self, root: str) -> ToolResult:
        base = Path(root)
        deps = {}
        # Python
        for f in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]:
            p = base / f
            if p.exists():
                deps[f] = p.read_text(errors="ignore")[:3000]
        # Node
        pkg = base / "package.json"
        if pkg.exists():
            deps["package.json"] = pkg.read_text(errors="ignore")[:3000]
        # Go
        gomod = base / "go.mod"
        if gomod.exists():
            deps["go.mod"] = gomod.read_text(errors="ignore")[:3000]
        # Rust
        cargo = base / "Cargo.toml"
        if cargo.exists():
            deps["Cargo.toml"] = cargo.read_text(errors="ignore")[:3000]

        if not deps:
            return ToolResult(success=True, output="No dependency files found")
        lines = []
        for name, content in deps.items():
            lines.append(f"=== {name} ===\n{content}\n")
        return ToolResult(success=True, output="\n".join(lines))

    def _summary(self, root: str, max_depth: int) -> ToolResult:
        base = Path(root)
        file_counts: dict[str, int] = {}
        total_lines = 0
        total_files = 0
        for item in base.rglob("*"):
            if any(s in item.parts for s in SKIP_DIRS):
                continue
            if item.is_file() and item.suffix in CODE_EXTS:
                ext = item.suffix
                file_counts[ext] = file_counts.get(ext, 0) + 1
                total_files += 1
                try:
                    total_lines += len(item.read_text(errors="ignore").splitlines())
                except Exception:
                    pass

        lines = [f"Repository: {root}", f"Total code files: {total_files}", f"Total lines: {total_lines}", "", "File types:"]
        for ext, count in sorted(file_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {ext}: {count} files")
        return ToolResult(success=True, output="\n".join(lines))
