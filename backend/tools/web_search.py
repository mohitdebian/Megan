"""
Web Search Tool — search the web for information.
Uses httpx to call search APIs (DuckDuckGo HTML fallback if no API key).
"""

import httpx
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


class WebSearchTool(BaseTool):
    name = "internet_search"
    description = (
        "Search the web for current information. Use this when you need "
        "up-to-date information, facts, documentation, news, or anything "
        "that might not be in your training data. Returns search results "
        "with titles, URLs, and snippets."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "The search query",
            "required": True,
        },
        "num_results": {
            "type": "integer",
            "description": "Number of results to return (default: 5, max: 10)",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        self._settings = settings

    async def execute(
        self, query: str, num_results: int = 5, **_
    ) -> ToolResult:
        num_results = min(num_results, 10)
        try:
            return await self._duckduckgo_search(query, num_results)
        except Exception as e:
            logger.error("web_search_error", error=str(e))
            return ToolResult(
                success=False, output="", error=f"Search failed: {str(e)}"
            )

    async def _duckduckgo_search(
        self, query: str, num_results: int
    ) -> ToolResult:
        """Fallback: scrape DuckDuckGo HTML results."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                DUCKDUCKGO_URL,
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Megan/1.0"
                },
            )
            resp.raise_for_status()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for i, result in enumerate(soup.select(".result")):
            if i >= num_results:
                break
            title_el = result.select_one(".result__title")
            snippet_el = result.select_one(".result__snippet")
            link_el = result.select_one(".result__url")

            title = title_el.get_text(strip=True) if title_el else "No title"
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = link_el.get_text(strip=True) if link_el else ""

            results.append(f"[{i+1}] {title}\n    URL: {url}\n    {snippet}")

        if not results:
            return ToolResult(
                success=True, output="No results found for this query."
            )

        return ToolResult(
            success=True,
            output=f"Search results for '{query}':\n\n"
            + "\n\n".join(results),
        )
