"""
Scene Tool

Allows Megan to trigger, list, and manage environment scenes.
"""

import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class SceneTool(BaseTool):
    name = "execute_scene"
    description = (
        "Control smart home environment scenes. Use this when the user asks "
        "to enter a specific mode like 'movie mode', 'gaming mode', 'focus mode', "
        "'sleep mode', 'party mode', 'cyberpunk mode', 'presentation mode', "
        "'anime night mode', or 'normal mode' to deactivate. "
        "Actions: 'activate' (default), 'list', 'status'."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: 'activate' to start a scene, 'list' to show all scenes, 'status' to show current scene.",
        },
        "scene_name": {
            "type": "string",
            "description": "Name of the scene (e.g., 'movie_mode', 'focus_mode', 'normal_mode'). Required for 'activate'.",
        },
    }
    dangerous = False

    def __init__(self, scene_manager) -> None:
        self.scene_manager = scene_manager

    async def execute(self, action: str = "activate", scene_name: str = "", **_) -> ToolResult:
        try:
            if action == "list":
                scenes = self.scene_manager.list_scenes()
                out = "🎭 Available Scenes:\n"
                for s in scenes:
                    out += f"  {s['icon']} {s['display_name']} — {s['description']}\n"
                active = self.scene_manager.get_active_scene()
                if active:
                    out += f"\n🔵 Currently active: {active}"
                else:
                    out += f"\n⚪ No scene active (normal mode)"
                return ToolResult(success=True, output=out)

            elif action == "status":
                active = self.scene_manager.get_active_scene()
                if active:
                    return ToolResult(success=True, output=f"Currently active scene: {active}")
                else:
                    return ToolResult(success=True, output="No active scene. Running in normal mode.")

            elif action == "activate":
                if not scene_name:
                    return ToolResult(success=False, output="Please specify a scene_name to activate.")
                result = await self.scene_manager.execute_scene(scene_name)
                return ToolResult(success=True, output=result)

            else:
                return ToolResult(success=False, output=f"Unknown action: {action}. Use 'activate', 'list', or 'status'.")

        except ValueError as e:
            return ToolResult(success=False, output=str(e))
        except Exception as e:
            logger.error("scene_tool_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Scene execution failed: {str(e)}",
            )
