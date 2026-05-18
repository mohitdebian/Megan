"""
Semantic Memory — ChromaDB vector storage for semantic retrieval.
"""

import chromadb
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


class SemanticMemory:
    """ChromaDB-backed vector memory for semantic search."""

    def __init__(self, chroma_path: str) -> None:
        self._path = chroma_path
        self._client: chromadb.ClientAPI | None = None
        self._collection = None

    def initialize(self) -> None:
        import os
        os.makedirs(self._path, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._path)
        self._collection = self._client.get_or_create_collection(
            name="megan_memories",
            metadata={"hnsw:space": "cosine"},
        )
        count = self._collection.count()
        logger.info("semantic_memory_initialized", path=self._path, documents=count)

    def store(self, content: str, doc_id: str, metadata: dict[str, Any] | None = None) -> None:
        self._collection.upsert(
            documents=[content],
            ids=[doc_id],
            metadatas=[metadata or {}],
        )

    def search(self, query: str, k: int = 5, where: dict | None = None) -> list[dict]:
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(k, self._collection.count()) if self._collection.count() > 0 else 1,
        }
        if where:
            kwargs["where"] = where

        if self._collection.count() == 0:
            return []

        results = self._collection.query(**kwargs)

        memories = []
        for i in range(len(results["ids"][0])):
            memories.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })
        return memories

    def delete(self, doc_id: str) -> None:
        self._collection.delete(ids=[doc_id])

    def count(self) -> int:
        return self._collection.count()
