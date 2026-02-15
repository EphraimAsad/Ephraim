"""
Ask User Tool

Handles user interaction for:
- Approval requests
- Clarification questions
- Confirmation prompts
"""

from typing import Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool
from ..logging_setup import (
    print_approval_request,
    print_separator,
    confirm,
    get_user_input,
    console,
)


@register_tool
class AskUserTool(BaseTool):
    """
    Ask the user for input.

    Used for:
    - Plan approval requests
    - Clarification questions
    - Risk acknowledgment
    """

    name = "ask_user"
    description = "Ask the user a question or request approval"
    category = ToolCategory.USER_INPUT

    parameters = [
        ToolParam(
            name="question",
            type="string",
            description="The question or request to present to the user",
            required=True,
        ),
        ToolParam(
            name="request_type",
            type="string",
            description="Type of request: 'approval', 'clarification', or 'confirmation'",
            required=False,
            default="approval",
        ),
        ToolParam(
            name="options",
            type="list",
            description="List of options for multiple choice (optional)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="context",
            type="string",
            description="Additional context to display",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Present the question to the user and get response."""
        question = params["question"]
        request_type = params.get("request_type", "approval")
        options = params.get("options")
        context = params.get("context")

        # Display context if provided
        if context:
            console.print(context)
            print_separator()

        # Handle different request types
        if request_type == "approval":
            return self._handle_approval(question)
        elif request_type == "clarification":
            return self._handle_clarification(question, options)
        elif request_type == "confirmation":
            return self._handle_confirmation(question)
        else:
            return ToolResult.fail(f"Unknown request type: {request_type}")

    def _handle_approval(self, question: str) -> ToolResult:
        """Handle approval request (yes/no)."""
        print_approval_request(question)

        try:
            approved = confirm("Approve?")

            return ToolResult.ok(
                data={
                    "approval": approved,
                    "response": "approved" if approved else "rejected",
                },
                summary="Plan approved" if approved else "Plan rejected",
            )
        except (KeyboardInterrupt, EOFError):
            return ToolResult.ok(
                data={
                    "approval": False,
                    "response": "cancelled",
                },
                summary="User cancelled",
            )

    def _handle_clarification(
        self,
        question: str,
        options: Optional[list],
    ) -> ToolResult:
        """Handle clarification request (free text or multiple choice)."""
        console.print(f"\n[yellow]Clarification needed:[/yellow]")
        console.print(question)

        if options:
            # Multiple choice
            console.print("\nOptions:")
            for i, option in enumerate(options, 1):
                console.print(f"  {i}. {option}")
            console.print(f"  {len(options) + 1}. Other (specify)")

            try:
                choice = get_user_input("Enter choice (number): ").strip()

                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(options):
                        selected = options[choice_num - 1]
                        return ToolResult.ok(
                            data={
                                "response": selected,
                                "choice_index": choice_num - 1,
                            },
                            summary=f"User selected: {selected}",
                        )
                    elif choice_num == len(options) + 1:
                        # Other option
                        custom = get_user_input("Specify: ").strip()
                        return ToolResult.ok(
                            data={
                                "response": custom,
                                "custom": True,
                            },
                            summary=f"User specified: {custom}",
                        )

                # Invalid choice, treat as free text
                return ToolResult.ok(
                    data={
                        "response": choice,
                        "custom": True,
                    },
                    summary=f"User response: {choice}",
                )

            except (KeyboardInterrupt, EOFError):
                return ToolResult.ok(
                    data={"response": None, "cancelled": True},
                    summary="User cancelled",
                )
        else:
            # Free text response
            try:
                response = get_user_input("> ").strip()
                return ToolResult.ok(
                    data={"response": response},
                    summary=f"User response: {response[:50]}..."
                            if len(response) > 50 else f"User response: {response}",
                )
            except (KeyboardInterrupt, EOFError):
                return ToolResult.ok(
                    data={"response": None, "cancelled": True},
                    summary="User cancelled",
                )

    def _handle_confirmation(self, question: str) -> ToolResult:
        """Handle simple confirmation (yes/no)."""
        console.print(f"\n[yellow]{question}[/yellow]")

        try:
            confirmed = confirm()
            return ToolResult.ok(
                data={
                    "confirmed": confirmed,
                    "response": "yes" if confirmed else "no",
                },
                summary="Confirmed" if confirmed else "Not confirmed",
            )
        except (KeyboardInterrupt, EOFError):
            return ToolResult.ok(
                data={"confirmed": False, "cancelled": True},
                summary="User cancelled",
            )
