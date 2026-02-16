"""
Ephraim Conversation History System

Maintains full conversation context across turns, preserving:
- LLM reasoning (not just actions)
- Tool results with full detail
- Phase transitions
- Error contexts

This enables the LLM to build on previous reasoning and learn from failures.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from .state import Phase


@dataclass
class Turn:
    """Single turn in conversation."""

    # What triggered this turn
    user_message: str

    # LLM's response
    llm_reasoning: str
    llm_action: str
    llm_params: Dict[str, Any]
    llm_confidence: int = 0
    llm_risk: str = "LOW"

    # Tool execution result
    tool_success: bool = False
    tool_summary: str = ""
    tool_error: Optional[str] = None
    tool_data: Dict[str, Any] = field(default_factory=dict)

    # Context
    phase: Phase = Phase.PLANNING
    timestamp: datetime = field(default_factory=datetime.now)

    def to_messages(self) -> List[Dict[str, str]]:
        """Convert turn to message format for LLM context."""
        messages = []

        # User's request
        messages.append({
            "role": "user",
            "content": self.user_message
        })

        # Assistant's response
        assistant_content = json.dumps({
            "reasoning": self.llm_reasoning,
            "action": self.llm_action,
            "params": self.llm_params,
            "confidence": self.llm_confidence,
            "risk": self.llm_risk
        })
        messages.append({
            "role": "assistant",
            "content": assistant_content
        })

        # Tool result (as system message)
        if self.tool_summary:
            result_text = f"Tool '{self.llm_action}' "
            if self.tool_success:
                result_text += f"succeeded: {self.tool_summary}"
            else:
                result_text += f"failed: {self.tool_error or 'Unknown error'}"

            messages.append({
                "role": "system",
                "content": result_text
            })

        return messages

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_message": self.user_message,
            "llm_reasoning": self.llm_reasoning,
            "llm_action": self.llm_action,
            "llm_params": self.llm_params,
            "llm_confidence": self.llm_confidence,
            "llm_risk": self.llm_risk,
            "tool_success": self.tool_success,
            "tool_summary": self.tool_summary,
            "tool_error": self.tool_error,
            "phase": self.phase.value,
            "timestamp": self.timestamp.isoformat()
        }


class ConversationHistory:
    """
    Maintains full conversation context for multi-turn interactions.

    Unlike simple action logging, this preserves:
    - The LLM's reasoning (why it chose an action)
    - Full tool results (not truncated)
    - Error details for recovery
    """

    def __init__(self, max_turns: int = 20):
        self.turns: List[Turn] = []
        self.max_turns = max_turns

    def add_turn(self, turn: Turn) -> None:
        """Add a turn to history, maintaining size limit."""
        self.turns.append(turn)

        # Rolling window - keep most recent turns
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)

    def get_context_messages(self, max_recent: int = 10) -> List[Dict[str, str]]:
        """
        Convert recent turns to message format for LLM context.

        Args:
            max_recent: Maximum number of recent turns to include

        Returns:
            List of message dicts in chat format
        """
        messages = []
        recent_turns = self.turns[-max_recent:] if len(self.turns) > max_recent else self.turns

        for turn in recent_turns:
            messages.extend(turn.to_messages())

        return messages

    def get_recent_reasoning(self, n: int = 3) -> List[str]:
        """Get the reasoning from the last n turns."""
        recent = self.turns[-n:] if len(self.turns) >= n else self.turns
        return [t.llm_reasoning for t in recent if t.llm_reasoning]

    def get_failed_actions(self) -> List[Turn]:
        """Get all failed action turns for error analysis."""
        return [t for t in self.turns if not t.tool_success and t.tool_error]

    def get_last_failure(self) -> Optional[Turn]:
        """Get the most recent failed turn."""
        failed = self.get_failed_actions()
        return failed[-1] if failed else None

    def get_successful_patterns(self) -> List[Dict[str, Any]]:
        """Extract patterns from successful actions for learning."""
        patterns = []
        for turn in self.turns:
            if turn.tool_success:
                patterns.append({
                    "action": turn.llm_action,
                    "params_keys": list(turn.llm_params.keys()),
                    "phase": turn.phase.value,
                    "reasoning_snippet": turn.llm_reasoning[:100] if turn.llm_reasoning else ""
                })
        return patterns

    def clear(self) -> None:
        """Clear all conversation history."""
        self.turns = []

    def summarize(self) -> str:
        """Generate a summary of the conversation for context."""
        if not self.turns:
            return "No previous actions."

        lines = [f"Conversation history ({len(self.turns)} turns):"]

        for i, turn in enumerate(self.turns[-5:], 1):  # Last 5 turns
            status = "OK" if turn.tool_success else "FAILED"
            lines.append(f"  {i}. {turn.llm_action} - {status}")
            if turn.tool_error:
                lines.append(f"     Error: {turn.tool_error[:50]}...")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize conversation history."""
        return {
            "turns": [t.to_dict() for t in self.turns],
            "max_turns": self.max_turns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationHistory":
        """Deserialize conversation history."""
        history = cls(max_turns=data.get("max_turns", 20))
        # Note: Full deserialization would require reconstructing Turn objects
        # For now, just create empty history on reload
        return history

    def __len__(self) -> int:
        return len(self.turns)

    def __bool__(self) -> bool:
        return len(self.turns) > 0
