"""
Delegate Tool — Megan's "CEO" interface for spawning sub-agents.

When Megan determines a task requires deep research and a written report,
she uses this tool to orchestrate the Researcher and Writer agents
in the background, delivering the final product via TTS notification.
"""

import asyncio
import uuid
import structlog

from tools.base import BaseTool, ToolResult
from agent.swarm.researcher import ResearcherAgent
from agent.swarm.writer import WriterAgent
from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


class DelegateTaskTool(BaseTool):
    """
    Delegate a complex task to the multi-agent swarm.
    Spawns a Researcher agent to gather data, then a Writer agent
    to draft a polished report. Runs in the background.
    """

    name = "delegate_task"
    description = (
        "Delegate a complex research-and-report task to Megan's sub-agent swarm. "
        "Use this when the user asks for a detailed report, deep research, or analysis "
        "that would benefit from multiple specialized agents working together. "
        "The Researcher agent will search the web for data, and the Writer agent "
        "will draft a polished markdown report saved to ~/Documents/. "
        "This runs in the background and the user will be notified when done."
    )
    parameters = {
        "topic": {
            "type": "string",
            "description": "The research topic or question to investigate and write about.",
            "required": True,
        },
        "depth": {
            "type": "integer",
            "description": "Number of search queries to make (1-5). Default 3.",
        },
    }
    dangerous = False

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    async def execute(self, **kwargs) -> ToolResult:
        topic = kwargs.get("topic", "")
        depth = int(kwargs.get("depth", 3))

        if not topic:
            return ToolResult(success=False, output="Please provide a research topic.")

        # Spawn the swarm pipeline in the background
        asyncio.create_task(self._run_swarm(topic, depth))

        return ToolResult(
            success=True,
            output=(
                f"🧠 Swarm deployed! I've dispatched the Researcher and Writer agents "
                f"to work on: '{topic}'. I'll notify you when the report is ready. "
                f"This will run in the background."
            ),
        )

    async def _run_swarm(self, topic: str, depth: int):
        """Background pipeline: Research → Write → Notify."""
        try:
            logger.info("swarm_started", topic=topic)

            # Phase 1: Research
            researcher = ResearcherAgent()
            research_notes = await researcher.research(topic, depth=depth)

            if not research_notes or "No research results" in research_notes:
                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={
                            "message": f"Sir, my research agents couldn't find enough data on '{topic}'. You may want to try a more specific query."
                        },
                        conversation_id=str(uuid.uuid4()),
                    )
                )
                return

            # Phase 2: Write
            writer = WriterAgent()
            result = await writer.write(topic, research_notes)

            # Phase 3: Notify
            if result["success"]:
                message = (
                    f"Sir, the research report on '{topic}' is complete. "
                    f"{result['summary']} "
                    f"I've saved it to {result['file_path']}."
                )
            else:
                message = f"Sir, the research on '{topic}' is done, but the writer agent had trouble drafting the report. {result['summary']}"

            await self.event_bus.emit(
                Event(
                    type=EventType.SYSTEM_NOTIFICATION,
                    data={"message": message},
                    conversation_id=str(uuid.uuid4()),
                )
            )

            logger.info("swarm_complete", topic=topic, success=result["success"])

        except Exception as e:
            logger.error("swarm_error", topic=topic, error=str(e))
            await self.event_bus.emit(
                Event(
                    type=EventType.SYSTEM_NOTIFICATION,
                    data={
                        "message": f"Sir, the swarm agents encountered an error while researching '{topic}': {str(e)[:100]}"
                    },
                    conversation_id=str(uuid.uuid4()),
                )
            )
