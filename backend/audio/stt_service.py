"""
STT Service — Speech-to-Text using faster-whisper.

Processes audio chunks from the microphone and returns transcriptions.
Runs on GPU (CUDA) for low latency.
"""

import io
import asyncio
import numpy as np
import structlog
from typing import AsyncGenerator

from config import Settings

logger = structlog.get_logger(__name__)


class STTService:
    """
    Speech-to-Text service using faster-whisper with GPU acceleration.

    Receives raw PCM audio bytes and returns transcribed text.
    """

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.audio.stt_model
        self._device = settings.audio.stt_device
        self._sample_rate = settings.audio.sample_rate
        self._model = None
        self._initialized = False

    def _ensure_model(self) -> None:
        """Lazy-load the whisper model (heavy, only load when needed)."""
        if self._initialized:
            return

        try:
            from faster_whisper import WhisperModel

            logger.info(
                "stt_loading_model",
                model=self._model_name,
                device=self._device,
            )
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type="float16" if self._device == "cuda" else "int8",
            )
            self._initialized = True
            logger.info("stt_model_loaded")

        except Exception as e:
            logger.error("stt_model_load_failed", error=str(e))
            # Fallback to CPU
            try:
                from faster_whisper import WhisperModel

                logger.info("stt_falling_back_to_cpu")
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8",
                )
                self._initialized = True
            except Exception as e2:
                logger.error("stt_cpu_fallback_failed", error=str(e2))

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM audio bytes (16-bit, 16kHz, mono) to text.

        Args:
            audio_bytes: Raw PCM audio data

        Returns:
            Transcribed text string
        """
        if not audio_bytes:
            return ""

        self._ensure_model()
        if not self._model:
            return ""

        # Wrap bytes in a file-like object so faster-whisper can decode the WebM/MP4 natively
        audio_file = io.BytesIO(audio_bytes)

        # Run transcription in thread pool (faster-whisper is sync)
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, self._transcribe_sync, audio_file
        )
        return text

    def _transcribe_sync(self, audio: io.BytesIO) -> str:
        """Synchronous transcription (runs in thread pool)."""
        # Note: faster_whisper handles its own VAD internally.
        try:
            segments, info = self._model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )
            
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            return " ".join(text_parts).strip()
            
        except Exception as e:
            error_str = str(e)
            if "libcublas" in error_str or "cublas" in error_str.lower() or "cuda" in error_str.lower():
                logger.warning("stt_cuda_inference_failed", error=error_str, action="falling_back_to_cpu")
                
                # Switch to CPU model dynamically and retry
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8",
                )
                self._device = "cpu"
                
                # Reset stream position to start for retry
                audio.seek(0)
                
                # Retry transcription
                segments, info = self._model.transcribe(
                    audio,
                    beam_size=5,
                    language="en",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=200,
                    ),
                )
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text.strip())
                return " ".join(text_parts).strip()
            
            # Re-raise if it's some other exception
            raise

    async def transcribe_stream(
        self, audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        """
        Streaming transcription — accumulate audio chunks and
        transcribe when enough audio is buffered.
        """
        buffer = b""
        # Buffer ~2 seconds of audio before transcribing
        chunk_size = self._sample_rate * 2 * 2  # 2 seconds * 2 bytes/sample

        async for chunk in audio_stream:
            buffer += chunk

            if len(buffer) >= chunk_size:
                text = await self.transcribe(buffer)
                if text:
                    yield text
                buffer = b""

        # Transcribe remaining audio
        if buffer:
            text = await self.transcribe(buffer)
            if text:
                yield text
