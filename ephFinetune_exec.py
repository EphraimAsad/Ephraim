#!/usr/bin/env python3
"""
Ephraim Execution Model Fine-Tuning Script
===========================================
Generates 500,000 training examples for the execution model (BKnight-coder:14b).

The execution model ONLY executes tools. It never proposes plans.
It receives approved plan steps and outputs tool calls.

This file covers:
- All 36 tools with multiple examples each
- Context-aware patterns (read before edit)
- Error recovery patterns
- Production-quality code generation
- Multi-agent operations (NEW): spawn, wait, coordinate agents

Run this on Google Colab with A100 GPU (40GB VRAM).
"""

import json
import random
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# =============================================================================
# CODE SNIPPETS - Production Quality Examples
# =============================================================================

CALCULATOR_CODE = '''#!/usr/bin/env python3
"""CLI Calculator - Interactive arithmetic calculator.

Usage:
    python calculator.py

Examples:
    >>> 5 + 3
    8
    >>> 10 / 2
    5.0
"""

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Add two numbers and return the result."""
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Subtract b from a and return the result."""
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Multiply two numbers and return the result."""
    return a * b


def divide(a: Number, b: Number) -> float:
    """Divide a by b and return the result.

    Raises:
        ValueError: If b is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def main() -> None:
    """Main entry point for the calculator."""
    print("Calculator - Enter 'q' to quit")
    print("Format: number operator number (e.g., 5 + 3)")

    operations = {
        '+': add,
        '-': subtract,
        '*': multiply,
        '/': divide,
    }

    while True:
        try:
            expr = input(">>> ").strip()

            if expr.lower() == 'q':
                print("Goodbye!")
                break

            # Parse expression
            parts = expr.split()
            if len(parts) != 3:
                print("Error: Use format 'number operator number'")
                continue

            a, op, b = parts
            a, b = float(a), float(b)

            if op not in operations:
                print(f"Error: Unknown operator '{op}'")
                continue

            result = operations[op](a, b)
            print(result)

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
'''

TODO_APP_CODE = '''#!/usr/bin/env python3
"""Todo List Application with JSON persistence.

Usage:
    python todo.py add "Task description"
    python todo.py list
    python todo.py done <task_id>
    python todo.py remove <task_id>
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Task:
    """Represents a todo task."""
    id: int
    description: str
    completed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class TodoList:
    """Manages a list of tasks with JSON persistence."""

    def __init__(self, filepath: str = "todos.json"):
        self.filepath = Path(filepath)
        self.tasks: List[Task] = []
        self._load()

    def _load(self) -> None:
        """Load tasks from JSON file."""
        if self.filepath.exists():
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                self.tasks = [Task(**t) for t in data]

    def _save(self) -> None:
        """Save tasks to JSON file."""
        with open(self.filepath, 'w') as f:
            json.dump([asdict(t) for t in self.tasks], f, indent=2)

    def _next_id(self) -> int:
        """Get the next available task ID."""
        if not self.tasks:
            return 1
        return max(t.id for t in self.tasks) + 1

    def add(self, description: str) -> Task:
        """Add a new task."""
        task = Task(id=self._next_id(), description=description)
        self.tasks.append(task)
        self._save()
        return task

    def list_all(self) -> List[Task]:
        """List all tasks."""
        return self.tasks

    def mark_done(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.completed = True
                self._save()
                return task
        return None

    def remove(self, task_id: int) -> bool:
        """Remove a task by ID."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self._save()
                return True
        return False


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return

    todo = TodoList()
    command = sys.argv[1].lower()

    if command == "add" and len(sys.argv) > 2:
        description = " ".join(sys.argv[2:])
        task = todo.add(description)
        print(f"Added task {task.id}: {task.description}")

    elif command == "list":
        tasks = todo.list_all()
        if not tasks:
            print("No tasks.")
        for t in tasks:
            status = "✓" if t.completed else " "
            print(f"[{status}] {t.id}: {t.description}")

    elif command == "done" and len(sys.argv) > 2:
        task_id = int(sys.argv[2])
        if todo.mark_done(task_id):
            print(f"Task {task_id} marked as done.")
        else:
            print(f"Task {task_id} not found.")

    elif command == "remove" and len(sys.argv) > 2:
        task_id = int(sys.argv[2])
        if todo.remove(task_id):
            print(f"Task {task_id} removed.")
        else:
            print(f"Task {task_id} not found.")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
'''

HELLO_WORLD_CODE = '''#!/usr/bin/env python3
"""Simple Hello World program."""

def main() -> None:
    """Print hello world message."""
    print("Hello, World!")


if __name__ == "__main__":
    main()
'''

CONFIG_CODE = '''#!/usr/bin/env python3
"""Application configuration module."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""
    debug: bool = True
    host: str = "localhost"
    port: int = 8080
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            debug=os.getenv("DEBUG", "true").lower() == "true",
            host=os.getenv("HOST", "localhost"),
            port=int(os.getenv("PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Default configuration
config = Config()
'''

TEST_CODE = '''#!/usr/bin/env python3
"""Unit tests for calculator module."""

import unittest
from calculator import add, subtract, multiply, divide


class TestCalculator(unittest.TestCase):
    """Test cases for calculator functions."""

    def test_add(self):
        """Test addition."""
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)

    def test_subtract(self):
        """Test subtraction."""
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(0, 5), -5)

    def test_multiply(self):
        """Test multiplication."""
        self.assertEqual(multiply(3, 4), 12)
        self.assertEqual(multiply(-2, 3), -6)
        self.assertEqual(multiply(0, 100), 0)

    def test_divide(self):
        """Test division."""
        self.assertEqual(divide(10, 2), 5)
        self.assertEqual(divide(7, 2), 3.5)

    def test_divide_by_zero(self):
        """Test division by zero raises error."""
        with self.assertRaises(ValueError):
            divide(10, 0)


if __name__ == "__main__":
    unittest.main()
'''

