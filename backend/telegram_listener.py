import asyncio
import httpx
import structlog
from core.events import Event, EventType

logger = structlog.get_logger(__name__)


async def start_telegram_listener(container):
    """
    Long-polling loop that listens for incoming Telegram messages
    and processes them via the AgentBrain.
    """
    settings = container.settings
    bot_token = settings.telegram.bot_token
    auth_chat_id = str(settings.telegram.chat_id)

    if not bot_token or not auth_chat_id:
        logger.warning("telegram_listener_disabled", reason="Missing bot_token or chat_id in config")
        return

    offset = 0
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    logger.info("telegram_listener_started")

    async with httpx.AsyncClient(timeout=70.0) as client:
        while True:
            try:
                # Long polling: wait up to 60 seconds for a new message
                payload = {"offset": offset, "timeout": 60, "allowed_updates": ["message"]}
                resp = await client.post(url, json=payload)
                
                if resp.status_code != 200:
                    logger.error("telegram_polling_error", status=resp.status_code, body=resp.text)
                    await asyncio.sleep(5)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    logger.error("telegram_polling_failed", data=data)
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    update_id = update.get("update_id")
                    offset = update_id + 1  # Acknowledge up to this update

                    message = update.get("message")
                    if not message:
                        continue

                    chat_id = str(message.get("chat", {}).get("id", ""))
                    text = message.get("text", "").strip()

                    if not text:
                        continue

                    if chat_id != auth_chat_id:
                        logger.warning("telegram_unauthorized_access", chat_id=chat_id, text=text)
                        continue

                    # Authorized message received! Handle it in the background
                    logger.info("telegram_message_received", text=text)
                    asyncio.create_task(handle_telegram_message(container, text, chat_id))

            except asyncio.CancelledError:
                logger.info("telegram_listener_stopped")
                break
            except httpx.ReadTimeout:
                # Expected when timeout=60 is reached and no messages arrive
                continue
            except Exception as e:
                logger.error("telegram_listener_exception", error=str(e))
                await asyncio.sleep(5)


async def handle_telegram_message(container, text: str, chat_id: str):
    """Passes the Telegram message to a fresh AgentBrain instance and sends the reply back."""
    
    agent_brain = container.new_agent_brain()
    
    from agent.schemas import ConversationContext
    context = ConversationContext(conversation_id="telegram_remote", is_background=False)
    
    # Prepend context instruction
    instruction = (
        "You are operating as a Telegram Remote Control. The user just sent you a message via Telegram from their phone. "
        "Execute whatever task they requested. When you are finished, summarize your findings or actions clearly. "
        "Your final output will be sent back to the user via Telegram automatically."
    )
    context.messages.append({"role": "user", "content": instruction})

    final_response = ""
    try:
        # Emit initial user message so it shows up in transcript
        from core.events import Event, EventType
        await container.event_bus().emit(
            Event(
                type=EventType.SYSTEM_NOTIFICATION,
                data={"text": f"Incoming Telegram Command: {text}"},
                conversation_id="telegram_remote"
            )
        )

        # 1. Process the task via the agent
        async for event in agent_brain.process(text, context):
            event_type = event.get("type", "")
            if event_type == "response_text":
                final_response += event.get("text", "")
                
            # Forward the event to the EventBus so the Desktop UI can render it live
            try:
                await container.event_bus().emit(
                    Event(
                        type=EventType(event_type),
                        data=event,
                        conversation_id="telegram_remote"
                    )
                )
            except ValueError:
                # Ignore unknown event types
                pass
                
        # 2. Send the final response back to Telegram
        if final_response:
            telegram_tool = container.tool_registry().get_tool("telegram")
            if telegram_tool:
                await telegram_tool.execute(action="send_message", message=final_response.strip())
                
    except Exception as e:
        logger.error("telegram_remote_handling_error", error=str(e))
        telegram_tool = container.tool_registry().get_tool("telegram")
        if telegram_tool:
            await telegram_tool.execute(action="send_message", message=f"❌ Error executing task: {str(e)}")
