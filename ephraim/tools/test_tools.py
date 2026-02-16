"""
Test Tools

Smart test running and analysis capabilities.

Commands:
- run_tests: Run tests with intelligent framework detection
- analyze_test_failure: Parse and explain test failures
- suggest_test_fix: Propose fixes for failing tests
- coverage_report: Generate coverage summary
"""

import os
import re
import subprocess
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def run_command(
    command: List[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Run a command and return result.

    Returns dict with: returncode, stdout, stderr
    """
    try:
        result = subprocess.run(
            command,
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
            "stderr": f"Command timed out after {timeout}s",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


def detect_test_framework(cwd: Optional[str] = None) -> Dict[str, Any]:
    """Detect the test framework used in the project."""
    cwd = cwd or os.getcwd()

    framework = {
        "name": "unknown",
        "command": None,
        "config_file": None,
    }

    # Check for Python test frameworks
    if os.path.exists(os.path.join(cwd, "pytest.ini")) or \
       os.path.exists(os.path.join(cwd, "pyproject.toml")) or \
       os.path.exists(os.path.join(cwd, "setup.py")):
        # Check for pytest in requirements
        for req_file in ["requirements.txt", "requirements-dev.txt", "setup.py", "pyproject.toml"]:
            path = os.path.join(cwd, req_file)
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        content = f.read()
                        if "pytest" in content:
                            framework = {
                                "name": "pytest",
                                "command": ["pytest", "-v"],
                                "config_file": "pytest.ini" if os.path.exists(os.path.join(cwd, "pytest.ini")) else "pyproject.toml",
                            }
                            break
                except Exception:
                    pass

    # Check for JavaScript/TypeScript test frameworks
    package_json = os.path.join(cwd, "package.json")
    if os.path.exists(package_json):
        try:
            import json
            with open(package_json) as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                scripts = pkg.get("scripts", {})

                if "jest" in deps:
                    framework = {
                        "name": "jest",
                        "command": ["npm", "test"],
                        "config_file": "jest.config.js" if os.path.exists(os.path.join(cwd, "jest.config.js")) else "package.json",
                    }
                elif "mocha" in deps:
                    framework = {
                        "name": "mocha",
                        "command": ["npm", "test"],
                        "config_file": ".mocharc.js" if os.path.exists(os.path.join(cwd, ".mocharc.js")) else "package.json",
                    }
                elif "vitest" in deps:
                    framework = {
                        "name": "vitest",
                        "command": ["npm", "test"],
                        "config_file": "vite.config.ts",
                    }
                elif "test" in scripts:
                    framework = {
                        "name": "npm-test",
                        "command": ["npm", "test"],
                        "config_file": "package.json",
                    }
        except Exception:
            pass

    # Check for Go tests
    if any(f.endswith("_test.go") for f in os.listdir(cwd) if os.path.isfile(os.path.join(cwd, f))):
        framework = {
            "name": "go-test",
            "command": ["go", "test", "-v", "./..."],
            "config_file": "go.mod",
        }

    # Check for Rust tests
    if os.path.exists(os.path.join(cwd, "Cargo.toml")):
        framework = {
            "name": "cargo-test",
            "command": ["cargo", "test"],
            "config_file": "Cargo.toml",
        }

    return framework


@register_tool
class RunTestsTool(BaseTool):
    """
    Run tests with intelligent framework detection.

    Auto-detects pytest, jest, mocha, vitest, go test, cargo test.
    """

    name = "run_tests"
    description = "Run tests with automatic framework detection"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Specific test file or directory to run",
            required=False,
            default=None,
        ),
        ToolParam(
            name="pattern",
            type="string",
            description="Test name pattern to match (e.g., 'test_login')",
            required=False,
            default=None,
        ),
        ToolParam(
            name="verbose",
            type="bool",
            description="Verbose output",
            required=False,
            default=True,
        ),
        ToolParam(
            name="coverage",
            type="bool",
            description="Run with coverage enabled",
            required=False,
            default=False,
        ),
        ToolParam(
            name="timeout",
            type="int",
            description="Timeout in seconds",
            required=False,
            default=300,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Project directory",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Run tests."""
        path = params.get("path")
        pattern = params.get("pattern")
        verbose = params.get("verbose", True)
        coverage = params.get("coverage", False)
        timeout = params.get("timeout", 300)
        cwd = params.get("cwd")

        # Detect framework
        framework = detect_test_framework(cwd)

        if framework["name"] == "unknown":
            return ToolResult.fail("Could not detect test framework. No pytest, jest, mocha, or other test config found.")

        # Build command
        command = list(framework["command"])

        # Add framework-specific options
        if framework["name"] == "pytest":
            if verbose:
                if "-v" not in command:
                    command.append("-v")
            if coverage:
                command.extend(["--cov", "--cov-report=term-missing"])
            if pattern:
                command.extend(["-k", pattern])
            if path:
                command.append(path)

        elif framework["name"] in ["jest", "npm-test", "vitest"]:
            if coverage:
                command.append("--coverage")
            if pattern:
                command.extend(["--", "--testNamePattern", pattern])
            if path:
                command.extend(["--", path])

        elif framework["name"] == "go-test":
            if verbose and "-v" not in command:
                command.append("-v")
            if coverage:
                command.append("-cover")
            if pattern:
                command.extend(["-run", pattern])
            if path:
                command[-1] = path  # Replace ./... with specific path

        elif framework["name"] == "cargo-test":
            if pattern:
                command.append(pattern)

        # Run tests
        result = run_command(command, cwd, timeout)

        # Parse output
        output = result["stdout"] + result["stderr"]
        test_results = self._parse_test_output(output, framework["name"])

        return ToolResult.ok(
            data={
                "framework": framework["name"],
                "command": " ".join(command),
                "passed": result["returncode"] == 0,
                "tests_run": test_results["total"],
                "tests_passed": test_results["passed"],
                "tests_failed": test_results["failed"],
                "tests_skipped": test_results["skipped"],
                "failed_tests": test_results["failed_names"],
                "output": output[:20000],  # Truncate if needed
                "truncated": len(output) > 20000,
            },
            summary=f"{'PASSED' if result['returncode'] == 0 else 'FAILED'}: "
                    f"{test_results['passed']}/{test_results['total']} tests passed",
        )

    def _parse_test_output(self, output: str, framework: str) -> Dict[str, Any]:
        """Parse test output to extract results."""
        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "failed_names": [],
        }

        if framework == "pytest":
            # Parse pytest summary: "5 passed, 2 failed, 1 skipped"
            match = re.search(r'(\d+) passed', output)
            if match:
                results["passed"] = int(match.group(1))

            match = re.search(r'(\d+) failed', output)
            if match:
                results["failed"] = int(match.group(1))

            match = re.search(r'(\d+) skipped', output)
            if match:
                results["skipped"] = int(match.group(1))

            # Extract failed test names
            failed_pattern = r'FAILED\s+(\S+::\S+)'
            results["failed_names"] = re.findall(failed_pattern, output)

        elif framework in ["jest", "vitest"]:
            # Parse jest summary: "Tests: 2 failed, 5 passed, 7 total"
            match = re.search(r'Tests:\s+(?:(\d+) failed,\s+)?(?:(\d+) skipped,\s+)?(\d+) passed,\s+(\d+) total', output)
            if match:
                results["failed"] = int(match.group(1) or 0)
                results["skipped"] = int(match.group(2) or 0)
                results["passed"] = int(match.group(3) or 0)
                results["total"] = int(match.group(4) or 0)

            # Extract failed test names
            failed_pattern = r'FAIL\s+(\S+)'
            results["failed_names"] = re.findall(failed_pattern, output)

        elif framework == "go-test":
            # Parse go test: "--- PASS:" or "--- FAIL:"
            results["passed"] = len(re.findall(r'--- PASS:', output))
            results["failed"] = len(re.findall(r'--- FAIL:', output))
            results["skipped"] = len(re.findall(r'--- SKIP:', output))

            # Extract failed test names
            failed_pattern = r'--- FAIL:\s+(\S+)'
            results["failed_names"] = re.findall(failed_pattern, output)

        results["total"] = results["passed"] + results["failed"] + results["skipped"]
        return results


@register_tool
class AnalyzeTestFailureTool(BaseTool):
    """
    Analyze a test failure to understand the cause.
    """

    name = "analyze_test_failure"
    description = "Analyze a test failure and explain the cause"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="test_output",
            type="string",
            description="Test output containing the failure",
            required=True,
        ),
        ToolParam(
            name="test_name",
            type="string",
            description="Specific test name to analyze",
            required=False,
            default=None,
        ),
    ]

    # Error patterns and their explanations
    ERROR_PATTERNS = {
        "assertion_error": {
            "patterns": [r"AssertionError", r"Expected .* but got", r"to equal", r"to be"],
            "explanation": "Test assertion failed - expected value doesn't match actual value",
            "category": "assertion",
        },
        "type_error": {
            "patterns": [r"TypeError", r"is not a function", r"undefined"],
            "explanation": "Type mismatch or undefined value accessed",
            "category": "type",
        },
        "import_error": {
            "patterns": [r"ImportError", r"ModuleNotFoundError", r"Cannot find module"],
            "explanation": "Missing import or module not installed",
            "category": "import",
        },
        "attribute_error": {
            "patterns": [r"AttributeError", r"has no attribute"],
            "explanation": "Accessing non-existent attribute on object",
            "category": "attribute",
        },
        "key_error": {
            "patterns": [r"KeyError", r"key .* not found"],
            "explanation": "Dictionary key doesn't exist",
            "category": "key",
        },
        "timeout": {
            "patterns": [r"timeout", r"timed out", r"exceeded"],
            "explanation": "Test took too long to complete",
            "category": "timeout",
        },
        "fixture_error": {
            "patterns": [r"fixture .* not found", r"SetUp failed", r"BeforeEach"],
            "explanation": "Test setup/fixture failed",
            "category": "fixture",
        },
    }

    def execute(self, **params) -> ToolResult:
        """Analyze test failure."""
        test_output = params["test_output"]
        test_name = params.get("test_name")

        # Find the error category
        error_category = "unknown"
        explanation = "Unknown test failure"

        for cat, info in self.ERROR_PATTERNS.items():
            for pattern in info["patterns"]:
                if re.search(pattern, test_output, re.IGNORECASE):
                    error_category = info["category"]
                    explanation = info["explanation"]
                    break
            if error_category != "unknown":
                break

        # Extract specific error details
        error_details = self._extract_error_details(test_output)

        # Extract affected file and line
        file_info = self._extract_file_info(test_output)

        return ToolResult.ok(
            data={
                "test_name": test_name,
                "error_category": error_category,
                "explanation": explanation,
                "error_message": error_details.get("message", ""),
                "expected": error_details.get("expected"),
                "actual": error_details.get("actual"),
                "file": file_info.get("file"),
                "line": file_info.get("line"),
                "stack_trace": error_details.get("stack_trace", "")[:2000],
            },
            summary=f"Analysis: {error_category} - {explanation}",
        )

    def _extract_error_details(self, output: str) -> Dict[str, Any]:
        """Extract detailed error information."""
        details = {
            "message": "",
            "expected": None,
            "actual": None,
            "stack_trace": "",
        }

        # Extract error message
        msg_patterns = [
            r"(?:Error|Exception):\s*(.+?)(?:\n|$)",
            r"AssertionError:\s*(.+?)(?:\n|$)",
        ]
        for pattern in msg_patterns:
            match = re.search(pattern, output)
            if match:
                details["message"] = match.group(1).strip()
                break

        # Extract expected vs actual
        exp_patterns = [
            r"Expected[:\s]+(.+?)(?:\n|but|got)",
            r"expected[:\s]+(.+?)(?:\n|but|got)",
        ]
        for pattern in exp_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                details["expected"] = match.group(1).strip()
                break

        act_patterns = [
            r"(?:but got|actual|received)[:\s]+(.+?)(?:\n|$)",
            r"Actual[:\s]+(.+?)(?:\n|$)",
        ]
        for pattern in act_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                details["actual"] = match.group(1).strip()
                break

        # Extract stack trace
        trace_start = output.find("Traceback")
        if trace_start == -1:
            trace_start = output.find("at ")
        if trace_start != -1:
            details["stack_trace"] = output[trace_start:trace_start + 2000]

        return details

    def _extract_file_info(self, output: str) -> Dict[str, Any]:
        """Extract file and line number from error."""
        info = {"file": None, "line": None}

        # Python traceback pattern
        py_pattern = r'File "([^"]+)", line (\d+)'
        match = re.search(py_pattern, output)
        if match:
            info["file"] = match.group(1)
            info["line"] = int(match.group(2))
            return info

        # JavaScript pattern
        js_pattern = r'at .+?\(([^:]+):(\d+):\d+\)'
        match = re.search(js_pattern, output)
        if match:
            info["file"] = match.group(1)
            info["line"] = int(match.group(2))
            return info

        # Generic pattern
        generic_pattern = r'(\S+\.(?:py|js|ts|jsx|tsx|go|rs)):(\d+)'
        match = re.search(generic_pattern, output)
        if match:
            info["file"] = match.group(1)
            info["line"] = int(match.group(2))

        return info


