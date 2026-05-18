"""
Telegram Tool — send messages to the user via Telegram Bot API.

Used for reminders, notifications, and async alerts when the user
isn't at the Megan terminal.

Actions:
  - send_message: Send a Telegram message to the configured user
"""

import httpx
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class TelegramTool(BaseTool):
    name = "telegram"
    description = (
        "Send a message to the user via Telegram. "
        "Use this for reminders, notifications, or any time you need to reach the user "
        "when they might not be at the terminal. The bot token and chat ID are pre-configured."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'send_message'",
            "enum": ["send_message"],
            "required": True,
        },
        "message": {
            "type": "string",
            "description": "The message text to send via Telegram.",
            "required": True,
        },
    }
    dangerous = False

    def __init__(self, settings) -> None:
        self._bot_token = settings.telegram.bot_token
        self._chat_id = settings.telegram.chat_id

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")

        if action == "send_message":
            message = kwargs.get("message", "").strip()
            if not message:
                return ToolResult(success=False, output="", error="Message text is required")

            if not self._bot_token or not self._chat_id:
                return ToolResult(
                    success=False, output="",
                    error="Telegram bot_token or chat_id not configured in .env"
                )

            try:
                url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
                payload = {
                    "chat_id": self._chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json=payload)
                    data = resp.json()

                if data.get("ok"):
                    logger.info("telegram_sent", chat_id=self._chat_id)
                    return ToolResult(
                        success=True,
                        output=f"Telegram message sent: '{message[:100]}'"
                    )
                else:
                    error = data.get("description", "Unknown Telegram API error")
                    return ToolResult(success=False, output="", error=error)
            except Exception as e:
                logger.error("telegram_error", error=str(e))
                return ToolResult(success=False, output="", error=str(e))

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
