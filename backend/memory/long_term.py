"""
Long-Term Memory — SQLite persistent storage for conversations, preferences, tasks.
"""

import aiosqlite
import json
import structlog
from datetime import datetime, timezone
from typing import Any

logger = structlog.get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
"""


class LongTermMemory:
    """SQLite-backed persistent memory."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("long_term_memory_initialized", path=self._db_path)

    async def store(self, content: str, memory_type: str, metadata: dict[str, Any] | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "INSERT INTO memories (type, content, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (memory_type, content, json.dumps(metadata or {}), now, now),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def search(self, memory_type: str | None = None, limit: int = 10) -> list[dict]:
        if memory_type:
            cursor = await self._db.execute(
                "SELECT id, type, content, metadata, created_at FROM memories WHERE type = ? ORDER BY created_at DESC LIMIT ?",
                (memory_type, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT id, type, content, metadata, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "type": r[1], "content": r[2], "metadata": json.loads(r[3]), "created_at": r[4]}
            for r in rows
        ]

    async def get_preference(self, key: str) -> str | None:
        cursor = await self._db.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_preference(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        await self._db.commit()

    async def get_all_preferences(self) -> dict[str, str]:
        """Return all stored preferences as a dict."""
        cursor = await self._db.execute("SELECT key, value FROM preferences")
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}

    async def delete_preference(self, key: str) -> None:
        """Remove a preference entirely."""
        await self._db.execute("DELETE FROM preferences WHERE key = ?", (key,))
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
