"""
Git Tools

Git integration with structured output formats.

Commands:
- git_status: Parse `git status --porcelain`
- git_diff: Parse `git diff --staged`
- git_commit: Execute commit and parse result
- git_add: Stage specific files
"""

import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def run_git_command(
    args: List[str],
    cwd: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Run a git command and return result.

    Returns dict with: returncode, stdout, stderr
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Git command timed out",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


@register_tool
class GitStatusTool(BaseTool):
    """
    Get the current git status.

    Parses `git status --porcelain` into structured format.
    """

    name = "git_status"
    description = "Get the current git repository status"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Get git status."""
        cwd = params.get("cwd")

        # Get branch
        branch_result = run_git_command(['branch', '--show-current'], cwd)
        branch = branch_result['stdout'].strip() if branch_result['returncode'] == 0 else ""

        # Get status
        status_result = run_git_command(['status', '--porcelain'], cwd)

        if status_result['returncode'] != 0:
            return ToolResult.fail(f"Git status failed: {status_result['stderr']}")

        # Parse porcelain output
        modified_files: List[str] = []
        untracked_files: List[str] = []
        staged_files: List[str] = []
        deleted_files: List[str] = []

        # Don't use strip() - it removes leading spaces that are part of porcelain format
        for line in status_result['stdout'].split('\n'):
            if not line or len(line) < 3:
                continue

            # Format: XY filename
            # X = index status (position 0), Y = work tree status (position 1)
            # Position 2 is always a space, filename starts at position 3
            x_status = line[0]
            y_status = line[1]
            filename = line[3:]

            # Staged changes (index)
            if x_status == 'M':
                staged_files.append(filename)
            elif x_status == 'A':
                staged_files.append(filename)
            elif x_status == 'D':
                deleted_files.append(filename)

            # Work tree changes
            if y_status == 'M':
                modified_files.append(filename)
            elif y_status == 'D':
                deleted_files.append(filename)

            # Untracked
            if x_status == '?' and y_status == '?':
                untracked_files.append(filename)

        # Build structured output
        git_status = {
            "git_status": {
                "modified_files": modified_files,
                "untracked_files": untracked_files,
                "staged_files": staged_files,
                "deleted_files": deleted_files,
            },
            "branch": branch,
            "is_clean": not any([modified_files, untracked_files, staged_files, deleted_files]),
        }

        total_changes = len(modified_files) + len(untracked_files) + len(staged_files)

        return ToolResult.ok(
            data=git_status,
            summary=f"Branch: {branch}, {total_changes} changes"
                    if total_changes else f"Branch: {branch}, clean",
        )


@register_tool
class GitDiffTool(BaseTool):
    """
    Get the current git diff.

    Parses `git diff --staged` into structured format.
    """

    name = "git_diff"
    description = "Get the staged diff for the repository"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="staged",
            type="bool",
            description="Show staged changes (True) or unstaged (False)",
            required=False,
            default=True,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Get git diff."""
        staged = params.get("staged", True)
        cwd = params.get("cwd")

        args = ['diff']
        if staged:
            args.append('--staged')

        result = run_git_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Git diff failed: {result['stderr']}")

        # Parse diff output
        diff_output = result['stdout']
        git_diff = self._parse_diff(diff_output)

        return ToolResult.ok(
            data={
                "git_diff": git_diff,
                "raw_diff": diff_output,
            },
            summary=f"{len(git_diff)} files changed",
        )

    def _parse_diff(self, diff_output: str) -> List[Dict[str, Any]]:
        """Parse unified diff format into structured data."""
        files: List[Dict[str, Any]] = []
        current_file = None
        current_changes: List[Dict[str, Any]] = []

        lines = diff_output.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # New file
            if line.startswith('diff --git'):
                # Save previous file
                if current_file:
                    files.append({
                        "file": current_file,
                        "changes": current_changes,
                    })

                # Extract filename
                match = re.search(r'b/(.+)$', line)
                current_file = match.group(1) if match else "unknown"
                current_changes = []

            # Hunk header
            elif line.startswith('@@'):
                match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
                if match:
                    old_start = int(match.group(1))
                    new_start = int(match.group(2))

                    # Collect hunk changes
                    hunk_added = []
                    hunk_removed = []
                    i += 1

                    while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('diff'):
                        hunk_line = lines[i]
                        if hunk_line.startswith('+') and not hunk_line.startswith('+++'):
                            hunk_added.append(hunk_line[1:])
                        elif hunk_line.startswith('-') and not hunk_line.startswith('---'):
                            hunk_removed.append(hunk_line[1:])
                        i += 1

                    if hunk_added or hunk_removed:
                        current_changes.append({
                            "line_start": new_start,
                            "line_end": new_start + len(hunk_added),
                            "added": '\n'.join(hunk_added) if hunk_added else None,
                            "removed": '\n'.join(hunk_removed) if hunk_removed else None,
                        })
                    continue

            i += 1

        # Save last file
        if current_file:
            files.append({
                "file": current_file,
                "changes": current_changes,
            })

        return files


@register_tool
class GitCommitTool(BaseTool):
    """
    Create a git commit.

    Commits staged changes with the Ephraim prefix.
    """

    name = "git_commit"
    description = "Commit staged changes"
    category = ToolCategory.GIT  # Requires approval

    parameters = [
        ToolParam(
            name="message",
            type="string",
            description="Commit message (Ephraim prefix will be added)",
            required=True,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Create the commit."""
        message = params["message"]
        cwd = params.get("cwd")

        # Add Ephraim prefix if not present
        if not message.startswith("Ephraim:"):
            message = f"Ephraim: {message}"

        # Execute commit
        result = run_git_command(['commit', '-m', message], cwd)

        if result['returncode'] != 0:
            # Check if there's nothing to commit
            if 'nothing to commit' in result['stdout'] or 'nothing to commit' in result['stderr']:
                return ToolResult.fail("Nothing to commit")
            return ToolResult.fail(f"Git commit failed: {result['stderr']}")

        # Parse commit output
        stdout = result['stdout']

        # Extract commit info
        commit_info = {
            "commit_message": message,
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
        }

        # Parse stats line: "2 files changed, 4 insertions(+), 1 deletion(-)"
        stats_match = re.search(
            r'(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?',
            stdout,
        )
        if stats_match:
            commit_info['files_changed'] = int(stats_match.group(1))
            commit_info['insertions'] = int(stats_match.group(2) or 0)
            commit_info['deletions'] = int(stats_match.group(3) or 0)

        # Get commit hash
        hash_result = run_git_command(['rev-parse', 'HEAD'], cwd)
        if hash_result['returncode'] == 0:
            commit_info['commit_hash'] = hash_result['stdout'].strip()[:8]

        return ToolResult.ok(
            data={"git_commit": commit_info},
            summary=f"Committed: {commit_info['files_changed']} files, "
                    f"+{commit_info['insertions']}/-{commit_info['deletions']}",
        )


@register_tool
class GitAddTool(BaseTool):
    """
    Stage files for commit.
    """

    name = "git_add"
    description = "Stage files for commit"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="files",
            type="list",
            description="List of files to stage (or ['.'] for all)",
            required=True,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Stage the files."""
        files = params["files"]
        cwd = params.get("cwd")

        if not files:
            return ToolResult.fail("No files specified")

        result = run_git_command(['add'] + files, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Git add failed: {result['stderr']}")

        return ToolResult.ok(
            data={
                "staged_files": files,
            },
            summary=f"Staged {len(files)} file(s)",
        )


# Convenience functions for direct use

def git_status(cwd: Optional[str] = None) -> Dict[str, Any]:
    """Get git status as structured dict."""
    tool = GitStatusTool()
    result = tool(cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_diff(staged: bool = True, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Get git diff as structured dict."""
    tool = GitDiffTool()
    result = tool(staged=staged, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_commit(message: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Create a commit and return result."""
    tool = GitCommitTool()
    result = tool(message=message, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_add(files: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Stage files and return result."""
    tool = GitAddTool()
    result = tool(files=files, cwd=cwd)
    return result.data if result.success else {"error": result.error}
