"""
Writer Agent — Specialized agent for drafting documents.

Takes research notes and user intent, and drafts a polished
markdown document saved to the filesystem.
"""

import asyncio
import httpx
import structlog
from pathlib import Path
from datetime import datetime

from config import get_settings

logger = structlog.get_logger(__name__)


class WriterAgent:
    """
    A focused sub-agent that takes raw research data and drafts
    a polished markdown report, saving it to disk.
    """

    def __init__(self):
        self.settings = get_settings()

    async def write(self, topic: str, research_notes: str, output_dir: str = None) -> dict:
        """
        Draft a report based on research notes.
        
        Args:
            topic: The report subject
            research_notes: Raw research data from the ResearcherAgent
            output_dir: Directory to save the report (default ~/Documents/)
            
        Returns:
            dict with keys: success, file_path, summary
        """
        logger.info("writer_starting", topic=topic)

        if not output_dir:
            output_dir = str(Path.home() / "Documents")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate a clean filename
        safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)
        safe_topic = safe_topic.strip().replace(" ", "_")[:50]
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{safe_topic}_report_{date_str}.md"
        file_path = output_path / filename

        # Draft the report
        prompt = (
            f"You are an expert technical writer. Write a comprehensive, well-structured "
            f"markdown report on the following topic:\n\n"
            f"**Topic:** {topic}\n\n"
            f"**Research Notes:**\n{research_notes}\n\n"
            f"Write a polished report with:\n"
            f"- A clear title (# heading)\n"
            f"- Executive Summary\n"
            f"- Key Findings (with subheadings)\n"
            f"- Analysis & Implications\n"
            f"- Conclusion\n"
            f"- Sources (if available from the research)\n\n"
            f"Target ~1000 words. Use professional tone. Include markdown formatting "
            f"(headers, bullet points, bold text, code blocks if relevant)."
        )

        report = await self._llm_call(prompt, max_tokens=4096)

        if not report or len(report) < 100:
            return {
                "success": False,
                "file_path": "",
                "summary": "Writer agent failed to generate a meaningful report."
            }

        # Save to disk
        file_path.write_text(report)
        logger.info("writer_complete", file=str(file_path), words=len(report.split()))

        # Generate a short summary for the TTS announcement
        summary_prompt = (
            f"Summarize this report in ONE sentence (under 30 words) for a voice announcement:\n\n"
            f"{report[:500]}"
        )
        summary = await self._llm_call(summary_prompt, max_tokens=100)

        return {
            "success": True,
            "file_path": str(file_path),
            "summary": summary.strip() if summary else f"Report on {topic} saved."
        }

    async def _llm_call(self, prompt: str, max_tokens: int = 1024) -> str:
        """Make a direct LLM call."""
        headers = {
            "Authorization": f"Bearer {self.settings.claude.auth_token}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.settings.claude.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        url = f"{self.settings.claude.base_url.rstrip('/')}/v1/messages"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return ""

                data = resp.json()
                text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        text += block.get("text", "")
                return text.strip()
        except Exception as e:
            logger.error("writer_llm_error", error=str(e))
            return ""
