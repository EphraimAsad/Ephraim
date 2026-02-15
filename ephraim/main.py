"""
Ephraim CLI Entry Point

This module provides the main entry function that is called when
the user runs `Ephraim` from the terminal.
"""

import argparse
import sys
from typing import Optional, List

from .boot import boot, BootError
from .agent_loop import run_agent
from .config import create_default_context_md
from .logging_setup import (
    print_header,
    print_info,
    print_error,
    print_success,
    print_separator,
    get_user_input,
    console,
)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='Ephraim',
        description='Senior-Engineer Terminal Coding Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Ephraim                  Start Ephraim in interactive mode
  Ephraim status           Show current status (Context.md)
  Ephraim config           Show configuration (Ephraim.md)
  Ephraim reset            Reset Context.md to defaults
        """,
    )

    parser.add_argument(
        'command',
        nargs='?',
        default='run',
        choices=['run', 'status', 'config', 'reset', 'version'],
        help='Command to execute (default: run)',
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging to console',
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0',
    )

    return parser.parse_args(args)


def show_status(state) -> None:
    """Display current status from Context.md and state."""
    print_header("EPHRAIM STATUS")

    print_info(f"Phase: {state.phase.value}")
    print_info(f"Repository: {state.repo_root}")

    if state.current_goal:
        print_info(f"Current Goal: {state.current_goal}")
    else:
        print_info("Current Goal: None")

    print_separator()
    print_info("Git Status:")
    print_info(f"  Branch: {state.git.branch or 'N/A'}")
    print_info(f"  Clean: {state.git.is_clean}")
    if state.git.modified_files:
        print_info(f"  Modified: {', '.join(state.git.modified_files)}")
    if state.git.untracked_files:
        print_info(f"  Untracked: {', '.join(state.git.untracked_files)}")

    print_separator()
    print_info(f"Iterations: {state.execution.iteration}/{state.execution.max_iterations}")
    print_info(f"Actions taken: {len(state.action_history)}")


def show_config(config) -> None:
    """Display current configuration."""
    print_header("EPHRAIM CONFIGURATION")

    print_info("Model:")
    print_info(f"  Provider: {config.model.provider}")
    print_info(f"  Model: {config.model.model_name}")
    print_info(f"  Endpoint: {config.model.endpoint}")

    print_separator()
    print_info("Safety:")
    print_info(f"  Require Approval: {config.safety.require_approval}")
    print_info(f"  Max Iterations: {config.safety.max_iterations}")
    if config.safety.protected_paths:
        print_info(f"  Protected Paths: {', '.join(config.safety.protected_paths)}")

    print_separator()
    print_info("Git:")
    print_info(f"  Auto Commit: {config.git.auto_commit}")
    print_info(f"  Commit Prefix: {config.git.commit_prefix}")

    print_separator()
    print_info("CI:")
    print_info(f"  Enabled: {config.ci.enabled}")
    print_info(f"  Provider: {config.ci.provider}")

    if config.architecture_constraints:
        print_separator()
        print_info("Architecture Constraints:")
        for constraint in config.architecture_constraints:
            print_info(f"  - {constraint}")


def run_interactive(state, config) -> None:
    """
    Run Ephraim in interactive mode using the agent loop.
    """
    run_agent(state, config)


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for Ephraim.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        parsed = parse_args(args)

        # Handle version (already handled by argparse)
        if parsed.command == 'version':
            console.print("Ephraim 0.1.0")
            return 0

        # Boot the system
        try:
            state, config = boot()
        except BootError as e:
            print_error(f"Boot failed: {e}")
            return 1

        # Handle commands
        if parsed.command == 'status':
            show_status(state)
            return 0

        if parsed.command == 'config':
            show_config(config)
            return 0

        if parsed.command == 'reset':
            import os
            context_path = os.path.join(state.repo_root, 'Context.md')
            with open(context_path, 'w', encoding='utf-8') as f:
                f.write(create_default_context_md())
            print_success(f"Reset Context.md at {context_path}")
            return 0

        # Default: run interactive mode
        run_interactive(state, config)
        return 0

    except KeyboardInterrupt:
        print_info("\nExiting...")
        return 130


if __name__ == '__main__':
    sys.exit(main())