# More code snippets
CODE_SNIPPETS = {
    "calculator": CALCULATOR_CODE,
    "todo": TODO_APP_CODE,
    "hello": HELLO_WORLD_CODE,
    "config": CONFIG_CODE,
    "test": TEST_CODE,
}

# =============================================================================
# TOOL DEFINITIONS - All 36 Tools
# =============================================================================

# Tool: write_file
WRITE_FILE_EXAMPLES = [
    ("Create calculator.py with full implementation", "calculator.py", CALCULATOR_CODE),
    ("Create todo.py with task management", "todo.py", TODO_APP_CODE),
    ("Create hello.py with hello world", "hello.py", HELLO_WORLD_CODE),
    ("Create config.py with settings", "config.py", CONFIG_CODE),
    ("Create test_calculator.py with unit tests", "test_calculator.py", TEST_CODE),
    ("Create main.py entry point", "main.py", '#!/usr/bin/env python3\n"""Main entry point."""\n\nfrom app import run\n\nif __name__ == "__main__":\n    run()\n'),
    ("Create utils.py with helper functions", "utils.py", '#!/usr/bin/env python3\n"""Utility functions."""\n\ndef format_string(s: str) -> str:\n    """Format a string."""\n    return s.strip().lower()\n\ndef is_valid(x) -> bool:\n    """Check if value is valid."""\n    return x is not None and str(x).strip() != ""\n'),
    ("Create requirements.txt", "requirements.txt", "requests>=2.28.0\npytest>=7.0.0\nclick>=8.0.0\n"),
    ("Create .gitignore", ".gitignore", "*.pyc\n__pycache__/\n.env\nvenv/\n*.egg-info/\ndist/\nbuild/\n"),
    ("Create README.md", "README.md", "# Project\n\nDescription of the project.\n\n## Installation\n\n```bash\npip install -r requirements.txt\n```\n\n## Usage\n\n```bash\npython main.py\n```\n"),
]

# Tool: read_file
READ_FILE_EXAMPLES = [
    ("Read main.py to understand the code", "main.py"),
    ("Read calculator.py to understand its structure", "calculator.py"),
    ("Read config.json for settings", "config.json"),
    ("Read requirements.txt for dependencies", "requirements.txt"),
    ("Read README.md for documentation", "README.md"),
    ("Read .env for environment variables", ".env"),
    ("Read test_main.py to understand test structure", "test_main.py"),
    ("Read utils.py to find helper functions", "utils.py"),
    ("Read setup.py for package configuration", "setup.py"),
    ("Read pyproject.toml for project settings", "pyproject.toml"),
]

# Tool: apply_patch
APPLY_PATCH_EXAMPLES = [
    ("Add error handling to divide function", "calculator.py",
     "def divide(a, b):\n    return a / b",
     'def divide(a, b):\n    """Divide a by b with error handling."""\n    if b == 0:\n        raise ValueError("Cannot divide by zero")\n    return a / b'),
    ("Add type hints to function", "utils.py",
     "def format_string(s):",
     "def format_string(s: str) -> str:"),
    ("Add import statement", "main.py",
     "import json",
     "import json\nimport os\nfrom typing import Dict, Any"),
    ("Fix the typo in function name", "utils.py",
     "def proccess_data(",
     "def process_data("),
    ("Add docstring to function", "calculator.py",
     "def add(a, b):\n    return a + b",
     'def add(a, b):\n    """Add two numbers and return the result."""\n    return a + b'),
    ("Add logging to function", "main.py",
     "def main():",
     'import logging\n\nlogger = logging.getLogger(__name__)\n\ndef main():\n    logger.info("Starting application")'),
    ("Fix indentation error", "script.py",
     "def foo():\nreturn 1",
     "def foo():\n    return 1"),
    ("Add return statement", "utils.py",
     "def validate(x):\n    if x > 0:\n        pass",
     "def validate(x):\n    if x > 0:\n        return True\n    return False"),
]

# Tool: run_command
RUN_COMMAND_EXAMPLES = [
    ("Run the script to verify it works", "python calculator.py"),
    ("Run the main script", "python main.py"),
    ("Run hello.py to test", "python hello.py"),
    ("Run the tests", "python -m pytest"),
    ("Run tests with verbose output", "python -m pytest -v"),
    ("Run specific test file", "python -m pytest test_calculator.py"),
    ("Check Python version", "python --version"),
    ("Install dependencies", "pip install -r requirements.txt"),
    ("Run linter", "python -m flake8 ."),
    ("Format code with black", "python -m black ."),
    ("Type check with mypy", "python -m mypy ."),
    ("Run with arguments", "python script.py --input data.txt"),
]

# Tool: final_answer
FINAL_ANSWER_EXAMPLES = [
    ("All steps completed", "Created calculator.py with add, subtract, multiply, and divide functions. All operations tested successfully."),
    ("Calculator complete", "Successfully implemented the CLI calculator with error handling for division by zero."),
    ("Task finished", "Completed todo.py with full CRUD operations and JSON persistence. Ready for use."),
    ("Implementation done", "Implemented the requested feature with proper error handling and tests."),
    ("Bug fixed", "Fixed the TypeError by adding proper type checking. The function now handles edge cases correctly."),
    ("Refactoring complete", "Extracted validation logic into a separate function and added type hints throughout."),
    ("Tests added", "Added comprehensive unit tests covering all functions and edge cases."),
    ("API endpoint created", "Created the REST API endpoint with proper validation and error responses."),
    ("Configuration complete", "Set up environment configuration with .env file and config loading."),
    ("Documentation added", "Added docstrings to all public functions and updated README."),
]

