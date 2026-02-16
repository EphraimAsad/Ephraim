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


@register_tool
class GitPushTool(BaseTool):
    """
    Push commits to a remote repository.
    """

    name = "git_push"
    description = "Push commits to remote repository"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="remote",
            type="string",
            description="Remote name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParam(
            name="branch",
            type="string",
            description="Branch to push (default: current branch)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="set_upstream",
            type="bool",
            description="Set upstream tracking (-u flag)",
            required=False,
            default=False,
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
        """Push to remote."""
        remote = params.get("remote", "origin")
        branch = params.get("branch")
        set_upstream = params.get("set_upstream", False)
        cwd = params.get("cwd")

        # Get current branch if not specified
        if not branch:
            branch_result = run_git_command(['branch', '--show-current'], cwd)
            if branch_result['returncode'] == 0:
                branch = branch_result['stdout'].strip()
            else:
                return ToolResult.fail("Could not determine current branch")

        # Build push command
        args = ['push']
        if set_upstream:
            args.append('-u')
        args.extend([remote, branch])

        result = run_git_command(args, cwd, timeout=60)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Git push failed: {result['stderr']}")

        return ToolResult.ok(
            data={
                "remote": remote,
                "branch": branch,
                "set_upstream": set_upstream,
            },
            summary=f"Pushed {branch} to {remote}",
        )


@register_tool
class GitPullTool(BaseTool):
    """
    Pull changes from a remote repository.
    """

    name = "git_pull"
    description = "Pull changes from remote repository"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="remote",
            type="string",
            description="Remote name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParam(
            name="branch",
            type="string",
            description="Branch to pull (default: current branch)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="rebase",
            type="bool",
            description="Use rebase instead of merge",
            required=False,
            default=False,
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
        """Pull from remote."""
        remote = params.get("remote", "origin")
        branch = params.get("branch")
        rebase = params.get("rebase", False)
        cwd = params.get("cwd")

        # Build pull command
        args = ['pull']
        if rebase:
            args.append('--rebase')
        args.append(remote)
        if branch:
            args.append(branch)

        result = run_git_command(args, cwd, timeout=60)

        if result['returncode'] != 0:
            # Check for merge conflicts
            if 'CONFLICT' in result['stdout'] or 'conflict' in result['stderr'].lower():
                return ToolResult.fail(f"Pull resulted in merge conflicts: {result['stdout']}")
            return ToolResult.fail(f"Git pull failed: {result['stderr']}")

        # Parse output for updates
        stdout = result['stdout']
        files_changed = 0
        insertions = 0
        deletions = 0

        stats_match = re.search(
            r'(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?',
            stdout,
        )
        if stats_match:
            files_changed = int(stats_match.group(1))
            insertions = int(stats_match.group(2) or 0)
            deletions = int(stats_match.group(3) or 0)

        already_up_to_date = 'Already up to date' in stdout or 'Already up-to-date' in stdout

        return ToolResult.ok(
            data={
                "remote": remote,
                "branch": branch,
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions,
                "already_up_to_date": already_up_to_date,
            },
            summary="Already up to date" if already_up_to_date else
                    f"Pulled {files_changed} files (+{insertions}/-{deletions})",
        )


