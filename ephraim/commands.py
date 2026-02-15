"""
Command System

Handles slash commands and built-in commands.
Commands start with / and provide quick actions.
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Callable, Any
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class Command:
    """Represents a parsed command."""
    name: str
    args: str
    raw: str


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    message: str
    data: Optional[Any] = None
    should_continue: bool = True  # False to exit


def parse_command(input_text: str) -> Optional[Command]:
    """
    Parse a slash command from input.

    Returns Command if input starts with /, None otherwise.
    """
    input_text = input_text.strip()

    if not input_text.startswith('/'):
        return None

    parts = input_text.split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return Command(name=name, args=args, raw=input_text)


class CommandRegistry:
    """Registry of available commands."""

    def __init__(self):
        self.commands: Dict[str, Callable] = {}
        self.descriptions: Dict[str, str] = {}

    def register(self, name: str, description: str):
        """Decorator to register a command."""
        def decorator(func: Callable):
            self.commands[name] = func
            self.descriptions[name] = description
            return func
        return decorator

    def get(self, name: str) -> Optional[Callable]:
        """Get a command handler."""
        return self.commands.get(name)

    def list_all(self) -> Dict[str, str]:
        """List all commands with descriptions."""
        return dict(self.descriptions)


# Global registry
command_registry = CommandRegistry()


# ============ Built-in Commands ============

@command_registry.register("/help", "Show available commands")
def cmd_help(args: str, context: Dict) -> CommandResult:
    """Show help for commands."""
    table = Table(title="Available Commands", show_header=True)
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    for name, desc in sorted(command_registry.list_all().items()):
        table.add_row(name, desc)

    # Add skills
    from .skills import skill_registry
    for name, skill in skill_registry.list_all().items():
        table.add_row(name, f"[dim](skill)[/dim] {skill.description}")

    console.print(table)
    return CommandResult(success=True, message="")


@command_registry.register("/clear", "Clear the terminal screen")
def cmd_clear(args: str, context: Dict) -> CommandResult:
    """Clear the screen."""
    os.system('cls' if os.name == 'nt' else 'clear')
    return CommandResult(success=True, message="Screen cleared")


@command_registry.register("/status", "Show current session status")
def cmd_status(args: str, context: Dict) -> CommandResult:
    """Show status."""
    state = context.get("state")
    if not state:
        return CommandResult(success=False, message="No state available")

    from .state import Phase

    console.print(f"[bold]Phase:[/bold] {state.phase.value}")
    console.print(f"[bold]Goal:[/bold] {state.current_goal or 'None'}")
    console.print(f"[bold]Confidence:[/bold] {state.confidence_score}%")
    console.print(f"[bold]Risk:[/bold] {state.risk_level.value}")
    console.print(f"[bold]Iteration:[/bold] {state.execution.iteration}/{state.execution.max_iterations}")
    console.print(f"[bold]Plan Approved:[/bold] {state.current_plan.approved}")

    return CommandResult(success=True, message="")


@command_registry.register("/tasks", "Show all tasks")
def cmd_tasks(args: str, context: Dict) -> CommandResult:
    """Show tasks."""
    from .tasks import get_task_manager

    manager = get_task_manager()
    tasks = manager.list_all()
    summary = manager.get_summary()

    if not tasks:
        console.print("[dim]No tasks[/dim]")
        return CommandResult(success=True, message="")

    table = Table(title="Tasks", show_header=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Status", width=12)
    table.add_column("Subject")
    table.add_column("Blocked By", width=10)

    status_styles = {
        "pending": "yellow",
        "in_progress": "blue",
        "completed": "green",
    }

    for task in tasks:
        status = task.status.value
        style = status_styles.get(status, "white")
        blocked = ", ".join(task.blocked_by) if task.blocked_by else ""
        table.add_row(
            task.id,
            f"[{style}]{status}[/{style}]",
            task.subject,
            blocked,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {summary['total']} | "
                  f"Pending: {summary['pending']} | "
                  f"In Progress: {summary['in_progress']} | "
                  f"Completed: {summary['completed']}[/dim]")

    return CommandResult(success=True, message="")


@command_registry.register("/reset", "Reset the current session")
def cmd_reset(args: str, context: Dict) -> CommandResult:
    """Reset session."""
    from .tasks import get_task_manager

    # Clear tasks
    manager = get_task_manager()
    count = manager.clear()

    # Reset state
    state = context.get("state")
    if state:
        from .state import Phase, Plan
        state.phase = Phase.PLANNING
        state.current_goal = ""
        state.current_plan = Plan()
        state.confidence_score = 0
        state.action_history.clear()
        state.execution.iteration = 0

    return CommandResult(
        success=True,
        message=f"Session reset. Cleared {count} tasks.",
    )


@command_registry.register("/quit", "Exit Ephraim")
def cmd_quit(args: str, context: Dict) -> CommandResult:
    """Exit."""
    return CommandResult(
        success=True,
        message="Goodbye!",
        should_continue=False,
    )


@command_registry.register("/compact", "Compact context (clear old history)")
def cmd_compact(args: str, context: Dict) -> CommandResult:
    """Compact context."""
    state = context.get("state")
    if state:
        # Keep only last 5 actions
        if len(state.action_history) > 5:
            state.action_history = state.action_history[-5:]

    return CommandResult(
        success=True,
        message="Context compacted. Kept last 5 actions.",
    )


@command_registry.register("/background", "List background tasks")
def cmd_background(args: str, context: Dict) -> CommandResult:
    """Show background tasks."""
    from .background import get_background_manager

    manager = get_background_manager()
    tasks = manager.list_tasks()

    if not tasks:
        console.print("[dim]No background tasks[/dim]")
        return CommandResult(success=True, message="")

    table = Table(title="Background Tasks", show_header=True)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Status", width=12)
    table.add_column("Command")
    table.add_column("Started", width=20)

    status_styles = {
        "running": "blue",
        "completed": "green",
        "failed": "red",
        "stopped": "yellow",
    }

    for task in tasks:
        status = task.status.value
        style = status_styles.get(status, "white")
        table.add_row(
            task.id,
            f"[{style}]{status}[/{style}]",
            task.command[:50] + "..." if len(task.command) > 50 else task.command,
            task.started_at.strftime("%Y-%m-%d %H:%M:%S"),
        )

    console.print(table)
    return CommandResult(success=True, message="")


def execute_command(cmd: Command, context: Dict) -> CommandResult:
    """
    Execute a command.

    Returns CommandResult with success/failure and message.
    """
    handler = command_registry.get(cmd.name)

    if handler:
        return handler(cmd.args, context)

    # Check if it's a skill
    from .skills import skill_registry
    skill = skill_registry.get(cmd.name)
    if skill:
        # Skills return a prompt to process
        prompt = skill.execute(cmd.args)
        return CommandResult(
            success=True,
            message=f"Executing skill: {cmd.name}",
            data={"skill_prompt": prompt},
        )

    return CommandResult(
        success=False,
        message=f"Unknown command: {cmd.name}. Use /help for available commands.",
    )
