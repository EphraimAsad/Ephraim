"""
Ephraim LLM Interface

Handles communication with the Ollama local LLM server.

Features:
- System prompt injection
- JSON schema enforcement
- Retry on invalid outputs
- Streaming response support
"""

import json
import re
from typing import Dict, Any, Optional, Generator
from dataclasses import dataclass

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from .config import ModelConfig
from .logging_setup import get_logger, print_info, print_warning, print_error


# ============================================================================
# DUAL-PROMPT ARCHITECTURE
# Planning and Execution models use separate prompts for better accuracy
# ============================================================================

# Prompt for PLANNING model - ONLY proposes plans, never executes tools
PLANNING_PROMPT = """## REQUIRED JSON OUTPUT
You are in PLANNING mode. Propose a plan for user approval.

### SCHEMA:
{{"reasoning": "string", "confidence": 0-100, "risk": "LOW|MEDIUM|HIGH", "action": "propose_plan", "plan": {{"goal_understanding": "...", "execution_steps": ["..."], "validation_plan": "...", "git_strategy": "..."}}}}

### EXAMPLE:
{{"reasoning": "The user wants a CLI calculator. I will create a Python script with basic arithmetic functions.", "confidence": 85, "risk": "LOW", "action": "propose_plan", "plan": {{"goal_understanding": "Create CLI calculator with add/subtract/multiply/divide", "execution_steps": ["Create calculator.py with menu and input handling", "Add arithmetic functions (add, subtract, multiply, divide)", "Add input validation and error handling", "Test all operations"], "validation_plan": "Run calculator and test each operation manually", "git_strategy": "Single commit: Add CLI calculator"}}}}

### IF UNCERTAIN (confidence < 60):
{{"reasoning": "Need more details about requirements", "confidence": 40, "risk": "LOW", "action": "ask_user", "params": {{"question": "Your clarifying question here"}}}}

## CONTEXT
{context}

You MUST use action="propose_plan" with a plan object. JSON ONLY."""


# Prompt for EXECUTION model - ONLY executes tools, never proposes plans
EXECUTION_PROMPT = """## REQUIRED JSON OUTPUT
You are in EXECUTION mode. Execute the approved plan using tools.

### SCHEMA:
{{"reasoning": "string", "confidence": 0-100, "risk": "LOW|MEDIUM|HIGH", "action": "tool_name", "params": {{...}}}}

### EXAMPLES:
{{"reasoning": "Creating the calculator file with full implementation", "confidence": 90, "risk": "LOW", "action": "write_file", "params": {{"path": "calculator.py", "content": "#!/usr/bin/env python3\\n# Calculator implementation\\n\\ndef add(a, b):\\n    return a + b\\n..."}}}}

{{"reasoning": "Reading existing code to understand structure", "confidence": 95, "risk": "LOW", "action": "read_file", "params": {{"path": "main.py"}}}}

{{"reasoning": "Running the test suite", "confidence": 85, "risk": "LOW", "action": "run_command", "params": {{"command": "python -m pytest tests/"}}}}

{{"reasoning": "All plan steps completed successfully", "confidence": 95, "risk": "LOW", "action": "final_answer", "params": {{"summary": "Created calculator.py with add, subtract, multiply, divide operations. All tests pass."}}}}

## RULES
- "action" MUST be a tool name string: write_file, read_file, apply_patch, run_command, final_answer, etc.
- "params" contains the tool's arguments as an object
- Follow the approved plan steps in order
- Use final_answer when all steps are complete

## AVAILABLE TOOLS
{available_tools}

## CONTEXT
{context}

Execute the next plan step. JSON ONLY."""


# Legacy alias for backwards compatibility
SYSTEM_PROMPT = PLANNING_PROMPT


@dataclass
class LLMResponse:
    """Structured response from the LLM."""
    raw: str
    parsed: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str] = None


