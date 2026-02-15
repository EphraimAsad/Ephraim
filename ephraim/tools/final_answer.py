"""
Final Answer Tool

Marks task completion and provides summary.
"""

from datetime import datetime

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool
from ..logging_setup import print_success, print_separator, console


@register_tool
class FinalAnswerTool(BaseTool):
    """
    Mark task as complete.

    Used when Ephraim has finished the assigned task.
    Provides a summary of what was accomplished.
    """

    name = "final_answer"
    description = "Mark the task as complete and provide a summary"
    category = ToolCategory.READ_ONLY  # No approval needed to complete

    parameters = [
        ToolParam(
            name="message",
            type="string",
            description="Summary of what was accomplished",
            required=True,
        ),
        ToolParam(
            name="files_modified",
            type="list",
            description="List of files that were modified",
            required=False,
            default=None,
        ),
        ToolParam(
            name="tests_passed",
            type="bool",
            description="Whether tests passed after changes",
            required=False,
            default=None,
        ),
        ToolParam(
            name="commit_hash",
            type="string",
            description="Git commit hash if changes were committed",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Mark task complete and display summary."""
        message = params["message"]
        files_modified = params.get("files_modified") or []
        tests_passed = params.get("tests_passed")
        commit_hash = params.get("commit_hash")

        # Display completion summary
        print_separator()
        print_success("TASK COMPLETED")
        print_separator()

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(message)

        if files_modified:
            console.print(f"\n[bold]Files modified:[/bold]")
            for f in files_modified:
                console.print(f"  - {f}")

        if tests_passed is not None:
            status = "[green]PASSED[/green]" if tests_passed else "[red]FAILED[/red]"
            console.print(f"\n[bold]Tests:[/bold] {status}")

        if commit_hash:
            console.print(f"\n[bold]Commit:[/bold] {commit_hash}")

        print_separator()

        return ToolResult.ok(
            data={
                "status": "completed",
                "message": message,
                "files_modified": files_modified,
                "tests_passed": tests_passed,
                "commit_hash": commit_hash,
                "completed_at": datetime.now().isoformat(),
            },
            summary=message,
        )


def mark_task_complete(
    message: str,
    files_modified: list = None,
    tests_passed: bool = None,
    commit_hash: str = None,
) -> ToolResult:
    """
    Convenience function to mark task complete.

    Can be called directly without going through tool registry.
    """
    tool = FinalAnswerTool()
    return tool(
        message=message,
        files_modified=files_modified or [],
        tests_passed=tests_passed,
        commit_hash=commit_hash,
    )
