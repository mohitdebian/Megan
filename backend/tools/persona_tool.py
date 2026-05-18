"""
Persona Tool — allows Megan to store and retrieve user preferences/personality traits.

This creates a persistent "persona" layer so Megan remembers things like:
- Favorite coffee, food preferences
- Communication style preferences
- Nicknames, relationships
- Work habits, meeting preferences
"""

import structlog
from tools.base import BaseTool, ToolResult
from memory.manager import MemoryManager

logger = structlog.get_logger(__name__)


class PersonaTool(BaseTool):
    name = "persona"
    description = (
        "Store, retrieve, and delete personal preferences about the user. "
        "Use 'get' to recall preferences (optionally pass a specific key). "
        "Use 'set' to remember a new preference (e.g., favorite coffee, work style, delegated_whatsapp_contacts). "
        "Use 'delete' to remove a preference entirely. "
        "Use this whenever the user shares personal information worth remembering or wants to update/remove something."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'get' (retrieve preferences), 'set' (store a preference), or 'delete' (remove a preference).",
            "enum": ["get", "set", "delete"],
            "required": True,
        },
        "key": {
            "type": "string",
            "description": "Preference key (e.g., 'favorite_coffee', 'delegated_whatsapp_contacts'). Required for 'set' and 'delete'. Optional for 'get' — if omitted, returns all preferences.",
        },
        "value": {
            "type": "string",
            "description": "Preference value (e.g., 'black, no sugar' or '[\"Miku\"]'). Required for 'set'.",
        },
    }
    dangerous = False

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory = memory_manager

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")

        if action == "get":
            try:
                key = kwargs.get("key", "").strip()
                if key:
                    value = await self._memory.long_term.get_preference(key)
                    if value is None:
                        return ToolResult(success=True, output=f"No preference found for key '{key}'.")
                    return ToolResult(success=True, output=f"{key} = {value}")

                prefs = await self._memory.long_term.get_all_preferences()
                if not prefs:
                    return ToolResult(success=True, output="No personal preferences stored yet.")
                lines = [f"- {k}: {v}" for k, v in prefs.items()]
                return ToolResult(
                    success=True,
                    output="User preferences:\n" + "\n".join(lines),
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        elif action == "set":
            key = kwargs.get("key", "").strip()
            value = kwargs.get("value", "").strip()
            if not key or not value:
                return ToolResult(success=False, output="", error="Both 'key' and 'value' are required.")
            try:
                await self._memory.long_term.set_preference(key, value)
                logger.info("persona_preference_set", key=key, value=value)
                return ToolResult(
                    success=True,
                    output=f"Preference saved: {key} = {value}",
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        elif action == "delete":
            key = kwargs.get("key", "").strip()
            if not key:
                return ToolResult(success=False, output="", error="'key' is required for delete.")
            try:
                await self._memory.long_term.delete_preference(key)
                logger.info("persona_preference_deleted", key=key)
                return ToolResult(
                    success=True,
                    output=f"Preference deleted: {key}",
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