class LLMInterface:
    """
    Interface to the Ollama LLM server.

    Handles prompt formatting, response parsing, and retry logic.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = get_logger()

        if not OLLAMA_AVAILABLE:
            self.logger.warning("Ollama package not installed. LLM features disabled.")

    def is_available(self) -> bool:
        """Check if LLM is available."""
        if not OLLAMA_AVAILABLE:
            return False

        try:
            # Try to list models to verify connection
            ollama.list()
            return True
        except Exception as e:
            self.logger.error(f"Ollama not available: {e}")
            return False

    def generate(
        self,
        context: Dict[str, Any],
        user_message: str,
        max_retries: int = 3,
        prompt_template: Optional[str] = None,
        conversation_history: Optional[list] = None,
        error_context: Optional[Dict[str, Any]] = None,
        previous_reasoning: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM with full context.

        Args:
            context: The LLM brief from state manager
            user_message: The current task or user input
            max_retries: Number of retries for invalid JSON
            prompt_template: Custom prompt template (PLANNING_PROMPT or EXECUTION_PROMPT)
            conversation_history: List of previous turn messages for context
            error_context: Information about previous failed action
            previous_reasoning: LLM's reasoning from last turn

        Returns:
            LLMResponse with parsed JSON or error
        """
        if not OLLAMA_AVAILABLE:
            return LLMResponse(
                raw="",
                parsed=None,
                success=False,
                error="Ollama not installed",
            )

        # Build system prompt with context
        system_prompt = self._build_system_prompt(context, prompt_template)

        # Build messages list with conversation history
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history for context (recent turns)
        if conversation_history:
            messages.extend(conversation_history[-10:])  # Last 10 exchanges

        # Add error context if previous action failed
        if error_context:
            error_msg = (
                f"PREVIOUS ACTION FAILED:\n"
                f"  Action: {error_context.get('action', 'unknown')}\n"
                f"  Error: {error_context.get('error', 'unknown')}\n"
                f"  Suggestion: {error_context.get('suggestion', 'Try a different approach')}"
            )
            messages.append({"role": "system", "content": error_msg})

        # Add previous reasoning to maintain continuity
        if previous_reasoning:
            messages.append({
                "role": "system",
                "content": f"Your previous reasoning: {previous_reasoning}"
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        for attempt in range(max_retries):
            try:
                # Call Ollama
                response = ollama.chat(
                    model=self.config.model_name,
                    messages=messages,
                    options={
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
                    format="json",
                )

                raw_response = response["message"]["content"]

                # Try to parse JSON
                parsed = self._parse_json_response(raw_response)

                if parsed is not None:
                    # Validate response structure
                    if self._validate_response(parsed):
                        return LLMResponse(
                            raw=raw_response,
                            parsed=parsed,
                            success=True,
                        )
                    else:
                        self.logger.warning(f"Invalid response structure (attempt {attempt + 1})")
                else:
                    self.logger.warning(f"Failed to parse JSON (attempt {attempt + 1})")

                # If we have retries left, ask for correction with specific feedback
                if attempt < max_retries - 1:
                    got_keys = list(parsed.keys()) if parsed else []
                    user_message = (
                        f"INVALID RESPONSE. Your JSON must have these fields: reasoning, action, confidence, risk. "
                        f"You returned keys: {got_keys}. "
                        f"Original task: {user_message}"
                    )

            except Exception as e:
                self.logger.error(f"LLM error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return LLMResponse(
                        raw="",
                        parsed=None,
                        success=False,
                        error=str(e),
                    )

        return LLMResponse(
            raw="",
            parsed=None,
            success=False,
            error="Failed to get valid JSON response after retries",
        )

    def generate_stream(
        self,
        context: Dict[str, Any],
        user_message: str,
        prompt_template: Optional[str] = None,
        conversation_history: Optional[list] = None,
        error_context: Optional[Dict[str, Any]] = None,
        previous_reasoning: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the LLM with full context.

        Yields chunks of the response as they arrive.

        Args:
            context: The LLM brief from state manager
            user_message: The current task or user input
            prompt_template: Custom prompt template (PLANNING_PROMPT or EXECUTION_PROMPT)
            conversation_history: List of previous turn messages for context
            error_context: Information about previous failed action
            previous_reasoning: LLM's reasoning from last turn
        """
        if not OLLAMA_AVAILABLE:
            yield '{"error": "Ollama not installed"}'
            return

        system_prompt = self._build_system_prompt(context, prompt_template)

        # Build messages list with conversation history
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-10:])

        # Add error context if previous action failed
        if error_context:
            error_msg = (
                f"PREVIOUS ACTION FAILED:\n"
                f"  Action: {error_context.get('action', 'unknown')}\n"
                f"  Error: {error_context.get('error', 'unknown')}\n"
                f"  Suggestion: {error_context.get('suggestion', 'Try a different approach')}"
            )
            messages.append({"role": "system", "content": error_msg})

        # Add previous reasoning
        if previous_reasoning:
            messages.append({
                "role": "system",
                "content": f"Your previous reasoning: {previous_reasoning}"
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        try:
            stream = ollama.chat(
                model=self.config.model_name,
                messages=messages,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
                stream=True,
                format="json",
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except Exception as e:
            yield f'{{"error": "{str(e)}"}}'

    def _build_system_prompt(
        self,
        context: Dict[str, Any],
        template: Optional[str] = None,
    ) -> str:
        """Build the system prompt with context.

        Args:
            context: The LLM brief from state manager
            template: Prompt template to use (defaults to PLANNING_PROMPT)
        """
        prompt = template or PLANNING_PROMPT

        # Format available tools (only needed for EXECUTION_PROMPT)
        tools_text = ""
        if "available_tools" in context and "{available_tools}" in prompt:
            for tool in context["available_tools"]:
                params = ", ".join(
                    f"{p['name']}: {p['type']}"
                    for p in tool.get("parameters", [])
                )
                tools_text += f"- {tool['name']}: {tool['description']}\n"
                if params:
                    tools_text += f"  Parameters: {params}\n"

        # Format context
        context_text = json.dumps(context, indent=2, default=str)

        return prompt.format(
            available_tools=tools_text or "N/A",
            context=context_text,
        )

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response.

        Handles common issues like markdown code blocks.
        """
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
            # Find matching closing brace
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

    def _validate_response(self, parsed: Dict[str, Any]) -> bool:
        """Validate that response has required fields."""
        required_fields = ["reasoning", "action"]

        # Check for missing required fields
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            self.logger.warning(f"Response missing required fields: {missing}")
            self.logger.warning(f"Got keys: {list(parsed.keys())}")
            return False

        # Action must be string
        if not isinstance(parsed.get("action"), str):
            self.logger.warning(f"'action' must be string, got: {type(parsed.get('action'))}")
            return False

        # Confidence must be number if present
        if "confidence" in parsed:
            if not isinstance(parsed["confidence"], (int, float)):
                self.logger.warning(f"'confidence' must be number, got: {type(parsed['confidence'])}")
                return False

        # Risk must be valid if present
        if "risk" in parsed:
            if parsed["risk"] not in ("LOW", "MEDIUM", "HIGH"):
                self.logger.warning(f"'risk' must be LOW/MEDIUM/HIGH, got: {parsed['risk']}")
                return False

        return True


def create_llm_interface(config: ModelConfig) -> LLMInterface:
    """Create an LLM interface instance."""
    return LLMInterface(config)


def verify_ollama_connection(config: ModelConfig) -> bool:
    """Verify if Ollama is available and model is loaded."""
    if not OLLAMA_AVAILABLE:
        print_error("Ollama package not installed. Run: pip install ollama")
        return False

    try:
        # Check connection
        response = ollama.list()

        # Check if our model is available
        # Ollama API returns ListResponse with .models list of Model objects
        model_names = [m.model for m in response.models]
        if config.model_name not in model_names:
            # Try to find partial match (with tags)
            found = any(config.model_name.split(":")[0] in m for m in model_names)
            if not found:
                print_warning(f"Model '{config.model_name}' not found. Available: {model_names}")
                print_info(f"Run: ollama pull {config.model_name}")
                return False

        print_info(f"Ollama connected. Model: {config.model_name}")
        return True

    except Exception as e:
        print_error(f"Cannot connect to Ollama: {e}")
        print_info("Make sure Ollama is running: ollama serve")
        return False
