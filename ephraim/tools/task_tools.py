"""
Task Management Tools

Provides tools for creating, updating, and listing tasks.
"""

from typing import Optional, List, Dict

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool
from ..tasks import get_task_manager, TaskStatus


@register_tool
class TaskCreateTool(BaseTool):
    """
    Create a new task.

    Tasks help track multi-step work and show progress.
    """

    name = "task_create"
    description = "Create a new task to track work"
    category = ToolCategory.USER_INPUT

    parameters = [
        ToolParam(
            name="subject",
            type="string",
            description="Brief task title (imperative form, e.g., 'Run tests')",
            required=True,
        ),
        ToolParam(
            name="description",
            type="string",
            description="Detailed description of what needs to be done",
            required=True,
        ),
        ToolParam(
            name="active_form",
            type="string",
            description="Present continuous form for spinner (e.g., 'Running tests')",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Create the task."""
        subject = params["subject"]
        description = params["description"]
        active_form = params.get("active_form")

        manager = get_task_manager()
        task = manager.create(
            subject=subject,
            description=description,
            active_form=active_form,
        )

        return ToolResult.ok(
            data=task.to_dict(),
            summary=f"Created task #{task.id}: {subject}",
        )


@register_tool
class TaskUpdateTool(BaseTool):
    """
    Update an existing task.

    Can change status, description, add dependencies, etc.
    """

    name = "task_update"
    description = "Update a task's status or details"
    category = ToolCategory.USER_INPUT

    parameters = [
        ToolParam(
            name="task_id",
            type="string",
            description="ID of the task to update",
            required=True,
        ),
        ToolParam(
            name="status",
            type="string",
            description="New status: pending, in_progress, completed, deleted",
            required=False,
            default=None,
        ),
        ToolParam(
            name="subject",
            type="string",
            description="New subject/title",
            required=False,
            default=None,
        ),
        ToolParam(
            name="description",
            type="string",
            description="New description",
            required=False,
            default=None,
        ),
        ToolParam(
            name="add_blocked_by",
            type="list",
            description="Task IDs that block this task",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Update the task."""
        task_id = params["task_id"]
        status = params.get("status")
        subject = params.get("subject")
        description = params.get("description")
        add_blocked_by = params.get("add_blocked_by")

        manager = get_task_manager()
        task = manager.update(
            task_id=task_id,
            status=status,
            subject=subject,
            description=description,
            add_blocked_by=add_blocked_by,
        )

        if not task:
            return ToolResult.fail(f"Task not found: {task_id}")

        action = status if status else "Updated"
        return ToolResult.ok(
            data=task.to_dict(),
            summary=f"Task #{task_id} {action}: {task.subject}",
        )


@register_tool
class TaskGetTool(BaseTool):
    """
    Get details of a specific task.
    """

    name = "task_get"
    description = "Get details of a task by ID"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="task_id",
            type="string",
            description="ID of the task to get",
            required=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Get the task."""
        task_id = params["task_id"]

        manager = get_task_manager()
        task = manager.get(task_id)

        if not task:
            return ToolResult.fail(f"Task not found: {task_id}")

        return ToolResult.ok(
            data=task.to_dict(),
            summary=f"Task #{task_id}: {task.subject} ({task.status.value})",
        )


@register_tool
class TaskListTool(BaseTool):
    """
    List all tasks.

    Shows summary of all tasks with their status.
    """

    name = "task_list"
    description = "List all tasks and their status"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="include_completed",
            type="bool",
            description="Include completed tasks",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """List tasks."""
        include_completed = params.get("include_completed", True)

        manager = get_task_manager()
        tasks = manager.list_all(include_completed=include_completed)
        summary = manager.get_summary()

        task_list = [t.to_dict() for t in tasks]

        return ToolResult.ok(
            data={
                "tasks": task_list,
                "summary": summary,
            },
            summary=f"{len(tasks)} tasks: {summary['pending']} pending, "
                    f"{summary['in_progress']} in progress, {summary['completed']} completed",
        )


# Convenience functions
def task_create(subject: str, description: str) -> ToolResult:
    """Create a task."""
    tool = TaskCreateTool()
    return tool(subject=subject, description=description)


def task_update(task_id: str, **kwargs) -> ToolResult:
    """Update a task."""
    tool = TaskUpdateTool()
    return tool(task_id=task_id, **kwargs)


def task_list() -> ToolResult:
    """List all tasks."""
    tool = TaskListTool()
    return tool()
