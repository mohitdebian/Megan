"""
RAG Indexer — indexes repository files into ChromaDB for semantic search.
"""

import os
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build", ".next"}
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".md", ".yaml", ".yml", ".toml"}


class Indexer:
    def __init__(self, semantic_memory) -> None:
        self._memory = semantic_memory

    def index_repository(self, repo_path: str, max_depth: int = 4) -> dict:
        base = Path(repo_path)
        stats = {"files": 0, "chunks": 0, "skipped": 0}

        from rag.chunker import chunk_file

        for item in base.rglob("*"):
            if any(s in item.parts for s in SKIP_DIRS):
                continue
            if not item.is_file() or item.suffix not in CODE_EXTS:
                stats["skipped"] += 1
                continue
            depth = len(item.relative_to(base).parts)
            if depth > max_depth:
                continue

            try:
                content = item.read_text(errors="ignore")
                rel_path = str(item.relative_to(base))
                chunks = chunk_file(content, rel_path, item.suffix)

                for i, chunk in enumerate(chunks):
                    doc_id = f"{rel_path}::chunk_{i}"
                    self._memory.store(
                        content=chunk["content"],
                        doc_id=doc_id,
                        metadata={
                            "file": rel_path,
                            "language": item.suffix,
                            "chunk_type": chunk.get("type", "code"),
                            "type": "code",
                        },
                    )
                    stats["chunks"] += 1

                stats["files"] += 1
            except Exception as e:
                logger.warning("index_file_error", file=str(item), error=str(e))
                stats["skipped"] += 1

        logger.info("indexing_complete", **stats)
        return stats
