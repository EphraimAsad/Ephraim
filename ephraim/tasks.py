"""
Task Management System

Provides todo/task tracking for complex multi-step work.
Tasks can have dependencies and status tracking.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Literal
from enum import Enum


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELETED = "deleted"


@dataclass
class Task:
    """Represents a task/todo item."""
    id: str
    subject: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    owner: Optional[str] = None
    active_form: Optional[str] = None  # Present tense for spinner
    blocks: List[str] = field(default_factory=list)  # Task IDs this blocks
    blocked_by: List[str] = field(default_factory=list)  # Task IDs blocking this
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner": self.owner,
            "active_form": self.active_form,
            "blocks": self.blocks,
            "blocked_by": self.blocked_by,
            "metadata": self.metadata,
        }

    def is_blocked(self) -> bool:
        """Check if task is blocked by other tasks."""
        return len(self.blocked_by) > 0


class TaskManager:
    """
    Manages tasks for the current session.

    Singleton pattern - use get_manager() to access.
    """

    _instance: Optional["TaskManager"] = None

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._counter = 0

    @classmethod
    def get_manager(cls) -> "TaskManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def _generate_id(self) -> str:
        """Generate a simple sequential ID."""
        self._counter += 1
        return str(self._counter)

    def create(
        self,
        subject: str,
        description: str,
        active_form: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            subject: Brief title (imperative form, e.g., "Run tests")
            description: Detailed description
            active_form: Present continuous form (e.g., "Running tests")
            metadata: Optional metadata dict
        """
        task_id = self._generate_id()

        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            active_form=active_form,
            metadata=metadata or {},
        )

        self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def update(
        self,
        task_id: str,
        status: Optional[str] = None,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        active_form: Optional[str] = None,
        owner: Optional[str] = None,
        add_blocks: Optional[List[str]] = None,
        add_blocked_by: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Task]:
        """
        Update a task.

        Returns the updated task or None if not found.
        """
        task = self.get(task_id)
        if not task:
            return None

        if status:
            try:
                if status == "deleted":
                    task.status = TaskStatus.DELETED
                else:
                    task.status = TaskStatus(status)
            except ValueError:
                pass

        if subject is not None:
            task.subject = subject

        if description is not None:
            task.description = description

        if active_form is not None:
            task.active_form = active_form

        if owner is not None:
            task.owner = owner

        if add_blocks:
            for bid in add_blocks:
                if bid not in task.blocks:
                    task.blocks.append(bid)
                # Also update the blocked task
                blocked_task = self.get(bid)
                if blocked_task and task_id not in blocked_task.blocked_by:
                    blocked_task.blocked_by.append(task_id)

        if add_blocked_by:
            for bid in add_blocked_by:
                if bid not in task.blocked_by:
                    task.blocked_by.append(bid)
                # Also update the blocking task
                blocking_task = self.get(bid)
                if blocking_task and task_id not in blocking_task.blocks:
                    blocking_task.blocks.append(task_id)

        if metadata:
            for key, value in metadata.items():
                if value is None:
                    task.metadata.pop(key, None)
                else:
                    task.metadata[key] = value

        task.updated_at = datetime.now()

        # When completing a task, unblock dependent tasks
        if status == "completed":
            self._unblock_dependents(task_id)

        return task

    def _unblock_dependents(self, completed_task_id: str) -> None:
        """Remove completed task from blocked_by lists."""
        for task in self.tasks.values():
            if completed_task_id in task.blocked_by:
                task.blocked_by.remove(completed_task_id)

    def delete(self, task_id: str) -> bool:
        """
        Delete a task.

        Returns True if deleted, False if not found.
        """
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.DELETED
            return True
        return False

    def list_all(
        self,
        include_deleted: bool = False,
        include_completed: bool = True,
    ) -> List[Task]:
        """List all tasks."""
        tasks = []
        for task in self.tasks.values():
            if task.status == TaskStatus.DELETED and not include_deleted:
                continue
            if task.status == TaskStatus.COMPLETED and not include_completed:
                continue
            tasks.append(task)

        # Sort by ID (creation order)
        return sorted(tasks, key=lambda t: int(t.id))

    def get_pending(self) -> List[Task]:
        """Get tasks that are pending and not blocked."""
        return [
            t for t in self.list_all(include_completed=False)
            if t.status == TaskStatus.PENDING and not t.is_blocked()
        ]

    def get_in_progress(self) -> List[Task]:
        """Get tasks currently in progress."""
        return [
            t for t in self.list_all(include_completed=False)
            if t.status == TaskStatus.IN_PROGRESS
        ]

    def get_summary(self) -> Dict:
        """Get a summary of task counts."""
        tasks = self.list_all()
        return {
            "total": len(tasks),
            "pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "blocked": len([t for t in tasks if t.is_blocked()]),
        }

    def clear(self) -> int:
        """Clear all tasks. Returns count removed."""
        count = len(self.tasks)
        self.tasks.clear()
        self._counter = 0
        return count


# Convenience function
def get_task_manager() -> TaskManager:
    """Get the task manager."""
    return TaskManager.get_manager()
