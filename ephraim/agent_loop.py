"""
Ephraim Agent Loop

The main execution loop that orchestrates the agent workflow.

Flow:
BOOT -> WAIT FOR TASK -> PLAN -> APPROVE -> EXECUTE -> VALIDATE -> COMMIT -> CI_CHECK -> COMPLETE/REPLAN
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime

from .state import EphraimState, Phase, Plan
from .config import EphraimConfig
from .state_manager import StateManager, create_state_manager, LLMResponse as ParsedLLMResponse
from .llm_interface import LLMInterface, create_llm_interface, verify_ollama_connection
from .tools import tool_registry, ToolResult
from .boot import load_git_status
from .logging_setup import (
    print_header,
    print_phase,
    print_info,
    print_warning,
    print_error,
    print_success,
    print_separator,
    print_plan,
    print_approval_request,
    print_confidence,
    print_risk,
    get_user_input,
    confirm,
    console,
    get_logger,
)


class AgentLoop:
    """
    The main agent loop for Ephraim.

    Orchestrates the full workflow from task input to completion.
    """

    def __init__(
        self,
        state: EphraimState,
        config: EphraimConfig,
    ):
        self.state = state
        self.config = config
        self.state_manager = create_state_manager(state, config)
        self.llm = create_llm_interface(config.model)
        self.logger = get_logger()

    def run(self) -> None:
        """
        Run the agent loop.

        Main entry point for the agent.
        """
        print_header("EPHRAIM AGENT")

        # Verify LLM connection
        if not verify_ollama_connection(self.config.model):
            print_warning("Running in limited mode without LLM.")

        print_separator()
        print_info("Enter your task, or type 'quit' to exit.")
        print_separator()

        while True:
            try:
                # Wait for task input
                user_input = get_user_input("Ephraim> ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ('quit', 'exit', 'q'):
                    print_info("Goodbye!")
                    break

                if user_input.lower() == 'status':
                    self._show_status()
                    continue

                if user_input.lower() == 'help':
                    self._show_help()
                    continue

                # Process the task
                self._process_task(user_input)

            except KeyboardInterrupt:
                print_info("\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                print_error(f"Error: {e}")
                self.logger.exception("Agent loop error")

    def _process_task(self, task: str) -> None:
        """
        Process a user task through the full workflow.
        """
        # Set the goal
        self.state.current_goal = task
        self.logger.info(f"New task: {task}")

        # Ensure we're in planning phase
        self.state_manager.transition(Phase.PLANNING)
        print_phase("PLANNING")

        # Update git status
        self.state.git = load_git_status(self.state.repo_root)

        # Main agent loop
        while self.state_manager.can_continue():
            try:
                # Build LLM context
                context = self.state_manager.build_llm_brief()

                # Get LLM response
                response = self.llm.generate(context, task)

                if not response.success:
                    print_error(f"LLM error: {response.error}")
                    break

                parsed = response.parsed
                if not parsed:
                    print_error("Failed to parse LLM response")
                    break

                # Process the response
                should_continue = self._handle_response(parsed)

                if not should_continue:
                    break

                # Update task message for next iteration
                task = self._get_next_prompt()

            except Exception as e:
                print_error(f"Error in agent loop: {e}")
                self.logger.exception("Agent loop iteration error")
                break

    def _handle_response(self, response: Dict[str, Any]) -> bool:
        """
        Handle an LLM response.

        Returns True to continue loop, False to stop.
        """
        # Update confidence and risk
        if "confidence" in response:
            self.state_manager.update_confidence(response["confidence"])
            print_confidence(response["confidence"])

        if "risk" in response:
            self.state_manager.update_risk(response["risk"])
            print_risk(response["risk"])

        # Show reasoning
        if response.get("reasoning"):
            print_info(f"Reasoning: {response['reasoning'][:200]}...")

        # Check for clarification question
        if response.get("question"):
            return self._handle_question(response["question"])

        # Handle action
        action = response.get("action", "")

        if action == "propose_plan":
            return self._handle_plan_proposal(response.get("plan", {}))
        elif action == "final_answer":
            return self._handle_completion(response)
        else:
            return self._handle_tool_action(action, response.get("params", {}))

    def _handle_question(self, question: str) -> bool:
        """Handle a clarification question from the LLM."""
        print_separator()
        console.print(f"[yellow]Question:[/yellow] {question}")

        answer = get_user_input("Your answer: ").strip()

        if answer.lower() in ('quit', 'cancel', 'stop'):
            return False

        # Add answer to context for next iteration
        self.state.current_goal = f"{self.state.current_goal}\n\nClarification: {answer}"
        return True

    def _handle_plan_proposal(self, plan_data: Dict[str, Any]) -> bool:
        """Handle a plan proposal from the LLM."""
        # Store the plan
        self.state.current_plan = Plan(
            goal_understanding=plan_data.get("goal_understanding", ""),
            reasoning=plan_data.get("reasoning", ""),
            execution_steps=plan_data.get("execution_steps", []),
            risk_assessment=plan_data.get("risk_assessment", ""),
            validation_plan=plan_data.get("validation_plan", ""),
            git_strategy=plan_data.get("git_strategy", ""),
            approved=False,
        )

        # Display the plan
        print_plan(plan_data)

        # Request approval
        self.state_manager.request_approval()
        print_approval_request("Do you approve this plan?")

        if confirm("Approve plan?"):
            self.state_manager.grant_approval()
            print_success("Plan approved. Executing...")
            print_phase("EXECUTING")
            update_context_md(self.state)  # Persist plan to Context.md
            return True
        else:
            print_info("Plan rejected. Please provide feedback or a new task.")
            self.state_manager.deny_approval()
            return False

    def _handle_tool_action(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> bool:
        """Handle a tool action from the LLM."""
        # Check if tool can be used
        allowed, reason = self.state_manager.can_use_tool(tool_name)

        if not allowed:
            print_warning(f"Cannot use tool: {reason}")
            return True  # Continue but tool was blocked

        # Get the tool
        tool = tool_registry.get(tool_name)
        if not tool:
            print_warning(f"Unknown tool: {tool_name}")
            return True

        # Show step progress if we have an approved plan
        if self.state.current_plan.approved:
            steps = self.state.current_plan.execution_steps
            current_step = self.state_manager._get_current_step()
            total = len(steps)
            if current_step < total:
                print_separator()
                print_info(f">>> Step {current_step + 1}/{total}: {steps[current_step]}")

        # Show tool and key parameters
        print_info(f"    Tool: {tool_name}")
        if tool_name == "run_command":
            print_info(f"    Command: {params.get('command', '')}")
        elif tool_name == "read_file":
            print_info(f"    File: {params.get('path', '')}")
        elif tool_name == "apply_patch":
            print_info(f"    File: {params.get('path', '')}")
        elif tool_name == "git_commit":
            print_info(f"    Message: {params.get('message', '')}")

        try:
            result = tool(**params)

            # Record the action
            self.state_manager.record_action(
                action=tool_name,
                tool=tool_name,
                params=params,
                result=result.to_dict(),
                success=result.success,
            )

            # Show result
            if result.success:
                print_success(f"Result: {result.summary}")
            else:
                print_error(f"Failed: {result.error}")

            return True

        except Exception as e:
            print_error(f"Tool execution failed: {e}")
            return True

    def _handle_completion(self, response: Dict[str, Any]) -> bool:
        """Handle task completion."""
        message = response.get("params", {}).get("message", "Task completed")

        print_separator()
        print_success("TASK COMPLETED")
        console.print(message)
        print_separator()

        # Persist completion to Context.md
        update_context_md(self.state)

        # Transition to completed
        self.state_manager.transition(Phase.COMPLETED)

        # Reset for next task
        self.state.current_goal = ""
        self.state.current_plan = Plan()
        self.state.execution.iteration = 0

        return False

    def _get_next_prompt(self) -> str:
        """Get the prompt for the next iteration."""
        recent_actions = self.state.get_recent_actions(3)

        if recent_actions:
            last_action = recent_actions[-1]
            return (
                f"Continue with the task: {self.state.current_goal}\n"
                f"Last action: {last_action.tool} - {last_action.result.get('summary', 'completed')}"
            )
        else:
            return self.state.current_goal

    def _show_status(self) -> None:
        """Show current status."""
        summary = self.state_manager.get_state_summary()

        print_separator()
        print_info("Current Status")
        print_separator()

        for key, value in summary.items():
            print_info(f"  {key}: {value}")

        print_separator()

    def _show_help(self) -> None:
        """Show help message."""
        print_info("Commands:")
        print_info("  status  - Show current state")
        print_info("  quit    - Exit Ephraim")
        print_info("  help    - Show this help")
        print_info("")
        print_info("Or enter a task description to begin.")


def run_agent(state: EphraimState, config: EphraimConfig) -> None:
    """
    Run the Ephraim agent.

    Main entry point from main.py.
    """
    agent = AgentLoop(state, config)
    agent.run()


def update_context_md(state: EphraimState) -> None:
    """
    Update Context.md with current state.

    Called after significant actions (plan approval, task completion).
    """
    content = f"""# Current Task
{state.current_goal or "No active task."}

# Phase
{state.phase.value}

# Active Plan
"""
    # Add plan details if there's an approved plan
    if state.current_plan.approved and state.current_plan.goal_understanding:
        content += f"Goal: {state.current_plan.goal_understanding}\n"
        content += "Steps:\n"
        for i, step in enumerate(state.current_plan.execution_steps, 1):
            content += f"  {i}. {step}\n"
    elif state.phase == Phase.COMPLETED:
        content += "Completed.\n"
    else:
        content += "No approved plan.\n"

    content += "\n# Recent Decisions\n"

    recent = state.get_recent_actions(5)
    if recent:
        for action in recent:
            content += f"- {action.timestamp}: {action.tool} - {action.result.get('summary', '')[:50]}\n"
    else:
        content += "None yet.\n"

    content += f"""
# CI Status
{state.ci.ci_status or "Not checked."}

# Git Status
Branch: {state.git.branch or "N/A"}
Clean: {state.git.is_clean}

# Next Steps
{"Awaiting user input." if state.phase == Phase.COMPLETED else "In progress."}

# Updated
{datetime.now().isoformat()}
"""

    try:
        with open(state.context_md_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        pass  # Non-critical
