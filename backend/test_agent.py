import asyncio
from config import get_settings
from core.dependencies import get_container
from agent.schemas import ConversationContext
from agent.brain import AgentBrain
import uuid

async def test_agent():
    container = get_container()
    await container.initialize()
    agent = container.agent_brain()
    
    context = ConversationContext(conversation_id=str(uuid.uuid4()))
    print("Testing agent process...")
    
    try:
        async for event in agent.process("hello", context):
            print(f"Event: {event}")
    except Exception as e:
        print(f"Error: {e}")
        
    await container.shutdown()

if __name__ == "__main__":
    asyncio.run(test_agent())
