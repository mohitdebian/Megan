"""
Self-Healing Manager — watches for errors and implements retry logic.
"""

import asyncio
import structlog
from typing import Any, Callable, Coroutine, TypeVar

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class SelfHealingManager:
    """
    Monitors system errors and provides utilities to retry transient failures.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.event_bus.subscribe(EventType.ERROR, self._on_system_error)
        
    async def _on_system_error(self, event: Event) -> None:
        """Log system errors so the SEAL engine or other monitors can learn from them."""
        logger.warning("self_healing_error_detected", data=event.data)
        # Future: Store chronic errors to SQLite for long-term self-healing analysis

    async def execute_with_retry(
        self, 
        coro_func: Callable[[], Coroutine[Any, Any, T]], 
        max_retries: int = 2,
        base_delay: float = 1.0,
        context_msg: str = "operation"
    ) -> T:
        """
        Execute an async function with exponential backoff.
        Emits EventType.ERROR on failures.
        """
        retries = 0
        while True:
            try:
                return await coro_func()
            except Exception as e:
                retries += 1
                
                await self.event_bus.emit(
                    Event(
                        type=EventType.ERROR,
                        data={
                            "context": context_msg,
                            "error": str(e),
                            "retry": retries,
                            "max_retries": max_retries
                        }
                    )
                )
                
                if retries > max_retries:
                    logger.error("self_healing_max_retries_exceeded", context=context_msg, error=str(e))
                    raise e
                    
                delay = base_delay * (2 ** (retries - 1))
                logger.info("self_healing_retry", context=context_msg, retry=retries, delay=delay)
                await asyncio.sleep(delay)
