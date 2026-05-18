import asyncio
from config import get_settings
from audio.stt_service import STTService

async def main():
    settings = get_settings()
    stt = STTService(settings)
    print("Loading model...")
    stt._ensure_model()
    print("Model loaded successfully.")

if __name__ == "__main__":
    asyncio.run(main())
