"""
WebSocket Handler — real-time bidirectional communication with the frontend.

Protocol:
  Client→Server: audio_chunk, text_input, interrupt, confirm_action
  Server→Client: transcript, thinking, tool_start, tool_result,
                  response_text, response_audio, confirm_request, status
"""

import json
import uuid
import asyncio
import base64
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from core.events import EventBus, Event, EventType
from core.dependencies import get_container
from agent.schemas import ConversationContext

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("ws_connected", client_id=client_id)

    def disconnect(self, client_id: str) -> None:
        self.active_connections.pop(client_id, None)
        logger.info("ws_disconnected", client_id=client_id)

    async def send(self, client_id: str, message: dict) -> None:
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error("ws_send_error", client_id=client_id, error=str(e))


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket handler for a single client connection."""
    client_id = str(uuid.uuid4())
    container = get_container()
    event_bus = container.event_bus()
    agent = container.agent_brain()
    stream_mgr = container.stream_manager()

    # Create conversation context
    conversation_id = str(uuid.uuid4())
    context = ConversationContext(conversation_id=conversation_id)

    await manager.connect(websocket, client_id)

    # Subscribe to all events and forward to this client
    async def forward_event(event: Event):
        if event.conversation_id == conversation_id or event.conversation_id is None or event.conversation_id == "telegram_remote":
            if event.type == EventType.SYSTEM_NOTIFICATION:
                text = event.data.get("text", "")
                
                # IMPORTANT: Inject the notification into the AI's memory context
                # so if the user replies "yes", the AI knows what they are agreeing to!
                # Format it as a clear actionable context block.
                if text and context:
                    wa_ctx = event.data.get("whatsapp_reply_context", {})
                    full_body = wa_ctx.get("body", "")
                    wa_name = wa_ctx.get("name", "Unknown")
                    wa_number = wa_ctx.get("number", "")
                    extra = ""
                    if full_body:
                        extra = f"\n\n[FULL WHATSAPP MESSAGE FROM {wa_name}]: {full_body}"
                    if wa_number:
                        extra += f"\n[RECIPIENT PHONE NUMBER]: {wa_number}"
                    context.messages.append({
                        "role": "assistant",
                        "content": (
                            f"{text}{extra}\n\n"
                            "[SYSTEM CONTEXT — CRITICAL]: The above is a WhatsApp notification I just showed the user. "
                            "If they reply with 'yes', 'ok', 'sure', 'handle it', 'you handle it', 'take care of it', 'reply to them', or similar — "
                            "I MUST use the `whatsapp` tool with action='send_message' and the phone number above to reply to THIS message IMMEDIATELY. "
                            "I must auto-compose a natural, contextual response. I must NOT ask the user what to say. I must NOT just confirm — I must SEND the reply. "
                            "If they also said something like 'handle [Name]' or 'take care of [Name]'s chat', I must ALSO use the `persona` tool to add them to delegation. "
                            "But the FIRST priority is always: reply to the current message NOW using the whatsapp tool."
                        ),
                    })
                
                if text:
                    async def _speak_notification():
                        try:
                            # Notify UI we are speaking
                            await manager.send(client_id, {"type": "status", "data": {"status": "speaking"}})
                            
                            # Synthesize and stream audio chunks
                            async for audio_msg in stream_mgr.stream_tts_response(text, conversation_id):
                                await manager.send(client_id, audio_msg)
                                
                            # Signal audio stream complete
                            await manager.send(client_id, {"type": "audio_done", "data": {}})
                        except Exception as e:
                            logger.error("system_notification_tts_error", error=str(e))

                    # Run TTS in a background task so it doesn't block event forwarding
                    asyncio.create_task(_speak_notification())

            await manager.send(
                client_id,
                {"type": event.type.value, "data": event.data, "timestamp": event.timestamp},
            )

    event_bus.subscribe_all(forward_event)

    # Send initial status
    await manager.send(client_id, {
        "type": "status",
        "data": {
            "status": "connected",
            "conversation_id": conversation_id,
            "tools": container.tool_registry().list_tools(),
        },
    })

    # Audio accumulation buffer for STT
    audio_buffer = b""
    processing_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")
            data = msg.get("data", {})

            if msg_type == "text_input":
                # Text input from user
                text = data.get("text", "").strip()
                if not text:
                    continue

                # Cancel any ongoing processing
                if processing_task and not processing_task.done():
                    agent.interrupt()
                    stream_mgr.interrupt_tts()
                    processing_task.cancel()

                # Process through agent
                processing_task = asyncio.create_task(
                    _process_agent_response(
                        agent, stream_mgr, context, text,
                        client_id, conversation_id
                    )
                )

            elif msg_type == "audio_file":
                # Full audio recording received
                audio_b64 = data.get("audio", "")
                if audio_b64:
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        
                        transcript = await stream_mgr.process_audio_input(
                            audio_bytes, conversation_id
                        )

                        if transcript:
                            # Send the full transcript to client
                            await manager.send(client_id, {
                                "type": "transcript",
                                "data": {"text": transcript, "final": True},
                            })

                            # Cancel any ongoing processing
                            if processing_task and not processing_task.done():
                                agent.interrupt()
                                stream_mgr.interrupt_tts()
                                processing_task.cancel()

                            # Process full utterance through agent
                            processing_task = asyncio.create_task(
                                _process_agent_response(
                                    agent, stream_mgr, context, transcript,
                                    client_id, conversation_id
                                )
                            )
                        else:
                            # STT returned empty — no speech detected.
                            # Send response_done so the frontend resets state
                            logger.info("stt_empty_transcript", audio_size=len(audio_bytes))
                            await manager.send(client_id, {
                                "type": "response_done",
                                "data": {},
                            })
                    except Exception as e:
                        logger.error("audio_processing_error", error=str(e))
                        await manager.send(client_id, {
                            "type": "error",
                            "data": {"message": f"Audio processing failed: {str(e)}"}
                        })
                        await manager.send(client_id, {
                            "type": "response_done",
                            "data": {},
                        })

            elif msg_type == "interrupt":
                # User wants to interrupt current response
                agent.interrupt()
                stream_mgr.interrupt_tts()
                if processing_task and not processing_task.done():
                    processing_task.cancel()
                audio_buffer = b""

            elif msg_type == "confirm_action":
                # User confirms/denies a dangerous tool action
                await event_bus.emit(
                    Event(
                        type=EventType.CONFIRM_RESPONSE,
                        data=data,
                        conversation_id=conversation_id,
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("ws_error", client_id=client_id, error=str(e))
    finally:
        event_bus.unsubscribe_all(forward_event)
        manager.disconnect(client_id)
        if processing_task and not processing_task.done():
            processing_task.cancel()


async def _process_agent_response(
    agent, stream_mgr, context, text, client_id, conversation_id
) -> None:
    """Process user input through agent and stream response + TTS.

    NOTE: Events from agent.process() are emitted via EventBus, which the
    forward_event subscriber already sends to the client. We do NOT send
    them again here — we only consume the generator to accumulate text
    for TTS synthesis.

    A 120-second timeout prevents the UI from getting stuck forever.
    """
    full_response = ""
    got_response_done = False

    try:
        async with asyncio.timeout(120):  # 2 minute hard timeout
            async for event in agent.process(text, context):
                event_type = event.get("type", "")

                # Forward ALL generator events to the client.
                # The generator yields: thinking, response_text, tool_start,
                # tool_result, confirm_request, and response_done.
                # These are NOT emitted via EventBus, so we must send them here.
                await manager.send(client_id, {"type": event_type, "data": event})

                # Accumulate response text for TTS
                if event_type == "response_text":
                    full_response += event.get("text", "")

                elif event_type == "response_done":
                    got_response_done = True
                    # Stream TTS for the full response
                    if full_response.strip():
                        async for audio_msg in stream_mgr.stream_tts_response(
                            full_response, conversation_id
                        ):
                            await manager.send(client_id, audio_msg)

                        # Signal audio stream complete
                        await manager.send(client_id, {
                            "type": "audio_done",
                            "data": {},
                        })

    except asyncio.CancelledError:
        logger.info("agent_processing_cancelled")
    except TimeoutError:
        logger.error("agent_processing_timeout", elapsed="120s")
        await manager.send(client_id, {
            "type": "error",
            "data": {"message": "Processing timed out after 120 seconds"},
        })
    except Exception as e:
        logger.error("agent_processing_error", error=str(e))
        await manager.send(client_id, {
            "type": "error",
            "data": {"message": str(e)},
        })
    finally:
        # Safety net: if we never got response_done, send it now so the UI resets
        if not got_response_done:
            await manager.send(client_id, {
                "type": "response_done",
                "data": {},
            })

