"""
Tool Registry — central registry for all tools.

Claude gets schemas from here. The agent dispatches tool calls through here.
Adding a new tool = create a class + register it. That's it.
"""

import structlog
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """
    Registry of all available tools.

    Usage:
        registry = ToolRegistry()
        registry.register(TerminalTool())
        schemas = registry.get_all_schemas()       # → send to Claude
        result = await registry.execute("terminal", command="ls")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its name."""
        if tool.name in self._tools:
            logger.warning("tool_already_registered", tool=tool.name)
        self._tools[tool.name] = tool
        logger.debug("tool_registered", tool=tool.name)

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict]:
        """Get Claude-compatible schemas for all registered tools."""
        return [tool.to_claude_schema() for tool in self._tools.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def is_dangerous(self, name: str) -> bool:
        """Check if a tool requires user confirmation."""
        tool = self._tools.get(name)
        return tool.dangerous if tool else False

    async def execute(self, name: str, params: dict) -> ToolResult:
        """Execute a tool by name with given parameters."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}",
            )

        # Safety policy check
        from core.safety_policies import SafetyPolicyEngine, PolicyAction
        action, reason = SafetyPolicyEngine.check(name, params)
        
        if action == PolicyAction.BLOCK:
            logger.warning("tool_blocked_by_policy", tool=name, reason=reason)
            return ToolResult(
                success=False,
                output="",
                error=f"BLOCKED by safety policy: {reason}. This action is not permitted.",
            )
        elif action == PolicyAction.CONFIRM:
            # Mark the tool as requiring confirmation for this specific call
            tool.dangerous = True

        try:
            logger.info("tool_executing", tool=name, params=params)
            result = await tool.execute(**params)
            logger.info(
                "tool_completed",
                tool=name,
                success=result.success,
                output_length=len(result.output),
            )
            return result
        except Exception as e:
            logger.error("tool_error", tool=name, error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution failed: {str(e)}",
            )
