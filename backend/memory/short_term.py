"""
Short-Term Memory — in-process conversation buffer with sliding window.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShortTermMemory:
    """Sliding window of recent conversation messages."""

    max_messages: int = 50
    messages: list[dict[str, Any]] = field(default_factory=list)

    def add(self, role: str, content: Any) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            # Keep system-relevant messages, trim oldest
            self.messages = self.messages[-self.max_messages:]

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()

    def get_summary(self) -> str:
        """Get a brief summary of conversation context."""
        if not self.messages:
            return ""
        recent = self.messages[-5:]
        parts = []
        for msg in recent:
            role = msg["role"]
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            parts.append(f"{role}: {content[:100]}")
        return "\n".join(parts)
