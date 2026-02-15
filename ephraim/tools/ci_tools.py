"""
CI Tools

GitHub Actions CI/CD integration via GitHub CLI.

Commands:
- check_ci_status: Parse `gh run list --limit 1`
- get_ci_logs: Parse `gh run view <id> --log`
- check_ci_result: Parse `gh run view <id>` for pass/fail
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


def get_repo_info(cwd: Optional[str] = None) -> Dict[str, str]:
    """Get repository owner and name from git remote."""
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Parse GitHub URL
            match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', url)
            if match:
                return {
                    "owner": match.group(1),
                    "repo": match.group(2),
                }
    except Exception:
        pass
    return {"owner": "", "repo": ""}


@register_tool
class CheckCIStatusTool(BaseTool):
    """
    Check the latest CI run status.

    Uses `gh run list --limit 1` to get the most recent workflow run.
    """

    name = "check_ci_status"
    description = "Check the latest CI/CD workflow run status"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="workflow",
            type="string",
            description="Specific workflow name to check (optional)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Check CI status."""
        cwd = params.get("cwd")
        workflow = params.get("workflow")

        # Build command
        args = ['run', 'list', '--limit', '1', '--json',
                'databaseId,status,conclusion,name,workflowName,createdAt,updatedAt']

        if workflow:
            args.extend(['--workflow', workflow])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to check CI status: {result['stderr']}")

        # Parse JSON output
        try:
            import json
            runs = json.loads(result['stdout'])

            if not runs:
                return ToolResult.ok(
                    data={
                        "ci_status": "none",
                        "message": "No workflow runs found",
                    },
                    summary="No CI runs found",
                )

            run = runs[0]
            repo_info = get_repo_info(cwd)

            # Calculate duration
            duration = ""
            if run.get('createdAt') and run.get('updatedAt'):
                try:
                    from datetime import datetime
                    created = datetime.fromisoformat(run['createdAt'].replace('Z', '+00:00'))
                    updated = datetime.fromisoformat(run['updatedAt'].replace('Z', '+00:00'))
                    delta = updated - created
                    minutes = int(delta.total_seconds() / 60)
                    duration = f"{minutes}m"
                except Exception:
                    pass

            # Build structured response
            ci_status = {
                "ci_status": run.get('conclusion') or run.get('status', 'unknown'),
                "workflow_name": run.get('workflowName', 'unknown'),
                "run_id": run.get('databaseId'),
                "status": run.get('status', 'unknown'),
                "conclusion": run.get('conclusion', 'pending'),
                "duration": duration,
                "last_run_url": f"https://github.com/{repo_info['owner']}/{repo_info['repo']}/actions/runs/{run.get('databaseId')}"
                                if repo_info['owner'] and run.get('databaseId') else "",
            }

            # Determine overall status
            if run.get('conclusion') == 'success':
                summary = f"CI passed: {run.get('workflowName')}"
            elif run.get('conclusion') == 'failure':
                summary = f"CI failed: {run.get('workflowName')}"
            elif run.get('status') == 'in_progress':
                summary = f"CI running: {run.get('workflowName')}"
            else:
                summary = f"CI status: {run.get('conclusion') or run.get('status')}"

            return ToolResult.ok(data=ci_status, summary=summary)

        except Exception as e:
            return ToolResult.fail(f"Failed to parse CI status: {str(e)}")


