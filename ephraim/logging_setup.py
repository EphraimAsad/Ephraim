"""
Ephraim Logging System

Provides file logging for debugging and console output via rich.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text


# Custom theme for Ephraim
EPHRAIM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green",
    "phase": "magenta bold",
    "tool": "blue",
    "plan": "cyan italic",
    "approval": "yellow bold",
    "risk.low": "green",
    "risk.medium": "yellow",
    "risk.high": "red bold",
})

# Global console instance
console = Console(theme=EPHRAIM_THEME)


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: int = logging.DEBUG,
    console_level: int = logging.INFO,
) -> logging.Logger:
    """
    Set up logging for Ephraim.

    Args:
        log_dir: Directory for log files. Defaults to .ephraim/logs in repo root.
        log_level: Level for file logging (default DEBUG)
        console_level: Level for console output (default INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("ephraim")
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with rich formatting
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    console_handler.setLevel(console_level)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler for debugging
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_path / f"ephraim_{timestamp}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the Ephraim logger instance."""
    return logging.getLogger("ephraim")


# Rich console output helpers

def print_header(text: str) -> None:
    """Print a styled header."""
    console.print()
    console.print(Panel(
        Text(text, style="bold white"),
        border_style="cyan",
        padding=(0, 2),
    ))


def print_phase(phase: str) -> None:
    """Print current phase indicator."""
    console.print(f"[phase]>>> Phase: {phase}[/phase]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[info]{message}[/info]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]Warning: {message}[/warning]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[error]Error: {message}[/error]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[success]{message}[/success]")


def print_tool_call(tool_name: str, params: dict) -> None:
    """Print a tool call notification."""
    console.print(f"[tool]Executing: {tool_name}[/tool]")
    if params:
        for key, value in params.items():
            console.print(f"  {key}: {value}")


def print_risk(level: str) -> None:
    """Print risk level with appropriate styling."""
    style = f"risk.{level.lower()}"
    console.print(f"[{style}]Risk Level: {level}[/{style}]")


def print_confidence(score: int) -> None:
    """Print confidence score with level indicator."""
    if score >= 80:
        level = "HIGH"
        style = "green"
    elif score >= 55:
        level = "MEDIUM"
        style = "yellow"
    elif score >= 30:
        level = "LOW"
        style = "red"
    else:
        level = "VERY LOW"
        style = "red bold"

    console.print(f"[{style}]Confidence: {score}% ({level})[/{style}]")


def print_plan(plan: dict) -> None:
    """Print a formatted plan."""
    console.print()
    console.print(Panel(
        "\n".join([
            f"[bold]Goal:[/bold] {plan.get('goal_understanding', 'N/A')}",
            "",
            f"[bold]Reasoning:[/bold] {plan.get('reasoning', 'N/A')}",
            "",
            "[bold]Steps:[/bold]",
            *[f"  {i+1}. {step}" for i, step in enumerate(plan.get('execution_steps', []))],
            "",
            f"[bold]Risk:[/bold] {plan.get('risk_assessment', 'N/A')}",
            f"[bold]Validation:[/bold] {plan.get('validation_plan', 'N/A')}",
        ]),
        title="[plan]Execution Plan[/plan]",
        border_style="cyan",
    ))


def print_approval_request(question: str) -> None:
    """Print an approval request."""
    console.print()
    console.print(Panel(
        question,
        title="[approval]Approval Required[/approval]",
        border_style="yellow",
    ))


def print_separator() -> None:
    """Print a visual separator."""
    console.print("─" * 60, style="dim")


def get_user_input(prompt: str = "> ") -> str:
    """Get input from user with styled prompt."""
    return console.input(f"[bold cyan]{prompt}[/bold cyan]")


def confirm(prompt: str = "Proceed?") -> bool:
    """Get yes/no confirmation from user."""
    response = console.input(f"[yellow]{prompt} (y/n): [/yellow]").strip().lower()
    return response in ('y', 'yes')
