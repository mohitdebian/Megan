"""
Megan Backend — FastAPI Application Entry Point.

Initializes all services, mounts routes, and starts the server.
"""

import sys
import os
import asyncio
from contextlib import asynccontextmanager

# Add backend dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from config import get_settings
from core.logging import setup_logging
from core.dependencies import get_container
from api.routes import router as api_router
from api.websocket import websocket_endpoint


# Setup logging first
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup services."""
    logger.info("megan_starting")

    # Initialize all services
    container = get_container()
    await container.initialize()

    logger.info(
        "megan_ready",
        tools=container.tool_registry().list_tools(),
    )

    # Start Telegram Listener in background
    from telegram_listener import start_telegram_listener
    telegram_task = asyncio.create_task(start_telegram_listener(container))

    yield

    # Cleanup
    telegram_task.cancel()
    try:
        await telegram_task
    except asyncio.CancelledError:
        pass
        
    await container.shutdown()
    logger.info("megan_shutdown")


# Create FastAPI app
app = FastAPI(
    title="Megan",
    description="AI-Native Voice Assistant — Jarvis-style autonomous AI OS",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(api_router)

# Mount static directory for screencast HLS files
from fastapi.staticfiles import StaticFiles
from pathlib import Path
hls_dir = Path(settings.data_dir) / "screencast"
hls_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/screencast", StaticFiles(directory=str(hls_dir)), name="screencast")

# WebSocket
app.websocket("/ws")(websocket_endpoint)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
        log_level=settings.server.log_level,
    )
