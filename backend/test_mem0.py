import os
import asyncio
from mem0 import Memory
from dotenv import load_dotenv

load_dotenv()

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": os.getenv("CLAUDE_MODEL", "gpt-3.5-turbo"),
            "api_key": os.getenv("CLAUDE_AUTH_TOKEN", "dummy"),
            "base_url": f"{os.getenv('CLAUDE_BASE_URL', 'http://localhost:8082/v1').rstrip('/')}",
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "megan_memories",
            "path": "./data/mem0_chroma",
        }
    }
}

try:
    m = Memory.from_config(config_dict=config)
    print("Memory instance created successfully.")
    
    # Try a simple add
    m.add("I am testing the new memory system. My name is Mohit.", user_id="mohit")
    print("Memory added.")
    
    res = m.search("What is my name?", user_id="mohit")
    print("Search results:", res)
except Exception as e:
    print("Error:", e)
