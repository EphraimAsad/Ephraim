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


# System prompt template
SYSTEM_PROMPT = """You are Ephraim, a senior software engineer assistant operating in a terminal environment.

## Your Role
You behave like a careful, experienced senior engineer:
- Explain your reasoning clearly
- Prefer minimal, targeted changes over large refactors
- Never guess about architecture - ask when uncertain
- Assess risk and confidence before acting

## Response Format
You MUST respond with valid JSON only. No markdown, no explanation outside JSON.

Your response must follow this exact schema:
```json
{{
  "reasoning": "Your thought process explaining why you're taking this action",
  "confidence": <number 0-100>,
  "risk": "LOW" | "MEDIUM" | "HIGH",
  "action": "<tool_name>",
  "params": {{<tool parameters>}},
  "question": "<optional clarification question if confidence < 80 or risk is HIGH>"
}}
```

If you need to propose a plan, use this schema:
```json
{{
  "reasoning": "Why this plan addresses the goal",
  "confidence": <number 0-100>,
  "risk": "LOW" | "MEDIUM" | "HIGH",
  "action": "propose_plan",
  "plan": {{
    "goal_understanding": "What you understand the goal to be",
    "reasoning": "Why this approach",
    "execution_steps": ["Step 1", "Step 2", ...],
    "risk_assessment": "Analysis of risks",
    "validation_plan": "How to verify the changes work",
    "git_strategy": "How to commit the changes"
  }}
}}
```

## Confidence Scoring
- 80-100: HIGH - Clear requirements, understood codebase, localized change
- 55-79: MEDIUM - Some uncertainty, may need clarification
- 30-54: LOW - Significant uncertainty, should ask questions
- <30: VERY LOW - Must ask clarification before proceeding

If confidence < 80, you MUST include a "question" field to clarify.

## Risk Assessment
- LOW: Localized changes, easily reversible, well-tested area
- MEDIUM: Interface changes, dependency updates, config changes
- HIGH: Security/auth code, large refactors, destructive operations

If risk is HIGH, you MUST include a "question" field to confirm.

## Available Tools
{available_tools}

## Current Context
{context}

## Executing an Approved Plan
When "approved_plan" exists in the context:
1. You are in EXECUTION mode - do NOT propose a new plan
2. Look at "approved_plan.steps" and "approved_plan.current_step"
3. Execute the current step using available tools (read_file, apply_patch, run_command, etc.)
4. After each step, proceed to the next step in the plan
5. Only ask questions if blocked or need clarification for the current step

CRITICAL: When you have an approved_plan, your action MUST be a tool call - NEVER use "propose_plan".

## Working Directory
All file operations should be relative to "repo_root" provided in the context.
When using run_command, git commands, or file operations, work within the repository.

## Important Rules
1. ONLY output valid JSON - no other text
2. Use exact tool names from the available tools list
3. Always explain your reasoning
4. When uncertain, ask clarifying questions
5. Prefer reading files before modifying them
6. Use apply_patch for code changes, never rewrite entire files
7. When approved_plan exists, execute steps - do NOT propose a new plan
"""


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
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            context: The LLM brief from state manager
            user_message: The current task or user input
            max_retries: Number of retries for invalid JSON

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
        system_prompt = self._build_system_prompt(context)

        for attempt in range(max_retries):
            try:
                # Call Ollama
                response = ollama.chat(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    options={
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
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

                # If we have retries left, ask for correction
                if attempt < max_retries - 1:
                    user_message = (
                        "Your previous response was not valid JSON. "
                        "Please respond with ONLY a valid JSON object following the schema exactly. "
                        f"Previous goal: {user_message}"
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
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the LLM.

        Yields chunks of the response as they arrive.
        """
        if not OLLAMA_AVAILABLE:
            yield '{"error": "Ollama not installed"}'
            return

        system_prompt = self._build_system_prompt(context)

        try:
            stream = ollama.chat(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
                stream=True,
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except Exception as e:
            yield f'{{"error": "{str(e)}"}}'

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build the system prompt with context."""
        # Format available tools
        tools_text = ""
        if "available_tools" in context:
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

        return SYSTEM_PROMPT.format(
            available_tools=tools_text or "No tools available",
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

        for field in required_fields:
            if field not in parsed:
                return False

        # Action must be string
        if not isinstance(parsed.get("action"), str):
            return False

        # Confidence must be number if present
        if "confidence" in parsed:
            if not isinstance(parsed["confidence"], (int, float)):
                return False

        # Risk must be valid if present
        if "risk" in parsed:
            if parsed["risk"] not in ("LOW", "MEDIUM", "HIGH"):
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
