"""
Hooks System

Allows running shell commands in response to events.
Hooks are configured in Ephraim.md.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class HookEvent(Enum):
    """Events that can trigger hooks."""
    PRE_TOOL = "pre_tool"  # Before any tool execution
    POST_TOOL = "post_tool"  # After any tool execution
    PRE_COMMIT = "pre_commit"  # Before git commit
    POST_COMMIT = "post_commit"  # After git commit
    ON_ERROR = "on_error"  # When an error occurs
    ON_COMPLETE = "on_complete"  # When task completes
    ON_PLAN_APPROVED = "on_plan_approved"  # When plan is approved
    ON_START = "on_start"  # When Ephraim starts


@dataclass
class Hook:
    """Represents a hook configuration."""
    event: HookEvent
    command: str
    tools: Optional[List[str]] = None  # Filter by tool name (for tool hooks)
    description: Optional[str] = None
    enabled: bool = True

    def matches_tool(self, tool_name: str) -> bool:
        """Check if hook applies to a specific tool."""
        if self.tools is None:
            return True
        return tool_name in self.tools


@dataclass
class HookResult:
    """Result of hook execution."""
    hook: Hook
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    blocked: bool = False  # If True, operation should be blocked


class HookManager:
    """
    Manages hooks.

    Singleton pattern - use get_manager() to access.
    """

    _instance: Optional["HookManager"] = None

    def __init__(self):
        self.hooks: List[Hook] = []
        self.enabled = True

    @classmethod
    def get_manager(cls) -> "HookManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        event: str,
        command: str,
        tools: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Hook:
        """Register a hook."""
        try:
            hook_event = HookEvent(event.lower())
        except ValueError:
            raise ValueError(f"Unknown hook event: {event}")

        hook = Hook(
            event=hook_event,
            command=command,
            tools=tools,
            description=description,
        )

        self.hooks.append(hook)
        return hook

    def load_from_config(self, ephraim_md_content: str) -> int:
        """
        Load hooks from Ephraim.md content.

        Expected format in Ephraim.md:
        # Hooks
        - pre_tool: npm run lint (for apply_patch, write_file)
        - post_commit: ./scripts/notify.sh
        - on_error: echo "Error occurred"

        Returns number of hooks loaded.
        """
        count = 0
        in_hooks_section = False

        for line in ephraim_md_content.split('\n'):
            line = line.strip()

            # Check for hooks section
            if line.lower().startswith('# hooks'):
                in_hooks_section = True
                continue

            # Check for new section
            if line.startswith('# ') and in_hooks_section:
                in_hooks_section = False
                continue

            # Parse hook line
            if in_hooks_section and line.startswith('- '):
                try:
                    hook = self._parse_hook_line(line[2:])
                    if hook:
                        self.hooks.append(hook)
                        count += 1
                except Exception:
                    pass

        return count

    def _parse_hook_line(self, line: str) -> Optional[Hook]:
        """
        Parse a hook definition line.

        Format: event: command (for tool1, tool2)
        Example: pre_tool: npm run lint (for apply_patch, write_file)
        """
        if ':' not in line:
            return None

        event_part, rest = line.split(':', 1)
        event_part = event_part.strip()
        rest = rest.strip()

        # Check for tool filter
        tools = None
        if '(for ' in rest:
            command, tools_part = rest.rsplit('(for ', 1)
            command = command.strip()
            tools_str = tools_part.rstrip(')')
            tools = [t.strip() for t in tools_str.split(',')]
        else:
            command = rest

        try:
            hook_event = HookEvent(event_part.lower())
        except ValueError:
            return None

        return Hook(
            event=hook_event,
            command=command,
            tools=tools,
        )

    def run_hooks(
        self,
        event: str,
        context: Dict[str, Any],
        tool_name: Optional[str] = None,
    ) -> List[HookResult]:
        """
        Run all hooks for an event.

        Returns list of results. If any hook sets blocked=True,
        the operation should be cancelled.
        """
        if not self.enabled:
            return []

        try:
            hook_event = HookEvent(event.lower())
        except ValueError:
            return []

        results = []

        for hook in self.hooks:
            if not hook.enabled:
                continue

            if hook.event != hook_event:
                continue

            # Check tool filter
            if tool_name and not hook.matches_tool(tool_name):
                continue

            result = self._run_hook(hook, context)
            results.append(result)

            # If hook blocks, stop running more hooks
            if result.blocked:
                break

        return results

    def _run_hook(self, hook: Hook, context: Dict[str, Any]) -> HookResult:
        """Run a single hook."""
        # Prepare environment with context
        env = os.environ.copy()
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                env[f"EPHRAIM_{key.upper()}"] = str(value)

        # Run command
        try:
            if sys.platform == 'win32':
                shell_cmd = ['cmd', '/c', hook.command]
            else:
                shell_cmd = ['bash', '-c', hook.command]

            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                cwd=context.get('repo_root', os.getcwd()),
            )

            # Non-zero exit code blocks the operation
            blocked = result.returncode != 0

            return HookResult(
                hook=hook,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                blocked=blocked,
            )

        except subprocess.TimeoutExpired:
            return HookResult(
                hook=hook,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Hook timed out",
                blocked=True,
            )
        except Exception as e:
            return HookResult(
                hook=hook,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                blocked=False,
            )

    def get_hooks_for_event(self, event: str) -> List[Hook]:
        """Get all hooks for an event."""
        try:
            hook_event = HookEvent(event.lower())
        except ValueError:
            return []

        return [h for h in self.hooks if h.event == hook_event and h.enabled]

    def clear(self) -> None:
        """Clear all hooks."""
        self.hooks.clear()


# Convenience function
def get_hook_manager() -> HookManager:
    """Get the hook manager."""
    return HookManager.get_manager()
