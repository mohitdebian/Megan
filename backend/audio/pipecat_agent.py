"""
Pipecat Agent Service for MEGAN.
Wraps the LangGraph AgentBrain in a Pipecat FrameProcessor to stream natively
within the Pipecat low-latency audio pipeline.
"""

import asyncio
import structlog
from typing import AsyncGenerator

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
)

from agent.brain import AgentBrain
from agent.schemas import ConversationContext

logger = structlog.get_logger(__name__)


class MeganAgentService(FrameProcessor):
    """
    A custom Pipecat processor that listens for TranscriptionFrames from STT,
    passes the text to the LangGraph AgentBrain, and yields TextFrames (for TTS)
    and custom UI events back down the pipeline.
    """

    def __init__(self, brain: AgentBrain, context: ConversationContext):
        super().__init__()
        self.brain = brain
        self.context = context
        self._processing_task = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frames (e.g., transcriptions from the user)."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if not text:
                return
                
            logger.info("pipecat_agent_received_transcription", text=text)
            
            # Start the reasoning pipeline
            if self._processing_task and not self._processing_task.done():
                self.brain.interrupt()
                await self._processing_task
                
            self._processing_task = asyncio.create_task(self._run_brain(text))

    async def _run_brain(self, text: str):
        """Run the AgentBrain and push TextFrames for TTS."""
        try:
            await self.push_frame(LLMFullResponseStartFrame())
            
            # AgentBrain returns an async generator yielding dicts:
            # {"type": "response_text", "text": "..."}
            # {"type": "thinking", "text": "..."}
            
            async for chunk in self.brain.process(text, self.context):
                chunk_type = chunk.get("type")
                
                if chunk_type == "response_text":
                    await self.push_frame(TextFrame(chunk["text"]))
                    
                # We could potentially push Custom UI frames here if Pipecat supported
                # arbitrary JSON out to the websocket, but AgentBrain already emits
                # these to the global EventBus! So the frontend gets them via a 
                # parallel side-channel WebSocket or the same transport.
                
            await self.push_frame(LLMFullResponseEndFrame())
            
        except Exception as e:
            logger.error("pipecat_agent_error", error=str(e))
        finally:
            self._processing_task = None
