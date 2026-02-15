"""
Ephraim Boot Sequence

Handles initialization of the system before any LLM reasoning occurs.
No LLM calls happen until the environment is verified stable.
"""

import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional

from .state import EphraimState, Phase, GitStatus, create_initial_state
from .config import (
    EphraimConfig,
    load_config_from_ephraim_md,
    create_default_ephraim_md,
    create_default_context_md,
    get_default_config,
)
from .logging_setup import (
    setup_logging,
    get_logger,
    print_header,
    print_info,
    print_warning,
    print_error,
    print_success,
    print_phase,
)


class BootError(Exception):
    """Raised when boot sequence fails."""
    pass


def detect_repo_root(start_path: Optional[str] = None) -> str:
    """
    Detect the Git repository root.

    Walks up from start_path (or cwd) looking for .git directory.
    Returns the repo root path, or cwd if not in a git repo.
    """
    path = Path(start_path) if start_path else Path.cwd()

    # Walk up looking for .git
    current = path.resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return str(current)
        current = current.parent

    # Check root
    if (current / '.git').exists():
        return str(current)

    # Not in a git repo - use current directory
    return str(path.resolve())


def verify_git_available() -> bool:
    """Check if git is available on the system."""
    try:
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def verify_gh_cli_available() -> bool:
    """Check if GitHub CLI is available and authenticated."""
    try:
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def load_git_status(repo_root: str) -> GitStatus:
    """
    Load current git status from the repository.

    Uses `git status --porcelain` for structured output.
    """
    status = GitStatus()

    try:
        # Get branch name
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if branch_result.returncode == 0:
            status.branch = branch_result.stdout.strip()

        # Get status
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if status_result.returncode == 0:
            # Don't use strip() - it removes leading spaces that are part of porcelain format
            for line in status_result.stdout.split('\n'):
                if not line or len(line) < 3:
                    continue

                # Parse porcelain format: XY filename
                # X = index status (position 0), Y = work tree status (position 1)
                # Position 2 is always a space, filename starts at position 3
                x_status = line[0]
                y_status = line[1]
                filename = line[3:]

                if x_status == '?' and y_status == '?':
                    status.untracked_files.append(filename)
                elif x_status == 'M' or y_status == 'M':
                    if x_status == 'M':
                        status.staged_files.append(filename)
                    if y_status == 'M':
                        status.modified_files.append(filename)
                elif x_status == 'A':
                    status.staged_files.append(filename)
                elif x_status == 'D' or y_status == 'D':
                    status.deleted_files.append(filename)

            # Clean if no changes
            status.is_clean = not any([
                status.modified_files,
                status.untracked_files,
                status.staged_files,
                status.deleted_files,
            ])

        # Check for remote
        remote_result = subprocess.run(
            ['git', 'remote'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status.has_remote = bool(remote_result.stdout.strip())

    except subprocess.SubprocessError:
        # Return empty status on error
        pass

    return status


def ensure_ephraim_md(repo_root: str) -> str:
    """
    Ensure Ephraim.md exists in the repo root.

    Creates with defaults if it doesn't exist.
    Returns the path to Ephraim.md.
    """
    ephraim_md_path = os.path.join(repo_root, 'Ephraim.md')

    if not os.path.exists(ephraim_md_path):
        print_info("Creating Ephraim.md with default configuration...")
        with open(ephraim_md_path, 'w', encoding='utf-8') as f:
            f.write(create_default_ephraim_md())
        print_success("Created Ephraim.md")

    return ephraim_md_path


def ensure_context_md(repo_root: str) -> str:
    """
    Ensure Context.md exists in the repo root.

    Creates with defaults if it doesn't exist.
    Returns the path to Context.md.
    """
    context_md_path = os.path.join(repo_root, 'Context.md')

    if not os.path.exists(context_md_path):
        print_info("Creating Context.md for session tracking...")
        with open(context_md_path, 'w', encoding='utf-8') as f:
            f.write(create_default_context_md())
        print_success("Created Context.md")

    return context_md_path


def ensure_log_directory(repo_root: str) -> str:
    """
    Ensure .ephraim/logs directory exists.

    Returns the path to the logs directory.
    """
    log_dir = os.path.join(repo_root, '.ephraim', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def boot() -> Tuple[EphraimState, EphraimConfig]:
    """
    Execute the full boot sequence.

    Returns:
        Tuple of (state, config) ready for the agent loop.

    Raises:
        BootError: If critical boot steps fail.
    """
    print_header("EPHRAIM - Senior Engineer Terminal Agent")
    print_phase("BOOT")

    # Step 1: Detect repo root
    print_info("Detecting repository root...")
    repo_root = detect_repo_root()
    print_success(f"Repository root: {repo_root}")

    # Step 2: Set up logging
    log_dir = ensure_log_directory(repo_root)
    setup_logging(log_dir=log_dir)
    logger = get_logger()
    logger.info(f"Boot sequence started in {repo_root}")

    # Step 3: Initialize state
    print_info("Initializing state...")
    state = create_initial_state()
    state.repo_root = repo_root

    # Step 4: Verify git
    print_info("Verifying git availability...")
    if not verify_git_available():
        print_warning("Git is not available. Some features will be limited.")
        logger.warning("Git not available")
    else:
        print_success("Git is available")

    # Step 5: Create/load Ephraim.md
    print_info("Loading Ephraim.md...")
    ephraim_md_path = ensure_ephraim_md(repo_root)
    state.ephraim_md_path = ephraim_md_path
    config = load_config_from_ephraim_md(ephraim_md_path)
    print_success("Configuration loaded")

    # Step 6: Create/load Context.md
    print_info("Loading Context.md...")
    context_md_path = ensure_context_md(repo_root)
    state.context_md_path = context_md_path
    print_success("Context loaded")

    # Step 7: Load git status
    print_info("Loading git status...")
    state.git = load_git_status(repo_root)
    if state.git.branch:
        print_success(f"On branch: {state.git.branch}")
    if not state.git.is_clean:
        print_warning(f"Working tree has changes: {len(state.git.modified_files)} modified, {len(state.git.untracked_files)} untracked")
    else:
        print_success("Working tree is clean")

    # Step 8: Check GitHub CLI
    print_info("Checking GitHub CLI authentication...")
    if verify_gh_cli_available():
        print_success("GitHub CLI is authenticated")
    else:
        print_warning("GitHub CLI not available or not authenticated. CI features will be limited.")
        config.ci.enabled = False
        logger.warning("GitHub CLI not available")

    # Step 9: Transition to planning phase
    state.phase = Phase.PLANNING
    state.execution.max_iterations = config.safety.max_iterations

    print_phase("PLANNING")
    print_success("Boot sequence complete. Ready for task input.")
    logger.info("Boot sequence completed successfully")

    return state, config


def quick_boot(repo_root: Optional[str] = None) -> Tuple[EphraimState, EphraimConfig]:
    """
    Quick boot for testing - minimal output.

    Returns:
        Tuple of (state, config)
    """
    root = repo_root or str(Path.cwd())

    state = create_initial_state()
    state.repo_root = root
    state.ephraim_md_path = os.path.join(root, 'Ephraim.md')
    state.context_md_path = os.path.join(root, 'Context.md')

    config = get_default_config()

    if verify_git_available():
        state.git = load_git_status(root)

    state.phase = Phase.PLANNING

    return state, config