# Tool: glob_search
GLOB_SEARCH_EXAMPLES = [
    ("Find all Python files", "**/*.py"),
    ("Find all test files", "**/test_*.py"),
    ("Find config files", "**/*.json"),
    ("Find all markdown files", "**/*.md"),
    ("Find JavaScript files", "**/*.js"),
    ("Find TypeScript files", "**/*.ts"),
    ("Find all files in src", "src/**/*"),
    ("Find requirements files", "**/requirements*.txt"),
    ("Find YAML files", "**/*.yaml"),
    ("Find all init files", "**/__init__.py"),
]

# Tool: grep_search
GREP_SEARCH_EXAMPLES = [
    ("Find where function is defined", "def calculate"),
    ("Search for TODO comments", "TODO"),
    ("Find class definitions", "class.*:"),
    ("Search for imports", "import requests"),
    ("Find error handling", "except.*Error"),
    ("Search for API endpoints", "@app.route"),
    ("Find test functions", "def test_"),
    ("Search for config usage", "config\\."),
    ("Find database queries", "SELECT.*FROM"),
    ("Search for logging", "logger\\.(info|error|warning)"),
]

# Tool: list_directory
LIST_DIR_EXAMPLES = [
    ("List current directory", "."),
    ("List src folder", "src"),
    ("List tests folder", "tests"),
    ("List project root", "."),
    ("List config directory", "config"),
]

# Tool: create_directory
CREATE_DIR_EXAMPLES = [
    ("Create src directory", "src"),
    ("Create tests directory", "tests"),
    ("Create docs directory", "docs"),
    ("Create config directory", "config"),
    ("Create output directory", "output"),
]

# Tool: delete_file
DELETE_FILE_EXAMPLES = [
    ("Delete temporary file", "temp.py"),
    ("Delete old backup", "backup_old.py"),
    ("Remove unused file", "unused.py"),
]

# Tool: move_file
MOVE_FILE_EXAMPLES = [
    ("Move file to src folder", "utils.py", "src/utils.py"),
    ("Rename file", "old_name.py", "new_name.py"),
    ("Move test to tests folder", "test_main.py", "tests/test_main.py"),
]

# Tool: copy_file
COPY_FILE_EXAMPLES = [
    ("Copy config as template", "config.py", "config.example.py"),
    ("Backup file", "main.py", "main.py.bak"),
]

# Tool: git_status
GIT_STATUS_EXAMPLES = [
    ("Check repository status", None),
]

# Tool: git_diff
GIT_DIFF_EXAMPLES = [
    ("View uncommitted changes", None),
    ("View changes in file", "main.py"),
]

# Tool: git_add
GIT_ADD_EXAMPLES = [
    ("Stage all changes", "."),
    ("Stage specific file", "calculator.py"),
    ("Stage test files", "tests/"),
]

# Tool: git_commit
GIT_COMMIT_EXAMPLES = [
    ("Commit with message", "Add calculator implementation"),
    ("Commit bug fix", "Fix division by zero error"),
    ("Commit feature", "Add todo list functionality"),
]

# Tool: ask_user
ASK_USER_EXAMPLES = [
    ("Clarify requirements", "Should the calculator support floating point numbers?"),
    ("Get confirmation", "The file already exists. Should I overwrite it?"),
    ("Ask for input", "What should the default port be?"),
]

# =============================================================================
# MULTI-AGENT TOOLS (NEW - 25K examples target)
# =============================================================================

# Tool: spawn_agent - spawn a sub-agent for focused tasks
SPAWN_AGENT_EXAMPLES = [
    # EXPLORE agents
    ("Find all files importing the deprecated module", "EXPLORE", "old_utils.py",
     {"target_module": "old_utils.py", "purpose": "find_imports"}),
    ("Search for all API endpoint definitions", "EXPLORE", "REST endpoints",
     {"target_pattern": "@app.route", "scope": "api"}),
    ("Analyze frontend component structure", "EXPLORE", "React components",
     {"framework": "react", "scope": "components"}),
    ("Find all database models", "EXPLORE", "database schema",
     {"target_pattern": "class.*Model", "scope": "models"}),
    ("Locate configuration files", "EXPLORE", "config files",
     {"pattern": "*.config.*", "scope": "project"}),
    ("Find test files for the module", "EXPLORE", "test coverage",
     {"target_module": "calculator", "scope": "tests"}),

    # RESEARCH agents
    ("Analyze performance bottlenecks", "RESEARCH", "performance analysis",
     {"focus": "bottlenecks", "metrics": "response_time"}),
    ("Evaluate security vulnerabilities", "RESEARCH", "security audit",
     {"focus": "owasp_top_10", "scope": "full"}),
    ("Profile memory usage patterns", "RESEARCH", "memory profiling",
     {"focus": "memory_leaks", "scope": "runtime"}),
    ("Analyze code complexity", "RESEARCH", "complexity analysis",
     {"focus": "cyclomatic_complexity", "threshold": 10}),
    ("Review error handling patterns", "RESEARCH", "error patterns",
     {"focus": "exception_handling", "scope": "full"}),

    # EXECUTE agents
    ("Update imports in service files", "EXECUTE", "import updates",
     {"old_import": "from old_utils", "new_import": "from new_utils"}),
    ("Add logging to API endpoints", "EXECUTE", "logging addition",
     {"target": "endpoints", "log_level": "INFO"}),
    ("Apply code formatting", "EXECUTE", "code formatting",
     {"formatter": "black", "scope": "src"}),
    ("Update type hints", "EXECUTE", "type annotation",
     {"scope": "public_functions", "style": "pep484"}),

    # PLAN agents
    ("Design refactoring strategy", "PLAN", "refactoring plan",
     {"target": "authentication", "approach": "incremental"}),
    ("Plan migration approach", "PLAN", "migration strategy",
     {"from": "monolith", "to": "microservices"}),
]

# Tool: wait_agent - wait for a single agent to complete
WAIT_AGENT_EXAMPLES = [
    ("agent_abc123", 60, "exploration results"),
    ("agent_def456", 120, "research analysis"),
    ("agent_ghi789", 90, "code execution"),
    ("agent_jkl012", 30, "quick search"),
    ("agent_mno345", 180, "comprehensive audit"),
]

