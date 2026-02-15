"""
Ephraim State Object Model

The state object is the true brain of the system.
The LLM does NOT control state directly - the state manager does.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class Phase(Enum):
    """Valid phases in the Ephraim workflow."""
    BOOT = "boot"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    CI_CHECK = "ci_check"
    COMPLETED = "completed"


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class GitStatus:
    """Structured Git repository status."""
    modified_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    staged_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    branch: str = ""
    is_clean: bool = True
    has_remote: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modified_files": self.modified_files,
            "untracked_files": self.untracked_files,
            "staged_files": self.staged_files,
            "deleted_files": self.deleted_files,
            "branch": self.branch,
            "is_clean": self.is_clean,
            "has_remote": self.has_remote,
        }


@dataclass
class CIStatus:
    """Structured CI/CD status from GitHub Actions."""
    ci_status: str = ""  # passed, failed, pending, unknown
    workflow_name: str = ""
    run_id: Optional[int] = None
    status: str = ""
    conclusion: str = ""
    duration: str = ""
    last_run_url: str = ""
    failed_tests: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ci_status": self.ci_status,
            "workflow_name": self.workflow_name,
            "run_id": self.run_id,
            "status": self.status,
            "conclusion": self.conclusion,
            "duration": self.duration,
            "last_run_url": self.last_run_url,
            "failed_tests": self.failed_tests,
        }


@dataclass
class ExecutionState:
    """Tracks execution progress and limits."""
    iteration: int = 0
    max_iterations: int = 20

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }

    def can_continue(self) -> bool:
        """Check if we haven't exceeded iteration limit."""
        return self.iteration < self.max_iterations

    def increment(self) -> None:
        """Increment the iteration counter."""
        self.iteration += 1


@dataclass
class ActionRecord:
    """Record of an action taken by Ephraim."""
    timestamp: str
    action: str
    tool: str
    params: Dict[str, Any]
    result: Dict[str, Any]
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "tool": self.tool,
            "params": self.params,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class Plan:
    """Structured plan for task execution."""
    goal_understanding: str = ""
    reasoning: str = ""
    execution_steps: List[str] = field(default_factory=list)
    risk_assessment: str = ""
    validation_plan: str = ""
    git_strategy: str = ""
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_understanding": self.goal_understanding,
            "reasoning": self.reasoning,
            "execution_steps": self.execution_steps,
            "risk_assessment": self.risk_assessment,
            "validation_plan": self.validation_plan,
            "git_strategy": self.git_strategy,
            "approved": self.approved,
        }


@dataclass
class EphraimState:
    """
    The central state object for Ephraim.

    This is the authoritative source of truth for the system.
    All state changes go through the state manager.
    """

    # Core workflow state
    phase: Phase = Phase.BOOT
    current_goal: str = ""

    # Risk and confidence assessment
    confidence_score: int = 0  # 0-100
    risk_level: RiskLevel = RiskLevel.LOW

    # Approval tracking
    awaiting_user_approval: bool = False
    planning_scope: str = "full_goal"

    # Current plan
    current_plan: Plan = field(default_factory=Plan)

    # External system state
    git: GitStatus = field(default_factory=GitStatus)
    ci: CIStatus = field(default_factory=CIStatus)

    # Execution tracking
    execution: ExecutionState = field(default_factory=ExecutionState)

    # History
    action_history: List[ActionRecord] = field(default_factory=list)

    # Project paths
    repo_root: str = ""
    ephraim_md_path: str = ""
    context_md_path: str = ""

    # Session metadata
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "phase": self.phase.value,
            "current_goal": self.current_goal,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level.value,
            "awaiting_user_approval": self.awaiting_user_approval,
            "planning_scope": self.planning_scope,
            "current_plan": self.current_plan.to_dict(),
            "git": self.git.to_dict(),
            "ci": self.ci.to_dict(),
            "execution": self.execution.to_dict(),
            "action_history": [a.to_dict() for a in self.action_history],
            "repo_root": self.repo_root,
            "ephraim_md_path": self.ephraim_md_path,
            "context_md_path": self.context_md_path,
            "session_start": self.session_start,
        }

    def get_confidence_level(self) -> str:
        """Get human-readable confidence level."""
        if self.confidence_score >= 80:
            return "HIGH"
        elif self.confidence_score >= 55:
            return "MEDIUM"
        elif self.confidence_score >= 30:
            return "LOW"
        else:
            return "VERY_LOW"

    def requires_clarification(self) -> bool:
        """Check if clarification is needed based on confidence/risk."""
        return (
            self.confidence_score < 80 or
            self.risk_level == RiskLevel.HIGH
        )

    def add_action(
        self,
        action: str,
        tool: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        success: bool
    ) -> None:
        """Record an action in the history."""
        record = ActionRecord(
            timestamp=datetime.now().isoformat(),
            action=action,
            tool=tool,
            params=params,
            result=result,
            success=success,
        )
        self.action_history.append(record)

    def get_recent_actions(self, count: int = 5) -> List[ActionRecord]:
        """Get the most recent actions."""
        return self.action_history[-count:]


def create_initial_state() -> EphraimState:
    """Create a fresh state object for a new session."""
    return EphraimState()
