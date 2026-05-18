"""
WhatsApp Tool — send and read WhatsApp messages via local Node.js bridge.

The bridge (whatsapp-bridge/server.js) runs a headless Chrome with whatsapp-web.js
and exposes a REST API on localhost:3001.

No third-party services. No browser popups. Fully local.

Actions:
  - send_message: Send a WhatsApp message to a phone number
  - read_messages: Read recent incoming messages (optionally filtered by sender)
  - search_contacts: Search contacts by name
"""

import httpx
import json
import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


def _is_phone_number(s: str) -> bool:
    """Heuristic: prefer numbers that look like real phone numbers over formatted IDs."""
    digits = s.strip().replace("+", "").replace(" ", "").replace("-", "")
    return digits.isdigit() and len(digits) >= 10 and not digits.startswith("1208")


def _deduplicate_contacts(contacts: list[dict]) -> list[dict]:
    """Deduplicate contacts by their WhatsApp ID. If same ID has multiple entries,
    keep the one with the most phone-like number."""
    seen: dict[str, dict] = {}
    for c in contacts:
        cid = c.get("id", "").strip()
        if not cid:
            continue
        if cid not in seen:
            seen[cid] = c
        else:
            # Prefer entry with a cleaner phone number
            existing = seen[cid]
            if _is_phone_number(c.get("number", "")) and not _is_phone_number(existing.get("number", "")):
                seen[cid] = c
    return list(seen.values())


