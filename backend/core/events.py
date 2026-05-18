"""
Async Event Bus — publish/subscribe system for decoupled communication.

All components emit events here instead of calling each other directly.
The WebSocket handler subscribes to events and forwards them to clients.
"""

import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)


class EventType(str, Enum):
    """All event types in the system."""

    # Audio pipeline
    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    AUDIO_CHUNK = "audio_chunk"

    # Agent
    THINKING = "thinking"
    RESPONSE_TEXT = "response_text"
    RESPONSE_DONE = "response_done"

    # Tools
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"

    # Safety
    CONFIRM_REQUEST = "confirm_request"
    CONFIRM_RESPONSE = "confirm_response"

    # Memory
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"

    # System
    STATUS = "status"
    ERROR = "error"
    SYSTEM_NOTIFICATION = "system_notification"

    # Network & Devices
    NETWORK_DEVICE_DISCOVERED = "network_device_discovered"
    NETWORK_DEVICE_LOST = "network_device_lost"
    DEVICE_ONLINE = "device_online"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_HEALTH_CHECK = "device_health_check"

    # Scenes & Automation
    SCENE_ACTIVATED = "scene_activated"
    SCENE_DEACTIVATED = "scene_deactivated"

    # Media
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_STOPPED = "playback_stopped"
    MEDIA_QUEUE_UPDATED = "media_queue_updated"

    # Security
    SECURITY_ALERT = "security_alert"
    NEW_UNKNOWN_DEVICE = "new_unknown_device"


@dataclass
class Event:
    """A system event with type, payload, and metadata."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    conversation_id: str | None = None


# Subscriber type: async function that takes an Event
Subscriber = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async pub/sub event bus.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.THINKING, my_handler)
        await bus.emit(Event(type=EventType.THINKING, data={"text": "..."}))
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscriber]] = {}
        self._global_subscribers: list[Subscriber] = []

    def subscribe(self, event_type: EventType, handler: Subscriber) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Subscriber) -> None:
        """Subscribe to ALL event types (used by WebSocket forwarder)."""
        self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: Subscriber) -> None:
        """Remove a subscriber."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    def unsubscribe_all(self, handler: Subscriber) -> None:
        """Remove a global subscriber."""
        self._global_subscribers = [
            h for h in self._global_subscribers if h != handler
        ]

    async def emit(self, event: Event) -> None:
        """Emit an event to all matching subscribers. Non-blocking."""
        handlers = list(self._global_subscribers)
        handlers.extend(self._subscribers.get(event.type, []))

        if not handlers:
            return

        # Fire all handlers concurrently, don't let one failure kill others
        results = await asyncio.gather(
            *(h(event) for h in handlers), return_exceptions=True
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_error",
                    event_type=event.type,
                    handler=str(handlers[i]),
                    error=str(result),
                )


# Singleton event bus
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
