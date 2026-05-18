"""
REST API Routes — health checks, history, memory search, configuration.
"""

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
import os
from api.schemas import HealthResponse, MemorySearchRequest
from core.dependencies import get_container
from core.events import Event, EventType
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api")

# In-memory log of recent auto-handled WhatsApp messages (for the System Ops dashboard)
# Format: [{"name": str, "number": str, "body": str, "handled_at": iso_timestamp}]
_auto_handled_log: list[dict] = []
_MAX_AUTO_HANDLED = 20

# Background agent thought stream log — tracks what delegated agents are thinking/doing
# Format: [{"conversation_id": str, "name": str, "number": str, "events": [...], "started_at": iso, "updated_at": iso}]
_background_thought_streams: list[dict] = []
_MAX_THOUGHT_STREAMS = 10

# Persistent conversation context for delegated WhatsApp contacts
# Key: conversation_id (e.g., "wa-auto-919876543210"), Value: list of message dicts
_whatsapp_conversation_history: dict[str, list[dict]] = {}
_MAX_WHATSAPP_HISTORY_MESSAGES = 50


def _log_background_event(conversation_id: str, event_type: str, data: dict, name: str = "", number: str = "") -> None:
    """Log an event from a background agent to the thought stream."""
    global _background_thought_streams
    now = datetime.now(timezone.utc).isoformat()
    # Find existing stream for this conversation
    stream = next((s for s in _background_thought_streams if s["conversation_id"] == conversation_id), None)
    if stream is None:
        stream = {
            "conversation_id": conversation_id,
            "name": name,
            "number": number,
            "events": [],
            "started_at": now,
            "updated_at": now,
        }
        _background_thought_streams.append(stream)
        if len(_background_thought_streams) > _MAX_THOUGHT_STREAMS:
            _background_thought_streams.pop(0)
    stream["events"].append({
        "type": event_type,
        "data": data,
        "timestamp": now,
    })
    # Keep max 30 events per stream
    if len(stream["events"]) > 30:
        stream["events"] = stream["events"][-30:]
    stream["updated_at"] = now


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        services={
            "agent": "ready",
            "memory": "ready",
            "tts": "ready",
            "stt": "ready",
        },
    )


@router.get("/history")
async def get_history(limit: int = 20):
    container = get_container()
    memory = container.memory_manager()
    memories = await memory.get_recent(limit=limit)
    return {"memories": memories}


@router.post("/memories/search")
async def search_memories(req: MemorySearchRequest):
    container = get_container()
    memory = container.memory_manager()
    results = await memory.recall(req.query, k=req.limit)
    return {"results": results}


@router.get("/tools")
async def list_tools():
    container = get_container()
    registry = container.tool_registry()
    tools = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "dangerous": tool.dangerous,
        })
    return {"tools": tools}


@router.get("/config")
async def get_config():
    from config import get_settings
    s = get_settings()
    return {
        "claude_model": s.claude.model,
        "claude_base_url": s.claude.base_url,
        "tts_voice": s.tts.voice,
        "stt_model": s.audio.stt_model,
    }


