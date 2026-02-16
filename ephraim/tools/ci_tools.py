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


@register_tool
class WaitForCITool(BaseTool):
    """
    Wait for CI run to complete.

    Polls the CI status until completion or timeout.
    """

    name = "wait_for_ci"
    description = "Wait for a CI workflow run to complete"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="run_id",
            type="int",
            description="The workflow run ID to wait for",
            required=False,
            default=None,
        ),
        ToolParam(
            name="timeout",
            type="int",
            description="Maximum seconds to wait (default: 600)",
            required=False,
            default=600,
        ),
        ToolParam(
            name="poll_interval",
            type="int",
            description="Seconds between status checks (default: 30)",
            required=False,
            default=30,
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
        """Wait for CI to complete."""
        import time
        import json

        run_id = params.get("run_id")
        timeout = params.get("timeout", 600)
        poll_interval = params.get("poll_interval", 30)
        cwd = params.get("cwd")

        # If no run_id, get the latest
        if not run_id:
            args = ['run', 'list', '--limit', '1', '--json', 'databaseId']
            result = run_gh_command(args, cwd)
            if result['returncode'] == 0:
                runs = json.loads(result['stdout'])
                if runs:
                    run_id = runs[0]['databaseId']

        if not run_id:
            return ToolResult.fail("No run ID provided and no recent runs found")

        start_time = time.time()
        elapsed = 0

        while elapsed < timeout:
            # Check status
            args = ['run', 'view', str(run_id), '--json', 'status,conclusion,workflowName']
            result = run_gh_command(args, cwd)

            if result['returncode'] != 0:
                return ToolResult.fail(f"Failed to check CI status: {result['stderr']}")

            run_info = json.loads(result['stdout'])
            status = run_info.get('status', '')
            conclusion = run_info.get('conclusion', '')
            workflow = run_info.get('workflowName', 'CI')

            # Check if completed
            if status == 'completed':
                return ToolResult.ok(
                    data={
                        "run_id": run_id,
                        "status": status,
                        "conclusion": conclusion,
                        "workflow": workflow,
                        "wait_time": int(time.time() - start_time),
                        "passed": conclusion == "success",
                    },
                    summary=f"{workflow} {'passed' if conclusion == 'success' else 'failed'} "
                            f"after {int(time.time() - start_time)}s",
                )

            # Still running, wait and poll again
            time.sleep(poll_interval)
            elapsed = time.time() - start_time

        return ToolResult.fail(
            f"Timeout waiting for CI run {run_id} after {timeout}s. "
            f"Last status: {status}"
        )


@register_tool
class AnalyzeCIFailureTool(BaseTool):
    """
    Analyze a CI failure to identify the cause.

    Parses logs and extracts error information, failed tests, and suggestions.
    """

    name = "analyze_ci_failure"
    description = "Analyze a CI failure and identify the cause"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="run_id",
            type="int",
            description="The failed workflow run ID",
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

    # Common error patterns and their categories
    ERROR_PATTERNS = {
        "test_failure": [
            r'FAILED\s+(\S+)',
            r'FAIL\s+(\S+)',
            r'AssertionError',
            r'Expected .* but got',
            r'test.*failed',
        ],
        "syntax_error": [
            r'SyntaxError',
            r'IndentationError',
            r'unexpected token',
            r'Parse error',
        ],
        "import_error": [
            r'ImportError',
            r'ModuleNotFoundError',
            r'cannot find module',
            r'No module named',
        ],
        "type_error": [
            r'TypeError',
            r'is not a function',
            r'is not callable',
            r'undefined is not',
        ],
        "build_error": [
            r'Build failed',
            r'Compilation failed',
            r'error: ',
            r'fatal error',
        ],
        "dependency_error": [
            r'npm ERR!',
            r'pip install.*failed',
            r'Could not resolve dependencies',
            r'Package .* not found',
        ],
        "timeout": [
            r'timed? ?out',
            r'deadline exceeded',
            r'Job exceeded maximum time',
        ],
        "permission_error": [
            r'Permission denied',
            r'EACCES',
            r'not authorized',
        ],
    }

    def execute(self, **params) -> ToolResult:
        """Analyze CI failure."""
        run_id = params["run_id"]
        cwd = params.get("cwd")

        # Get failed logs
        args = ['run', 'view', str(run_id), '--log-failed']
        result = run_gh_command(args, cwd, timeout=120)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to get CI logs: {result['stderr']}")

        logs = result['stdout']

        # Analyze the logs
        analysis = self._analyze_logs(logs)

        return ToolResult.ok(
            data={
                "run_id": run_id,
                "error_category": analysis["category"],
                "error_summary": analysis["summary"],
                "failed_tests": analysis["failed_tests"],
                "error_details": analysis["details"],
                "affected_files": analysis["affected_files"],
                "log_excerpt": logs[:5000] if len(logs) > 5000 else logs,
            },
            summary=f"CI failed: {analysis['category']} - {analysis['summary'][:100]}",
        )

    def _analyze_logs(self, logs: str) -> Dict[str, Any]:
        """Analyze logs to categorize and extract error information."""
        category = "unknown"
        summary = "Unknown failure"
        failed_tests: List[str] = []
        details: List[str] = []
        affected_files: List[str] = []

        # Find error category
        for cat, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, logs, re.IGNORECASE):
                    category = cat
                    break
            if category != "unknown":
                break

        # Extract failed test names
        test_patterns = [
            r'FAILED\s+(\S+::\S+)',
            r'FAIL\s+(\S+\.test\.\w+)',
            r'✕\s+(\S+)',
        ]
        for pattern in test_patterns:
            matches = re.findall(pattern, logs)
            failed_tests.extend(matches[:10])  # Limit to 10

        # Extract error messages
        error_line_patterns = [
            r'Error:\s*(.+)',
            r'error\[\w+\]:\s*(.+)',
            r'AssertionError:\s*(.+)',
            r'TypeError:\s*(.+)',
        ]
        for pattern in error_line_patterns:
            matches = re.findall(pattern, logs)
            details.extend(matches[:5])  # Limit to 5

        # Extract affected files
        file_patterns = [
            r'(\S+\.(?:py|js|ts|jsx|tsx)):(\d+)',
            r'at (\S+\.(?:py|js|ts)):(\d+)',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, logs)
            for match in matches[:5]:
                affected_files.append(f"{match[0]}:{match[1]}")

        # Generate summary
        if failed_tests:
            summary = f"{len(failed_tests)} test(s) failed: {', '.join(failed_tests[:3])}"
        elif details:
            summary = details[0][:200]
        else:
            # Try to extract the most relevant error line
            for line in logs.split('\n'):
                if any(keyword in line.lower() for keyword in ['error', 'fail', 'exception']):
                    summary = line.strip()[:200]
                    break

        return {
            "category": category,
            "summary": summary,
            "failed_tests": list(set(failed_tests)),
            "details": list(set(details)),
            "affected_files": list(set(affected_files)),
        }


