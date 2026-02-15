"""
Ephraim State Manager

The orchestration layer that controls state transitions and enforces safety rules.

Key responsibilities:
- Phase transitions and enforcement
- Approval gating
- LLM brief building (curated context)
- Action history tracking
"""

from typing import Dict, List, Any, Optional, Set

from .state import EphraimState, Phase, RiskLevel, ActionRecord
from .config import EphraimConfig
from .tools.base import ToolCategory, tool_registry


# Valid phase transitions
VALID_TRANSITIONS: Dict[Phase, Set[Phase]] = {
    Phase.BOOT: {Phase.PLANNING},
    Phase.PLANNING: {Phase.AWAITING_APPROVAL, Phase.COMPLETED},
    Phase.AWAITING_APPROVAL: {Phase.PLANNING, Phase.EXECUTING, Phase.COMPLETED},
    Phase.EXECUTING: {Phase.VALIDATING, Phase.PLANNING, Phase.COMPLETED},
    Phase.VALIDATING: {Phase.CI_CHECK, Phase.PLANNING, Phase.COMPLETED, Phase.EXECUTING},
    Phase.CI_CHECK: {Phase.COMPLETED, Phase.PLANNING, Phase.EXECUTING},
    Phase.COMPLETED: {Phase.PLANNING},  # Can start new task
}

# Tools allowed in each phase
ALLOWED_TOOLS_BY_PHASE: Dict[Phase, Set[ToolCategory]] = {
    Phase.BOOT: set(),  # No tools during boot
    Phase.PLANNING: {ToolCategory.READ_ONLY, ToolCategory.USER_INPUT},
    Phase.AWAITING_APPROVAL: {ToolCategory.USER_INPUT},
    Phase.EXECUTING: {
        ToolCategory.READ_ONLY,
        ToolCategory.EXECUTION,
        ToolCategory.GIT,
        ToolCategory.USER_INPUT,
    },
    Phase.VALIDATING: {
        ToolCategory.READ_ONLY,
        ToolCategory.EXECUTION,  # For running tests
        ToolCategory.USER_INPUT,
    },
    Phase.CI_CHECK: {ToolCategory.READ_ONLY, ToolCategory.CI, ToolCategory.USER_INPUT},
    Phase.COMPLETED: {ToolCategory.READ_ONLY, ToolCategory.USER_INPUT},
}