@router.get("/system")
async def get_system_metrics():
    """Real system metrics for the dashboard."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except ImportError:
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_gb": 0,
            "memory_total_gb": 0,
            "disk_percent": 0,
            "error": "psutil not installed",
        }


@router.get("/memories")
async def get_memories(limit: int = 10):
    """Recent memories for the dashboard."""
    container = get_container()
    memory = container.memory_manager()
    memories = await memory.get_recent(limit=limit)
    return {"memories": memories}


@router.get("/persona")
async def get_persona():
    """All stored persona preferences."""
    container = get_container()
    memory = container.memory_manager()
    prefs = await memory.long_term.get_all_preferences()
    return {"preferences": prefs}


@router.get("/background_tasks")
async def get_background_tasks():
    """Status of all background tasks."""
    from tools.background_worker import _active_tasks
    import time
    tasks = []
    for tid, data in _active_tasks.items():
        tasks.append({
            "id": tid,
            "description": data["description"][:200],
            "status": data["status"],
            "elapsed_seconds": round(time.time() - data["start_time"], 1),
            "result": (data.get("result") or "")[:500] if data["status"] == "completed" else None,
            "error": data.get("error") if data["status"] == "failed" else None,
        })
    return {"tasks": tasks}


@router.get("/system-ops")
async def get_system_ops():
    """Unified system operations data for the dashboard."""
    from tools.background_worker import _active_tasks
    import time

    container = get_container()
    memory = container.memory_manager()

    # Delegated contacts
    delegated = []
    delegated_raw = await memory.long_term.get_preference("delegated_whatsapp_contacts")
    if delegated_raw:
        try:
            import json
            parsed = json.loads(delegated_raw)
            if isinstance(parsed, list):
                delegated = [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    # Background tasks
    tasks = []
    for tid, data in _active_tasks.items():
        tasks.append({
            "id": tid,
            "description": data["description"][:200],
            "status": data["status"],
            "elapsed_seconds": round(time.time() - data["start_time"], 1),
            "result": (data.get("result") or "")[:500] if data["status"] == "completed" else None,
            "error": data.get("error") if data["status"] == "failed" else None,
        })

    return {
        "delegated_contacts": delegated,
        "auto_handled_messages": list(reversed(_auto_handled_log[-_MAX_AUTO_HANDLED:])),
        "background_tasks": tasks,
        "background_thought_streams": list(reversed(_background_thought_streams[-_MAX_THOUGHT_STREAMS:])),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/whatsapp-incoming")
async def whatsapp_incoming(request: dict):
    """
    Webhook called by the WhatsApp bridge when a new message arrives.
    
    If the contact is delegated (user said "handle Miku"), process the message
    autonomously in the background without notifying the user.
    Otherwise, emit a SYSTEM_NOTIFICATION so Megan speaks it aloud.
    """
    import asyncio
    from core.events import Event, EventType

    name = request.get("name", "Unknown")
    number = request.get("number", "")
    body = request.get("body", "")

    if not body.strip():
        return {"status": "ignored", "reason": "empty message"}

    container = get_container()
    event_bus = container.event_bus()
    memory = container.memory_manager()

    # Check if this contact is delegated for autonomous handling
    delegated_contacts_raw = await memory.long_term.get_preference("delegated_whatsapp_contacts")
    delegated_contacts = []
    if delegated_contacts_raw:
        try:
            import json
            parsed = json.loads(delegated_contacts_raw)
            # Guard against corrupted values: must be a list of non-empty strings
            if isinstance(parsed, list):
                delegated_contacts = [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            delegated_contacts = []

    # Check if the sender name or number exactly matches any delegated contact
    is_delegated = False
    logger.info("whatsapp_delegation_check", name=name, number=number, delegated_contacts=delegated_contacts)
    name_lower = name.lower().strip()
    number_lower = number.lower().strip()
    for dc in delegated_contacts:
        dc_lower = dc.lower()
        # Exact match on name or on number (or the name is contained as a whole-word-ish prefix)
        if dc_lower == name_lower or dc_lower == number_lower or name_lower.startswith(dc_lower + " "):
            is_delegated = True
            break

    if is_delegated:
        # Handle autonomously in the background
        logger.info("whatsapp_delegated_auto_handle", name=name, number=number)

        # Log for System Ops dashboard
        _auto_handled_log.append({
            "name": name,
            "number": number,
            "body": body[:300],
            "handled_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(_auto_handled_log) > _MAX_AUTO_HANDLED:
            _auto_handled_log.pop(0)

        async def _auto_handle():
            conversation_id = f"wa-auto-{number}"
            try:
                from agent.schemas import ConversationContext
                agent = container.agent_brain()

                ctx = ConversationContext(
                    conversation_id=conversation_id,
                    is_background=True,
                )

                # Load previous conversation history for this contact
                global _whatsapp_conversation_history
                prev_messages = _whatsapp_conversation_history.get(conversation_id, [])
                if prev_messages:
                    ctx.messages = list(prev_messages)
                    # Also log that we're continuing a thread
                    _log_background_event(
                        conversation_id, "thread_loaded",
                        {"message_count": len(prev_messages)},
                        name=name, number=number,
                    )

                # Log the incoming message
                _log_background_event(
                    conversation_id, "message_received",
                    {"body": body[:500], "from": name, "number": number},
                    name=name, number=number,
                )

                prompt = (
                    f"You are handling a WhatsApp chat autonomously for the user. "
                    f"A message just arrived from {name} ({number}): \"{body[:500]}\"\n\n"
                    f"CRITICAL: You must ONLY reply to {name} ({number}). Do NOT reply to any other contacts.\n"
                    f"You have the FULL conversation history above. Reference prior messages naturally when replying. "
                    f"Reply to them on WhatsApp as the user's AI assistant. Be helpful, natural, "
                    f"and act as if the user themselves is replying. Use the whatsapp tool with action 'send_message', "
                    f"phone_number='{number}', and your reply message. Keep it concise and contextual.\n\n"
                    f"If they ask for a phone number or contact info:\n"
                    f"1. First use the `whatsapp` tool with action 'search_contacts' to look it up in the user's WhatsApp contacts.\n"
                    f"2. Also check persona memory with action 'get', key 'contact_whatsapp_[name]' (e.g., 'contact_whatsapp_mummy').\n"
                    f"3. ONLY say you can't find it AFTER trying both of the above."
                )

                # Capture all events from the background agent
                async for event in agent.process(prompt, ctx):
                    event_type = event.get("type", "")

                    # Map internal generator events to EventBus types for broadcasting
                    evt_type_map = {
                        "thinking": EventType.THINKING,
                        "tool_start": EventType.TOOL_START,
                        "tool_result": EventType.TOOL_RESULT,
                        "response_text": EventType.RESPONSE_TEXT,
                        "response_done": EventType.RESPONSE_DONE,
                        "error": EventType.ERROR,
                    }
                    evt_bus_type = evt_type_map.get(event_type)
                    if evt_bus_type:
                        # Broadcast to all connected WebSocket clients so the logic stream can show it
                        await event_bus.emit(
                            Event(
                                type=evt_bus_type,
                                data={"source": "background", **event},
                                conversation_id=None,
                            )
                        )

                    if event_type == "thinking":
                        _log_background_event(conversation_id, "thinking", {"text": event.get("text", "")[:300]}, name=name, number=number)
                    elif event_type == "tool_start":
                        _log_background_event(conversation_id, "tool_start", {
                            "tool": event.get("tool", ""),
                            "input": event.get("input", {}),
                        }, name=name, number=number)
                    elif event_type == "tool_result":
                        _log_background_event(conversation_id, "tool_result", {
                            "tool": event.get("tool", ""),
                            "output": event.get("output", "")[:300],
                            "success": event.get("success", False),
                        }, name=name, number=number)
                    elif event_type == "response_text":
                        _log_background_event(conversation_id, "response_text", {"text": event.get("text", "")[:300]}, name=name, number=number)
                    elif event_type == "response_done":
                        _log_background_event(conversation_id, "response_done", {}, name=name, number=number)

                # Save the updated conversation history back
                # Filter to keep only the last N messages to prevent unbounded growth
                _whatsapp_conversation_history[conversation_id] = ctx.messages[-_MAX_WHATSAPP_HISTORY_MESSAGES:]

            except Exception as e:
                logger.error("whatsapp_auto_handle_failed", error=str(e))
                _log_background_event(conversation_id, "error", {"error": str(e)}, name=name, number=number)

        asyncio.create_task(_auto_handle())
        return {"status": "auto_handled", "delegated": True}

    # Not delegated — notify the user in a natural, human-like way
    body_preview = body[:80].strip()
    if len(body) <= 80:
        notification = f"Hey, {name} just messaged: '{body}'. Should I reply?"
    else:
        notification = (
            f"Hey, {name} sent a longer message. It starts: '{body_preview}...' "
            f"Want me to reply, or read you the full thing?"
        )

    await event_bus.emit(
        Event(
            type=EventType.SYSTEM_NOTIFICATION,
            data={
                "text": notification,
                "whatsapp_reply_context": {"name": name, "number": number, "body": body},
            },
        )
    )

    return {"status": "notified"}


# ─── YouTube Video Search Proxy ──────────────────────────────────────────────
# Proxies search requests to the Invidious API to avoid browser CORS issues.
# Used by the Desktop YoutubeWindow component to find and embed videos.

@router.get("/youtube/search")
async def youtube_search(q: str, count: int = 3):
    """Search for YouTube videos via Invidious API and return video IDs."""
    import httpx

    invidious_instances = [
        "https://y.com.sb",
        "https://invidious.nerdvpn.de",
        "https://invidious.jing.rocks",
    ]

    for instance in invidious_instances:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{instance}/api/v1/search",
                    params={"q": q, "type": "video"},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()

            if not isinstance(data, list) or len(data) == 0:
                continue

            results = []
            for item in data[:count]:
                if item.get("type") != "video":
                    continue
                video_id = item.get("videoId")
                if video_id:
                    # Format view count nicely
                    views = item.get("viewCount", 0)
                    if views > 1_000_000:
                        views_str = f"{views / 1_000_000:.1f}M"
                    elif views > 1_000:
                        views_str = f"{views / 1_000:.0f}K"
                    else:
                        views_str = str(views)

                    # Format duration
                    dur = item.get("lengthSeconds", 0)
                    dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else ""

                    results.append({
                        "videoId": video_id,
                        "title": item.get("title", ""),
                        "channel": item.get("author", ""),
                        "views": views_str,
                        "duration": dur_str,
                        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                    })

            if results:
                return {"results": results}

        except Exception as e:
            logger.warning("invidious_search_failed", instance=instance, error=str(e))
            continue

    return {"results": [], "error": "All Invidious instances failed"}


@router.get("/media/stream")
async def stream_local_media(path: str, request: Request):
    """
    Stream a local file over HTTP with Range support.
    Used by Chromecast to play local media from this machine.
    """
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(path)
    range_header = request.headers.get("Range")

    if range_header:
        # Parse standard Range header (e.g., bytes=0-1024)
        range_match = range_header.strip().replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
    else:
        start = 0
        end = file_size - 1

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    chunk_size = (end - start) + 1

    def file_iterator():
        with open(path, "rb") as f:
            f.seek(start)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_size = min(bytes_left, 1024 * 1024) # 1MB chunks
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    import mimetypes
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        if path.endswith(".mkv"):
            mime_type = "video/x-matroska"
        elif path.endswith(".webm"):
            mime_type = "video/webm"
        else:
            mime_type = "application/octet-stream"

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": mime_type,
    }
    
    # 206 Partial Content is required for video streaming
    status_code = 206 if range_header else 200
    
    return StreamingResponse(
        file_iterator(),
        status_code=status_code,
        headers=headers,
    )
