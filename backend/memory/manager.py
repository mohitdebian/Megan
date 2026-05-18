"""
Memory Manager — unified interface to all memory systems.
Combines short-term, long-term, and semantic memory.
"""

import uuid
import structlog
from typing import Any

from config import Settings
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.semantic import SemanticMemory
from memory.seal_engine import SealEngine

logger = structlog.get_logger(__name__)


class MemoryManager:
    """
    Unified memory interface.

    Usage:
        manager = MemoryManager(settings)
        await manager.initialize()
        await manager.extract_and_store("My name is Mohit and I like Python")
        context = await manager.get_context("What programming language do I like?")
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.short_term = ShortTermMemory(
            max_messages=settings.memory.short_term_max_messages
        )
        self.long_term = LongTermMemory(settings.memory.sqlite_path)
        self.semantic = SemanticMemory(settings.memory.chroma_path)
        self.seal = SealEngine(settings, self.long_term)

    async def initialize(self) -> None:
        await self.long_term.initialize()
        self.semantic.initialize()
        logger.info("memory_manager_initialized")

    async def store(
        self,
        content: str,
        memory_type: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store content in both long-term and semantic memory."""
        doc_id = str(uuid.uuid4())
        meta = metadata or {}
        meta["type"] = memory_type

        # Long-term (structured)
        await self.long_term.store(content, memory_type, meta)

        # Semantic (vector)
        self.semantic.store(content, doc_id, meta)

        logger.debug("memory_stored", type=memory_type, length=len(content))

    async def extract_and_store(self, user_input: str) -> None:
        """
        Mem0-like entity and fact extraction.
        Uses the local LLM to parse facts from user input and stores them as distinct semantic memories.
        """
        try:
            import httpx
            import json
            
            system_prompt = (
                "You are a memory extraction engine. "
                "Analyze the user's input and extract any permanent facts, preferences, or entities about the user. "
                "Return ONLY a JSON array of strings. If no new facts are present, return an empty array []. "
                "Example output: [\"User's name is Mohit\", \"User likes Python\"]"
            )
            
            headers = {
                "Authorization": f"Bearer {self.settings.claude.auth_token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            
            payload = {
                "model": self.settings.claude.model,
                "max_tokens": 500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_input}],
            }
            
            base_url = self.settings.claude.base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{base_url}/v1/messages", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = ""
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            content += block.get("text", "")
                    
                    try:
                        # Find json array in the text if it's wrapped in markdown
                        import re
                        match = re.search(r'\[.*\]', content, re.DOTALL)
                        if match:
                            facts = json.loads(match.group(0))
                            for fact in facts:
                                await self.store(fact, memory_type="extracted_fact")
                                logger.info("mem0_extracted_fact", fact=fact)
                    except json.JSONDecodeError:
                        logger.warning("mem0_extraction_parse_failed", content=content)
        except Exception as e:
            logger.warning("mem0_extraction_failed", error=str(e))

    async def process_feedback(self, user_input: str, response: str, context_id: str) -> None:
        """Trigger SEAL engine to analyze user input for corrective feedback."""
        await self.seal.process_feedback(user_input, response, context_id)

    async def recall(
        self, query: str, k: int = 5
    ) -> list[dict]:
        """Recall relevant memories using semantic search."""
        return self.semantic.search(query, k=k)

    async def get_context(self, query: str, k: int = 5) -> str:
        """Get formatted memory context for Claude system prompt."""
        memories = await self.recall(query, k=k)

        if not memories:
            return ""

        # Filter by relevance (cosine distance < 1.0 = somewhat relevant)
        relevant = [m for m in memories if m.get("distance", 1) < 1.2]

        if not relevant:
            return ""

        parts = ["Relevant memories:"]
        for m in relevant:
            parts.append(f"- {m['content'][:300]}")

        return "\n".join(parts)

    async def get_recent(self, limit: int = 10) -> list[dict]:
        """Get most recent memories from long-term storage."""
        return await self.long_term.search(limit=limit)

    async def close(self) -> None:
        await self.long_term.close()
