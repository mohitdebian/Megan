"""
Agent Schemas — data models for the agent system.
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class AgentState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    TOOL_EXECUTING = "tool_executing"
    SPEAKING = "speaking"
    WAITING_CONFIRMATION = "waiting_confirmation"


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultMsg:
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class ConversationMessage:
    role: str  # "user" or "assistant"
    content: Any  # str or list of content blocks


@dataclass
class ConversationContext:
    conversation_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    memories: str = ""
    state: AgentState = AgentState.IDLE
    iteration_count: int = 0
    is_background: bool = False
