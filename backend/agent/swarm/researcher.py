"""
Researcher Agent — Specialized agent for web research.

Given a research topic, this agent autonomously browses the web,
collects relevant data, and returns structured research notes.
"""

import asyncio
import httpx
import json
import structlog
from config import get_settings

logger = structlog.get_logger(__name__)


class ResearcherAgent:
    """
    A focused sub-agent equipped only with web search capabilities.
    Returns raw research findings as structured text.
    """

    def __init__(self):
        self.settings = get_settings()

    async def research(self, topic: str, depth: int = 3) -> str:
        """
        Research a topic by making multiple web searches and synthesizing results.
        
        Args:
            topic: The research subject
            depth: Number of search queries to make (default 3)
            
        Returns:
            Structured research notes as a string
        """
        logger.info("researcher_starting", topic=topic, depth=depth)

        # Step 1: Generate search queries
        queries = await self._generate_queries(topic, depth)
        if not queries:
            queries = [topic]

        # Step 2: Execute searches
        all_results = []
        for query in queries:
            results = await self._web_search(query)
            if results:
                all_results.append({"query": query, "results": results})

        if not all_results:
            return f"No research results found for: {topic}"

        # Step 3: Synthesize into research notes
        synthesis = await self._synthesize(topic, all_results)
        logger.info("researcher_complete", topic=topic, result_len=len(synthesis))
        return synthesis

    async def _generate_queries(self, topic: str, count: int) -> list[str]:
        """Use the LLM to break a topic into focused search queries."""
        prompt = (
            f"Break the following research topic into {count} specific web search queries "
            f"that would find the most relevant and recent information:\n\n"
            f"Topic: {topic}\n\n"
            f"Return ONLY a JSON array of strings. Example: [\"query 1\", \"query 2\"]"
        )

        response = await self._llm_call(prompt, max_tokens=200)
        try:
            # Try to parse JSON from the response
            # Strip any markdown fences
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
            
            queries = json.loads(cleaned)
            if isinstance(queries, list):
                return [str(q) for q in queries[:count]]
        except (json.JSONDecodeError, ValueError):
            pass
        return [topic]

    async def _web_search(self, query: str) -> str:
        """Perform a web search using DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS
            results = await asyncio.to_thread(
                lambda: list(DDGS().text(query, max_results=5))
            )
            if results:
                formatted = []
                for r in results:
                    formatted.append(f"- **{r.get('title', '')}**: {r.get('body', '')}")
                return "\n".join(formatted)
        except Exception as e:
            logger.error("researcher_search_error", query=query, error=str(e))
        return ""

    async def _synthesize(self, topic: str, results: list[dict]) -> str:
        """Use the LLM to synthesize raw search results into research notes."""
        results_text = ""
        for r in results:
            results_text += f"\n### Search: {r['query']}\n{r['results']}\n"

        prompt = (
            f"You are a research analyst. Synthesize the following web search results "
            f"into well-organized research notes about: {topic}\n\n"
            f"Raw Results:\n{results_text}\n\n"
            f"Format as structured markdown with:\n"
            f"- Key Findings (bullet points)\n"
            f"- Notable Sources\n"
            f"- Summary\n\n"
            f"Be factual and concise. ~500 words."
        )

        return await self._llm_call(prompt, max_tokens=2048)

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return f"LLM error: {resp.status_code}"

                data = resp.json()
                text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        text += block.get("text", "")
                return text.strip()
        except Exception as e:
            logger.error("researcher_llm_error", error=str(e))
            return f"Error: {str(e)}"
