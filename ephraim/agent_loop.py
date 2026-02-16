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
from .state_manager import StateManager, create_state_manager
from .llm_interface import (
    LLMInterface,
    create_llm_interface,
    verify_ollama_connection,
    PLANNING_PROMPT,
    EXECUTION_PROMPT,
)
from .tools import tool_registry, ToolResult
from .boot import load_git_status
from rich.panel import Panel
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
        streaming: bool = True,
    ):
        self.state = state
        self.config = config
        self.streaming = streaming  # Enable streaming token display
        self.state_manager = create_state_manager(state, config)

        # Create both LLM interfaces (planning and execution)
        self.planning_llm = create_llm_interface(config.model)

        # Use execution_model if configured, otherwise use default
        from .config import get_default_execution_model
        exec_model = config.execution_model or get_default_execution_model()
        self.execution_llm = create_llm_interface(exec_model)
        self._execution_model_name = exec_model.model_name

        # Start with planning model
        self.llm = self.planning_llm

        self.logger = get_logger()
        self._plan_rejection_count = 0  # Track repeated plan proposals
        self._last_failed_action = None  # Track last failed action
        self._failed_action_count = 0  # Track repeated failures

        # NEW: Conversation history and error recovery
        from .conversation import ConversationHistory
        from .recovery import RecoveryStrategy
        self.conversation = ConversationHistory(max_turns=20)
        self.recovery = RecoveryStrategy()
        self._last_reasoning = None  # Preserve LLM's reasoning for next turn
        self._error_context = None   # Error context for recovery

    def run(self) -> None:
        """
        Run the agent loop.

        Main entry point for the agent.
        """
        print_header("EPHRAIM AGENT")

        # Verify planning model
        if not verify_ollama_connection(self.config.model):
            print_warning("Planning model not available. Running in limited mode.")

        # Verify execution model
        from .config import get_default_execution_model
        exec_model = self.config.execution_model or get_default_execution_model()
        if not verify_ollama_connection(exec_model):
            print_warning(f"Execution model '{exec_model.model_name}' not available.")
            print_info("Using planning model for execution (may cause re-planning)")
            self.execution_llm = self.planning_llm
            self._execution_model_name = self.config.model.model_name

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

                # Select prompt based on phase
                if self.state.phase == Phase.PLANNING:
                    prompt = PLANNING_PROMPT
                else:
                    prompt = EXECUTION_PROMPT

                # Get LLM response (with streaming if enabled)
                if self.streaming:
                    response = self._generate_with_streaming(context, task)
                else:
                    response = self.llm.generate(context, task, prompt_template=prompt)

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
        # Visual separator for new response
        print_separator()

        # Show full reasoning FIRST in styled panel (ALL phases)
        if response.get("reasoning"):
            phase_name = self.state.phase.value.upper()
            console.print(Panel(
                response['reasoning'],
                title=f"[bold cyan]Thinking ({phase_name})[/bold cyan]",
                border_style="cyan"
            ))
        else:
            # Debug: Show if reasoning is missing
            console.print("[dim]No reasoning provided by LLM[/dim]")

        # Show confidence and risk after reasoning
        if "confidence" in response:
            self.state_manager.update_confidence(response["confidence"])
            print_confidence(response["confidence"])

        if "risk" in response:
            self.state_manager.update_risk(response["risk"])
            print_risk(response["risk"])

        # Show the action being taken
        action = response.get("action", "")
        if action:
            console.print(f"[bold yellow]Action:[/bold yellow] {action}")

        # Check for clarification question
        if response.get("question"):
            return self._handle_question(response["question"])

        # Handle action (action already defined above)
        if action == "propose_plan":
            # GUARD: If we already have an approved plan, reject new plan proposals
            if self.state.current_plan.approved:
                self._plan_rejection_count += 1

                if self._plan_rejection_count >= 3:
                    print_error("LLM keeps proposing plans instead of executing.")
                    print_error("This model may not follow execution instructions well.")
                    print_info("Try using a more capable model (e.g., qwen2.5-coder:14b)")
                    return False  # Stop the loop

                print_warning(f"Plan already approved. Ignoring new plan proposal. (attempt {self._plan_rejection_count}/3)")
                print_info("Reprompting LLM to execute the approved plan...")

                # Get the current step from the plan
                steps = self.state.current_plan.execution_steps
                current_idx = self.state_manager._get_current_step()
                current_step = steps[current_idx] if current_idx < len(steps) else steps[0]

                # Force the LLM to execute by updating the goal with explicit instruction
                self.state.current_goal = (
                    f"YOU MUST EXECUTE NOW. DO NOT PROPOSE A PLAN.\n\n"
                    f"Your approved plan step to execute NOW: {current_step}\n\n"
                    f"Respond with a tool action like:\n"
                    f'- {{"action": "run_command", "params": {{"command": "..."}}}}\n'
                    f'- {{"action": "apply_patch", "params": {{"path": "...", "find": "...", "replace": "..."}}}}\n'
                    f'- {{"action": "read_file", "params": {{"path": "..."}}}}\n\n'
                    f"DO NOT use action: propose_plan"
                )
                return True  # Continue loop with updated prompt
            return self._handle_plan_proposal(response.get("plan", {}))
        else:
            # Handle all actions through tool execution (including final_answer)
            result = self._handle_tool_action(action, response.get("params", {}))

            # If final_answer was called successfully, handle completion
            if action == "final_answer" and result:
                return self._handle_completion(response)

            return result

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

            # Switch to execution model for better instruction following
            self.llm = self.execution_llm
            print_info(f"Switched to execution model: {self._execution_model_name}")

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

        # Show action and all parameters clearly
        console.print(f"    [bold yellow]Action:[/bold yellow] {tool_name}")
        if params:
            for key, value in params.items():
                # Truncate long values for display
                display_val = str(value)
                if len(display_val) > 100:
                    display_val = display_val[:100] + "..."
                console.print(f"      [dim]{key}:[/dim] {display_val}")

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

            # Record turn in conversation history
            from .conversation import Turn
            from .recovery import create_error_context
            self.conversation.add_turn(Turn(
                user_message=self.state.current_goal,
                llm_reasoning=self._last_reasoning or "",
                llm_action=tool_name,
                llm_params=params,
                tool_success=result.success,
                tool_summary=result.summary,
                tool_error=result.error,
                tool_data=result.data,
                phase=self.state.phase
            ))

            # Show result
            if result.success:
                print_success(f"Result: {result.summary}")
                # Reset counters on success
                self._plan_rejection_count = 0
                self._failed_action_count = 0
                self._last_failed_action = None
                self._error_context = None
            else:
                print_error(f"Failed: {result.error}")

                # Track repeated failures
                action_key = f"{tool_name}:{str(params)}"
                if self._last_failed_action == action_key:
                    self._failed_action_count += 1
                else:
                    self._last_failed_action = action_key
                    self._failed_action_count = 1

                # Use recovery system to analyze error and suggest fix
                error_ctx = create_error_context(
                    action=tool_name,
                    error=result.error or "Unknown error",
                    params=params,
                    attempt=self._failed_action_count,
                    phase=self.state.phase.value,
                    reasoning=self._last_reasoning or ""
                )

                if self.recovery.should_retry(error_ctx):
                    # Get recovery suggestion for next LLM call
                    suggestion = self.recovery.analyze_error(error_ctx)
                    self._error_context = {
                        "action": tool_name,
                        "error": result.error,
                        "suggestion": suggestion.reasoning,
                        "suggested_action": suggestion.action
                    }
                    print_info(f"Recovery suggestion: {suggestion.reasoning}")
                elif self._failed_action_count >= 3:
                    # Give up after 3 failures with no recovery path
                    print_warning(f"Action failed {self._failed_action_count} times. Forcing task completion.")
                    self._force_completion(tool_name, result.error)
                    return False

            # Check if all plan steps are complete -> transition to VALIDATING
            if self.state.current_plan.approved and self._all_steps_complete():
                self._transition_to_validation()

            return True

        except Exception as e:
            print_error(f"Tool execution failed: {e}")
            return True

    def _all_steps_complete(self) -> bool:
        """Check if all plan steps have been executed."""
        if not self.state.current_plan.execution_steps:
            return False

        current_step = self.state_manager._get_current_step()
        total_steps = len(self.state.current_plan.execution_steps)

        # Consider complete if we've executed at least as many steps as planned
        return current_step >= total_steps - 1

    def _force_completion(self, failed_tool: str, error: str) -> None:
        """Force task completion after repeated failures."""
        from .context_persistence import update_context_md

        print_separator()
        print_warning("Task completed with issues due to repeated action failures.")
        print_info(f"Failed action: {failed_tool}")
        print_info(f"Error: {error}")

        # Persist to Context.md
        update_context_md(self.state)

        # Transition to completed
        self.state_manager.transition(Phase.COMPLETED)

        # Reset for next task
        self.state.current_goal = ""
        self.state.current_plan = Plan()
        self.state.execution.iteration = 0
        self._failed_action_count = 0
        self._last_failed_action = None

        # Switch back to planning model
        self.llm = self.planning_llm
        print_info(f"Switched back to planning model: {self.config.model.model_name}")

    def _transition_to_validation(self) -> None:
        """Transition to validation phase."""
        if self.state.phase == Phase.EXECUTING:
            print_separator()
            print_phase("VALIDATING")
            self.state_manager.transition(Phase.VALIDATING)

            # Check if there's a validation plan
            if self.state.current_plan.validation_plan:
                print_info(f"Validation plan: {self.state.current_plan.validation_plan}")

    def _transition_to_ci_check(self) -> None:
        """Transition to CI check phase."""
        if self.state.phase == Phase.VALIDATING and self.config.ci.enabled:
            print_separator()
            print_phase("CI_CHECK")
            self.state_manager.transition(Phase.CI_CHECK)
            print_info("Checking CI status...")

    def _handle_validation_complete(self, success: bool) -> None:
        """Handle validation completion."""
        if success:
            if self.config.ci.enabled and self.config.ci.check_after_commit:
                self._transition_to_ci_check()
            else:
                print_info("Validation passed. Skipping CI check (disabled).")
        else:
            print_warning("Validation failed. May need to fix issues.")

    def _handle_ci_check_complete(self, success: bool) -> None:
        """Handle CI check completion."""
        if success:
            print_success("CI checks passed!")
        else:
            print_warning("CI checks failed. Review may be needed.")

    def _handle_completion(self, response: Dict[str, Any]) -> bool:
        """Handle task completion after final_answer tool executes."""
        # Tool already displayed completion message, just handle state

        # Persist completion to Context.md
        update_context_md(self.state)

        # Transition to completed
        self.state_manager.transition(Phase.COMPLETED)

        # Reset for next task
        self.state.current_goal = ""
        self.state.current_plan = Plan()
        self.state.execution.iteration = 0

        # Switch back to planning model for next task
        self.llm = self.planning_llm
        print_info(f"Switched back to planning model: {self.config.model.model_name}")

        return False

    def _generate_with_streaming(self, context, task):
        """
        Generate LLM response with streaming token display.

        Shows tokens as they arrive, then parses the complete response.
        Uses PLANNING_PROMPT or EXECUTION_PROMPT based on current phase.
        Includes conversation history and error context for better responses.
        """
        from .llm_interface import LLMResponse
        import json
        import re

        # Select prompt based on phase
        if self.state.phase == Phase.PLANNING:
            prompt = PLANNING_PROMPT
        else:
            prompt = EXECUTION_PROMPT

        print_separator()
        console.print("[bold cyan]Thinking...[/bold cyan]", end=" ")

        # Get conversation history for context
        conv_history = self.conversation.get_context_messages(max_recent=5)

        # Prepare error context if last action failed
        error_ctx = None
        if self._error_context:
            error_ctx = {
                "action": self._error_context.get("action", ""),
                "error": self._error_context.get("error", ""),
                "suggestion": self._error_context.get("suggestion", ""),
            }

        # Collect streamed tokens with full context
        full_response = ""
        for token in self.llm.generate_stream(
            context,
            task,
            prompt_template=prompt,
            conversation_history=conv_history,
            error_context=error_ctx,
            previous_reasoning=self._last_reasoning
        ):
            console.print(token, end="", highlight=False)
            full_response += token

        console.print()  # Newline after streaming

        # Clear error context after using it
        self._error_context = None

        # Parse the complete response
        parsed = self._parse_json_response(full_response)

        if parsed and self._validate_response(parsed):
            # Preserve reasoning for next turn
            self._last_reasoning = parsed.get("reasoning", "")
            return LLMResponse(
                raw=full_response,
                parsed=parsed,
                success=True,
            )
        else:
            return LLMResponse(
                raw=full_response,
                parsed=None,
                success=False,
                error="Failed to parse streamed response as valid JSON",
            )

    def _parse_json_response(self, response: str):
        """Parse JSON from LLM response."""
        import json
        import re

        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in response
        brace_start = response.find('{')
        if brace_start != -1:
            depth = 0
            for i, char in enumerate(response[brace_start:], brace_start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(response[brace_start:i + 1])
                        except json.JSONDecodeError:
                            break

        return None

    def _validate_response(self, parsed) -> bool:
        """Validate that response has required fields."""
        from .state import RiskLevel

        required_fields = ["reasoning", "action"]

        for field in required_fields:
            if field not in parsed:
                return False

        if not isinstance(parsed.get("action"), str):
            return False

        if "confidence" in parsed:
            if not isinstance(parsed["confidence"], (int, float)):
                return False

        if "risk" in parsed:
            # Validate against RiskLevel enum values
            valid_risks = {level.value for level in RiskLevel}
            if parsed["risk"] not in valid_risks:
                return False

        return True

    def _get_next_prompt(self) -> str:
        """Get the prompt for the next iteration based on current phase."""
        recent_actions = self.state.get_recent_actions(3)

        # EXECUTING phase - give clear step-by-step instructions
        if self.state.phase == Phase.EXECUTING:
            steps = self.state.current_plan.execution_steps
            current_step_idx = self.state_manager._get_current_step()

            if steps and current_step_idx < len(steps):
                current_step = steps[current_step_idx]
                steps_text = "\n".join(
                    f"  {'-->' if i == current_step_idx else '   '} {i+1}. {step}"
                    for i, step in enumerate(steps)
                )
                return (
                    f"EXECUTE STEP {current_step_idx + 1}: {current_step}\n\n"
                    f"Approved plan:\n{steps_text}\n\n"
                    f"Use a tool to complete this step. Respond with JSON containing action and params."
                )
            else:
                return (
                    f"All plan steps complete. Use 'final_answer' to summarize what was done.\n"
                    f"Original goal: {self.state.current_goal}"
                )

        # Phase-specific prompts
        if self.state.phase == Phase.VALIDATING:
            validation_plan = self.state.current_plan.validation_plan
            if validation_plan:
                return (
                    f"VALIDATION PHASE: Execute the validation plan.\n"
                    f"Validation plan: {validation_plan}\n"
                    f"Run tests or checks to verify the changes work correctly.\n"
                    f"Use 'final_answer' when validation is complete."
                )
            else:
                return (
                    f"VALIDATION PHASE: Verify the changes work correctly.\n"
                    f"Run any relevant tests or manual verification.\n"
                    f"Use 'final_answer' when validation is complete."
                )

        if self.state.phase == Phase.CI_CHECK:
            return (
                f"CI CHECK PHASE: Check the CI/CD pipeline status.\n"
                f"Use 'check_ci_status' or 'check_ci_result' to verify CI passes.\n"
                f"Use 'final_answer' when CI check is complete."
            )

        # Default: continue with task
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