@register_tool
class SuggestTestFixTool(BaseTool):
    """
    Suggest fixes for failing tests.
    """

    name = "suggest_test_fix"
    description = "Suggest fixes for a failing test"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="test_output",
            type="string",
            description="Test output containing the failure",
            required=True,
        ),
        ToolParam(
            name="test_name",
            type="string",
            description="Specific test name",
            required=False,
            default=None,
        ),
    ]

    # Fix suggestions by error category
    FIX_SUGGESTIONS = {
        "assertion": [
            "Update test expectations if the behavior change is intentional",
            "Fix the implementation to return the expected value",
            "Check if test data/fixtures are correct",
            "Verify the test is testing the right thing",
        ],
        "type": [
            "Check for null/undefined values before accessing properties",
            "Verify function signatures and parameter types",
            "Add type guards or null checks",
            "Check import statements are correct",
        ],
        "import": [
            "Install missing package: pip install <package> or npm install <package>",
            "Check import path is correct (relative vs absolute)",
            "Verify the module exists at the specified path",
            "Check for circular import issues",
        ],
        "attribute": [
            "Verify the object has the expected structure",
            "Check for typos in attribute names",
            "Ensure the object is properly initialized",
            "Add defensive checks for optional attributes",
        ],
        "key": [
            "Use .get() method with default value",
            "Check if key exists before accessing",
            "Verify dictionary structure matches expectations",
            "Check for typos in key names",
        ],
        "timeout": [
            "Increase test timeout in configuration",
            "Optimize slow operations in the test",
            "Mock slow external services",
            "Split into smaller, faster tests",
        ],
        "fixture": [
            "Check fixture/setup function for errors",
            "Verify test dependencies are correct",
            "Review fixture scope and lifecycle",
            "Check for resource cleanup issues",
        ],
        "unknown": [
            "Read the error message carefully",
            "Check recent changes to the code",
            "Run the test in isolation",
            "Add more logging/debugging",
        ],
    }

    def execute(self, **params) -> ToolResult:
        """Suggest test fixes."""
        test_output = params["test_output"]
        test_name = params.get("test_name")

        # First analyze the failure
        analyze_tool = AnalyzeTestFailureTool()
        analysis_result = analyze_tool(test_output=test_output, test_name=test_name)

        if not analysis_result.success:
            return ToolResult.fail(f"Could not analyze failure: {analysis_result.error}")

        analysis = analysis_result.data
        category = analysis.get("error_category", "unknown")

        # Get suggestions for this category
        suggestions = self.FIX_SUGGESTIONS.get(category, self.FIX_SUGGESTIONS["unknown"])

        # Build specific actions
        fix_actions: List[Dict[str, Any]] = []

        # If we have file info, suggest reading it
        if analysis.get("file"):
            fix_actions.append({
                "action": "read_file",
                "params": {"path": analysis["file"]},
                "reason": f"Read the file where error occurred (line {analysis.get('line', '?')})",
            })

        # If assertion error with expected/actual, suggest comparing
        if category == "assertion" and analysis.get("expected") and analysis.get("actual"):
            fix_actions.append({
                "action": "compare_values",
                "expected": analysis["expected"],
                "actual": analysis["actual"],
                "reason": "Compare expected vs actual values",
            })

        return ToolResult.ok(
            data={
                "test_name": test_name,
                "error_category": category,
                "analysis": analysis,
                "suggestions": suggestions,
                "specific_actions": fix_actions,
            },
            summary=f"Suggested {len(suggestions)} fixes for {category} error",
        )


