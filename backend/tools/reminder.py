"""
Reminder Tool — schedule time-based reminders that fire via Telegram.

When the user says "remind me to X in 30 minutes", this tool:
1. Stores the reminder with a future timestamp
2. A background asyncio task checks every 30s and fires due reminders
3. Fires by sending a Telegram message via the TelegramTool

Actions:
  - set: Schedule a new reminder
  - list: List all pending reminders
  - cancel: Cancel a pending reminder by ID
"""

import asyncio
import time
import uuid
import structlog
from datetime import datetime, timedelta, timezone
from typing import Any

from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)

# In-memory reminder store (persists across the session)
_reminders: dict[str, dict[str, Any]] = {}
_scheduler_running = False


class ReminderTool(BaseTool):
    name = "reminder"
    description = (
        "Schedule reminders that will be sent to the user via Telegram at the specified time. "
        "Use action 'set' with 'message' and 'delay_minutes' (number of minutes from now). "
        "Use action 'list' to show pending reminders. "
        "Use action 'cancel' with 'reminder_id' to cancel a pending reminder."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'set', 'list', or 'cancel'",
            "enum": ["set", "list", "cancel"],
            "required": True,
        },
        "message": {
            "type": "string",
            "description": "The reminder message. Required for 'set'.",
        },
        "delay_minutes": {
            "type": "number",
            "description": "How many minutes from now to fire the reminder. Required for 'set'. Can be fractional (e.g., 0.5 for 30 seconds).",
        },
        "reminder_id": {
            "type": "string",
            "description": "ID of the reminder to cancel. Required for 'cancel'.",
        },
    }
    dangerous = False

    def __init__(self, telegram_tool) -> None:
        self._telegram = telegram_tool

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")

        if action == "set":
            return await self._set_reminder(
                message=kwargs.get("message", ""),
                delay_minutes=kwargs.get("delay_minutes", 0),
            )
        elif action == "list":
            return self._list_reminders()
        elif action == "cancel":
            return self._cancel_reminder(kwargs.get("reminder_id", ""))
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    async def _set_reminder(self, message: str, delay_minutes: float) -> ToolResult:
        if not message:
            return ToolResult(success=False, output="", error="Reminder message is required")
        if delay_minutes <= 0:
            return ToolResult(success=False, output="", error="delay_minutes must be positive")

        reminder_id = str(uuid.uuid4())[:8]
        fire_at = time.time() + (delay_minutes * 60)
        fire_dt = datetime.fromtimestamp(fire_at, tz=timezone(timedelta(hours=5, minutes=30)))

        _reminders[reminder_id] = {
            "id": reminder_id,
            "message": message,
            "fire_at": fire_at,
            "fire_at_human": fire_dt.strftime("%I:%M %p"),
            "created": time.time(),
            "status": "pending",
        }

        logger.info("reminder_set", id=reminder_id, message=message, fire_at=fire_dt.isoformat())

        # Ensure scheduler is running
        _ensure_scheduler(self._telegram)

        return ToolResult(
            success=True,
            output=f"Reminder set (ID: {reminder_id}). "
                   f"I'll send you a Telegram message at {fire_dt.strftime('%I:%M %p')} saying: \"{message}\""
        )

    def _list_reminders(self) -> ToolResult:
        pending = {k: v for k, v in _reminders.items() if v["status"] == "pending"}
        if not pending:
            return ToolResult(success=True, output="No pending reminders.")

        lines = []
        for rid, r in pending.items():
            lines.append(f"• [{rid}] at {r['fire_at_human']}: {r['message']}")
        return ToolResult(success=True, output=f"Pending reminders ({len(pending)}):\n" + "\n".join(lines))

    def _cancel_reminder(self, reminder_id: str) -> ToolResult:
        if not reminder_id:
            return ToolResult(success=False, output="", error="reminder_id is required")
        if reminder_id not in _reminders:
            return ToolResult(success=False, output="", error=f"Reminder {reminder_id} not found")
        _reminders[reminder_id]["status"] = "cancelled"
        return ToolResult(success=True, output=f"Reminder {reminder_id} cancelled.")


def _ensure_scheduler(telegram_tool):
    """Start the background scheduler if not already running."""
    global _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True
    asyncio.create_task(_scheduler_loop(telegram_tool))
    logger.info("reminder_scheduler_started")


async def _scheduler_loop(telegram_tool):
    """Check every 15 seconds for due reminders and fire them."""
    global _scheduler_running
    try:
        while True:
            await asyncio.sleep(15)
            now = time.time()

            for rid, r in list(_reminders.items()):
                if r["status"] == "pending" and now >= r["fire_at"]:
                    r["status"] = "fired"
                    logger.info("reminder_firing", id=rid, message=r["message"])

                    # Send via Telegram
                    try:
                        text = f"⏰ *Reminder from MEGAN*\n\n{r['message']}"
                        await telegram_tool.execute(action="send_message", message=text)
                        logger.info("reminder_sent", id=rid)
                    except Exception as e:
                        logger.error("reminder_send_failed", id=rid, error=str(e))

            # Clean up old fired/cancelled reminders (older than 1 hour)
            cutoff = now - 3600
            expired = [k for k, v in _reminders.items() if v["status"] != "pending" and v["created"] < cutoff]
            for k in expired:
                del _reminders[k]
    except asyncio.CancelledError:
        pass
    finally:
        _scheduler_running = False