class WhatsAppTool(BaseTool):
    name = "whatsapp"
    description = (
        "**WhatsApp Messaging**: You have a `whatsapp` tool. When the user asks to send a WhatsApp message:\n"
        "- You must know the recipient's exact phone number (with country code, e.g., 919876543210).\n"
        "- If the user only gives a name, use the `whatsapp` tool with action 'search_contacts' FIRST.\n"
        "- If 'search_contacts' returns MULTIPLE matching contacts:\n"
        "  1. BEFORE asking the user, use the `persona` tool with action 'get', key 'contact_whatsapp_[name]' (e.g., 'contact_whatsapp_miku') to see if a number was previously saved for this contact.\n"
        "  2. If there is NO stored mapping, check your Memory Context for any previous mention of a specific number for this name.\n"
        "  3. If there is NO clear memory mapping this name to a specific person, you MUST ask the user to clarify (e.g., 'I found Shyam Singh and Shyam Sharma, which one?').\n"
        "  4. If the memory DOES show who they mean, use that exact number confidently.\n"
        "- **MESSAGE LENGTH LIMIT**: WhatsApp messages are SHORT. If the user asks to send a research paper, report, article, or any long document:\n"
        "  1. NEVER try to send the full content as a WhatsApp text message.\n"
        "  2. INSTEAD: use the `filesystem` tool to save the content as a file (e.g., `.txt`, `.md`, `.pdf` if you can generate it) in the user's workspace.\n"
        "  3. Then send a SHORT WhatsApp message with a concise summary and mention that the full document is saved locally.\n"
        "  4. Example workflow: user says 'search Zepto research and send to Miku' → search web → compile findings → save as `/home/user/zepto_research.txt` → send WhatsApp: 'Hey, I compiled a research summary on Zepto for you. The full doc is saved on my laptop — check it out!'\n"
        "- Send directly — do NOT ask the user to confirm the message text."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'send_message', 'read_messages', or 'search_contacts'",
            "enum": ["send_message", "read_messages", "search_contacts"],
            "required": True,
        },
        "phone_number": {
            "type": "string",
            "description": "Recipient phone number with country code, no '+' (e.g., '919876543210'). Required for send_message.",
        },
        "message": {
            "type": "string",
            "description": "Message to send — auto-compose naturally from user intent. Required for send_message.",
        },
        "query": {
            "type": "string",
            "description": "Search query for contacts (name or number). Required for search_contacts.",
        },
        "limit": {
            "type": "integer",
            "description": "Number of messages to fetch (default 10). For read_messages.",
        },
        "from_number": {
            "type": "string",
            "description": "Filter messages by sender number. For read_messages.",
        },
    }
    dangerous = False  # Auto-send

    def __init__(self, settings, memory_manager=None) -> None:
        self._base_url = settings.whatsapp.bridge_url.rstrip("/")
        self._memory = memory_manager

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")

        try:
            if action == "send_message":
                return await self._send(
                    phone_number=kwargs.get("phone_number", ""),
                    message=kwargs.get("message", ""),
                )
            elif action == "read_messages":
                return await self._read_messages(
                    limit=kwargs.get("limit", 10),
                    from_number=kwargs.get("from_number"),
                )
            elif action == "search_contacts":
                return await self._search_contacts(kwargs.get("query", ""))
            else:
                return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except httpx.ConnectError:
            return ToolResult(
                success=False,
                output="",
                error="WhatsApp bridge not running. Start it with: cd whatsapp-bridge && npm start",
            )
        except Exception as e:
            logger.error("whatsapp_error", error=str(e))
            return ToolResult(success=False, output="", error=str(e))

    async def _send(self, phone_number: str, message: str) -> ToolResult:
        if not phone_number:
            return ToolResult(success=False, output="", error="Phone number is required")
        if not message:
            return ToolResult(success=False, output="", error="Message is required")

        # Normalize phone number
        phone_number = phone_number.strip().replace("+", "").replace(" ", "").replace("-", "")
        chat_id = f"{phone_number}@c.us"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/send",
                json={"chatId": chat_id, "message": message},
            )
            data = resp.json()

        if data.get("success"):
            logger.info("whatsapp_sent", to=phone_number, msg_id=data.get("messageId"))
            # Try to store the contact mapping for future lookups
            await self._store_contact_mapping(phone_number)
            return ToolResult(
                success=True,
                output=f"WhatsApp message sent to {phone_number}: "
                       f"'{message[:100]}{'...' if len(message) > 100 else ''}'",
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=data.get("error", "Unknown error from WhatsApp bridge"),
            )

    async def _store_contact_mapping(self, phone_number: str) -> None:
        """Look up the contact name by number and store name→number in long-term memory."""
        if not self._memory:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/contacts", params={"q": phone_number})
                data = resp.json()
            if data.get("success"):
                contacts = _deduplicate_contacts(data.get("contacts", []))
                for c in contacts:
                    name = c.get("name", "").strip()
                    num = c.get("number", "").strip()
                    if name and num:
                        key = f"contact_whatsapp_{name.lower().replace(' ', '_')}"
                        await self._memory.long_term.set_preference(key, num)
                        logger.info("whatsapp_contact_mapping_stored", name=name, number=num)
        except Exception as e:
            logger.debug("whatsapp_contact_mapping_failed", error=str(e))

    async def _read_messages(self, limit: int = 10, from_number: str | None = None) -> ToolResult:
        params: dict = {"limit": limit}
        if from_number:
            params["from"] = from_number.strip().replace("+", "").replace(" ", "")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self._base_url}/messages", params=params)
            data = resp.json()

        if data.get("success"):
            messages = data.get("messages", [])
            if not messages:
                return ToolResult(success=True, output="No recent messages found.")

            lines = []
            for msg in messages:
                name = msg.get("name", "Unknown")
                body = msg.get("body", "")[:200]
                lines.append(f"• {name}: {body}")

            return ToolResult(
                success=True,
                output=f"Recent messages ({len(messages)}):\n" + "\n".join(lines),
            )
        else:
            return ToolResult(success=False, output="", error=data.get("error", "Failed to read messages"))

    async def _search_contacts(self, query: str) -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="Search query is required")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self._base_url}/contacts", params={"q": query})
            data = resp.json()

        if data.get("success"):
            contacts = data.get("contacts", [])
            if not contacts:
                return ToolResult(success=True, output=f"No contacts found matching '{query}'")

            # CRITICAL: Deduplicate by WhatsApp ID. The same contact can appear
            # twice with different number formats (e.g., formatted vs raw).
            contacts = _deduplicate_contacts(contacts)

            lines = []
            for c in contacts:
                lines.append(f"• {c.get('name', 'Unknown')} — {c.get('number', 'N/A')} (ID: {c.get('id', '')})")

            return ToolResult(
                success=True,
                output=f"Contacts matching '{query}' ({len(contacts)}):\n" + "\n".join(lines),
            )
        else:
            return ToolResult(success=False, output="", error=data.get("error", "Contact search failed"))