# Tool: wait_all_agents - wait for multiple agents
WAIT_ALL_AGENTS_EXAMPLES = [
    (["agent_a1", "agent_b2", "agent_c3"], 120, "parallel explorations"),
    (["frontend_agent", "backend_agent"], 180, "full-stack analysis"),
    (["test_agent_1", "test_agent_2", "test_agent_3"], 90, "parallel test runs"),
    (["security_agent", "perf_agent"], 150, "security and performance audit"),
]

# Tool: get_agent_status - check agent progress
GET_AGENT_STATUS_EXAMPLES = [
    ("agent_abc123", "check exploration progress"),
    ("research_001", "verify research completion"),
    ("exec_worker", "monitor execution status"),
]

# Tool: cancel_agent - cancel a running agent
CANCEL_AGENT_EXAMPLES = [
    ("agent_slow", "taking too long"),
    ("agent_stuck", "appears to be stuck"),
    ("redundant_agent", "no longer needed"),
]

# Context patterns for using agent results
AGENT_RESULT_PATTERNS = [
    # Using explore results to guide action
    {
        "context": "EXECUTE STEP: Update files found by explore agent\nAgent Results: Found 5 files importing deprecated module: src/api/users.py, src/api/products.py, src/services/auth.py, src/utils/helpers.py, tests/test_api.py",
        "reasoning": "The explore agent found 5 files importing the deprecated module. I'll start updating the first file.",
        "action": "apply_patch",
        "params": {"path": "src/api/users.py", "find": "from old_utils import helper", "replace": "from new_utils import helper"}
    },
    # Using research results to make decisions
    {
        "context": "EXECUTE STEP: Implement optimization based on research\nAgent Results: Profiling shows database queries take 80% of response time. Top slow queries: get_user_by_id (200ms), get_all_products (500ms)",
        "reasoning": "Research agent identified database queries as the main bottleneck. I'll add caching to get_user_by_id first.",
        "action": "apply_patch",
        "params": {"path": "src/services/user_service.py", "find": "def get_user_by_id(user_id):", "replace": "@cache(ttl=300)\ndef get_user_by_id(user_id):"}
    },
    # Using multiple agent results
    {
        "context": "EXECUTE STEP: Integrate findings from parallel agents\nFrontend Agent: Found 12 components using old API\nBackend Agent: Found 8 endpoints returning deprecated format",
        "reasoning": "Both agents completed. The backend has fewer changes, so I'll update the API response format first to unblock frontend updates.",
        "action": "apply_patch",
        "params": {"path": "src/api/responses.py", "find": "return {'data': data}", "replace": "return {'data': data, 'metadata': get_metadata()}"}
    },
    # Handling agent failure
    {
        "context": "EXECUTE STEP: Continue after agent failure\nAgent Status: FAILED - timeout after 120s",
        "reasoning": "The agent timed out. I'll take a different approach and search directly.",
        "action": "glob_search",
        "params": {"pattern": "**/deprecated*.py"}
    },
    # Spawning follow-up agent
    {
        "context": "EXECUTE STEP: Deep dive based on initial findings\nAgent Results: Found complex authentication logic in auth_service.py (500 lines)",
        "reasoning": "The file is large. I'll spawn a focused RESEARCH agent to analyze the specific authentication patterns.",
        "action": "spawn_agent",
        "params": {"task": "Analyze authentication patterns in auth_service.py", "agent_type": "RESEARCH", "context": {"file": "auth_service.py", "focus": "auth_patterns"}}
    },
]

# Parallel agent coordination patterns
PARALLEL_COORDINATION_PATTERNS = [
    {
        "context": "EXECUTE STEP: Spawn parallel agents for full-stack analysis",
        "reasoning": "This requires analyzing both frontend and backend. I'll spawn two parallel EXPLORE agents to work simultaneously.",
        "action": "spawn_agents_parallel",
        "params": {
            "agents": [
                {"task": "Analyze React component hierarchy", "agent_type": "EXPLORE", "context": {"scope": "frontend"}},
                {"task": "Analyze API endpoint structure", "agent_type": "EXPLORE", "context": {"scope": "backend"}}
            ]
        }
    },
    {
        "context": "EXECUTE STEP: Parallel updates across services",
        "reasoning": "The changes to each service are independent. I'll spawn parallel EXECUTE agents for efficiency.",
        "action": "spawn_agents_parallel",
        "params": {
            "agents": [
                {"task": "Update user-service logging", "agent_type": "EXECUTE"},
                {"task": "Update product-service logging", "agent_type": "EXECUTE"},
                {"task": "Update order-service logging", "agent_type": "EXECUTE"}
            ]
        }
    },
]

# =============================================================================
# CONTEXT-AWARE PATTERNS
# =============================================================================

CONTEXT_PATTERNS = [
    # Read before edit
    {
        "context": "EXECUTE STEP: Modify calculator.py to add error handling",
        "reasoning": "Before modifying calculator.py, I should read it to understand its current structure and existing code patterns",
        "action": "read_file",
        "params": {"path": "calculator.py"}
    },
    # Search before write
    {
        "context": "EXECUTE STEP: Create a utility function for validation",
        "reasoning": "Before creating a new file, I should search for existing utility files to avoid duplication",
        "action": "glob_search",
        "params": {"pattern": "**/utils*.py"}
    },
    # Check before overwrite
    {
        "context": "EXECUTE STEP: Create config.py",
        "reasoning": "I should check if config.py already exists to avoid overwriting existing configuration",
        "action": "glob_search",
        "params": {"pattern": "**/config.py"}
    },
    # Understand before fix
    {
        "context": "EXECUTE STEP: Fix the bug in the calculate function",
        "reasoning": "I need to read the file first to understand the current implementation and locate the bug",
        "action": "read_file",
        "params": {"path": "calculator.py"}
    },
]