@register_tool
class GitBranchTool(BaseTool):
    """
    Create, list, or delete branches.
    """

    name = "git_branch"
    description = "Create, list, or delete git branches"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="action",
            type="string",
            description="Action: 'list', 'create', 'delete'",
            required=True,
        ),
        ToolParam(
            name="name",
            type="string",
            description="Branch name (required for create/delete)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="force",
            type="bool",
            description="Force delete (-D flag)",
            required=False,
            default=False,
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
        """Manage branches."""
        action = params["action"].lower()
        name = params.get("name")
        force = params.get("force", False)
        cwd = params.get("cwd")

        if action == "list":
            # List all branches
            result = run_git_command(['branch', '-a'], cwd)
            if result['returncode'] != 0:
                return ToolResult.fail(f"Git branch list failed: {result['stderr']}")

            branches = []
            current_branch = None
            for line in result['stdout'].strip().split('\n'):
                line = line.strip()
                if line.startswith('* '):
                    current_branch = line[2:]
                    branches.append(current_branch)
                elif line:
                    branches.append(line)

            return ToolResult.ok(
                data={
                    "branches": branches,
                    "current": current_branch,
                },
                summary=f"{len(branches)} branches, current: {current_branch}",
            )

        elif action == "create":
            if not name:
                return ToolResult.fail("Branch name required for create")

            result = run_git_command(['branch', name], cwd)
            if result['returncode'] != 0:
                return ToolResult.fail(f"Git branch create failed: {result['stderr']}")

            return ToolResult.ok(
                data={"created": name},
                summary=f"Created branch: {name}",
            )

        elif action == "delete":
            if not name:
                return ToolResult.fail("Branch name required for delete")

            flag = '-D' if force else '-d'
            result = run_git_command(['branch', flag, name], cwd)
            if result['returncode'] != 0:
                return ToolResult.fail(f"Git branch delete failed: {result['stderr']}")

            return ToolResult.ok(
                data={"deleted": name, "force": force},
                summary=f"Deleted branch: {name}",
            )

        else:
            return ToolResult.fail(f"Unknown action: {action}. Use 'list', 'create', or 'delete'")


@register_tool
class GitCheckoutTool(BaseTool):
    """
    Switch branches or restore files.
    """

    name = "git_checkout"
    description = "Switch branches or restore working tree files"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="target",
            type="string",
            description="Branch name or file path to checkout",
            required=True,
        ),
        ToolParam(
            name="create_branch",
            type="bool",
            description="Create new branch (-b flag)",
            required=False,
            default=False,
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
        """Checkout branch or file."""
        target = params["target"]
        create_branch = params.get("create_branch", False)
        cwd = params.get("cwd")

        args = ['checkout']
        if create_branch:
            args.append('-b')
        args.append(target)

        result = run_git_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Git checkout failed: {result['stderr']}")

        action = "Created and switched to" if create_branch else "Switched to"
        return ToolResult.ok(
            data={
                "target": target,
                "created": create_branch,
            },
            summary=f"{action}: {target}",
        )


@register_tool
class GitMergeTool(BaseTool):
    """
    Merge branches.
    """

    name = "git_merge"
    description = "Merge a branch into the current branch"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="branch",
            type="string",
            description="Branch to merge into current",
            required=True,
        ),
        ToolParam(
            name="no_ff",
            type="bool",
            description="Create merge commit even for fast-forward",
            required=False,
            default=False,
        ),
        ToolParam(
            name="message",
            type="string",
            description="Custom merge commit message",
            required=False,
            default=None,
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
        """Merge branch."""
        branch = params["branch"]
        no_ff = params.get("no_ff", False)
        message = params.get("message")
        cwd = params.get("cwd")

        args = ['merge']
        if no_ff:
            args.append('--no-ff')
        if message:
            args.extend(['-m', message])
        args.append(branch)

        result = run_git_command(args, cwd)

        if result['returncode'] != 0:
            # Check for merge conflicts
            if 'CONFLICT' in result['stdout'] or 'conflict' in result['stderr'].lower():
                return ToolResult.fail(
                    f"Merge conflict detected. Resolve conflicts manually.\n{result['stdout']}"
                )
            return ToolResult.fail(f"Git merge failed: {result['stderr']}")

        # Check if already up to date
        if 'Already up to date' in result['stdout']:
            return ToolResult.ok(
                data={"branch": branch, "already_merged": True},
                summary=f"Already up to date with {branch}",
            )

        # Parse merge result
        fast_forward = 'Fast-forward' in result['stdout']

        return ToolResult.ok(
            data={
                "branch": branch,
                "fast_forward": fast_forward,
                "no_ff": no_ff,
            },
            summary=f"Merged {branch}" + (" (fast-forward)" if fast_forward else ""),
        )


@register_tool
class GitStashTool(BaseTool):
    """
    Stash changes temporarily.
    """

    name = "git_stash"
    description = "Stash or restore uncommitted changes"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="action",
            type="string",
            description="Action: 'push', 'pop', 'list', 'drop', 'apply'",
            required=True,
        ),
        ToolParam(
            name="message",
            type="string",
            description="Message for stash (for push action)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="index",
            type="int",
            description="Stash index (for pop/drop/apply, default: 0)",
            required=False,
            default=0,
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
        """Manage stash."""
        action = params["action"].lower()
        message = params.get("message")
        index = params.get("index", 0)
        cwd = params.get("cwd")

        if action == "push":
            args = ['stash', 'push']
            if message:
                args.extend(['-m', message])
            result = run_git_command(args, cwd)

            if result['returncode'] != 0:
                return ToolResult.fail(f"Git stash push failed: {result['stderr']}")

            if 'No local changes to save' in result['stdout']:
                return ToolResult.ok(
                    data={"action": "push", "saved": False},
                    summary="No changes to stash",
                )

            return ToolResult.ok(
                data={"action": "push", "message": message, "saved": True},
                summary=f"Stashed changes" + (f": {message}" if message else ""),
            )

        elif action == "pop":
            result = run_git_command(['stash', 'pop', f'stash@{{{index}}}'], cwd)

            if result['returncode'] != 0:
                if 'CONFLICT' in result['stdout']:
                    return ToolResult.fail(f"Stash pop conflict: {result['stdout']}")
                return ToolResult.fail(f"Git stash pop failed: {result['stderr']}")

            return ToolResult.ok(
                data={"action": "pop", "index": index},
                summary=f"Popped stash@{{{index}}}",
            )

        elif action == "apply":
            result = run_git_command(['stash', 'apply', f'stash@{{{index}}}'], cwd)

            if result['returncode'] != 0:
                return ToolResult.fail(f"Git stash apply failed: {result['stderr']}")

            return ToolResult.ok(
                data={"action": "apply", "index": index},
                summary=f"Applied stash@{{{index}}}",
            )

        elif action == "list":
            result = run_git_command(['stash', 'list'], cwd)

            if result['returncode'] != 0:
                return ToolResult.fail(f"Git stash list failed: {result['stderr']}")

            stashes = []
            for line in result['stdout'].strip().split('\n'):
                if line:
                    stashes.append(line)

            return ToolResult.ok(
                data={"action": "list", "stashes": stashes},
                summary=f"{len(stashes)} stash(es)",
            )

        elif action == "drop":
            result = run_git_command(['stash', 'drop', f'stash@{{{index}}}'], cwd)

            if result['returncode'] != 0:
                return ToolResult.fail(f"Git stash drop failed: {result['stderr']}")

            return ToolResult.ok(
                data={"action": "drop", "index": index},
                summary=f"Dropped stash@{{{index}}}",
            )

        else:
            return ToolResult.fail(f"Unknown action: {action}. Use 'push', 'pop', 'list', 'drop', or 'apply'")


# Additional convenience functions

def git_push(remote: str = "origin", branch: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Push to remote."""
    tool = GitPushTool()
    result = tool(remote=remote, branch=branch, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_pull(remote: str = "origin", branch: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Pull from remote."""
    tool = GitPullTool()
    result = tool(remote=remote, branch=branch, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_branch(action: str, name: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Manage branches."""
    tool = GitBranchTool()
    result = tool(action=action, name=name, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_checkout(target: str, create_branch: bool = False, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Checkout branch or file."""
    tool = GitCheckoutTool()
    result = tool(target=target, create_branch=create_branch, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_merge(branch: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Merge branch."""
    tool = GitMergeTool()
    result = tool(branch=branch, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def git_stash(action: str, message: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Manage stash."""
    tool = GitStashTool()
    result = tool(action=action, message=message, cwd=cwd)
    return result.data if result.success else {"error": result.error}
