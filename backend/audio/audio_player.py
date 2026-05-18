"""
Audio Player — server-side audio format handling.
Actual playback happens on the frontend via Web Audio API.
This module handles format conversion and chunk packaging.
"""

import base64
import struct
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


def pcm_to_base64(pcm_bytes: bytes) -> str:
    """Encode PCM bytes as base64 for WebSocket transport."""
    return base64.b64encode(pcm_bytes).decode("ascii")


def base64_to_pcm(b64_string: str) -> bytes:
    """Decode base64 audio back to PCM bytes."""
    return base64.b64decode(b64_string)


def create_audio_message(
    audio_bytes: bytes, sample_rate: int = 24000, channels: int = 1
) -> dict[str, Any]:
    """Create a WebSocket message containing audio data."""
    return {
        "type": "response_audio",
        "data": {
            "audio": pcm_to_base64(audio_bytes),
            "sample_rate": sample_rate,
            "channels": channels,
            "format": "pcm_s16le",
        },
    }
