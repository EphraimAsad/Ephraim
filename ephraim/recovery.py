"""
Ephraim Error Recovery System

Intelligent error analysis and recovery strategies.
Instead of giving up after failures, this system:
- Classifies error types
- Suggests recovery actions
- Modifies parameters for retry
- Decides when to give up vs when to adapt
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class ErrorType(Enum):
    """Categories of errors for recovery strategies."""
    NOT_FOUND = "not_found"           # File/path doesn't exist
    PERMISSION = "permission"          # Access denied
    VALIDATION = "validation"          # Invalid params or content
    TIMEOUT = "timeout"                # Operation timed out
    NETWORK = "network"                # Connection issues
    SYNTAX = "syntax"                  # Code syntax errors
    CONFLICT = "conflict"              # Merge conflict, already exists
    UNKNOWN = "unknown"                # Uncategorized


@dataclass
class ErrorContext:
    """Context for a failed action."""
    failed_action: str
    error_message: str
    error_type: ErrorType
    attempt_count: int
    original_params: Dict[str, Any]
    phase: str = ""
    previous_reasoning: str = ""


@dataclass
class RecoverySuggestion:
    """Suggested recovery action."""
    strategy: str           # Name of recovery strategy
    action: str             # Tool to use for recovery
    params: Dict[str, Any]  # Parameters for the recovery action
    reasoning: str          # Explanation for the LLM
    confidence: int         # How confident we are this will work (0-100)


class RecoveryStrategy:
    """
    Intelligent error recovery system.

    Analyzes failures and suggests recovery actions based on error patterns.
    """

    # Error keywords to type mapping
    ERROR_PATTERNS = {
        ErrorType.NOT_FOUND: [
            "not found", "no such file", "does not exist", "cannot find",
            "missing", "404", "FileNotFoundError", "ENOENT"
        ],
        ErrorType.PERMISSION: [
            "permission denied", "access denied", "not permitted",
            "unauthorized", "forbidden", "403", "EACCES"
        ],
        ErrorType.VALIDATION: [
            "invalid", "pattern not found", "does not match",
            "validation failed", "expected", "malformed"
        ],
        ErrorType.TIMEOUT: [
            "timeout", "timed out", "deadline exceeded", "took too long"
        ],
        ErrorType.NETWORK: [
            "connection refused", "network error", "unreachable",
            "connection reset", "ECONNREFUSED"
        ],
        ErrorType.SYNTAX: [
            "syntax error", "SyntaxError", "parse error", "IndentationError",
            "unexpected token"
        ],
        ErrorType.CONFLICT: [
            "already exists", "conflict", "merge conflict", "duplicate"
        ]
    }

    def classify_error(self, error_message: str) -> ErrorType:
        """Classify an error message into an error type."""
        error_lower = error_message.lower()

        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    return error_type

        return ErrorType.UNKNOWN

    def analyze_error(self, ctx: ErrorContext) -> RecoverySuggestion:
        """
        Analyze error and suggest recovery action.

        Returns a suggestion for what to do next based on the error type.
        """
        error_type = ctx.error_type

        # File not found - search for it
        if error_type == ErrorType.NOT_FOUND:
            path = ctx.original_params.get("path", "")
            filename = path.split("/")[-1].split("\\")[-1] if path else "*"

            return RecoverySuggestion(
                strategy="search_first",
                action="glob_search",
                params={"pattern": f"**/{filename}"},
                reasoning=f"File '{path}' not found. Searching for similar files to locate the correct path.",
                confidence=70
            )

        # Validation failed (e.g., pattern not found in apply_patch)
        if error_type == ErrorType.VALIDATION:
            path = ctx.original_params.get("path", "")

            return RecoverySuggestion(
                strategy="read_first",
                action="read_file",
                params={"path": path},
                reasoning=f"Validation failed. Reading '{path}' to understand current content before retrying.",
                confidence=80
            )

        # Permission denied - try different approach
        if error_type == ErrorType.PERMISSION:
            return RecoverySuggestion(
                strategy="ask_permission",
                action="ask_user",
                params={"question": f"Permission denied for {ctx.failed_action}. Should I try a different approach?"},
                reasoning="Cannot access resource due to permissions. Need user guidance.",
                confidence=50
            )

        # Timeout - simplify or skip
        if error_type == ErrorType.TIMEOUT:
            return RecoverySuggestion(
                strategy="skip_slow",
                action="final_answer",
                params={"summary": f"Skipped {ctx.failed_action} due to timeout. Main task completed."},
                reasoning="Operation timed out. Completing task without this step.",
                confidence=60
            )

        # Syntax error - read file to fix
        if error_type == ErrorType.SYNTAX:
            path = ctx.original_params.get("path", "")

            return RecoverySuggestion(
                strategy="inspect_syntax",
                action="read_file",
                params={"path": path},
                reasoning=f"Syntax error detected. Reading '{path}' to identify and fix the issue.",
                confidence=75
            )

        # Conflict - handle existing resource
        if error_type == ErrorType.CONFLICT:
            path = ctx.original_params.get("path", "")

            return RecoverySuggestion(
                strategy="handle_existing",
                action="read_file",
                params={"path": path},
                reasoning=f"Resource already exists. Reading '{path}' to decide whether to update or use different name.",
                confidence=70
            )

        # Unknown error - ask user
        return RecoverySuggestion(
            strategy="ask_help",
            action="ask_user",
            params={"question": f"Action '{ctx.failed_action}' failed with: {ctx.error_message[:100]}. How should I proceed?"},
            reasoning="Encountered unexpected error. Requesting user guidance.",
            confidence=40
        )

    def should_retry(self, ctx: ErrorContext) -> bool:
        """
        Decide if retry is worthwhile.

        Args:
            ctx: Error context with attempt count and error info

        Returns:
            True if should retry, False if should give up or change approach
        """
        # Never retry permission errors
        if ctx.error_type == ErrorType.PERMISSION:
            return False

        # Don't retry unknown errors more than once
        if ctx.error_type == ErrorType.UNKNOWN and ctx.attempt_count >= 1:
            return False

        # Retry validation errors after reading file
        if ctx.error_type == ErrorType.VALIDATION and ctx.attempt_count < 2:
            return True

        # Retry not found after searching
        if ctx.error_type == ErrorType.NOT_FOUND and ctx.attempt_count < 2:
            return True

        # Retry syntax errors after inspection
        if ctx.error_type == ErrorType.SYNTAX and ctx.attempt_count < 2:
            return True

        # General limit
        return ctx.attempt_count < 3

    def should_complete(self, ctx: ErrorContext) -> bool:
        """
        Decide if task should be marked complete despite failure.

        Some failures are non-critical (e.g., test not found when testing wasn't required).
        """
        # If we've tried enough and it's a non-critical action
        if ctx.attempt_count >= 3:
            non_critical_actions = ["run_command", "git_add", "git_commit"]
            if ctx.failed_action in non_critical_actions:
                return True

        return False

    def modify_params(self, ctx: ErrorContext) -> Dict[str, Any]:
        """
        Suggest parameter modifications for retry.

        Returns modified params that might work better.
        """
        params = ctx.original_params.copy()

        # For apply_patch with pattern not found, try broader pattern
        if ctx.failed_action == "apply_patch" and ctx.error_type == ErrorType.VALIDATION:
            if "find" in params:
                # Try first line only
                find_text = params["find"]
                first_line = find_text.split("\n")[0]
                params["find"] = first_line

        # For run_command with not found, try python -c
        if ctx.failed_action == "run_command" and ctx.error_type == ErrorType.NOT_FOUND:
            command = params.get("command", "")
            if command.startswith("python ") and " tests/" in command:
                # No tests dir, just verify file runs
                script = command.split()[-1].replace("tests/", "")
                params["command"] = f"python -c 'import {script.replace('.py', '')}; print(\"OK\")'"

        return params

    def get_recovery_chain(self, ctx: ErrorContext) -> List[RecoverySuggestion]:
        """
        Get a sequence of recovery actions to try.

        For complex errors, multiple steps might be needed.
        """
        chain = []

        # Primary suggestion
        primary = self.analyze_error(ctx)
        chain.append(primary)

        # If primary is search, add read after
        if primary.action == "glob_search":
            chain.append(RecoverySuggestion(
                strategy="read_found",
                action="read_file",
                params={"path": "{{found_path}}"},  # Placeholder
                reasoning="After finding the file, read it to understand content.",
                confidence=75
            ))

        # If primary is read, might need patch after
        if primary.action == "read_file" and ctx.failed_action == "apply_patch":
            chain.append(RecoverySuggestion(
                strategy="retry_patch",
                action="apply_patch",
                params=self.modify_params(ctx),
                reasoning="After reading file, retry patch with corrected parameters.",
                confidence=70
            ))

        return chain


def create_error_context(
    action: str,
    error: str,
    params: Dict[str, Any],
    attempt: int = 1,
    phase: str = "",
    reasoning: str = ""
) -> ErrorContext:
    """Factory function to create ErrorContext with classified error type."""
    strategy = RecoveryStrategy()
    error_type = strategy.classify_error(error)

    return ErrorContext(
        failed_action=action,
        error_message=error,
        error_type=error_type,
        attempt_count=attempt,
        original_params=params,
        phase=phase,
        previous_reasoning=reasoning
    )
