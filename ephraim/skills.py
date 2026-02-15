"""
Skills System

Skills are pre-defined prompts that expand into full task descriptions.
They provide shortcuts for common operations like /commit, /test, /review.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Callable


@dataclass
class Skill:
    """Represents a skill."""
    name: str
    description: str
    prompt_template: str
    requires_args: bool = False

    def execute(self, args: str = "") -> str:
        """
        Execute the skill and return the expanded prompt.

        Args can be interpolated into the template using {args}.
        """
        if self.requires_args and not args:
            return f"Skill {self.name} requires arguments. Usage: {self.name} <args>"

        return self.prompt_template.format(args=args)


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register(
        self,
        name: str,
        description: str,
        prompt_template: str,
        requires_args: bool = False,
    ) -> None:
        """Register a skill."""
        if not name.startswith('/'):
            name = '/' + name

        self.skills[name] = Skill(
            name=name,
            description=description,
            prompt_template=prompt_template,
            requires_args=requires_args,
        )

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        if not name.startswith('/'):
            name = '/' + name
        return self.skills.get(name)

    def list_all(self) -> Dict[str, Skill]:
        """List all skills."""
        return dict(self.skills)


# Global registry
skill_registry = SkillRegistry()


# ============ Built-in Skills ============

skill_registry.register(
    name="/commit",
    description="Create a git commit with staged changes",
    prompt_template="""Create a git commit for the staged changes.

Steps:
1. Run `git status` to see what's staged
2. Run `git diff --cached` to see the actual changes
3. Analyze the changes and write a clear, concise commit message
4. The commit message should:
   - Start with a type: feat, fix, docs, style, refactor, test, chore
   - Be in imperative mood ("Add feature" not "Added feature")
   - Be under 72 characters for the first line
   - Include a body if the changes are complex
5. Run `git commit -m "..."` with the message
6. Show the result

{args}""",
)

skill_registry.register(
    name="/test",
    description="Run the project's test suite",
    prompt_template="""Run the project's test suite.

Steps:
1. Detect the test framework (pytest, unittest, jest, etc.)
2. Run the appropriate test command
3. Analyze the results
4. If there are failures, summarize what failed and why
5. Suggest fixes if applicable

{args}""",
)

skill_registry.register(
    name="/review",
    description="Review current changes and suggest improvements",
    prompt_template="""Review the current code changes.

Steps:
1. Run `git diff` to see unstaged changes
2. Run `git diff --cached` to see staged changes
3. Analyze the changes for:
   - Code quality issues
   - Potential bugs
   - Missing error handling
   - Security concerns
   - Performance issues
   - Style/formatting issues
4. Provide specific, actionable feedback
5. Suggest improvements with code examples

{args}""",
)

skill_registry.register(
    name="/fix",
    description="Fix the last error or test failure",
    prompt_template="""Fix the last error or test failure.

Steps:
1. Look at the recent actions and errors in context
2. Identify the root cause of the failure
3. Propose a fix
4. Implement the fix using apply_patch or write_file
5. Verify the fix works

{args}""",
)

skill_registry.register(
    name="/explain",
    description="Explain how a file or function works",
    prompt_template="""Explain how this code works: {args}

Steps:
1. Read the file or find the function
2. Analyze its purpose and functionality
3. Explain:
   - What it does at a high level
   - The key logic and algorithms
   - Important dependencies and side effects
   - How it fits into the larger system
4. Use clear, non-technical language where possible

{args}""",
    requires_args=True,
)

skill_registry.register(
    name="/search",
    description="Search the codebase for a pattern",
    prompt_template="""Search the codebase for: {args}

Steps:
1. Use glob_search to find relevant files
2. Use grep_search to find matches within files
3. Show the most relevant results with context
4. Summarize what was found

{args}""",
    requires_args=True,
)

skill_registry.register(
    name="/init",
    description="Initialize a new project",
    prompt_template="""Initialize a new project.

Steps:
1. Ask what type of project (Python, Node, etc.) if not specified
2. Create the basic project structure
3. Create configuration files (pyproject.toml, package.json, etc.)
4. Initialize git if not already a repo
5. Create a README.md with basic info
6. Create a .gitignore appropriate for the project type

{args}""",
)

skill_registry.register(
    name="/pr",
    description="Create a pull request",
    prompt_template="""Create a pull request.

Steps:
1. Run `git status` to check current state
2. Run `git log --oneline -10` to see recent commits
3. Determine the base branch (usually main or master)
4. Create a PR title based on the commits
5. Write a PR description with:
   - Summary of changes
   - Why the changes were made
   - Any testing done
6. Use `gh pr create` if GitHub CLI is available

{args}""",
)

skill_registry.register(
    name="/debug",
    description="Debug an issue step by step",
    prompt_template="""Debug this issue: {args}

Steps:
1. Understand the reported issue
2. Identify relevant files and code paths
3. Add strategic read_file calls to understand the code
4. Identify potential causes
5. Propose and test hypotheses
6. Find the root cause
7. Suggest or implement a fix

{args}""",
    requires_args=True,
)