@register_tool
class CoverageReportTool(BaseTool):
    """
    Generate a test coverage report.
    """

    name = "coverage_report"
    description = "Generate a test coverage summary"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="format",
            type="string",
            description="Output format: 'summary', 'detailed', 'files'",
            required=False,
            default="summary",
        ),
        ToolParam(
            name="min_coverage",
            type="int",
            description="Minimum coverage percentage to pass",
            required=False,
            default=80,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Project directory",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Generate coverage report."""
        format_type = params.get("format", "summary")
        min_coverage = params.get("min_coverage", 80)
        cwd = params.get("cwd")

        # Detect framework
        framework = detect_test_framework(cwd)

        # Run coverage command
        if framework["name"] == "pytest":
            command = ["pytest", "--cov", "--cov-report=term-missing", "-q"]
        elif framework["name"] in ["jest", "vitest"]:
            command = ["npm", "test", "--", "--coverage"]
        elif framework["name"] == "go-test":
            command = ["go", "test", "-cover", "./..."]
        else:
            return ToolResult.fail(f"Coverage not supported for framework: {framework['name']}")

        result = run_command(command, cwd, timeout=300)

        output = result["stdout"] + result["stderr"]

        # Parse coverage
        coverage_data = self._parse_coverage(output, framework["name"])

        # Check minimum
        passed = coverage_data["total_coverage"] >= min_coverage

        return ToolResult.ok(
            data={
                "framework": framework["name"],
                "total_coverage": coverage_data["total_coverage"],
                "files": coverage_data["files"] if format_type in ["detailed", "files"] else [],
                "uncovered_lines": coverage_data["uncovered_lines"] if format_type == "detailed" else {},
                "passed": passed,
                "min_coverage": min_coverage,
            },
            summary=f"Coverage: {coverage_data['total_coverage']}% "
                    f"({'PASS' if passed else 'FAIL'} - min {min_coverage}%)",
        )

    def _parse_coverage(self, output: str, framework: str) -> Dict[str, Any]:
        """Parse coverage output."""
        data = {
            "total_coverage": 0,
            "files": [],
            "uncovered_lines": {},
        }

        if framework == "pytest":
            # Parse pytest-cov output
            # TOTAL    100    10    90%
            total_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
            if total_match:
                data["total_coverage"] = int(total_match.group(1))

            # Parse file coverage lines
            file_pattern = r'^(\S+\.py)\s+(\d+)\s+(\d+)\s+(\d+)%(?:\s+(.+))?$'
            for line in output.split('\n'):
                match = re.match(file_pattern, line.strip())
                if match:
                    filename = match.group(1)
                    data["files"].append({
                        "file": filename,
                        "statements": int(match.group(2)),
                        "missing": int(match.group(3)),
                        "coverage": int(match.group(4)),
                    })
                    if match.group(5):
                        data["uncovered_lines"][filename] = match.group(5)

        elif framework in ["jest", "vitest"]:
            # Parse jest coverage
            # All files |   90.5 |   85.2 |   92.1 |   88.5 |
            total_match = re.search(r'All files\s*\|\s*([\d.]+)', output)
            if total_match:
                data["total_coverage"] = int(float(total_match.group(1)))

        elif framework == "go-test":
            # Parse go coverage
            # coverage: 85.0% of statements
            total_match = re.search(r'coverage:\s*([\d.]+)%', output)
            if total_match:
                data["total_coverage"] = int(float(total_match.group(1)))

        return data


# Convenience functions

def run_tests(path: Optional[str] = None, pattern: Optional[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Run tests."""
    tool = RunTestsTool()
    result = tool(path=path, pattern=pattern, cwd=cwd)
    return result.data if result.success else {"error": result.error}


def analyze_test_failure(test_output: str, test_name: Optional[str] = None) -> Dict[str, Any]:
    """Analyze test failure."""
    tool = AnalyzeTestFailureTool()
    result = tool(test_output=test_output, test_name=test_name)
    return result.data if result.success else {"error": result.error}


def suggest_test_fix(test_output: str, test_name: Optional[str] = None) -> Dict[str, Any]:
    """Suggest test fixes."""
    tool = SuggestTestFixTool()
    result = tool(test_output=test_output, test_name=test_name)
    return result.data if result.success else {"error": result.error}


def coverage_report(cwd: Optional[str] = None) -> Dict[str, Any]:
    """Generate coverage report."""
    tool = CoverageReportTool()
    result = tool(cwd=cwd)
    return result.data if result.success else {"error": result.error}