# =============================================================================
# ERROR RECOVERY PATTERNS
# =============================================================================

ERROR_RECOVERY_PATTERNS = [
    # File not found -> search
    {
        "context": "Previous: apply_patch to calculator.py FAILED - file not found",
        "reasoning": "The file was not found. I should search for it to find the correct path",
        "action": "glob_search",
        "params": {"pattern": "**/calculator.py"}
    },
    # Pattern not found -> read first
    {
        "context": "Previous: apply_patch FAILED - pattern not found in file",
        "reasoning": "The pattern I was looking for doesn't exist. I should read the file to see its actual content",
        "action": "read_file",
        "params": {"path": "calculator.py"}
    },
    # Tests directory not found -> complete anyway
    {
        "context": "Previous: run_command 'pytest tests/' FAILED - directory not found",
        "reasoning": "No tests directory exists. Since the main implementation is complete, I'll finish the task",
        "action": "final_answer",
        "params": {"summary": "Implementation complete. No existing test suite found, but the code is functional."}
    },
    # Command failed -> try alternative
    {
        "context": "Previous: run_command 'python script.py' FAILED - ModuleNotFoundError",
        "reasoning": "A required module is missing. I should check the imports or install dependencies",
        "action": "read_file",
        "params": {"path": "script.py"}
    },
    # Permission denied -> report
    {
        "context": "Previous: write_file FAILED - permission denied",
        "reasoning": "Cannot write to this location. I should ask the user for guidance",
        "action": "ask_user",
        "params": {"question": "Cannot write to this location due to permissions. Should I try a different path?"}
    },
]

# =============================================================================
# EXAMPLE GENERATION
# =============================================================================

