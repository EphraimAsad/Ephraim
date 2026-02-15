"""
Ephraim Tools Package

Contains all tool implementations for the agent.
Tools are automatically registered when imported.
"""

from .base import (
    BaseTool,
    ToolResult,
    ToolParam,
    ToolCategory,
    ToolRegistry,
    tool_registry,
    register_tool,
)

# Import all tools to register them
from .read_file import ReadFileTool
from .list_directory import ListDirectoryTool
from .apply_patch import ApplyPatchTool, preview_patch
from .run_command import RunCommandTool, run_command_simple
from .ask_user import AskUserTool
from .final_answer import FinalAnswerTool, mark_task_complete
from .git_tools import (
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitAddTool,
    git_status,
    git_diff,
    git_commit,
    git_add,
)
from .ci_tools import (
    CheckCIStatusTool,
    GetCILogsTool,
    CheckCIResultTool,
    check_ci_status,
    get_ci_logs,
    check_ci_result,
)

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "ToolParam",
    "ToolCategory",
    "ToolRegistry",
    "tool_registry",
    "register_tool",
    # Tool classes
    "ReadFileTool",
    "ListDirectoryTool",
    "ApplyPatchTool",
    "RunCommandTool",
    "AskUserTool",
    "FinalAnswerTool",
    "GitStatusTool",
    "GitDiffTool",
    "GitCommitTool",
    "GitAddTool",
    "CheckCIStatusTool",
    "GetCILogsTool",
    "CheckCIResultTool",
    # Utility functions
    "preview_patch",
    "run_command_simple",
    "mark_task_complete",
    "git_status",
    "git_diff",
    "git_commit",
    "git_add",
    "check_ci_status",
    "get_ci_logs",
    "check_ci_result",
]
