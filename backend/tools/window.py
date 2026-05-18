"""
Window Tool — spawn or close dynamic windows on the desktop UI.
"""

from tools.base import BaseTool, ToolResult

class WindowTool(BaseTool):
    name = "window_manager"
    description = (
        "Manage the user's autonomous Desktop Interface UI by spawning or closing dynamic windows. "
        "Use this tool when the user asks to see information visually (like news, weather, videos, or articles). "
        "Available actions: spawn_window, close_window, close_all_windows. "
        "You can spawn 1-4 windows per command. Use 'position' to layout multiple windows gracefully."
    )
    
    parameters = {
        "action": {
            "type": "string",
            "enum": ["spawn_window", "close_window", "close_all_windows"],
            "description": "Action to perform.",
            "required": True,
        },
        "type": {
            "type": "string",
            "enum": ["news", "youtube", "weather", "article", "chat", "custom"],
            "description": "The type of window. Required for spawn_window.",
            "required": False,
        },
        "title": {
            "type": "string",
            "description": "Title of the window. Required for spawn_window and close_window.",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search query or context for the window.",
            "required": False,
        },
        "content": {
            "type": "string",
            "description": "Raw text or HTML if type is chat or custom.",
            "required": False,
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True
            },
            "description": "Array of structured data for the window (e.g. news headlines or youtube videos).",
            "required": False,
        },
        "position": {
            "type": "string",
            "enum": ["left", "right", "center", "top-right", "bottom-left", "auto"],
            "description": "Desktop positioning. Default is auto.",
            "required": False,
        }
    }
    dangerous = False

    def __init__(self) -> None:
        pass

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        
        if action == "spawn_window":
            return ToolResult(
                success=True,
                output=f"Spawned {kwargs.get('type')} window titled '{kwargs.get('title')}' at position {kwargs.get('position', 'auto')}."
            )
        elif action == "close_window":
            return ToolResult(
                success=True,
                output=f"Closed window titled '{kwargs.get('title')}'."
            )
        elif action == "close_all_windows":
            return ToolResult(
                success=True,
                output="Closed all open windows on the desktop."
            )
            
        return ToolResult(success=False, output="", error=f"Invalid action: {action}")
