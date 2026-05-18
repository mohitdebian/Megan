"""
Morning Routine Service — Proactive daily briefing engine.

Triggers at a configured time (default 8:00 AM) to autonomously compile
a personalized morning brief using the LLM, then waits to deliver it
when the user first connects via WebSocket.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import structlog

from core.events import EventBus, Event, EventType
from core.classifier import PriorityClassifier

logger = structlog.get_logger(__name__)


class MorningRoutine:
    """
    Compiles a daily morning brief and stores it until the user is active.
    The heartbeat triggers `maybe_compile_brief()` periodically.
    The websocket handler calls `get_pending_brief()` on first connection.
    """

    def __init__(self, event_bus: EventBus, container):
        self.event_bus = event_bus
        self.container = container
        self._pending_brief: str | None = None
        self._last_brief_date: str = ""
        self._is_compiling = False
        self._briefing_hour = 8  # 8:00 AM local time

    async def maybe_compile_brief(self):
        """
        Called by the heartbeat. Checks if it's past the briefing hour
        and no brief has been compiled today. If so, triggers compilation.
        """
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if self._last_brief_date == today_str:
            return  # Already compiled today

        if now.hour < self._briefing_hour:
            return  # Too early

        if self._is_compiling:
            return

        self._is_compiling = True
        try:
            await self._compile_brief()
            self._last_brief_date = today_str
        except Exception as e:
            logger.error("morning_routine_compile_error", error=str(e))
        finally:
            self._is_compiling = False

    async def _compile_brief(self):
        """
        Uses the agent brain to autonomously gather data and compile
        a morning briefing.
        """
        logger.info("morning_routine_compiling")

        from agent.schemas import ConversationContext

        agent = self.container.agent_brain()

        ctx = ConversationContext(
            conversation_id=f"morning-brief-{datetime.now().strftime('%Y%m%d')}",
            is_background=True,
        )

        prompt = (
            "You are running an autonomous morning routine. The user has NOT spoken to you yet. "
            "Compile a concise, personalized morning briefing for the user. Do the following:\n\n"
            "1. Check the user's unread emails using the 'email' tool with action 'list_unread'.\n"
            "2. Search the web for today's top 3 tech/AI news headlines using the 'web_search' tool.\n"
            "3. Check persona memory for any reminders or preferences.\n\n"
            "After gathering all this data, compose a single, natural, spoken briefing "
            "(like a personal assistant would deliver verbally). Keep it under 200 words. "
            "Start with 'Good morning, Sir.' and include:\n"
            "- Number of unread emails and any important senders\n"
            "- Top news headlines\n"
            "- Any reminders or scheduled items\n\n"
            "Return ONLY the final briefing text. Do NOT use any tools after composing the brief."
        )

        # Run the agent and collect the final response text
        full_response = ""
        async for event in agent.process(prompt, ctx):
            if event.get("type") == "response_text":
                full_response += event.get("text", "")

        if full_response.strip():
            self._pending_brief = full_response.strip()
            logger.info("morning_routine_ready", length=len(self._pending_brief))
        else:
            logger.warning("morning_routine_empty")

    def get_pending_brief(self) -> str | None:
        """
        Called by the WebSocket handler on the first user interaction
        of the day. Returns the brief and clears it.
        """
        brief = self._pending_brief
        self._pending_brief = None
        return brief