@register_tool
class SuggestCIFixTool(BaseTool):
    """
    Suggest fixes for CI failures based on analysis.

    Uses error patterns to suggest specific fix actions.
    """

    name = "suggest_ci_fix"
    description = "Suggest fixes for a CI failure"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="run_id",
            type="int",
            description="The failed workflow run ID",
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

    # Fix suggestions by error category
    FIX_SUGGESTIONS = {
        "test_failure": [
            "Read the failing test file to understand what's being tested",
            "Read the implementation file being tested",
            "Run the test locally with verbose output",
            "Check if test expectations need updating",
        ],
        "syntax_error": [
            "Read the file mentioned in the error",
            "Check for missing brackets, quotes, or colons",
            "Verify indentation (especially in Python)",
            "Run a linter on the file",
        ],
        "import_error": [
            "Check if the module is in requirements.txt/package.json",
            "Verify the import path is correct",
            "Check for circular import issues",
            "Install missing dependencies locally",
        ],
        "type_error": [
            "Read the file at the error location",
            "Check function signatures and arguments",
            "Verify variable types",
            "Add type annotations if using TypeScript",
        ],
        "build_error": [
            "Check build configuration files",
            "Verify all dependencies are installed",
            "Check for missing environment variables",
            "Run build locally to reproduce",
        ],
        "dependency_error": [
            "Update package-lock.json or requirements.txt",
            "Check for conflicting dependency versions",
            "Clear dependency cache and reinstall",
            "Verify package names are correct",
        ],
        "timeout": [
            "Optimize slow tests or operations",
            "Increase timeout limits in CI config",
            "Split large jobs into smaller ones",
            "Add caching to CI workflow",
        ],
        "permission_error": [
            "Check file permissions in the repository",
            "Verify CI has necessary access tokens",
            "Check if files are committed correctly",
            "Review GitHub Actions permissions",
        ],
        "unknown": [
            "Review the full CI logs",
            "Try running the workflow locally",
            "Check recent changes that might have caused the failure",
            "Compare with previous successful runs",
        ],
    }

    def execute(self, **params) -> ToolResult:
        """Suggest fixes for CI failure."""
        run_id = params["run_id"]
        cwd = params.get("cwd")

        # First analyze the failure
        analyze_tool = AnalyzeCIFailureTool()
        analysis_result = analyze_tool(run_id=run_id, cwd=cwd)

        if not analysis_result.success:
            return ToolResult.fail(f"Could not analyze failure: {analysis_result.error}")

        analysis = analysis_result.data
        category = analysis.get("error_category", "unknown")
        affected_files = analysis.get("affected_files", [])
        failed_tests = analysis.get("failed_tests", [])

        # Get suggestions for this category
        suggestions = self.FIX_SUGGESTIONS.get(category, self.FIX_SUGGESTIONS["unknown"])

        # Build specific actions
        fix_actions: List[Dict[str, Any]] = []

        # Add file-specific actions
        for file_ref in affected_files[:3]:
            filepath = file_ref.split(':')[0]
            fix_actions.append({
                "action": "read_file",
                "params": {"path": filepath},
                "reason": f"Read affected file to understand the error context",
            })

        # Add test-specific actions
        for test in failed_tests[:3]:
            # Extract file from test name
            if '::' in test:
                test_file = test.split('::')[0]
                fix_actions.append({
                    "action": "read_file",
                    "params": {"path": test_file},
                    "reason": f"Read failing test: {test}",
                })

        return ToolResult.ok(
            data={
                "run_id": run_id,
                "error_category": category,
                "general_suggestions": suggestions,
                "specific_actions": fix_actions,
                "affected_files": affected_files,
                "failed_tests": failed_tests,
            },
            summary=f"Suggested {len(suggestions)} general fixes and {len(fix_actions)} specific actions",
        )


