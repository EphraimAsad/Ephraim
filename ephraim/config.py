"""
Ephraim Configuration System

Handles loading configuration from Ephraim.md and provides defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path


@dataclass
class ModelConfig:
    """LLM model configuration."""
    provider: str = "ollama"
    model_name: str = "llama3.1:8b"
    endpoint: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120  # seconds


@dataclass
class GitConfig:
    """Git integration configuration."""
    auto_commit: bool = True
    commit_prefix: str = "Ephraim:"
    require_clean_start: bool = False


@dataclass
class CIConfig:
    """CI/CD integration configuration."""
    enabled: bool = True
    provider: str = "github"  # github actions
    check_after_commit: bool = True
    max_wait_seconds: int = 300


@dataclass
class SafetyConfig:
    """Safety and approval configuration."""
    require_approval: bool = True
    max_iterations: int = 20
    protected_paths: List[str] = field(default_factory=list)
    dangerous_commands: List[str] = field(default_factory=lambda: [
        "rm -rf",
        "git push --force",
        "git reset --hard",
        "DROP TABLE",
        "DELETE FROM",
    ])


@dataclass
class EphraimConfig:
    """
    Main configuration object for Ephraim.

    Can be loaded from Ephraim.md or use defaults.
    """
    model: ModelConfig = field(default_factory=ModelConfig)
    git: GitConfig = field(default_factory=GitConfig)
    ci: CIConfig = field(default_factory=CIConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    # Project-specific rules from Ephraim.md
    architecture_constraints: List[str] = field(default_factory=list)
    coding_standards: List[str] = field(default_factory=list)
    protected_areas: List[str] = field(default_factory=list)
    validation_expectations: List[str] = field(default_factory=list)
    git_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "model": {
                "provider": self.model.provider,
                "model_name": self.model.model_name,
                "endpoint": self.model.endpoint,
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
                "timeout": self.model.timeout,
            },
            "git": {
                "auto_commit": self.git.auto_commit,
                "commit_prefix": self.git.commit_prefix,
                "require_clean_start": self.git.require_clean_start,
            },
            "ci": {
                "enabled": self.ci.enabled,
                "provider": self.ci.provider,
                "check_after_commit": self.ci.check_after_commit,
                "max_wait_seconds": self.ci.max_wait_seconds,
            },
            "safety": {
                "require_approval": self.safety.require_approval,
                "max_iterations": self.safety.max_iterations,
                "protected_paths": self.safety.protected_paths,
                "dangerous_commands": self.safety.dangerous_commands,
            },
            "architecture_constraints": self.architecture_constraints,
            "coding_standards": self.coding_standards,
            "protected_areas": self.protected_areas,
            "validation_expectations": self.validation_expectations,
            "git_rules": self.git_rules,
        }


def parse_ephraim_md(content: str) -> Dict[str, List[str]]:
    """
    Parse Ephraim.md content into structured sections.

    Expected format:
    # Section Name
    - item 1
    - item 2

    Returns dict of section_name -> list of items
    """
    sections: Dict[str, List[str]] = {}
    current_section = None
    current_items: List[str] = []

    for line in content.split('\n'):
        line = line.strip()

        # Section header
        if line.startswith('# '):
            # Save previous section
            if current_section:
                sections[current_section] = current_items
            current_section = line[2:].strip().lower().replace(' ', '_')
            current_items = []

        # List item
        elif line.startswith('- ') and current_section:
            current_items.append(line[2:].strip())

        # Continuation of previous item (non-empty, non-header)
        elif line and current_section and current_items:
            current_items[-1] += ' ' + line

    # Save last section
    if current_section:
        sections[current_section] = current_items

    return sections


def load_config_from_ephraim_md(ephraim_md_path: str) -> EphraimConfig:
    """
    Load configuration from an Ephraim.md file.

    Falls back to defaults if file doesn't exist or has missing sections.
    """
    config = EphraimConfig()

    if not os.path.exists(ephraim_md_path):
        return config

    try:
        with open(ephraim_md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = parse_ephraim_md(content)

        # Map sections to config fields
        if 'architecture_constraints' in sections:
            config.architecture_constraints = sections['architecture_constraints']
        if 'coding_standards' in sections:
            config.coding_standards = sections['coding_standards']
        if 'protected_areas' in sections:
            config.protected_areas = sections['protected_areas']
            config.safety.protected_paths = sections['protected_areas']
        if 'validation_expectations' in sections:
            config.validation_expectations = sections['validation_expectations']
        if 'git_rules' in sections:
            config.git_rules = sections['git_rules']

    except Exception:
        # Return default config on any error
        pass

    return config


def create_default_ephraim_md() -> str:
    """Generate default Ephraim.md content."""
    return """# Architecture Constraints
- Maintain existing module boundaries
- Preserve public API interfaces
- Follow established patterns in the codebase

# Coding Standards
- Follow project's existing style conventions
- Write clear, self-documenting code
- Include type hints for function signatures

# Protected Areas
- Do not modify configuration files without explicit approval
- Do not modify authentication/security modules without explicit approval
- Do not delete existing tests

# Validation Expectations
- All changes must pass existing tests
- New functionality should include tests
- Code should be linted before commit

# Git Rules
- Use descriptive commit messages
- Commit atomic, focused changes
- Do not force push to main/master
"""


def create_default_context_md() -> str:
    """Generate default Context.md content."""
    return """# Current Task
No active task.

# Recent Decisions
None yet.

# CI Status
Not checked.

# Next Steps
Awaiting user input.
"""


def get_default_config() -> EphraimConfig:
    """Get a default configuration object."""
    return EphraimConfig()
