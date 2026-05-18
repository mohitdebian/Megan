"""
Stream Manager — coordinates STT and TTS audio streams.
Handles interruption: if user speaks while TTS is playing, cancel TTS.
"""

import asyncio
import re
import structlog
from typing import AsyncGenerator

from audio.tts_service import TTSService
from audio.stt_service import STTService
from audio.audio_player import create_audio_message
from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


def _clean_text_for_speech(text: str) -> str:
    """
    Strip technical noise that makes speech robotic and hard to listen to.
    Applied before TTS synthesis.
    """
    if not text:
        return text

    # Remove version/build numbers like "2.2.17-1778044319" or "v1.2.3-build456"
    text = re.sub(r"\(?\d+\.\d+\.\d+[-–—]\d+\)?", "", text)
    text = re.sub(r"\(?v?\d+\.\d+\.\d+[-–—]?build\d+\)?", "", text)

    # Remove raw UTC timestamps like "14:19 15 UTC" or "2026-05-11 14:19:15 UTC"
    text = re.sub(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2}\s*(?:UTC|GMT)", "", text)
    text = re.sub(r"\d{1,2}:\d{2}\s+\d{1,2}\s*(?:UTC|GMT)", "", text)

    # Remove standalone UUID-like long numbers (e.g., 1778044319 in context)
    text = re.sub(r"\(\d{8,}\)", "", text)

    # Clean up double spaces and stray punctuation left behind
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text)
    text = re.sub(r"([({])\s+", r"\1", text)

    # Remove empty parenthesis or trailing punctuation clusters
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = re.sub(r"[.,;:!?]{2,}", ".", text)

    # Trim and ensure clean ending
    text = text.strip()
    if text.endswith((",", ":", ";")):
        text = text[:-1].strip()

    return text


class StreamManager:
    """
    Coordinates the full audio pipeline.

    Handles:
    - STT: audio chunks → transcribed text
    - TTS: response text → audio chunks
    - Interruption: cancel TTS if user starts speaking
    """

    def __init__(
        self, tts: TTSService, stt: STTService, event_bus: EventBus
    ) -> None:
        self.tts = tts
        self.stt = stt
        self.event_bus = event_bus
        self._tts_interrupt = asyncio.Event()
        self._is_speaking = False

    async def process_audio_input(self, audio_bytes: bytes, conversation_id: str) -> str | None:
        """
        Process incoming audio from the microphone.
        Returns transcribed text or None.
        """
        # If Megan is speaking and user starts talking, interrupt
        if self._is_speaking:
            self._tts_interrupt.set()
            self._is_speaking = False
            await self.event_bus.emit(
                Event(
                    type=EventType.STATUS,
                    data={"status": "interrupted"},
                    conversation_id=conversation_id,
                )
            )

        text = await self.stt.transcribe(audio_bytes)

        if text:
            # Emit partial transcript
            await self.event_bus.emit(
                Event(
                    type=EventType.TRANSCRIPT_FINAL,
                    data={"text": text},
                    conversation_id=conversation_id,
                )
            )

        return text if text else None

    async def stream_tts_response(
        self, text: str, conversation_id: str
    ) -> AsyncGenerator[dict, None]:
        """
        Convert text to speech and yield audio chunks.
        Can be interrupted if user starts speaking.
        """
        text = _clean_text_for_speech(text)
        if not text.strip():
            logger.warning("tts_empty_after_cleanup", conversation_id=conversation_id)
            return

        self._tts_interrupt.clear()
        self._is_speaking = True

        try:
            async for audio_chunk in self.tts.synthesize_sentences(text):
                if self._tts_interrupt.is_set():
                    logger.info("tts_interrupted")
                    break

                msg = create_audio_message(audio_chunk)
                await self.event_bus.emit(
                    Event(
                        type=EventType.AUDIO_CHUNK,
                        data=msg["data"],
                        conversation_id=conversation_id,
                    )
                )
                yield msg

        finally:
            self._is_speaking = False

    def interrupt_tts(self) -> None:
        """Interrupt ongoing TTS playback."""
        self._tts_interrupt.set()
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
