"""
YouTube Tool — Search YouTube videos for casting.
"""

import httpx
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class YouTubeTool(BaseTool):
    name = "youtube_search"
    description = (
        "Search YouTube for videos. Use this when the user asks to play something on YouTube "
        "(e.g., 'play bollywood music', 'put on a cooking video'). "
        "This tool returns YouTube video IDs which you can then pass to the 'chromecast' tool "
        "(using action='play_youtube' and video_id=...) to cast them to a TV."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "The search query (e.g., 'bollywood music 2023', 'lofi hip hop radio').",
        },
        "count": {
            "type": "integer",
            "description": "Number of results to return (default 3).",
        },
    }
    dangerous = False

    async def execute(self, query: str, count: int = 3, **_) -> ToolResult:
        if not query:
            return ToolResult(success=False, output="You must provide a search query.")

        invidious_instances = [
            "https://y.com.sb",
            "https://invidious.nerdvpn.de",
            "https://invidious.jing.rocks",
        ]

        for instance in invidious_instances:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        f"{instance}/api/v1/search",
                        params={"q": query, "type": "video"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()

                if not isinstance(data, list) or len(data) == 0:
                    continue

                out = f"🔍 YouTube Search Results for '{query}':\n\n"
                for i, item in enumerate(data[:count]):
                    if item.get("type") != "video":
                        continue
                    video_id = item.get("videoId")
                    title = item.get("title", "")
                    channel = item.get("author", "")
                    dur = item.get("lengthSeconds", 0)
                    dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else "Live/Unknown"
                    views = item.get("viewCount", 0)

                    out += (
                        f"{i+1}. {title}\n"
                        f"   Channel: {channel} | Duration: {dur_str} | Views: {views:,}\n"
                        f"   Video ID to cast: {video_id}\n\n"
                    )

                return ToolResult(success=True, output=out.strip())

            except Exception as e:
                logger.warning("youtube_tool_invidious_failed", instance=instance, error=str(e))
                continue

        return ToolResult(
            success=False,
            output="Failed to search YouTube. All API instances are currently down."
        )