@register_tool
class GetCILogsTool(BaseTool):
    """
    Get logs from a CI run.

    Uses `gh run view <id> --log` to fetch and parse logs.
    """

    name = "get_ci_logs"
    description = "Get logs from a CI workflow run"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="run_id",
            type="int",
            description="The workflow run ID",
            required=True,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Repository directory (optional)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="failed_only",
            type="bool",
            description="Only return logs from failed jobs",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Get CI logs."""
        run_id = params["run_id"]
        cwd = params.get("cwd")
        failed_only = params.get("failed_only", True)

        # Get logs
        args = ['run', 'view', str(run_id), '--log']
        if failed_only:
            args.append('--log-failed')

        result = run_gh_command(args, cwd, timeout=120)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to get CI logs: {result['stderr']}")

        logs = result['stdout']

        # Parse for failed tests
        failed_tests = self._parse_failed_tests(logs)

        return ToolResult.ok(
            data={
                "run_id": run_id,
                "logs": logs[:50000],  # Truncate if very long
                "failed_tests": failed_tests,
                "truncated": len(logs) > 50000,
            },
            summary=f"{len(failed_tests)} failed tests found" if failed_tests else "Logs retrieved",
        )

    def _parse_failed_tests(self, logs: str) -> List[Dict[str, Any]]:
        """Parse logs to extract failed test information."""
        failed_tests: List[Dict[str, Any]] = []

        # Common test failure patterns
        patterns = [
            # pytest
            r'(?P<test_name>\S+::test_\w+)\s+(?:FAILED|ERROR)',
            r'FAILED\s+(?P<test_name>\S+::test_\w+)',
            # Jest
            r'FAIL\s+(?P<test_name>\S+\.test\.\w+)',
            # Generic assertion errors
            r'(?P<file>\w+\.py):(?P<line>\d+).*(?P<error>AssertionError|Error|Exception):\s*(?P<message>.+)',
        ]

        for line in logs.split('\n'):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groupdict()
                    test_info = {
                        "test_name": groups.get('test_name', ''),
                        "error_type": groups.get('error', 'TestFailure'),
                        "message": groups.get('message', ''),
                        "file": groups.get('file', ''),
                        "line": int(groups['line']) if groups.get('line') else None,
                    }
                    # Avoid duplicates
                    if test_info['test_name'] and test_info not in failed_tests:
                        failed_tests.append(test_info)
                    break

        return failed_tests


@register_tool
class CheckCIResultTool(BaseTool):
    """
    Check if a specific CI run passed or failed.

    Simpler than get_ci_logs - just returns pass/fail status.
    """

    name = "check_ci_result"
    description = "Check if a CI run passed or failed"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="run_id",
            type="int",
            description="The workflow run ID",
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
        """Check CI result."""
        run_id = params["run_id"]
        cwd = params.get("cwd")

        # Get run info
        args = ['run', 'view', str(run_id), '--json', 'status,conclusion']

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to check CI result: {result['stderr']}")

        try:
            import json
            run_info = json.loads(result['stdout'])

            status = run_info.get('status', 'unknown')
            conclusion = run_info.get('conclusion', 'unknown')

            ci_result = {
                "ci_status": "passed" if conclusion == "success" else conclusion,
                "run_id": run_id,
                "status": status,
                "conclusion": conclusion,
            }

            if conclusion == "success":
                summary = f"CI run {run_id} passed"
            elif conclusion == "failure":
                summary = f"CI run {run_id} failed"
            elif status == "in_progress":
                summary = f"CI run {run_id} in progress"
            else:
                summary = f"CI run {run_id}: {conclusion}"

            return ToolResult.ok(data=ci_result, summary=summary)

        except Exception as e:
            return ToolResult.fail(f"Failed to parse CI result: {str(e)}")


# Convenience functions for direct use

def check_ci_status(cwd: Optional[str] = None) -> Dict[str, Any]:
    """Check latest CI status."""
    tool = CheckCIStatusTool()
    result = tool(cwd=cwd)
    return result.data if result.success else {"error": result.error}


def get_ci_logs(run_id: int, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Get CI logs for a run."""
    tool = GetCILogsTool()
    result = tool(run_id=run_id, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def check_ci_result(run_id: int, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Check if CI run passed."""
    tool = CheckCIResultTool()
    result = tool(run_id=run_id, cwd=cwd)
    return result.data if result.success else {"error": result.error}