@register_tool
class TriggerWorkflowTool(BaseTool):
    """
    Manually trigger a GitHub Actions workflow.
    """

    name = "trigger_workflow"
    description = "Trigger a GitHub Actions workflow manually"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="workflow",
            type="string",
            description="Workflow filename (e.g., 'ci.yml') or name",
            required=True,
        ),
        ToolParam(
            name="ref",
            type="string",
            description="Branch or tag to run on (default: current branch)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="inputs",
            type="dict",
            description="Workflow inputs as key-value pairs",
            required=False,
            default={},
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
        """Trigger workflow."""
        import json
        import subprocess

        workflow = params["workflow"]
        ref = params.get("ref")
        inputs = params.get("inputs", {})
        cwd = params.get("cwd")

        # Get current branch if ref not specified
        if not ref:
            try:
                result = subprocess.run(
                    ['git', 'branch', '--show-current'],
                    cwd=cwd or os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                ref = result.stdout.strip() or "main"
            except Exception:
                ref = "main"

        # Build command
        args = ['workflow', 'run', workflow, '--ref', ref]

        # Add inputs
        for key, value in inputs.items():
            args.extend(['-f', f'{key}={value}'])

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            return ToolResult.fail(f"Failed to trigger workflow: {result['stderr']}")

        return ToolResult.ok(
            data={
                "workflow": workflow,
                "ref": ref,
                "inputs": inputs,
                "triggered": True,
            },
            summary=f"Triggered workflow '{workflow}' on {ref}",
        )


@register_tool
class PRStatusTool(BaseTool):
    """
    Get the status of a pull request including checks and reviews.
    """

    name = "pr_status"
    description = "Get PR status including CI checks and review status"
    category = ToolCategory.CI

    parameters = [
        ToolParam(
            name="pr_number",
            type="int",
            description="Pull request number (optional, uses current branch if not specified)",
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
        """Get PR status."""
        import json

        pr_number = params.get("pr_number")
        cwd = params.get("cwd")

        # Build command
        if pr_number:
            args = ['pr', 'view', str(pr_number), '--json',
                    'number,title,state,mergeable,reviewDecision,statusCheckRollup,additions,deletions,changedFiles']
        else:
            # Get PR for current branch
            args = ['pr', 'view', '--json',
                    'number,title,state,mergeable,reviewDecision,statusCheckRollup,additions,deletions,changedFiles']

        result = run_gh_command(args, cwd)

        if result['returncode'] != 0:
            if 'no pull requests found' in result['stderr'].lower():
                return ToolResult.fail("No pull request found for current branch")
            return ToolResult.fail(f"Failed to get PR status: {result['stderr']}")

        pr_info = json.loads(result['stdout'])

        # Parse check status
        checks = pr_info.get('statusCheckRollup', []) or []
        check_summary = {"passed": 0, "failed": 0, "pending": 0}
        for check in checks:
            conclusion = check.get('conclusion', '').lower()
            if conclusion == 'success':
                check_summary["passed"] += 1
            elif conclusion in ('failure', 'cancelled'):
                check_summary["failed"] += 1
            else:
                check_summary["pending"] += 1

        # Determine overall status
        review_decision = pr_info.get('reviewDecision', 'REVIEW_REQUIRED')
        mergeable = pr_info.get('mergeable', 'UNKNOWN')

        overall_status = "ready"
        if check_summary["failed"] > 0:
            overall_status = "failing"
        elif check_summary["pending"] > 0:
            overall_status = "pending"
        elif review_decision == "CHANGES_REQUESTED":
            overall_status = "changes_requested"
        elif review_decision == "REVIEW_REQUIRED":
            overall_status = "needs_review"
        elif mergeable != "MERGEABLE":
            overall_status = "not_mergeable"

        return ToolResult.ok(
            data={
                "pr_number": pr_info.get('number'),
                "title": pr_info.get('title'),
                "state": pr_info.get('state'),
                "overall_status": overall_status,
                "mergeable": mergeable,
                "review_decision": review_decision,
                "checks": check_summary,
                "changes": {
                    "additions": pr_info.get('additions', 0),
                    "deletions": pr_info.get('deletions', 0),
                    "files": pr_info.get('changedFiles', 0),
                },
            },
            summary=f"PR #{pr_info.get('number')}: {overall_status} "
                    f"(checks: {check_summary['passed']}/{sum(check_summary.values())} passed)",
        )


# Additional convenience functions

def wait_for_ci(run_id: Optional[int] = None, timeout: int = 600, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Wait for CI to complete."""
    tool = WaitForCITool()
    result = tool(run_id=run_id, timeout=timeout, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def analyze_ci_failure(run_id: int, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Analyze CI failure."""
    tool = AnalyzeCIFailureTool()
    result = tool(run_id=run_id, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def suggest_ci_fix(run_id: int, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Suggest fixes for CI failure."""
    tool = SuggestCIFixTool()
    result = tool(run_id=run_id, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def trigger_workflow(workflow: str, ref: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Trigger a workflow."""
    tool = TriggerWorkflowTool()
    result = tool(workflow=workflow, ref=ref, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def pr_status(pr_number: Optional[int] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Get PR status."""
    tool = PRStatusTool()
    result = tool(pr_number=pr_number, cwd=cwd)
    return result.data if result.success else {"error": result.error}