def generate_write_file_example(description: str, path: str, content: str) -> Dict[str, Any]:
    """Generate a write_file training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()}. Creating the file with the complete implementation.",
        "confidence": random.randint(88, 98),
        "risk": "LOW",
        "action": "write_file",
        "params": {"path": path, "content": content}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_read_file_example(description: str, path: str) -> Dict[str, Any]:
    """Generate a read_file training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()} to understand its current structure.",
        "confidence": random.randint(90, 98),
        "risk": "LOW",
        "action": "read_file",
        "params": {"path": path}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_apply_patch_example(description: str, path: str, find: str, replace: str) -> Dict[str, Any]:
    """Generate an apply_patch training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()}. Using apply_patch for precise modification.",
        "confidence": random.randint(85, 95),
        "risk": "MEDIUM",
        "action": "apply_patch",
        "params": {"path": path, "find": find, "replace": replace}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_run_command_example(description: str, command: str) -> Dict[str, Any]:
    """Generate a run_command training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()}. Executing the command.",
        "confidence": random.randint(85, 95),
        "risk": "LOW",
        "action": "run_command",
        "params": {"command": command}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_final_answer_example(description: str, summary: str) -> Dict[str, Any]:
    """Generate a final_answer training example with pre-formatted text."""
    instruction = f"FINAL STEP: {description}"
    output = {
        "reasoning": "All plan steps have been completed successfully. The implementation is ready.",
        "confidence": 95,
        "risk": "LOW",
        "action": "final_answer",
        "params": {"summary": summary}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_glob_search_example(description: str, pattern: str) -> Dict[str, Any]:
    """Generate a glob_search training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()} to locate the files.",
        "confidence": random.randint(85, 95),
        "risk": "LOW",
        "action": "glob_search",
        "params": {"pattern": pattern}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_grep_search_example(description: str, pattern: str) -> Dict[str, Any]:
    """Generate a grep_search training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {description}"
    output = {
        "reasoning": f"I need to {description.lower()} by searching the code.",
        "confidence": random.randint(85, 95),
        "risk": "LOW",
        "action": "grep_search",
        "params": {"pattern": pattern}
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_git_example(action: str, params: Dict) -> Dict[str, Any]:
    """Generate a git tool training example with pre-formatted text."""
    descriptions = {
        "git_status": "Check the repository status",
        "git_diff": "View the changes",
        "git_add": "Stage the changes",
        "git_commit": "Commit the changes",
    }
    instruction = f"EXECUTE STEP: {descriptions.get(action, 'Git operation')}"
    output = {
        "reasoning": f"I need to {descriptions.get(action, 'perform git operation').lower()}.",
        "confidence": random.randint(90, 98),
        "risk": "LOW" if action in ["git_status", "git_diff"] else "MEDIUM",
        "action": action,
        "params": params
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_context_aware_example(pattern: Dict) -> Dict[str, Any]:
    """Generate a context-aware training example with pre-formatted text."""
    instruction = pattern["context"]
    output = {
        "reasoning": pattern["reasoning"],
        "confidence": random.randint(85, 95),
        "risk": "LOW",
        "action": pattern["action"],
        "params": pattern["params"]
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_error_recovery_example(pattern: Dict) -> Dict[str, Any]:
    """Generate an error recovery training example with pre-formatted text."""
    instruction = pattern["context"]
    output = {
        "reasoning": pattern["reasoning"],
        "confidence": random.randint(75, 90),
        "risk": "LOW",
        "action": pattern["action"],
        "params": pattern["params"]
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


# =============================================================================
# MULTI-AGENT EXAMPLE GENERATORS (NEW)
# =============================================================================

def generate_spawn_agent_example(task: str, agent_type: str, topic: str, context: Dict) -> Dict[str, Any]:
    """Generate a spawn_agent training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: {task}"
    reasoning_templates = [
        f"This step requires {topic}. I'll spawn a {agent_type} agent to handle this focused task.",
        f"To efficiently {task.lower()}, I'll spawn a {agent_type} agent with the appropriate context.",
        f"I need to {task.lower()}. A {agent_type} agent is best suited for this type of work.",
    ]

    output = {
        "reasoning": random.choice(reasoning_templates),
        "confidence": random.randint(85, 95),
        "risk": "LOW",
        "action": "spawn_agent",
        "params": {
            "task": task,
            "agent_type": agent_type,
            "context": context
        }
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_wait_agent_example(agent_id: str, timeout: int, description: str) -> Dict[str, Any]:
    """Generate a wait_agent training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: Wait for {description} to complete"
    output = {
        "reasoning": f"The {description} agent has been spawned. I need to wait for its results before proceeding.",
        "confidence": random.randint(90, 98),
        "risk": "LOW",
        "action": "wait_agent",
        "params": {
            "agent_id": agent_id,
            "timeout": timeout
        }
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_wait_all_agents_example(agent_ids: List[str], timeout: int, description: str) -> Dict[str, Any]:
    """Generate a wait_all_agents training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: Wait for all {description} agents"
    output = {
        "reasoning": f"Multiple agents are working on {description}. I'll wait for all of them to complete before proceeding.",
        "confidence": random.randint(88, 96),
        "risk": "LOW",
        "action": "wait_all_agents",
        "params": {
            "agent_ids": agent_ids,
            "timeout": timeout
        }
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_agent_status_example(agent_id: str, description: str) -> Dict[str, Any]:
    """Generate a get_agent_status training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: Check {description} agent status"
    output = {
        "reasoning": f"I need to check if the {description} agent is still running or has completed.",
        "confidence": random.randint(92, 98),
        "risk": "LOW",
        "action": "get_agent_status",
        "params": {
            "agent_id": agent_id
        }
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_cancel_agent_example(agent_id: str, reason: str) -> Dict[str, Any]:
    """Generate a cancel_agent training example with pre-formatted text."""
    instruction = f"EXECUTE STEP: Cancel agent ({reason})"
    output = {
        "reasoning": f"The agent needs to be cancelled because it's {reason}.",
        "confidence": random.randint(85, 95),
        "risk": "MEDIUM",
        "action": "cancel_agent",
        "params": {
            "agent_id": agent_id
        }
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_agent_result_example(pattern: Dict) -> Dict[str, Any]:
    """Generate an example of using agent results with pre-formatted text."""
    instruction = pattern["context"]
    output = {
        "reasoning": pattern["reasoning"],
        "confidence": random.randint(82, 94),
        "risk": "MEDIUM",
        "action": pattern["action"],
        "params": pattern["params"]
    }
    if "context_from_agent" in pattern:
        output["context_from_agent"] = pattern["context_from_agent"]
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_parallel_spawn_example(pattern: Dict) -> Dict[str, Any]:
    """Generate a parallel agent spawn example with pre-formatted text."""
    instruction = pattern["context"]
    output = {
        "reasoning": pattern["reasoning"],
        "confidence": random.randint(85, 94),
        "risk": "MEDIUM",
        "action": pattern["action"],
        "params": pattern["params"]
    }
    output_json = json.dumps(output)
    text = f"""### Instruction:
{instruction}

### Response:
{output_json}"""
    return {
        "instruction": instruction,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_execution_dataset(num_examples: int = 500000) -> List[Dict[str, Any]]:
    """Generate the full execution training dataset.

    Dataset composition for 500K examples:
    - write_file examples: ~70K (14%)
    - read_file patterns: ~45K (9%)
    - apply_patch variations: ~45K (9%)
    - run_command scenarios: ~35K (7%)
    - final_answer (CRITICAL): ~100K (20%)
    - Context-aware (read before edit): ~70K (14%)
    - Error recovery patterns: ~70K (14%)
    - Git workflow: ~30K (6%)
    - Multi-agent operations (NEW): ~25K (5%)
    - Other tools (glob, grep, etc.): ~10K (2%)
    """

    examples = []

    print(f"Generating {num_examples} execution examples...")

    # Base tool examples
    print("  Adding write_file examples...")
    for desc, path, content in WRITE_FILE_EXAMPLES:
        examples.append(generate_write_file_example(desc, path, content))

    print("  Adding read_file examples...")
    for desc, path in READ_FILE_EXAMPLES:
        examples.append(generate_read_file_example(desc, path))

    print("  Adding apply_patch examples...")
    for item in APPLY_PATCH_EXAMPLES:
        examples.append(generate_apply_patch_example(*item))

    print("  Adding run_command examples...")
    for desc, cmd in RUN_COMMAND_EXAMPLES:
        examples.append(generate_run_command_example(desc, cmd))

    print("  Adding final_answer examples...")
    for desc, summary in FINAL_ANSWER_EXAMPLES:
        examples.append(generate_final_answer_example(desc, summary))

    print("  Adding glob_search examples...")
    for desc, pattern in GLOB_SEARCH_EXAMPLES:
        examples.append(generate_glob_search_example(desc, pattern))

    print("  Adding grep_search examples...")
    for desc, pattern in GREP_SEARCH_EXAMPLES:
        examples.append(generate_grep_search_example(desc, pattern))

    # =========================================================================
    # MULTI-AGENT EXAMPLES (NEW - 5% = 25K target)
    # =========================================================================
    print("  Adding multi-agent operation examples...")

    multi_agent_target = num_examples // 20  # 5% = 25K
    multi_agent_count = 0

    # Add spawn_agent examples (5K)
    print("    Adding spawn_agent examples...")
    for task, agent_type, topic, context in SPAWN_AGENT_EXAMPLES:
        examples.append(generate_spawn_agent_example(task, agent_type, topic, context))
        multi_agent_count += 1

    spawn_target = 5000
    while multi_agent_count < spawn_target:
        task, agent_type, topic, context = random.choice(SPAWN_AGENT_EXAMPLES)
        # Vary the context slightly
        varied_context = context.copy()
        varied_context["variation"] = random.randint(1, 1000)
        examples.append(generate_spawn_agent_example(task, agent_type, topic, varied_context))
        multi_agent_count += 1

    # Add wait_agent examples (3K)
    print("    Adding wait_agent examples...")
    wait_target = 3000
    while multi_agent_count < spawn_target + wait_target:
        agent_id, timeout, desc = random.choice(WAIT_AGENT_EXAMPLES)
        varied_id = f"agent_{random.randint(100000, 999999)}"
        examples.append(generate_wait_agent_example(varied_id, timeout, desc))
        multi_agent_count += 1

    # Add wait_all_agents examples (3K)
    print("    Adding wait_all_agents examples...")
    wait_all_target = 3000
    while multi_agent_count < spawn_target + wait_target + wait_all_target:
        agent_ids, timeout, desc = random.choice(WAIT_ALL_AGENTS_EXAMPLES)
        varied_ids = [f"agent_{random.randint(100000, 999999)}" for _ in agent_ids]
        examples.append(generate_wait_all_agents_example(varied_ids, timeout, desc))
        multi_agent_count += 1

    # Add get_agent_status examples (2K)
    print("    Adding get_agent_status examples...")
    status_target = 2000
    while multi_agent_count < spawn_target + wait_target + wait_all_target + status_target:
        agent_id, desc = random.choice(GET_AGENT_STATUS_EXAMPLES)
        varied_id = f"agent_{random.randint(100000, 999999)}"
        examples.append(generate_agent_status_example(varied_id, desc))
        multi_agent_count += 1

    # Add cancel_agent examples (1K)
    print("    Adding cancel_agent examples...")
    cancel_target = 1000
    while multi_agent_count < spawn_target + wait_target + wait_all_target + status_target + cancel_target:
        agent_id, reason = random.choice(CANCEL_AGENT_EXAMPLES)
        varied_id = f"agent_{random.randint(100000, 999999)}"
        examples.append(generate_cancel_agent_example(varied_id, reason))
        multi_agent_count += 1

    # Add agent result handling examples (11K)
    print("    Adding agent result handling examples...")
    result_target = 11000
    while multi_agent_count < multi_agent_target:
        if random.random() > 0.3:
            pattern = random.choice(AGENT_RESULT_PATTERNS)
            examples.append(generate_agent_result_example(pattern))
        else:
            pattern = random.choice(PARALLEL_COORDINATION_PATTERNS)
            examples.append(generate_parallel_spawn_example(pattern))
        multi_agent_count += 1

    print(f"    Added {multi_agent_count} multi-agent examples")

    # =========================================================================
    # STANDARD PATTERNS
    # =========================================================================

    # Context-aware patterns (14% of total)
    print("  Adding context-aware patterns...")
    for _ in range(int(num_examples * 0.14)):
        pattern = random.choice(CONTEXT_PATTERNS)
        examples.append(generate_context_aware_example(pattern))

    # Error recovery patterns (14% of total)
    print("  Adding error recovery patterns...")
    for _ in range(int(num_examples * 0.14)):
        pattern = random.choice(ERROR_RECOVERY_PATTERNS)
        examples.append(generate_error_recovery_example(pattern))

    # Final answer variations (20% - CRITICAL for task completion)
    print("  Adding final_answer variations (20%)...")
    final_step_variations = [
        "Complete the task",
        "Finish the implementation",
        "Wrap up",
        "Finalize",
        "All steps done",
        "Task complete",
        "Implementation finished",
        "Work completed successfully",
        "Done with all changes",
        "Finished all steps",
    ]
    for _ in range(int(num_examples * 0.20)):
        desc = random.choice(final_step_variations)
        summary = random.choice(FINAL_ANSWER_EXAMPLES)[1]
        examples.append(generate_final_answer_example(desc, summary))

    # Weighted augmentation for remaining
    print("  Augmenting to reach target...")
    tool_weights = {
        "write_file": 14,
        "read_file": 9,
        "apply_patch": 9,
        "run_command": 7,
        "final_answer": 10,  # Extra on top of the 20%
        "glob_search": 4,
        "grep_search": 4,
        "git": 6,
        "context": 5,
        "recovery": 5,
        "multi_agent": 5,
    }

    tool_choices = []
    for tool, weight in tool_weights.items():
        tool_choices.extend([tool] * weight)

    while len(examples) < num_examples:
        tool = random.choice(tool_choices)

        if tool == "write_file":
            item = random.choice(WRITE_FILE_EXAMPLES)
            examples.append(generate_write_file_example(*item))
        elif tool == "read_file":
            item = random.choice(READ_FILE_EXAMPLES)
            examples.append(generate_read_file_example(*item))
        elif tool == "apply_patch":
            item = random.choice(APPLY_PATCH_EXAMPLES)
            examples.append(generate_apply_patch_example(*item))
        elif tool == "run_command":
            item = random.choice(RUN_COMMAND_EXAMPLES)
            examples.append(generate_run_command_example(*item))
        elif tool == "final_answer":
            item = random.choice(FINAL_ANSWER_EXAMPLES)
            examples.append(generate_final_answer_example(*item))
        elif tool == "glob_search":
            item = random.choice(GLOB_SEARCH_EXAMPLES)
            examples.append(generate_glob_search_example(*item))
        elif tool == "grep_search":
            item = random.choice(GREP_SEARCH_EXAMPLES)
            examples.append(generate_grep_search_example(*item))
        elif tool == "git":
            examples.append(generate_git_example("git_status", {}))
        elif tool == "context":
            pattern = random.choice(CONTEXT_PATTERNS)
            examples.append(generate_context_aware_example(pattern))
        elif tool == "recovery":
            pattern = random.choice(ERROR_RECOVERY_PATTERNS)
            examples.append(generate_error_recovery_example(pattern))
        elif tool == "multi_agent":
            # Mix of multi-agent operations
            choice = random.random()
            if choice < 0.4:
                task, agent_type, topic, context = random.choice(SPAWN_AGENT_EXAMPLES)
                examples.append(generate_spawn_agent_example(task, agent_type, topic, context))
            elif choice < 0.6:
                agent_ids, timeout, desc = random.choice(WAIT_ALL_AGENTS_EXAMPLES)
                examples.append(generate_wait_all_agents_example(agent_ids, timeout, desc))
            elif choice < 0.8:
                pattern = random.choice(AGENT_RESULT_PATTERNS)
                examples.append(generate_agent_result_example(pattern))
            else:
                pattern = random.choice(PARALLEL_COORDINATION_PATTERNS)
                examples.append(generate_parallel_spawn_example(pattern))

        if len(examples) % 50000 == 0:
            print(f"  Generated {len(examples)} examples...")

    random.shuffle(examples)
    return examples[:num_examples]


# =============================================================================
# TRAINING
# =============================================================================

def save_dataset(examples: List[Dict[str, Any]], filename: str):
    """Save dataset to JSONL file."""
    with open(filename, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example) + "\n")
    print(f"Saved {len(examples)} examples to {filename}")


def train_execution_model(
    dataset_path: str = "execution_training.jsonl",
    output_name: str = "BKnight-coder-14b",
    model_name: str = "unsloth/Qwen2.5-Coder-14B-Instruct",
    max_steps: int = 5000,
):
    """Fine-tune the execution model."""
    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    print(f"\n{'='*60}")
    print(f"Training Execution Model: {output_name}")
    print(f"Base model: {model_name}")
    print(f"{'='*60}\n")

    # Load model
    print("Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=4096,
        load_in_4bit=True,
        dtype=None,
    )

    # Add LoRA adapters
    print("Adding LoRA adapters (rank=32)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=32,
        lora_alpha=32,
        lora_dropout=0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Load dataset - text field is pre-formatted for speed
    print(f"Loading dataset from {dataset_path}...")
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # Note: We skip dataset.map() because text is already formatted
    # This significantly speeds up processing for 500K examples
    print(f"Dataset size: {len(dataset)} examples")

    # Training arguments optimized for A100 GPU
    training_args = TrainingArguments(
        output_dir=f"outputs/{output_name}",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_ratio=0.1,
        max_steps=max_steps,
        learning_rate=1e-4,
        fp16=False,
        bf16=True,
        logging_steps=100,
        save_steps=500,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
    )

    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=4096,
        args=training_args,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Export to GGUF
    print(f"\nExporting {output_name} to GGUF (Q4_K_M)...")
    model.save_pretrained_gguf(
        output_name,
        tokenizer,
        quantization_method="q4_k_m",
    )

    print(f"\nTraining complete: {output_name}")
    return model, tokenizer


def create_modelfile():
    """Create Ollama Modelfile for the execution model."""

    modelfile = '''FROM ./BKnight-coder-14b-unsloth.Q4_K_M.gguf

PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER stop "### Instruction:"
PARAMETER stop "### Response:"

SYSTEM """You are Ephraim's execution model (BKnight-coder). You ONLY execute tools to accomplish plan steps.

REQUIRED OUTPUT FORMAT (JSON):
{"reasoning": "why this action", "confidence": 0-100, "risk": "LOW|MEDIUM|HIGH", "action": "tool_name", "params": {...}}

AVAILABLE TOOLS:
File Operations:
- write_file: Create/overwrite file {"path": "...", "content": "..."}
- read_file: Read file {"path": "..."}
- apply_patch: Edit file {"path": "...", "find": "...", "replace": "..."}
- run_command: Run shell command {"command": "..."}
- glob_search: Find files {"pattern": "**/*.py"}
- grep_search: Search code {"pattern": "..."}

Git Operations:
- git_status, git_diff, git_add, git_commit: Git operations

Multi-Agent Operations (NEW):
- spawn_agent: Spawn sub-agent {"task": "...", "agent_type": "EXPLORE|RESEARCH|EXECUTE|PLAN", "context": {...}}
- wait_agent: Wait for agent {"agent_id": "...", "timeout": 60}
- wait_all_agents: Wait for multiple {"agent_ids": [...], "timeout": 120}
- get_agent_status: Check agent {"agent_id": "..."}
- cancel_agent: Cancel agent {"agent_id": "..."}
- spawn_agents_parallel: Spawn multiple {"agents": [{"task": "...", "agent_type": "..."}]}

Completion:
- final_answer: Complete task {"summary": "..."}

RULES:
- Read files BEFORE editing to understand structure
- Use spawn_agent for focused sub-tasks that can run in parallel
- Wait for agent results before using them
- If an action fails, adapt your approach
- Use final_answer when all steps are complete
- action MUST be a tool name string, not an object"""
'''

    with open("Modelfile.exec", "w") as f:
        f.write(modelfile)
    print("Created: Modelfile.exec")


def main():
    """Main entry point."""
    import os

    # Disable wandb
    os.environ["WANDB_DISABLED"] = "true"

    print("="*60)
    print("BKNIGHT-CODER EXECUTION MODEL FINE-TUNING")
    print("="*60)
    print(f"\nGenerating 500,000 execution training examples...")
    print("Base model: qwen2.5-coder:14b")
    print("Output: BKnight-coder:14b")
    print("GPU: A100 (batch_size=4, effective_batch=16)")
    print("="*60 + "\n")

    # Generate dataset
    examples = generate_execution_dataset(500000)
    save_dataset(examples, "execution_training.jsonl")

    # Train model
    train_execution_model(
        dataset_path="execution_training.jsonl",
        output_name="BKnight-coder-14b",
        max_steps=5000,
    )

    # Create modelfile
    create_modelfile()

    print("\n" + "="*60)
    print("BKNIGHT-CODER TRAINING COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Download BKnight-coder-14b-unsloth.Q4_K_M.gguf")
    print("2. Download Modelfile.exec")
    print("3. Run: ollama create BKnight-coder:14b -f Modelfile.exec")
    print("="*60)


if __name__ == "__main__":
    main()
