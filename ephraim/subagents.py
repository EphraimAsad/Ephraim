"""
Sub-Agent System

Allows spawning parallel agents to work on focused tasks.
Each sub-agent runs in its own thread with isolated LLM calls.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class AgentType(Enum):
    """Types of sub-agents."""
    EXPLORE = "explore"  # Search and understand codebase
    PLAN = "plan"  # Design implementation approach
    EXECUTE = "execute"  # Perform actions
    RESEARCH = "research"  # General research/analysis


class AgentStatus(Enum):
    """Status of a sub-agent."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentResult:
    """Result from a sub-agent."""
    success: bool
    result: str
    error: Optional[str] = None
    data: Dict = field(default_factory=dict)


@dataclass
class SubAgent:
    """
    Represents a sub-agent running a focused task.

    Sub-agents run in parallel threads with isolated LLM calls.
    """
    id: str
    task: str
    agent_type: AgentType
    status: AgentStatus = AgentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[SubAgentResult] = None
    model_name: str = "llama3.1:8b"
    _thread: Optional[threading.Thread] = field(default=None, repr=False)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "task": self.task,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": {
                "success": self.result.success,
                "result": self.result.result[:500] if self.result else None,
                "error": self.result.error if self.result else None,
            } if self.result else None,
        }


class SubAgentManager:
    """
    Manages sub-agents.

    Singleton pattern - use get_manager() to access.
    """

    _instance: Optional["SubAgentManager"] = None

    # System prompts for different agent types
    AGENT_PROMPTS = {
        AgentType.EXPLORE: """You are an exploration agent. Your job is to search and understand codebases.
Given a task, you should:
1. Identify what files and code are relevant
2. Understand the structure and patterns
3. Report your findings clearly and concisely
Respond with a summary of what you found.""",

        AgentType.PLAN: """You are a planning agent. Your job is to design implementation approaches.
Given a task, you should:
1. Break down the task into steps
2. Identify potential challenges
3. Propose a clear implementation plan
Respond with a structured plan.""",

        AgentType.EXECUTE: """You are an execution agent. Your job is to perform actions.
Given a task, you should:
1. Determine what actions are needed
2. Execute them in order
3. Report the results
Respond with what you did and the outcome.""",

        AgentType.RESEARCH: """You are a research agent. Your job is to analyze and research.
Given a task, you should:
1. Gather relevant information
2. Analyze and synthesize findings
3. Provide a clear summary
Respond with your research findings.""",
    }

    def __init__(self):
        self.agents: Dict[str, SubAgent] = {}
        self._lock = threading.Lock()
        self.model_name = "llama3.1:8b"

    @classmethod
    def get_manager(cls) -> "SubAgentManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_model(self, model_name: str) -> None:
        """Set the model to use for sub-agents."""
        self.model_name = model_name

    def spawn(
        self,
        task: str,
        agent_type: str = "explore",
        context: Optional[Dict] = None,
    ) -> str:
        """
        Spawn a new sub-agent.

        Returns the agent ID.
        """
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("Ollama not available")

        # Parse agent type
        try:
            atype = AgentType(agent_type.lower())
        except ValueError:
            atype = AgentType.EXPLORE

        agent_id = str(uuid.uuid4())[:8]

        agent = SubAgent(
            id=agent_id,
            task=task,
            agent_type=atype,
            model_name=self.model_name,
        )

        with self._lock:
            self.agents[agent_id] = agent

        # Start thread
        thread = threading.Thread(
            target=self._run_agent,
            args=(agent, context or {}),
            daemon=True,
        )
        agent._thread = thread
        thread.start()

        return agent_id

    def _run_agent(self, agent: SubAgent, context: Dict) -> None:
        """Run an agent in its thread."""
        agent.status = AgentStatus.RUNNING

        try:
            # Build prompt
            system_prompt = self.AGENT_PROMPTS.get(
                agent.agent_type,
                self.AGENT_PROMPTS[AgentType.EXPLORE]
            )

            # Add context if provided
            if context:
                context_str = "\n".join(
                    f"{k}: {v}" for k, v in context.items()
                    if isinstance(v, (str, int, float, bool))
                )
                if context_str:
                    system_prompt += f"\n\nContext:\n{context_str}"

            # Call Ollama
            response = ollama.chat(
                model=agent.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": agent.task},
                ],
                options={
                    "temperature": 0.3,
                    "num_predict": 2048,
                },
            )

            result_text = response["message"]["content"]

            agent.result = SubAgentResult(
                success=True,
                result=result_text,
            )
            agent.status = AgentStatus.COMPLETED

        except Exception as e:
            agent.result = SubAgentResult(
                success=False,
                result="",
                error=str(e),
            )
            agent.status = AgentStatus.FAILED

        finally:
            agent.completed_at = datetime.now()

    def check(self, agent_id: str) -> Optional[SubAgent]:
        """Check status of an agent."""
        with self._lock:
            return self.agents.get(agent_id)

    def wait(self, agent_id: str, timeout: float = 60.0) -> Optional[SubAgentResult]:
        """
        Wait for an agent to complete.

        Returns the result or None if timeout.
        """
        agent = self.check(agent_id)
        if not agent:
            return None

        if agent._thread:
            agent._thread.join(timeout=timeout)

        return agent.result

    def wait_all(
        self,
        agent_ids: List[str],
        timeout: float = 120.0,
    ) -> Dict[str, Optional[SubAgentResult]]:
        """
        Wait for multiple agents to complete.

        Returns dict of agent_id -> result.
        """
        results = {}

        for agent_id in agent_ids:
            results[agent_id] = self.wait(agent_id, timeout / len(agent_ids))

        return results

    def cancel(self, agent_id: str) -> bool:
        """
        Cancel an agent (note: can't actually stop the LLM call).

        Returns True if cancelled.
        """
        agent = self.check(agent_id)
        if not agent:
            return False

        if agent.status == AgentStatus.RUNNING:
            agent.status = AgentStatus.CANCELLED
            return True

        return False

    def list_agents(self, include_completed: bool = True) -> List[SubAgent]:
        """List all agents."""
        with self._lock:
            agents = list(self.agents.values())

        if not include_completed:
            agents = [a for a in agents if a.status == AgentStatus.RUNNING]

        return sorted(agents, key=lambda a: a.created_at, reverse=True)

    def cleanup(self, max_count: int = 50) -> int:
        """Remove old agents, keeping only the most recent."""
        with self._lock:
            if len(self.agents) <= max_count:
                return 0

            # Sort by created_at and remove oldest
            sorted_agents = sorted(
                self.agents.items(),
                key=lambda x: x[1].created_at,
                reverse=True,
            )

            to_remove = [aid for aid, _ in sorted_agents[max_count:]]
            for aid in to_remove:
                del self.agents[aid]

            return len(to_remove)


# Convenience function
def get_subagent_manager() -> SubAgentManager:
    """Get the sub-agent manager."""
    return SubAgentManager.get_manager()
