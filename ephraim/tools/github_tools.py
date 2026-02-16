"""
GitHub Tools

GitHub integration for PR and issue management via GitHub CLI.

Commands:
- gh_pr_create: Create a pull request
- gh_pr_list: List open pull requests
- gh_pr_review: Submit a PR review
- gh_issue_create: Create an issue
- gh_issue_list: List issues
- gh_issue_comment: Add a comment to an issue/PR
"""

import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def run_gh_command(
    args: List[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Run a gh CLI command and return result.

    Returns dict with: returncode, stdout, stderr
    """
    try:
        result = subprocess.run(
            ['gh'] + args,
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
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "GitHub CLI (gh) not found. Install from https://cli.github.com/",
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "GitHub CLI command timed out",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


@register_tool
class GHPRCreateTool(BaseTool):
    """
    Create a pull request.
    """

    name = "gh_pr_create"
    description = "Create a new pull request"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="title",
            type="string",
            description="PR title",
            required=True,
        ),
        ToolParam(
            name="body",
            type="string",
            description="PR description/body",
            required=False,
            default="",
        ),
        ToolParam(
            name="base",
            type="string",
            description="Base branch to merge into (default: main)",
            required=False,
            default="main",
        ),
        ToolParam(
            name="draft",
            type="bool",
            description="Create as draft PR",
            required=False,
            default=False,
        ),
        ToolParam(
            name="labels",
            type="list",
            description="Labels to add to the PR",
            required=False,
            default=[],
        ),
        ToolParam(
            name="reviewers",
            type="list",
            description="Reviewers to request",
            required=False,
            default=[],
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
        """Create PR."""
        title = params["title"]
        body = params.get("body", "")
        base = params.get("base", "main")
        draft = params.get("draft", False)
        labels = params.get("labels", [])
        reviewers = params.get("reviewers", [])
        cwd = params.get("cwd")

        # Build command
        args = ['pr', 'create', '--title', title, '--base', base]

        if body:
            args.extend(['--body', body])
        else:
            args.append('--fill')  # Auto-fill from commits

        if draft:
            args.append('--draft')

        for label in labels:
            args.extend(['--label', label])

        for reviewer in reviewers:
            args.extend(['--reviewer', reviewer])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to create PR: {result['stderr']}")

        # Extract PR URL from output
        pr_url = result['stdout'].strip()

        # Extract PR number from URL
        pr_number = None
        match = re.search(r'/pull/(\d+)', pr_url)
        if match:
            pr_number = int(match.group(1))

        return ToolResult.ok(
            data={
                "pr_number": pr_number,
                "url": pr_url,
                "title": title,
                "base": base,
                "draft": draft,
            },
            summary=f"Created PR #{pr_number}: {title}",
        )


@register_tool
class GHPRListTool(BaseTool):
    """
    List open pull requests.
    """

    name = "gh_pr_list"
    description = "List open pull requests"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="state",
            type="string",
            description="PR state: 'open', 'closed', 'merged', 'all'",
            required=False,
            default="open",
        ),
        ToolParam(
            name="author",
            type="string",
            description="Filter by author",
            required=False,
            default=None,
        ),
        ToolParam(
            name="label",
            type="string",
            description="Filter by label",
            required=False,
            default=None,
        ),
        ToolParam(
            name="limit",
            type="int",
            description="Maximum number of PRs to return",
            required=False,
            default=10,
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
        """List PRs."""
        import json

        state = params.get("state", "open")
        author = params.get("author")
        label = params.get("label")
        limit = params.get("limit", 10)
        cwd = params.get("cwd")

        # Build command
        args = ['pr', 'list', '--state', state, '--limit', str(limit),
                '--json', 'number,title,author,state,createdAt,updatedAt,labels,reviewDecision']

        if author:
            args.extend(['--author', author])
        if label:
            args.extend(['--label', label])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to list PRs: {result['stderr']}")

        prs = json.loads(result['stdout'])

        # Simplify output
        pr_list = []
        for pr in prs:
            pr_list.append({
                "number": pr.get('number'),
                "title": pr.get('title'),
                "author": pr.get('author', {}).get('login', ''),
                "state": pr.get('state'),
                "review_status": pr.get('reviewDecision', 'PENDING'),
                "labels": [l.get('name') for l in pr.get('labels', [])],
            })

        return ToolResult.ok(
            data={
                "prs": pr_list,
                "count": len(pr_list),
                "state_filter": state,
            },
            summary=f"Found {len(pr_list)} {state} PR(s)",
        )


@register_tool
class GHPRReviewTool(BaseTool):
    """
    Submit a review on a pull request.
    """

    name = "gh_pr_review"
    description = "Submit a review on a pull request"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="pr_number",
            type="int",
            description="Pull request number",
            required=True,
        ),
        ToolParam(
            name="action",
            type="string",
            description="Review action: 'approve', 'request-changes', 'comment'",
            required=True,
        ),
        ToolParam(
            name="body",
            type="string",
            description="Review comment",
            required=False,
            default="",
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
        """Submit PR review."""
        pr_number = params["pr_number"]
        action = params["action"].lower()
        body = params.get("body", "")
        cwd = params.get("cwd")

        # Validate action
        valid_actions = ['approve', 'request-changes', 'comment']
        if action not in valid_actions:
            return ToolResult.fail(f"Invalid action: {action}. Use one of: {valid_actions}")

        # Build command
        args = ['pr', 'review', str(pr_number), f'--{action}']

        if body:
            args.extend(['--body', body])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to submit review: {result['stderr']}")

        return ToolResult.ok(
            data={
                "pr_number": pr_number,
                "action": action,
                "body": body[:100] if body else "",
            },
            summary=f"Submitted '{action}' review on PR #{pr_number}",
        )


@register_tool
class GHIssueCreateTool(BaseTool):
    """
    Create a GitHub issue.
    """

    name = "gh_issue_create"
    description = "Create a new GitHub issue"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="title",
            type="string",
            description="Issue title",
            required=True,
        ),
        ToolParam(
            name="body",
            type="string",
            description="Issue description/body",
            required=False,
            default="",
        ),
        ToolParam(
            name="labels",
            type="list",
            description="Labels to add",
            required=False,
            default=[],
        ),
        ToolParam(
            name="assignees",
            type="list",
            description="Users to assign",
            required=False,
            default=[],
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
        """Create issue."""
        title = params["title"]
        body = params.get("body", "")
        labels = params.get("labels", [])
        assignees = params.get("assignees", [])
        cwd = params.get("cwd")

        # Build command
        args = ['issue', 'create', '--title', title]

        if body:
            args.extend(['--body', body])

        for label in labels:
            args.extend(['--label', label])

        for assignee in assignees:
            args.extend(['--assignee', assignee])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to create issue: {result['stderr']}")

        # Extract issue URL from output
        issue_url = result['stdout'].strip()

        # Extract issue number from URL
        issue_number = None
        match = re.search(r'/issues/(\d+)', issue_url)
        if match:
            issue_number = int(match.group(1))

        return ToolResult.ok(
            data={
                "issue_number": issue_number,
                "url": issue_url,
                "title": title,
            },
            summary=f"Created issue #{issue_number}: {title}",
        )


@register_tool
class GHIssueListTool(BaseTool):
    """
    List GitHub issues.
    """

    name = "gh_issue_list"
    description = "List GitHub issues"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="state",
            type="string",
            description="Issue state: 'open', 'closed', 'all'",
            required=False,
            default="open",
        ),
        ToolParam(
            name="label",
            type="string",
            description="Filter by label",
            required=False,
            default=None,
        ),
        ToolParam(
            name="assignee",
            type="string",
            description="Filter by assignee",
            required=False,
            default=None,
        ),
        ToolParam(
            name="limit",
            type="int",
            description="Maximum number of issues to return",
            required=False,
            default=10,
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
        """List issues."""
        import json

        state = params.get("state", "open")
        label = params.get("label")
        assignee = params.get("assignee")
        limit = params.get("limit", 10)
        cwd = params.get("cwd")

        # Build command
        args = ['issue', 'list', '--state', state, '--limit', str(limit),
                '--json', 'number,title,author,state,createdAt,labels,assignees']

        if label:
            args.extend(['--label', label])
        if assignee:
            args.extend(['--assignee', assignee])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to list issues: {result['stderr']}")

        issues = json.loads(result['stdout'])

        # Simplify output
        issue_list = []
        for issue in issues:
            issue_list.append({
                "number": issue.get('number'),
                "title": issue.get('title'),
                "author": issue.get('author', {}).get('login', ''),
                "state": issue.get('state'),
                "labels": [l.get('name') for l in issue.get('labels', [])],
                "assignees": [a.get('login') for a in issue.get('assignees', [])],
            })

        return ToolResult.ok(
            data={
                "issues": issue_list,
                "count": len(issue_list),
                "state_filter": state,
            },
            summary=f"Found {len(issue_list)} {state} issue(s)",
        )


@register_tool
class GHIssueCommentTool(BaseTool):
    """
    Add a comment to an issue or pull request.
    """

    name = "gh_issue_comment"
    description = "Add a comment to an issue or pull request"
    category = ToolCategory.GIT

    parameters = [
        ToolParam(
            name="number",
            type="int",
            description="Issue or PR number",
            required=True,
        ),
        ToolParam(
            name="body",
            type="string",
            description="Comment text",
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
        """Add comment."""
        number = params["number"]
        body = params["body"]
        cwd = params.get("cwd")

        # Build command
        args = ['issue', 'comment', str(number), '--body', body]

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to add comment: {result['stderr']}")

        return ToolResult.ok(
            data={
                "number": number,
                "comment_added": True,
            },
            summary=f"Added comment to #{number}",
        )


# Convenience functions

def gh_pr_create(title: str, body: str = "", base: str = "main", cwd: Optional[str] = None) -> Dict[str, Any]:
    """Create a PR."""
    tool = GHPRCreateTool()
    result = tool(title=title, body=body, base=base, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def gh_pr_list(state: str = "open", limit: int = 10, cwd: Optional[str] = None) -> Dict[str, Any]:
    """List PRs."""
    tool = GHPRListTool()
    result = tool(state=state, limit=limit, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def gh_pr_review(pr_number: int, action: str, body: str = "", cwd: Optional[str] = None) -> Dict[str, Any]:
    """Submit PR review."""
    tool = GHPRReviewTool()
    result = tool(pr_number=pr_number, action=action, body=body, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def gh_issue_create(title: str, body: str = "", cwd: Optional[str] = None) -> Dict[str, Any]:
    """Create an issue."""
    tool = GHIssueCreateTool()
    result = tool(title=title, body=body, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def gh_issue_list(state: str = "open", limit: int = 10, cwd: Optional[str] = None) -> Dict[str, Any]:
    """List issues."""
    tool = GHIssueListTool()
    result = tool(state=state, limit=limit, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def gh_issue_comment(number: int, body: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Add comment to issue/PR."""
    tool = GHIssueCommentTool()
    result = tool(number=number, body=body, cwd=cwd)
    return result.data if result.success else {"error": result.error}
