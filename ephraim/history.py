"""
Command History

Persists command history across sessions.
"""

import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class CommandHistory:
    """
    Manages command history.

    History is persisted to ~/.ephraim/history
    """

    def __init__(self, history_file: Optional[Path] = None, max_entries: int = 1000):
        self.max_entries = max_entries

        if history_file:
            self.history_file = history_file
        else:
            # Default to ~/.ephraim/history
            ephraim_dir = Path.home() / ".ephraim"
            ephraim_dir.mkdir(parents=True, exist_ok=True)
            self.history_file = ephraim_dir / "history"

        self.entries: List[str] = []
        self._load()

    def _load(self) -> None:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.entries = [
                        line.strip() for line in f
                        if line.strip()
                    ]
            except Exception:
                self.entries = []

    def _save(self) -> None:
        """Save history to file."""
        try:
            # Trim to max entries
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries:]

            with open(self.history_file, 'w', encoding='utf-8') as f:
                for entry in self.entries:
                    f.write(entry + '\n')
        except Exception:
            pass

    def add(self, command: str) -> None:
        """Add a command to history."""
        command = command.strip()
        if not command:
            return

        # Don't add duplicates in a row
        if self.entries and self.entries[-1] == command:
            return

        self.entries.append(command)
        self._save()

    def get_recent(self, n: int = 10) -> List[str]:
        """Get the n most recent entries."""
        return self.entries[-n:]

    def search(self, query: str) -> List[str]:
        """Search history for entries containing query."""
        query = query.lower()
        return [
            entry for entry in self.entries
            if query in entry.lower()
        ]

    def get_all(self) -> List[str]:
        """Get all history entries."""
        return list(self.entries)

    def clear(self) -> None:
        """Clear all history."""
        self.entries.clear()
        self._save()

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)


# Global instance
_history: Optional[CommandHistory] = None


def get_history() -> CommandHistory:
    """Get the global command history instance."""
    global _history
    if _history is None:
        _history = CommandHistory()
    return _history
