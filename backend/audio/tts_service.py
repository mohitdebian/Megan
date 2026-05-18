"""
TTS Service — Text-to-Speech using NVIDIA Magpie TTS Multilingual.

Streams audio chunks via NVIDIA NIM API. No temp files — all in-memory.
Falls back to edge-tts if NVIDIA key is not configured.
"""

import io
import httpx
import struct
import asyncio
import structlog
from typing import AsyncGenerator

from config import Settings

logger = structlog.get_logger(__name__)


class TTSService:
    """
    Text-to-Speech service using NVIDIA Magpie TTS Multilingual.

    Streams PCM audio chunks for realtime playback.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = settings.tts.api_key
        self._url = settings.tts.url
        self._voice = settings.tts.voice
        self._sample_rate = settings.tts.sample_rate
        self._use_edge_tts = not self._api_key or self._api_key == "your_nvidia_api_key_here"

        self._el_api_key = settings.elevenlabs.api_key
        self._el_voice_id = settings.elevenlabs.voice_id
        self._el_model_id = settings.elevenlabs.model_id
        self._el_output_format = settings.elevenlabs.output_format
        self._use_elevenlabs = bool(self._el_api_key and self._el_api_key != "your_api_key_here")

        if self._use_elevenlabs:
            logger.info("tts_initialized", provider="elevenlabs", voice=self._el_voice_id)
        elif self._use_edge_tts:
            logger.warning("tts_using_edge_fallback", reason="No API keys configured")
        else:
            logger.info("tts_initialized", provider="nvidia_magpie", voice=self._voice)

    # Speech style presets for ElevenLabs (stability, similarity_boost)
    STYLE_PRESETS = {
        "calm": {"stability": 0.85, "similarity_boost": 0.6},
        "excited": {"stability": 0.3, "similarity_boost": 0.85},
        "serious": {"stability": 0.9, "similarity_boost": 0.5},
        "warm": {"stability": 0.6, "similarity_boost": 0.75},
        "default": {"stability": 0.5, "similarity_boost": 0.75},
    }

    # Edge-TTS voice mapping per style
    EDGE_VOICES = {
        "calm": "en-US-AriaNeural",
        "excited": "en-US-JennyNeural",
        "serious": "en-US-GuyNeural",
        "warm": "en-US-AriaNeural",
        "default": "en-US-AriaNeural",
    }

    async def synthesize(self, text: str, style: str = "default") -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to audio, yielding PCM chunks.
        
        Args:
            text: Text to synthesize
            style: Speech style ('calm', 'excited', 'serious', 'warm', 'default')
        """
        if not text.strip():
            return

        # Extract style tag from text if present (e.g., "[style:calm] Hello")
        import re
        style_match = re.match(r'\[style:(\w+)\]\s*', text)
        if style_match:
            style = style_match.group(1)
            text = text[style_match.end():]

        success = False
        
        # 1. Try ElevenLabs
        if self._use_elevenlabs:
            async for chunk in self._elevenlabs_synthesize(text, style):
                success = True
                yield chunk
            if success:
                return
            logger.warning("elevenlabs_tts_failed_falling_back_to_edge")
            
        # 2. Try NVIDIA Magpie
        elif not self._use_edge_tts:
            async for chunk in self._nvidia_synthesize(text):
                success = True
                yield chunk
            if success:
                return
            logger.warning("nvidia_tts_failed_falling_back_to_edge")

        # 3. Fallback to Edge-TTS
        async for chunk in self._edge_tts_synthesize(text, style):
            yield chunk

    async def _elevenlabs_synthesize(self, text: str, style: str = "default") -> AsyncGenerator[bytes, None]:
        """Stream TTS via the official ElevenLabs Python SDK with style controls."""
        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self._el_api_key)

            preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["default"])

            # Use the SDK's convert method with voice settings
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=self._el_voice_id,
                model_id=self._el_model_id,
                output_format=self._el_output_format,
                voice_settings={
                    "stability": preset["stability"],
                    "similarity_boost": preset["similarity_boost"],
                },
            )

            # The SDK returns an iterator; collect and yield
            buffer = b""
            for chunk in audio:
                buffer += chunk
            
            if buffer:
                yield buffer

        except Exception as e:
            logger.error("elevenlabs_tts_error", error=str(e))

    async def _nvidia_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream TTS via NVIDIA NIM Magpie API."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }
        payload = {
            "model": "nvidia/magpie-tts-multilingual",
            "input": text,
            "voice": self._voice,
            "response_format": "wav",
            "speed": 1.0,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST", self._url, json=payload, headers=headers
                ) as resp:
                    resp.raise_for_status()

                    buffer = b""
                    async for chunk in resp.aiter_bytes():
                        buffer += chunk
                        
                    if buffer:
                        yield buffer

        except httpx.HTTPStatusError as e:
            logger.error("nvidia_tts_error", status=e.response.status_code, detail=str(e))
        except Exception as e:
            logger.error("nvidia_tts_error", error=str(e))

    async def _edge_tts_synthesize(self, text: str, style: str = "default") -> AsyncGenerator[bytes, None]:
        """Fallback TTS using edge-tts (Microsoft Edge, free, no API key)."""
        try:
            import edge_tts

            voice = self.EDGE_VOICES.get(style, self.EDGE_VOICES["default"])
            communicate = edge_tts.Communicate(text, voice=voice)
            buffer = b""
            async for chunk_data in communicate.stream():
                if chunk_data["type"] == "audio":
                    buffer += chunk_data["data"]
            
            if buffer:
                yield buffer

        except ImportError:
            logger.error("edge_tts_not_installed", hint="pip install edge-tts")
            # Generate silence as last resort
            silence = b"\x00" * 4096
            yield silence
        except Exception as e:
            logger.error("edge_tts_error", error=str(e))

    async def synthesize_sentences(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Split text into sentences and synthesize each for lower latency.
        Yields audio chunks as soon as each sentence is ready.
        """
        import re

        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                async for chunk in self.synthesize(sentence):
                    yield chunk
