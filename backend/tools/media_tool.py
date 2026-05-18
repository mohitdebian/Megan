"""
Media Tool — AI interface to the local media library.

Allows Megan to search, recommend, browse, and manage local media files.
"""

import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds <= 0:
        return "unknown"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _format_size(bytes: int) -> str:
    """Format bytes into human-readable size."""
    if bytes <= 0:
        return "unknown"
    gb = bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = bytes / (1024**2)
    return f"{mb:.0f} MB"


class MediaTool(BaseTool):
    name = "media_library"
    description = (
        "Search, browse, and manage local media files (videos, music) on this machine. "
        "Use this to find a movie or video file before casting it to the TV. "
        "Actions: 'search' (find by name), 'recent' (recently played), "
        "'recommendations' (AI suggestions), 'resumable' (continue watching), "
        "'favorites' (starred files), 'stats' (library overview), "
        "'scan' (re-scan directories for new files)."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: search, recent, recommendations, resumable, favorites, stats, scan",
            "required": True,
        },
        "query": {
            "type": "string",
            "description": "Search query (required for 'search' action).",
        },
        "media_type": {
            "type": "string",
            "description": "Filter by type: 'video' or 'audio'. Optional.",
        },
    }
    dangerous = False

    def __init__(self, media_library) -> None:
        self.library = media_library

    async def execute(self, action: str, query: str = "", media_type: str = "", **_) -> ToolResult:
        try:
            if action == "search":
                if not query:
                    return ToolResult(success=False, output="Provide a 'query' to search for.")

                results = self.library.search(query, media_type)
                if not results:
                    return ToolResult(success=True, output=f"No media files found matching '{query}'.")

                out = f"🔍 Found {len(results)} result(s) for '{query}':\n"
                for m in results:
                    dur = _format_duration(m.duration_seconds)
                    size = _format_size(m.size_bytes)
                    res = f" [{m.resolution}]" if m.resolution else ""
                    out += f"\n• {m.filename}{res}\n  Path: {m.path}\n  Duration: {dur} | Size: {size} | Type: {m.media_type}\n"
                return ToolResult(success=True, output=out)

            elif action == "recent":
                results = self.library.get_recent(10)
                if not results:
                    return ToolResult(success=True, output="No recently played media.")

                out = "📋 Recently Played:\n"
                for m in results:
                    out += f"  • {m.filename} — last played {m.last_played[:10]}\n"
                return ToolResult(success=True, output=out)

            elif action == "recommendations":
                results = self.library.get_recommendations()
                if not results:
                    return ToolResult(success=True, output="No recommendations yet. Try scanning your library first.")

                out = "💡 Recommended for you:\n"
                for m in results:
                    dur = _format_duration(m.duration_seconds)
                    label = "🆕 New" if m.play_count == 0 else f"🔥 Played {m.play_count}x"
                    out += f"  • {m.filename} ({dur}) — {label}\n    {m.path}\n"
                return ToolResult(success=True, output=out)

            elif action == "resumable":
                results = self.library.get_resumable()
                if not results:
                    return ToolResult(success=True, output="Nothing to resume.")

                out = "⏯️ Continue Watching:\n"
                for m in results:
                    pos = _format_duration(m.resume_position)
                    dur = _format_duration(m.duration_seconds)
                    out += f"  • {m.filename} — stopped at {pos}/{dur}\n    {m.path}\n"
                return ToolResult(success=True, output=out)

            elif action == "favorites":
                results = self.library.get_favorites()
                if not results:
                    return ToolResult(success=True, output="No favorites yet.")

                out = "⭐ Favorites:\n"
                for m in results:
                    out += f"  • {m.filename}\n    {m.path}\n"
                return ToolResult(success=True, output=out)

            elif action == "stats":
                stats = self.library.get_stats()
                out = (
                    f"📊 Media Library Stats:\n"
                    f"  Total files: {stats['total_files']}\n"
                    f"  Videos: {stats['videos']} | Audio: {stats['audio']}\n"
                    f"  Total size: {stats['total_size_gb']} GB\n"
                    f"  Total duration: {stats['total_duration_hours']} hours\n"
                    f"  Favorites: {stats['favorites']} | Resumable: {stats['resumable']}"
                )
                return ToolResult(success=True, output=out)

            elif action == "scan":
                count = await self.library.scan()
                return ToolResult(
                    success=True,
                    output=f"📂 Media scan complete. Found {count} new file(s). Total library: {len(self.library._files)} files.",
                )

            else:
                return ToolResult(
                    success=False,
                    output=f"Unknown action: '{action}'. Use: search, recent, recommendations, resumable, favorites, stats, scan.",
                )

        except Exception as e:
            logger.error("media_tool_error", error=str(e))
            return ToolResult(success=False, output="", error=f"Media library error: {str(e)}")
