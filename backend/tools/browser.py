"""
Browser Tool — fetch and read web page content.
Extracts readable text from URLs.
"""

import httpx
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class BrowserTool(BaseTool):
    name = "web_browser"
    description = (
        "Fetch and read the content of a web page. Extracts readable text "
        "from the HTML. Use this to read documentation, articles, API docs, "
        "GitHub READMEs, or any web page content."
    )
    parameters = {
        "url": {
            "type": "string",
            "description": "The URL to fetch",
            "required": True,
        },
        "extract_links": {
            "type": "boolean",
            "description": "Whether to include links in the output (default: false)",
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        pass

    async def execute(
        self, url: str, extract_links: bool = False, **_
    ) -> ToolResult:
        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True
            ) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Megan/1.0"
                    },
                )
                resp.raise_for_status()

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script and style elements
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            # Truncate
            if len(text) > 15000:
                text = text[:15000] + "\n... (content truncated)"

            output = f"Content from {url}:\n\n{text}"

            if extract_links:
                links = []
                for a in soup.find_all("a", href=True)[:30]:
                    href = a["href"]
                    link_text = a.get_text(strip=True)
                    if href.startswith("http") and link_text:
                        links.append(f"  - [{link_text}]({href})")
                if links:
                    output += "\n\nLinks:\n" + "\n".join(links)

            return ToolResult(success=True, output=output)

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to fetch URL: {str(e)}"
            )
