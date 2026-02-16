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

# NEW: File creation and management tools
from .write_file import WriteFileTool, write_file
from .file_operations import (
    DeleteFileTool,
    MoveFileTool,
    CopyFileTool,
    delete_file,
    move_file,
    copy_file,
)
from .directory_tools import (
    CreateDirectoryTool,
    DeleteDirectoryTool,
    create_directory,
    delete_directory,
)
from .search_tools import (
    GlobSearchTool,
    GrepSearchTool,
    glob_search,
    grep_search,
)

# Git tools
from .git_tools import (
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitAddTool,
    GitPushTool,
    GitPullTool,
    GitBranchTool,
    GitCheckoutTool,
    GitMergeTool,
    GitStashTool,
    git_status,
    git_diff,
    git_commit,
    git_add,
    git_push,
    git_pull,
    git_branch,
    git_checkout,
    git_merge,
    git_stash,
)

# CI tools
from .ci_tools import (
    CheckCIStatusTool,
    GetCILogsTool,
    CheckCIResultTool,
    WaitForCITool,
    AnalyzeCIFailureTool,
    SuggestCIFixTool,
    TriggerWorkflowTool,
    PRStatusTool,
    check_ci_status,
    get_ci_logs,
    check_ci_result,
    wait_for_ci,
    analyze_ci_failure,
    suggest_ci_fix,
    trigger_workflow,
    pr_status,
)

# Web tools
from .web_tools import (
    WebFetchTool,
    WebSearchTool,
    web_fetch,
    web_search,
)

# Task management tools
from .task_tools import (
    TaskCreateTool,
    TaskUpdateTool,
    TaskGetTool,
    TaskListTool,
    task_create,
    task_update,
    task_list,
)

# Notebook tools
from .notebook_tools import (
    NotebookReadTool,
    NotebookEditTool,
    notebook_read,
    notebook_edit,
)

# Multimodal tools (images/PDFs)
from .multimodal_tools import (
    ReadImageTool,
    ReadPDFTool,
    read_image,
    read_pdf,
    get_multimodal_status,
)

# MCP tools
from .mcp_tools import (
    MCPConnectTool,
    MCPDisconnectTool,
    MCPListToolsTool,
    MCPCallTool,
    MCPStatusTool,
    mcp_connect,
    mcp_disconnect,
    mcp_list_tools,
    mcp_call,
    mcp_status,
)

# GitHub tools (NEW)
from .github_tools import (
    GHPRCreateTool,
    GHPRListTool,
    GHPRReviewTool,
    GHIssueCreateTool,
    GHIssueListTool,
    GHIssueCommentTool,
    gh_pr_create,
    gh_pr_list,
    gh_pr_review,
    gh_issue_create,
    gh_issue_list,
    gh_issue_comment,
)

# Test tools (NEW)
from .test_tools import (
    RunTestsTool,
    AnalyzeTestFailureTool,
    SuggestTestFixTool,
    CoverageReportTool,
    run_tests,
    analyze_test_failure,
    suggest_test_fix,
    coverage_report,
)

# Code analysis tools (NEW)
from .analysis_tools import (
    FindReferencesTool,
    FindDefinitionTool,
    AnalyzeImportsTool,
    DeadCodeCheckTool,
    find_references,
    find_definition,
    analyze_imports,
    dead_code_check,
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
    # Original tool classes
    "ReadFileTool",
    "ListDirectoryTool",
    "ApplyPatchTool",
    "RunCommandTool",
    "AskUserTool",
    "FinalAnswerTool",
    # File management tools
    "WriteFileTool",
    "DeleteFileTool",
    "MoveFileTool",
    "CopyFileTool",
    # Directory tools
    "CreateDirectoryTool",
    "DeleteDirectoryTool",
    # Search tools
    "GlobSearchTool",
    "GrepSearchTool",
    # Git tools (10 total)
    "GitStatusTool",
    "GitDiffTool",
    "GitCommitTool",
    "GitAddTool",
    "GitPushTool",
    "GitPullTool",
    "GitBranchTool",
    "GitCheckoutTool",
    "GitMergeTool",
    "GitStashTool",
    # CI tools (8 total)
    "CheckCIStatusTool",
    "GetCILogsTool",
    "CheckCIResultTool",
    "WaitForCITool",
    "AnalyzeCIFailureTool",
    "SuggestCIFixTool",
    "TriggerWorkflowTool",
    "PRStatusTool",
    # Web tools
    "WebFetchTool",
    "WebSearchTool",
    # Task tools
    "TaskCreateTool",
    "TaskUpdateTool",
    "TaskGetTool",
    "TaskListTool",
    # Notebook tools
    "NotebookReadTool",
    "NotebookEditTool",
    # Multimodal tools
    "ReadImageTool",
    "ReadPDFTool",
    # MCP tools
    "MCPConnectTool",
    "MCPDisconnectTool",
    "MCPListToolsTool",
    "MCPCallTool",
    "MCPStatusTool",
    # GitHub tools (6 total)
    "GHPRCreateTool",
    "GHPRListTool",
    "GHPRReviewTool",
    "GHIssueCreateTool",
    "GHIssueListTool",
    "GHIssueCommentTool",
    # Test tools (4 total)
    "RunTestsTool",
    "AnalyzeTestFailureTool",
    "SuggestTestFixTool",
    "CoverageReportTool",
    # Code analysis tools (4 total)
    "FindReferencesTool",
    "FindDefinitionTool",
    "AnalyzeImportsTool",
    "DeadCodeCheckTool",
    # Utility functions
    "preview_patch",
    "run_command_simple",
    "mark_task_complete",
    "write_file",
    "delete_file",
    "move_file",
    "copy_file",
    "create_directory",
    "delete_directory",
    "glob_search",
    "grep_search",
    "git_status",
    "git_diff",
    "git_commit",
    "git_add",
    "git_push",
    "git_pull",
    "git_branch",
    "git_checkout",
    "git_merge",
    "git_stash",
    "check_ci_status",
    "get_ci_logs",
    "check_ci_result",
    "wait_for_ci",
    "analyze_ci_failure",
    "suggest_ci_fix",
    "trigger_workflow",
    "pr_status",
    "web_fetch",
    "web_search",
    "task_create",
    "task_update",
    "task_list",
    "notebook_read",
    "notebook_edit",
    "read_image",
    "read_pdf",
    "get_multimodal_status",
    "mcp_connect",
    "mcp_disconnect",
    "mcp_list_tools",
    "mcp_call",
    "mcp_status",
    "gh_pr_create",
    "gh_pr_list",
    "gh_pr_review",
    "gh_issue_create",
    "gh_issue_list",
    "gh_issue_comment",
    "run_tests",
    "analyze_test_failure",
    "suggest_test_fix",
    "coverage_report",
    "find_references",
    "find_definition",
    "analyze_imports",
    "dead_code_check",
]
