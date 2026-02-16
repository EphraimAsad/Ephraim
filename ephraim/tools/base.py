"""
Base Tool Class for Ephraim

All tools inherit from BaseTool and implement a consistent interface.
Tools must be testable independently without the LLM.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class ToolCategory(Enum):
    """Categories of tools for phase enforcement."""
    READ_ONLY = "read_only"      # Can run in any phase
    EXECUTION = "execution"      # Requires approval
    USER_INPUT = "user_input"    # User interaction
    GIT = "git"                  # Git operations
    CI = "ci"                    # CI/CD operations


@dataclass
class ToolResult:
    """
    Standardized result from tool execution.

    All tools return this structure for consistent handling.

    Enhanced fields for error recovery and context passing:
    - detailed_summary: Full description (not truncated)
    - intermediate_steps: Progress during execution
    - suggestions: What to do next on failure
    - context_for_next: Data to pass to next action
    - error_type: Classification for recovery strategy
    """
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    summary: str = ""

    # Enhanced fields for better LLM context
    detailed_summary: str = ""
    intermediate_steps: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    context_for_next: Dict[str, Any] = field(default_factory=dict)
    error_type: str = ""  # not_found, permission, validation, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "summary": self.summary,
            "detailed_summary": self.detailed_summary,
            "intermediate_steps": self.intermediate_steps,
            "suggestions": self.suggestions,
            "context_for_next": self.context_for_next,
            "error_type": self.error_type,
        }

    @classmethod
    def ok(
        cls,
        data: Dict[str, Any],
        summary: str = "",
        detailed_summary: str = "",
        suggestions: Optional[List[str]] = None,
        context_for_next: Optional[Dict[str, Any]] = None
    ) -> "ToolResult":
        """Create a successful result with optional enhanced fields."""
        return cls(
            success=True,
            data=data,
            summary=summary,
            detailed_summary=detailed_summary or summary,
            suggestions=suggestions or [],
            context_for_next=context_for_next or {}
        )

    @classmethod
    def fail(
        cls,
        error: str,
        data: Optional[Dict[str, Any]] = None,
        error_type: str = "",
        suggestions: Optional[List[str]] = None
    ) -> "ToolResult":
        """Create a failed result with optional recovery hints."""
        return cls(
            success=False,
            error=error,
            data=data or {},
            summary=f"Error: {error}",
            error_type=error_type,
            suggestions=suggestions or []
        )


@dataclass
class ToolParam:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "int", "bool", "list", "dict"
    description: str
    required: bool = True
    default: Any = None


class BaseTool(ABC):
    """
    Base class for all Ephraim tools.

    Tools must:
    - Be testable without the LLM
    - Return structured ToolResult
    - Validate parameters before execution
    - Handle errors gracefully
    """

    # Subclasses must define these
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.READ_ONLY
    parameters: List[ToolParam] = []

    def __init__(self):
        """Initialize the tool."""
        if not self.name:
            raise ValueError(f"Tool {self.__class__.__name__} must define 'name'")

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema for LLM context."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.parameters
            ],
        }

    def validate_params(self, **params) -> Optional[str]:
        """
        Validate parameters before execution.

        Returns None if valid, error message if invalid.
        """
        for param in self.parameters:
            if param.required and param.name not in params:
                return f"Missing required parameter: {param.name}"

            if param.name in params:
                value = params[param.name]

                # Skip type checking for None values on optional parameters
                if value is None and not param.required:
                    continue

                # Type checking
                if param.type == "string" and not isinstance(value, str):
                    return f"Parameter '{param.name}' must be a string"
                elif param.type == "int" and not isinstance(value, int):
                    return f"Parameter '{param.name}' must be an integer"
                elif param.type == "bool" and not isinstance(value, bool):
                    return f"Parameter '{param.name}' must be a boolean"
                elif param.type == "list" and not isinstance(value, list):
                    return f"Parameter '{param.name}' must be a list"
                elif param.type == "dict" and not isinstance(value, dict):
                    return f"Parameter '{param.name}' must be a dictionary"

        return None

    def __call__(self, **params) -> ToolResult:
        """
        Execute the tool with validation.

        This is the main entry point for tool execution.
        """
        # Validate parameters
        error = self.validate_params(**params)
        if error:
            return ToolResult.fail(error)

        # Apply defaults
        for param in self.parameters:
            if param.name not in params and param.default is not None:
                params[param.name] = param.default

        # Execute
        try:
            return self.execute(**params)
        except Exception as e:
            return ToolResult.fail(f"Execution error: {str(e)}")

    @abstractmethod
    def execute(self, **params) -> ToolResult:
        """
        Execute the tool logic.

        Must be implemented by subclasses.
        Returns ToolResult with structured data.
        """
        pass

    def requires_approval(self) -> bool:
        """Check if this tool requires user approval."""
        return self.category in (
            ToolCategory.EXECUTION,
            ToolCategory.GIT,
        )


class ToolRegistry:
    """
    Registry of available tools.

    Provides lookup and listing functionality.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """List tools by category."""
        return [t for t in self._tools.values() if t.category == category]

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools (for LLM context)."""
        return [tool.get_schema() for tool in self._tools.values()]


# Global tool registry instance
tool_registry = ToolRegistry()


def register_tool(tool_class: type) -> type:
    """Decorator to register a tool class."""
    instance = tool_class()
    tool_registry.register(instance)
    return tool_class
