"""
Background Worker Tool — allows Megan to spawn background tasks.

This tool spawns a detached asyncio task that runs a fresh instance of AgentBrain.
When the background agent completes its execution, it emits a SYSTEM_NOTIFICATION event
to alert the user via TTS/UI.
"""

import asyncio
import structlog
from typing import Any

from tools.base import BaseTool, ToolResult
from core.events import Event, EventType

logger = structlog.get_logger(__name__)


import time
import uuid

# Global task tracker
_active_tasks: dict[str, dict[str, Any]] = {}


class BackgroundWorkerTool(BaseTool):
    name = "background_worker"
    description = (
        "Run a complex, time-consuming task autonomously in the background. "
        "Use this when the user asks to do something 'in the background', or when "
        "a task might take a very long time (e.g. searching the web extensively). "
        "The task will run invisibly and notify the user when complete."
    )
    parameters = {
        "task_description": {
            "type": "string",
            "description": "A highly detailed description of exactly what the background agent needs to do.",
            "required": True,
        }
    }
    dangerous = False

    def __init__(self, container: Any) -> None:
        self.container = container

    async def execute(self, **kwargs) -> ToolResult:
        task_description = kwargs.get("task_description")
        if not task_description:
            return ToolResult(success=False, output="", error="task_description is required")

        task_id = str(uuid.uuid4())[:8]
        _active_tasks[task_id] = {
            "description": task_description,
            "status": "running",
            "start_time": time.time(),
            "result": None,
            "error": None,
        }

        # Spawn the background task and detach it
        asyncio.create_task(self._run_background_agent(task_id, task_description))

        return ToolResult(
            success=True,
            output=f"Background task '{task_id}' successfully dispatched. It is now running invisibly. Tell the user it has started.",
        )

    async def _run_background_agent(self, task_id: str, task_description: str) -> None:
        logger.info("background_agent_started", task=task_description, task_id=task_id)
        
        # 1. Get a fresh brain instance so we don't clobber the main conversation state
        agent_brain = self.container.new_agent_brain()
        
        # 2. Setup a custom context for the background agent
        from agent.brain import ConversationContext
        
        context = ConversationContext(conversation_id=task_id, is_background=True)
        
        # Prepend the strict background instruction into the context messages
        instruction = (
            "You are a background worker agent. You have been spawned to complete the following task:\n\n"
            f"{task_description}\n\n"
            "Execute the task autonomously using your tools. You cannot ask the user questions because you are running in the background. "
            "When you are finished, summarize your findings or actions clearly. Your final output will be spoken aloud to the user."
        )
        context.messages.append({"role": "user", "content": instruction})
        
        try:
            # 3. Process the task (run the loop to completion)
            final_response = ""
            async for event in agent_brain.process("Please complete the task assigned to you above.", context):
                if event.get("type") == "response_text":
                    final_response += event.get("text", "")

            # 4. Notify the user that the task is complete
            notification_text = f"Sir, your background task is complete. {final_response.strip()}"
            
            _active_tasks[task_id]["status"] = "completed"
            _active_tasks[task_id]["result"] = final_response.strip()

            await self.container.event_bus().emit(
                Event(
                    type=EventType.SYSTEM_NOTIFICATION,
                    data={"text": notification_text},
                )
            )
            logger.info("background_agent_completed", task_id=task_id)

        except Exception as e:
            logger.error("background_agent_error", error=str(e), task_id=task_id)
            _active_tasks[task_id]["status"] = "failed"
            _active_tasks[task_id]["error"] = str(e)
            await self.container.event_bus().emit(
                Event(
                    type=EventType.SYSTEM_NOTIFICATION,
                    data={"text": f"Sir, the background task failed with an error: {str(e)}"},
                )
            )

class CheckBackgroundTasksTool(BaseTool):
    name = "check_background_tasks"
    description = (
        "Check the status of all background tasks. "
        "Use this tool when the user asks if a background task is done, or what tasks are running."
    )
    parameters = {}
    dangerous = False

    def __init__(self, container: Any) -> None:
        self.container = container

    async def execute(self, **kwargs) -> ToolResult:
        if not _active_tasks:
            return ToolResult(success=True, output="There are no active or recently completed background tasks.")

        lines = []
        for tid, data in _active_tasks.items():
            elapsed = round(time.time() - data["start_time"], 1)
            status = data["status"].upper()
            desc = data["description"][:100] + ("..." if len(data["description"]) > 100 else "")
            
            line = f"- Task ID: {tid} | Status: {status} | Elapsed: {elapsed}s | Desc: {desc}"
            if status == "COMPLETED":
                res = data["result"][:100] + ("..." if len(data["result"]) > 100 else "")
                line += f"\n  Result: {res}"
            elif status == "FAILED":
                line += f"\n  Error: {data['error']}"
            lines.append(line)

        return ToolResult(
            success=True,
            output="Background Tasks Status:\n" + "\n".join(lines),
        )
