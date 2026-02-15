"""
Background Task Manager

Manages background shell commands and their outputs.
Allows starting, checking, and stopping long-running processes.
"""

import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class BackgroundTask:
    """Represents a background task."""
    id: str
    command: str
    status: TaskStatus
    started_at: datetime
    process: Optional[subprocess.Popen] = None
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None
    completed_at: Optional[datetime] = None
    cwd: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "command": self.command,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "exit_code": self.exit_code,
            "stdout_lines": len(self.stdout_lines),
            "stderr_lines": len(self.stderr_lines),
            "cwd": self.cwd,
        }


class BackgroundTaskManager:
    """
    Manages background tasks.

    Singleton pattern - use get_manager() to access.
    """

    _instance: Optional["BackgroundTaskManager"] = None

    def __init__(self):
        self.tasks: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_manager(cls) -> "BackgroundTaskManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Start a background task.

        Returns the task ID.
        """
        task_id = str(uuid.uuid4())[:8]

        # Resolve working directory
        if cwd:
            cwd = os.path.abspath(os.path.expanduser(cwd))
        else:
            cwd = os.getcwd()

        # Create task
        task = BackgroundTask(
            id=task_id,
            command=command,
            status=TaskStatus.PENDING,
            started_at=datetime.now(),
            cwd=cwd,
        )

        with self._lock:
            self.tasks[task_id] = task

        # Start in background thread
        thread = threading.Thread(
            target=self._run_task,
            args=(task,),
            daemon=True,
        )
        thread.start()

        return task_id

    def _run_task(self, task: BackgroundTask) -> None:
        """Run a task in background."""
        try:
            # Determine shell
            if sys.platform == 'win32':
                shell_cmd = ['cmd', '/c', task.command]
            else:
                shell_cmd = ['bash', '-c', task.command]

            # Start process
            process = subprocess.Popen(
                shell_cmd,
                cwd=task.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            task.process = process
            task.status = TaskStatus.RUNNING

            # Read stdout in separate thread
            def read_stdout():
                try:
                    for line in iter(process.stdout.readline, ''):
                        task.stdout_lines.append(line.rstrip('\n\r'))
                except Exception:
                    pass
                finally:
                    process.stdout.close()

            # Read stderr in separate thread
            def read_stderr():
                try:
                    for line in iter(process.stderr.readline, ''):
                        task.stderr_lines.append(line.rstrip('\n\r'))
                except Exception:
                    pass
                finally:
                    process.stderr.close()

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process
            process.wait()

            # Wait for output threads
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            # Update status
            task.exit_code = process.returncode
            task.completed_at = datetime.now()

            if task.status == TaskStatus.RUNNING:
                if process.returncode == 0:
                    task.status = TaskStatus.COMPLETED
                else:
                    task.status = TaskStatus.FAILED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.stderr_lines.append(f"Error: {str(e)}")
            task.completed_at = datetime.now()

    def check(self, task_id: str) -> Optional[BackgroundTask]:
        """
        Check status of a task.

        Returns the task or None if not found.
        """
        with self._lock:
            return self.tasks.get(task_id)

    def get_output(
        self,
        task_id: str,
        tail: int = 50,
    ) -> Optional[Dict]:
        """
        Get output from a task.

        Returns dict with stdout, stderr, and status.
        """
        task = self.check(task_id)
        if not task:
            return None

        return {
            "id": task_id,
            "status": task.status.value,
            "stdout": task.stdout_lines[-tail:] if tail else task.stdout_lines,
            "stderr": task.stderr_lines[-tail:] if tail else task.stderr_lines,
            "exit_code": task.exit_code,
        }

    def stop(self, task_id: str) -> bool:
        """
        Stop a running task.

        Returns True if stopped, False if not found or already stopped.
        """
        task = self.check(task_id)
        if not task:
            return False

        if task.status != TaskStatus.RUNNING:
            return False

        if task.process:
            try:
                task.process.terminate()
                task.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                task.process.kill()
            except Exception:
                pass

        task.status = TaskStatus.STOPPED
        task.completed_at = datetime.now()
        return True

    def list_tasks(self, include_completed: bool = True) -> List[BackgroundTask]:
        """List all tasks."""
        with self._lock:
            tasks = list(self.tasks.values())

        if not include_completed:
            tasks = [t for t in tasks if t.status == TaskStatus.RUNNING]

        return sorted(tasks, key=lambda t: t.started_at, reverse=True)

    def cleanup(self, max_age_hours: int = 24) -> int:
        """
        Remove old completed tasks.

        Returns number of tasks removed.
        """
        cutoff = datetime.now()
        removed = 0

        with self._lock:
            to_remove = []
            for task_id, task in self.tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED):
                    if task.completed_at:
                        age = (cutoff - task.completed_at).total_seconds() / 3600
                        if age > max_age_hours:
                            to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]
                removed += 1

        return removed


# Convenience function
def get_background_manager() -> BackgroundTaskManager:
    """Get the background task manager."""
    return BackgroundTaskManager.get_manager()
