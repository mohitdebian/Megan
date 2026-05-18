import asyncio
import io
from config import get_settings
from audio.stt_service import STTService

async def main():
    settings = get_settings()
    stt = STTService(settings)
    stt._ensure_model()
    
    # Let's create a minimal valid webm file
    # We can just write a short python script to download a tiny webm to test, or just use a wav
    pass

if __name__ == "__main__":
    asyncio.run(main())