class StateManager:
    """
    Manages state transitions and enforces system rules.

    This is the authoritative controller - the LLM cannot bypass it.
    """

    def __init__(self, state: EphraimState, config: EphraimConfig):
        self.state = state
        self.config = config

    def can_transition(self, to_phase: Phase) -> bool:
        """Check if transition to the given phase is valid."""
        return to_phase in VALID_TRANSITIONS.get(self.state.phase, set())

    def transition(self, to_phase: Phase) -> bool:
        """
        Attempt to transition to a new phase.

        Returns True if transition succeeded, False otherwise.
        """
        if not self.can_transition(to_phase):
            return False

        self.state.phase = to_phase

        # Reset approval flag when leaving awaiting_approval
        if to_phase != Phase.AWAITING_APPROVAL:
            self.state.awaiting_user_approval = False

        return True

    def can_use_tool(self, tool_name: str) -> tuple[bool, str]:
        """
        Check if a tool can be used in the current phase.

        Returns (allowed, reason).
        """
        tool = tool_registry.get(tool_name)
        if not tool:
            return False, f"Unknown tool: {tool_name}"

        allowed_categories = ALLOWED_TOOLS_BY_PHASE.get(self.state.phase, set())

        if tool.category not in allowed_categories:
            return False, (
                f"Tool '{tool_name}' (category: {tool.category.value}) "
                f"not allowed in phase '{self.state.phase.value}'"
            )

        # Check approval for execution tools
        if tool.requires_approval() and not self.state.current_plan.approved:
            return False, f"Tool '{tool_name}' requires plan approval first"

        return True, "Allowed"

    def requires_approval(self, action: str) -> bool:
        """Check if an action requires user approval."""
        if not self.config.safety.require_approval:
            return False

        # Check tool category
        tool = tool_registry.get(action)
        if tool and tool.requires_approval():
            return True

        # Check for dangerous patterns
        dangerous = self.config.safety.dangerous_commands
        for pattern in dangerous:
            if pattern.lower() in action.lower():
                return True

        return False

    def request_approval(self) -> None:
        """Set state to await approval."""
        self.state.awaiting_user_approval = True
        self.transition(Phase.AWAITING_APPROVAL)

    def grant_approval(self) -> None:
        """Grant approval and allow execution."""
        self.state.awaiting_user_approval = False
        self.state.current_plan.approved = True
        self.transition(Phase.EXECUTING)

    def deny_approval(self) -> None:
        """Deny approval and return to planning."""
        self.state.awaiting_user_approval = False
        self.state.current_plan.approved = False
        self.transition(Phase.PLANNING)

    def record_action(
        self,
        action: str,
        tool: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
    ) -> None:
        """Record an action in the history."""
        self.state.add_action(action, tool, params, result, success)
        self.state.execution.increment()

    def can_continue(self) -> bool:
        """Check if execution can continue (not at iteration limit)."""
        return self.state.execution.can_continue()

    def build_llm_brief(
        self,
        file_snippets: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a curated context brief for the LLM.

        This controls what information the LLM sees.
        The LLM never gets full system state directly.
        """
        brief: Dict[str, Any] = {
            "phase": self.state.phase.value,
            "goal": self.state.current_goal,
            "repo_root": self.state.repo_root,
            "iteration": self.state.execution.iteration,
            "max_iterations": self.state.execution.max_iterations,
        }

        # Add constraints from config
        if self.config.architecture_constraints:
            brief["constraints"] = {
                "architecture": self.config.architecture_constraints,
                "coding_standards": self.config.coding_standards,
                "protected_areas": self.config.protected_areas,
            }

        # Add approved plan if exists
        if self.state.current_plan.approved:
            brief["approved_plan"] = {
                "goal": self.state.current_plan.goal_understanding,
                "steps": self.state.current_plan.execution_steps,
                "current_step": self._get_current_step(),
            }

        # Add recent actions (summarized)
        recent = self.state.get_recent_actions(5)
        if recent:
            brief["recent_actions"] = [
                {
                    "action": a.action,
                    "tool": a.tool,
                    "success": a.success,
                    "summary": a.result.get("summary", "")[:200],
                }
                for a in recent
            ]

        # Add file snippets if provided
        if file_snippets:
            brief["file_context"] = file_snippets

        # Add git summary
        if self.state.git.branch:
            brief["git"] = {
                "branch": self.state.git.branch,
                "is_clean": self.state.git.is_clean,
                "modified_count": len(self.state.git.modified_files),
                "untracked_count": len(self.state.git.untracked_files),
            }

        # Add CI summary
        if self.state.ci.ci_status:
            brief["ci"] = {
                "status": self.state.ci.ci_status,
                "workflow": self.state.ci.workflow_name,
                "failed_tests": len(self.state.ci.failed_tests),
            }

        # Add available tools for current phase
        allowed_categories = ALLOWED_TOOLS_BY_PHASE.get(self.state.phase, set())
        available_tools = [
            t.get_schema()
            for t in tool_registry.list_all()
            if t.category in allowed_categories
        ]
        brief["available_tools"] = available_tools

        return brief

    def _get_current_step(self) -> int:
        """Estimate current step based on actions taken."""
        if not self.state.current_plan.execution_steps:
            return 0

        # All tools that represent execution progress
        execution_tools = {
            # File modification tools
            'apply_patch',
            'write_file',
            'delete_file',
            'move_file',
            'copy_file',
            # Directory tools
            'create_directory',
            'delete_directory',
            # Command execution
            'run_command',
            # Git tools
            'git_commit',
            'git_add',
            # Notebook tools
            'notebook_edit',
        }

        # Count execution tool uses
        execution_count = sum(
            1 for a in self.state.action_history
            if a.tool in execution_tools
        )
        return min(execution_count, len(self.state.current_plan.execution_steps) - 1)

    def update_confidence(self, score: int) -> None:
        """Update confidence score."""
        self.state.confidence_score = max(0, min(100, score))

    def update_risk(self, level: str) -> None:
        """Update risk level."""
        try:
            self.state.risk_level = RiskLevel(level.upper())
        except ValueError:
            pass  # Keep current if invalid

    def should_ask_clarification(self) -> bool:
        """Check if clarification should be requested based on confidence/risk."""
        return self.state.requires_clarification()

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current state for display."""
        return {
            "phase": self.state.phase.value,
            "goal": self.state.current_goal,
            "confidence": self.state.confidence_score,
            "confidence_level": self.state.get_confidence_level(),
            "risk": self.state.risk_level.value,
            "awaiting_approval": self.state.awaiting_user_approval,
            "plan_approved": self.state.current_plan.approved,
            "iteration": self.state.execution.iteration,
            "max_iterations": self.state.execution.max_iterations,
            "actions_taken": len(self.state.action_history),
        }


def create_state_manager(
    state: EphraimState,
    config: EphraimConfig,
) -> StateManager:
    """Create a state manager instance."""
    return StateManager(state, config)
