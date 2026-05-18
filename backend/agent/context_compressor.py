"""
Context Compressor — smart conversation history management.

When the conversation gets too long, older messages are summarized
to keep the context window within token limits while preserving
important context.
"""

import structlog
from typing import Any

logger = structlog.get_logger(__name__)

# Rough estimate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count for a message list."""
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total_chars += len(str(block.get("text", "")))
                    total_chars += len(str(block.get("content", "")))
    return total_chars // CHARS_PER_TOKEN


def compress_messages(
    messages: list[dict[str, Any]],
    max_tokens: int = 6000,
    keep_recent: int = 6,
) -> list[dict[str, Any]]:
    """
    Compress conversation history to fit within token limits.

    Strategy:
    1. Always keep the most recent `keep_recent` messages intact.
    2. Summarize older messages into a single context block.
    3. Truncate long tool results to 200 chars.

    Args:
        messages: Full conversation message list
        max_tokens: Target max token count
        keep_recent: Number of recent messages to always preserve

    Returns:
        Compressed message list
    """
    current_tokens = estimate_tokens(messages)

    if current_tokens <= max_tokens:
        return messages  # No compression needed

    logger.info(
        "context_compressing",
        original_tokens=current_tokens,
        max_tokens=max_tokens,
        message_count=len(messages),
    )

    # Split into old and recent
    if len(messages) <= keep_recent:
        # Can't compress further, just truncate tool results
        return _truncate_tool_results(messages)

    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Summarize old messages
    summary_parts = []
    for msg in old_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if isinstance(content, str):
            # Truncate long content
            text = content[:150].strip()
            if text:
                summary_parts.append(f"[{role}]: {text}")
        elif isinstance(content, list):
            # Handle tool results and other block content
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "tool_result":
                        tool_content = str(block.get("content", ""))[:100]
                        summary_parts.append(f"[tool_result]: {tool_content}")
                    elif block_type == "text":
                        text = block.get("text", "")[:150]
                        if text:
                            summary_parts.append(f"[{role}]: {text}")

    summary = "Earlier conversation summary:\n" + "\n".join(summary_parts[-15:])  # Keep last 15 entries

    # Build compressed message list
    compressed = [
        {"role": "user", "content": summary},
        {"role": "assistant", "content": "Understood. I have the context from our earlier conversation."},
    ] + _truncate_tool_results(recent_messages)

    new_tokens = estimate_tokens(compressed)
    logger.info(
        "context_compressed",
        new_tokens=new_tokens,
        messages_before=len(messages),
        messages_after=len(compressed),
    )

    return compressed


def _truncate_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Truncate long tool result content blocks to save tokens."""
    result = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block = dict(block)  # Copy
                    c = block.get("content", "")
                    if isinstance(c, str) and len(c) > 500:
                        block["content"] = c[:500] + "... [truncated]"
                new_blocks.append(block)
            result.append({**msg, "content": new_blocks})
        else:
            result.append(msg)
    return result
