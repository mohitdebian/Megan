"""
BaseTool — Abstract base class for all Megan tools.

Every tool implements this interface. Claude sees tool schemas via to_claude_schema().
The registry dispatches calls to the right tool's execute() method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result returned from tool execution."""

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_content(self) -> str:
        """Format result for Claude context injection."""
        if self.success:
            return self.output
        return f"Error: {self.error}\n{self.output}" if self.output else f"Error: {self.error}"


class BaseTool(ABC):
    """
    Abstract base for all tools.

    Subclasses must define:
        - name: unique tool identifier
        - description: what the tool does (Claude reads this)
        - parameters: JSON Schema for the tool's input
        - execute(**params): the actual implementation

    Optional:
        - dangerous: if True, requires user confirmation before execution
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    dangerous: bool = False

    @abstractmethod
    async def execute(self, **params) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    def to_claude_schema(self) -> dict:
        """Convert to Claude API tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": [
                    k
                    for k, v in self.parameters.items()
                    if v.get("required", False)
                ],
            },
        }
