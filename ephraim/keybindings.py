"""
Keyboard Bindings

Provides enhanced keyboard input using prompt_toolkit.
Includes history navigation, search, and shortcuts.
"""

import os
from typing import Optional, Callable

# Lazy import prompt_toolkit
PROMPT_TOOLKIT_AVAILABLE = False
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    pass

from pathlib import Path


class EphraimPrompt:
    """
    Enhanced prompt with keyboard bindings and history.

    Falls back to basic input() if prompt_toolkit not available.
    """

    def __init__(
        self,
        history_file: Optional[Path] = None,
        prompt_text: str = "Ephraim> ",
    ):
        self.prompt_text = prompt_text
        self.session: Optional["PromptSession"] = None

        if PROMPT_TOOLKIT_AVAILABLE:
            self._setup_prompt_toolkit(history_file)

    def _setup_prompt_toolkit(self, history_file: Optional[Path]) -> None:
        """Setup prompt_toolkit session."""
        # History
        if history_file:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(history_file))
        else:
            # Default history file
            default_path = Path.home() / ".ephraim" / "prompt_history"
            default_path.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(default_path))

        # Key bindings
        bindings = KeyBindings()

        @bindings.add('c-c')
        def _(event):
            """Ctrl+C - Abort current input."""
            event.app.exit(result='')

        @bindings.add('c-l')
        def _(event):
            """Ctrl+L - Clear screen."""
            os.system('cls' if os.name == 'nt' else 'clear')

        @bindings.add('c-d')
        def _(event):
            """Ctrl+D - Exit."""
            raise EOFError()

        # Style
        style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'input': '#ffffff',
        })

        # Create session
        self.session = PromptSession(
            history=history,
            key_bindings=bindings,
            style=style,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
        )

    def get_input(self, prompt: Optional[str] = None) -> str:
        """
        Get input from user.

        Uses prompt_toolkit if available, falls back to input().
        """
        display_prompt = prompt or self.prompt_text

        if self.session:
            try:
                return self.session.prompt(
                    HTML(f'<prompt>{display_prompt}</prompt>'),
                )
            except EOFError:
                return 'quit'
            except KeyboardInterrupt:
                return ''
        else:
            # Fallback to basic input
            try:
                return input(display_prompt)
            except EOFError:
                return 'quit'
            except KeyboardInterrupt:
                return ''

    def get_confirmation(self, prompt: str = "Proceed? (y/n): ") -> bool:
        """Get yes/no confirmation."""
        response = self.get_input(prompt).strip().lower()
        return response in ('y', 'yes')


# Global instance
_prompt: Optional[EphraimPrompt] = None


def get_prompt() -> EphraimPrompt:
    """Get the global prompt instance."""
    global _prompt
    if _prompt is None:
        _prompt = EphraimPrompt()
    return _prompt


def prompt_input(prompt: str = "Ephraim> ") -> str:
    """Get input using the global prompt."""
    return get_prompt().get_input(prompt)


def prompt_confirm(prompt: str = "Proceed? (y/n): ") -> bool:
    """Get confirmation using the global prompt."""
    return get_prompt().get_confirmation(prompt)
