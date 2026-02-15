"""
Run Command Tool

Executes shell commands with:
- Live streaming output to terminal
- Full capture of stdout/stderr internally
- Exit code capture
- Timeout handling
"""

import os
import subprocess
import sys
import threading
import queue
from typing import Optional, Dict, Any

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


@register_tool
class RunCommandTool(BaseTool):
    """
    Execute a shell command.

    Features:
    - Streams output live to terminal
    - Captures full output internally
    - Handles timeouts gracefully
    - Returns structured result
    """

    name = "run_command"
    description = "Execute a shell command and return the result"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="command",
            type="string",
            description="The command to execute",
            required=True,
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Working directory for the command",
            required=False,
            default=None,
        ),
        ToolParam(
            name="timeout",
            type="int",
            description="Timeout in seconds",
            required=False,
            default=120,
        ),
        ToolParam(
            name="stream_output",
            type="bool",
            description="Whether to stream output to terminal",
            required=False,
            default=True,
        ),
    ]

    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        'rm -rf /',
        'rm -rf ~',
        'rm -rf *',
        '> /dev/sda',
        'mkfs.',
        ':(){:|:&};:',  # Fork bomb
        'dd if=/dev/',
        'chmod -R 777 /',
        'chown -R',
    ]

    def execute(self, **params) -> ToolResult:
        """Execute the command."""
        command = params["command"]
        cwd = params.get("cwd")
        timeout = params.get("timeout", 120)
        stream_output = params.get("stream_output", True)

        # Validate command
        validation_error = self._validate_command(command)
        if validation_error:
            return ToolResult.fail(validation_error)

        # Resolve working directory
        if cwd:
            cwd = os.path.abspath(os.path.expanduser(cwd))
            if not os.path.isdir(cwd):
                return ToolResult.fail(f"Working directory not found: {cwd}")
        else:
            cwd = os.getcwd()

        # Execute command
        try:
            result = self._run_with_streaming(
                command=command,
                cwd=cwd,
                timeout=timeout,
                stream=stream_output,
            )
            return result

        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                "Timeout exceeded",
                data={
                    "command": command,
                    "exit_code": 124,  # Standard timeout exit code
                    "error": "Timeout exceeded",
                },
            )
        except Exception as e:
            return ToolResult.fail(f"Command execution failed: {str(e)}")

    def _validate_command(self, command: str) -> Optional[str]:
        """
        Validate command for dangerous patterns.

        Returns error message or None if safe.
        """
        command_lower = command.lower()

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in command_lower:
                return f"Dangerous command pattern detected: {pattern}"

        return None

    def _run_with_streaming(
        self,
        command: str,
        cwd: str,
        timeout: int,
        stream: bool,
    ) -> ToolResult:
        """
        Run command with optional live streaming.

        Uses subprocess with real-time output capture.
        """
        # Determine shell
        if sys.platform == 'win32':
            shell_cmd = ['cmd', '/c', command]
        else:
            shell_cmd = ['bash', '-c', command]

        # Start process
        process = subprocess.Popen(
            shell_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        def read_stream(pipe, lines_list, is_stderr=False):
            """Read from a pipe and optionally stream to terminal."""
            try:
                for line in iter(pipe.readline, ''):
                    lines_list.append(line)
                    if stream:
                        target = sys.stderr if is_stderr else sys.stdout
                        target.write(line)
                        target.flush()
            except Exception:
                pass
            finally:
                pipe.close()

        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(
            target=read_stream,
            args=(process.stdout, stdout_lines, False),
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(process.stderr, stderr_lines, True),
        )

        stdout_thread.start()
        stderr_thread.start()

        # Wait for process with timeout
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            raise

        # Wait for threads to complete
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        # Combine output
        stdout = ''.join(stdout_lines)
        stderr = ''.join(stderr_lines)
        exit_code = process.returncode

        # Generate summary
        summary = self._generate_summary(command, exit_code, stdout, stderr)

        return ToolResult(
            success=exit_code == 0,
            data={
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "summary": summary,
                "cwd": cwd,
            },
            error=stderr if exit_code != 0 else None,
            summary=summary,
        )

    def _generate_summary(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> str:
        """Generate a concise summary of command execution."""
        if exit_code == 0:
            # Check for test results
            if 'pytest' in command or 'test' in command.lower():
                return self._summarize_test_output(stdout)
            return f"Command succeeded (exit code 0)"
        else:
            # Extract key error message
            error_lines = stderr.strip().split('\n')
            if error_lines:
                last_error = error_lines[-1][:100]
                return f"Command failed (exit code {exit_code}): {last_error}"
            return f"Command failed (exit code {exit_code})"

    def _summarize_test_output(self, output: str) -> str:
        """Extract test summary from output."""
        lines = output.split('\n')

        for line in reversed(lines):
            line = line.strip()
            # pytest style
            if 'passed' in line or 'failed' in line or 'error' in line:
                if any(c.isdigit() for c in line):
                    return line[:100]
            # unittest style
            if line.startswith('OK') or line.startswith('FAILED'):
                return line[:100]

        return "Tests completed"


def run_command_simple(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Simple command execution without streaming.

    For use in tools that need quick command execution.
    """
    try:
        if sys.platform == 'win32':
            shell_cmd = ['cmd', '/c', command]
        else:
            shell_cmd = ['bash', '-c', command]

        result = subprocess.run(
            shell_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": 124,
            "error": "Timeout exceeded",
        }
    except Exception as e:
        return {
            "command": command,
            "exit_code": 1,
            "error": str(e),
        }
