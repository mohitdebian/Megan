"""
Scene Tool

Allows Megan to trigger multi-step automations and environmental scenes.
"""

import structlog
from typing import Any
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class SceneTool(BaseTool):
    name = "execute_scene"
    description = (
        "Execute a smart home or environment scene. Use this when the user asks "
        "to enter a specific mode (like 'movie mode', 'focus mode', 'gaming mode', or 'normal mode'). "
        "This will automatically orchestrate UI changes, lights, and sounds."
    )
    parameters = {
        "scene_name": {
            "type": "string",
            "description": "The name of the scene to execute (e.g., 'movie_mode', 'focus_mode', 'normal_mode')",
            "required": True,
        }
    }
    dangerous = False

    def __init__(self, scene_manager) -> None:
        self.scene_manager = scene_manager

    async def execute(self, scene_name: str, **_) -> ToolResult:
        try:
            logger.info("scene_tool_executing", scene=scene_name)
            result = await self.scene_manager.execute_scene(scene_name)
            return ToolResult(success=True, output=result)
        except ValueError as e:
            return ToolResult(success=False, output=str(e))
        except Exception as e:
            logger.error("scene_tool_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute scene: {str(e)}",
            )
