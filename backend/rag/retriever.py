"""
RAG Retriever — semantic search across indexed code and documents.
"""

import structlog

logger = structlog.get_logger(__name__)


class Retriever:
    def __init__(self, semantic_memory) -> None:
        self._memory = semantic_memory

    def search(self, query: str, k: int = 5, file_filter: str | None = None) -> list[dict]:
        where = None
        if file_filter:
            where = {"file": {"$contains": file_filter}}
        return self._memory.search(query, k=k, where=where)

    def search_formatted(self, query: str, k: int = 5) -> str:
        results = self.search(query, k=k)
        if not results:
            return "No relevant code found."

        parts = [f"Found {len(results)} relevant code sections:\n"]
        for r in results:
            meta = r.get("metadata", {})
            parts.append(f"--- {meta.get('file', 'unknown')} ({meta.get('chunk_type', 'code')}) ---")
            parts.append(r["content"][:800])
            parts.append("")

        return "\n".join(parts)
