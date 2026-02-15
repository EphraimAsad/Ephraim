# Ephraim

**A Senior-Engineer Terminal Coding Agent**

[![Version](https://img.shields.io/badge/version-0.1.1-blue.svg)](https://github.com/EphraimAsad/ephraim)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Ephraim is a terminal-first, local, Git-aware, CI-aware agentic coding system that behaves like a **senior software engineer**. It plans before it acts, asks for approval before making changes, and integrates with your existing development workflow.

## Features

- **Plan-First Approach** - Proposes a full execution plan before making any changes
- **Human Approval Required** - No code changes without your explicit approval
- **Dual-Model Architecture** - Uses a lightweight model for planning, switches to a capable model for execution
- **Git-Aware** - Understands your repository state, branches, and staged changes
- **CI-Aware** - Monitors GitHub Actions and responds to CI failures
- **Local & Private** - Runs entirely on your machine using Ollama (no data sent to cloud)
- **Patch-Based Edits** - Makes surgical, targeted changes instead of rewriting files
- **Live Output** - Streams command output in real-time
- **Session Memory** - Tracks progress in Context.md for continuity across sessions

## Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Safety > Speed** | Human approval required before code changes |
| **Architecture Preservation > Rewrites** | Minimal, targeted patch-based edits |
| **Incremental Change > Large Refactors** | One step at a time with verification |
| **Real System Feedback > Speculation** | Uses actual test/CI results to guide decisions |
| **Human Oversight Required** | No autonomous execution of dangerous operations |

## Requirements

- **Python 3.10+**
- **Ollama** - Local LLM server ([ollama.ai](https://ollama.ai))
- **Git** - Version control
- **GitHub CLI** (`gh`) - Optional, for CI integration

## Installation

### 1. Install Ollama

Download and install Ollama from [ollama.ai](https://ollama.ai).

```bash
# Pull both models (planning + execution)
ollama pull llama3.1:8b         # Fast planning model
ollama pull qwen2.5-coder:14b   # Capable execution model
```

### 2. Install Ephraim

```bash
# Clone the repository
git clone https://github.com/EphraimAsad/ephraim.git
cd ephraim

# Install in development mode
pip install -e .

# Or install with dev dependencies for testing
pip install -e ".[dev]"
```

### 3. (Optional) Install GitHub CLI

For CI integration features:

```bash
# Windows (winget)
winget install GitHub.cli

# macOS
brew install gh

# Linux
# See https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Authenticate
gh auth login
```

## Quick Start

```bash
# Navigate to your project
cd your-project

# Launch Ephraim
Ephraim
```

Ephraim will:
1. Detect your Git repository root
2. Create `Ephraim.md` (project configuration) if it doesn't exist
3. Create `Context.md` (session memory) if it doesn't exist
4. Connect to Ollama and verify both models are available
5. Wait for your task input

### Example Session

```
╭──────────────────────────────────────────────────────────╮
│  EPHRAIM - Senior Engineer Terminal Agent               │
╰──────────────────────────────────────────────────────────╯
>>> Phase: BOOT
Repository root: C:\Projects\my-app
Ollama connected. Model: llama3.1:8b
Ollama connected. Model: qwen2.5-coder:14b
────────────────────────────────────────────────────────────
Enter your task, or type 'quit' to exit.
────────────────────────────────────────────────────────────
Ephraim> Add input validation to the user registration form

>>> Phase: PLANNING
Confidence: 85% (HIGH)
Risk Level: MEDIUM

╭─────────────────── Execution Plan ───────────────────────╮
│ Goal: Add input validation to user registration form    │
│                                                          │
│ Steps:                                                   │
│   1. Read the current registration form component        │
│   2. Identify input fields that need validation          │
│   3. Add email format validation                         │
│   4. Add password strength requirements                  │
│   5. Add error message display                           │
│   6. Test the validation logic                           │
╰──────────────────────────────────────────────────────────╯

Approve plan? (y/n): y
Plan approved. Executing...
Switched to execution model: qwen2.5-coder:14b

>>> Step 1/6: Read the current registration form component
    Tool: read_file
    File: src/components/RegisterForm.tsx
    Success: Read 45 lines

>>> Step 2/6: Identify input fields...
```

## Dual-Model Architecture

Ephraim uses two models for optimal performance:

| Role | Default Model | Purpose |
|------|---------------|---------|
| **Planning** | llama3.1:8b | Fast reasoning, plan generation, clarifying questions |
| **Execution** | qwen2.5-coder:14b | Reliable tool execution, follows instructions precisely |

**Why two models?**
- Smaller models are fast and good at high-level reasoning
- Larger models follow execution instructions more reliably
- Automatic switching eliminates re-planning loops

**Model switching happens automatically:**
1. Planning phase uses the lightweight model
2. After plan approval, switches to the execution model
3. After task completion, switches back to planning model

### Customizing Models

Edit `ephraim/config.py` to change defaults:

```python
@dataclass
class ModelConfig:
    provider: str = "ollama"
    model_name: str = "llama3.1:8b"  # Planning model
    endpoint: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 4096

def get_default_execution_model() -> ModelConfig:
    return ModelConfig(
        model_name="qwen2.5-coder:14b",  # Execution model
        temperature=0.2,
    )
```

## Configuration

### Ephraim.md

Created automatically in your project root. Customize to set project-specific rules:

```markdown
# Ephraim.md - Project Configuration

## Architecture Constraints
- Use React functional components with hooks
- State management via Redux Toolkit
- API calls through RTK Query

## Coding Standards
- TypeScript strict mode
- ESLint + Prettier formatting
- Jest for unit tests

## Protected Areas
- Do not modify: config/, .env files
- Require extra approval: auth/, payment/

## Validation Expectations
- All PRs must pass CI
- Test coverage > 80%

## Git Rules
- Conventional commits (feat:, fix:, etc.)
- No direct commits to main
```

### Context.md

Automatically maintained by Ephraim to track session progress:

```markdown
# Current Task
Add input validation to user registration form

# Phase
executing

# Active Plan
Goal: Add input validation to user registration form
Steps:
  1. Read the current registration form component
  2. Identify input fields that need validation
  3. Add email format validation
  ...

# Recent Decisions
- 2024-01-15T10:30:00: read_file - Read RegisterForm.tsx
- 2024-01-15T10:30:05: apply_patch - Added email validation

# Git Status
Branch: feature/form-validation
Clean: False
```

## Available Tools

Ephraim has access to these tools during execution:

| Tool | Description | Phase |
|------|-------------|-------|
| `read_file` | Read file contents with line numbers | Planning, Executing |
| `list_directory` | List directory contents | Planning, Executing |
| `apply_patch` | Make surgical edits to files | Executing (requires approval) |
| `run_command` | Execute shell commands | Executing (requires approval) |
| `git_status` | Get repository status | All phases |
| `git_diff` | View staged/unstaged changes | All phases |
| `git_add` | Stage files for commit | Executing |
| `git_commit` | Create commits | Executing (requires approval) |
| `check_ci_status` | Check GitHub Actions status | CI Check |
| `get_ci_logs` | Fetch CI failure logs | CI Check |

## Workflow Phases

```
BOOT → PLANNING → EXECUTING → VALIDATING → COMMITTING → CI_CHECK → COMPLETED
                      ↑                                       │
                      └───────────── (on CI failure) ─────────┘
```

1. **BOOT** - Initialize environment, verify Git/Ollama, check both models
2. **PLANNING** - Analyze task, propose execution plan (using planning model)
3. **EXECUTING** - Run approved plan steps (using execution model)
4. **VALIDATING** - Run tests, verify changes work
5. **COMMITTING** - Stage and commit changes
6. **CI_CHECK** - Monitor CI pipeline
7. **COMPLETED** - Task finished successfully

## Architecture

Ephraim is NOT a chatbot. It is:

> A deterministic engineering workflow engine driven by LLMs.

The LLMs reason. The system controls execution.

```
User Input
    ↓
Terminal Interface
    ↓
State Manager (phase enforcement, approval gating)
    ↓
LLM Brief Builder (curated context for LLM)
    ↓
Planning LLM (llama3.1:8b) ──────┐
    ↓                            │
Plan Approval                    │
    ↓                            │
Execution LLM (qwen2.5-coder:14b)│
    ↓                            │
Tool Executor (sandboxed)        │
    ↓                            │
State Update + Context.md        │
    ↓                            │
Loop until complete ─────────────┘
```

## Project Structure

```
ephraim/
├── pyproject.toml          # Package configuration
├── README.md               # This file
├── LICENSE                 # MIT License
├── ephraim/
│   ├── __init__.py         # Package init
│   ├── main.py             # CLI entry point
│   ├── boot.py             # Boot sequence
│   ├── state.py            # State object model
│   ├── state_manager.py    # State transitions, LLM brief builder
│   ├── agent_loop.py       # Main execution loop, model switching
│   ├── llm_interface.py    # Ollama integration
│   ├── config.py           # Configuration, model defaults
│   ├── logging_setup.py    # Rich terminal output
│   └── tools/
│       ├── __init__.py     # Tool registry
│       ├── base.py         # Base tool class
│       ├── read_file.py    # File reading
│       ├── list_directory.py
│       ├── apply_patch.py  # Patch engine (safety checks)
│       ├── run_command.py  # Command execution (streaming)
│       ├── ask_user.py     # User interaction
│       ├── final_answer.py # Task completion
│       ├── git_tools.py    # Git operations
│       └── ci_tools.py     # GitHub CLI integration
└── tests/                  # Test suite (285 tests)
```

## CLI Commands

```bash
# Launch interactive mode
Ephraim

# Show current status
Ephraim status

# Show version
Ephraim --version

# Reset Context.md
Ephraim reset
```

## Troubleshooting

### "Ollama not connected" error

```bash
# Make sure Ollama is running
ollama serve

# Verify both models are pulled
ollama list

# Test connection
curl http://localhost:11434/api/tags
```

### "Model not found" warning

```bash
# Pull both required models
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:14b
```

### Execution model not available

If the execution model (qwen2.5-coder:14b) is not available, Ephraim will fall back to using the planning model for execution. You'll see a warning:

```
Warning: Execution model 'qwen2.5-coder:14b' not available.
Using planning model for execution (may cause re-planning)
```

To fix, pull the execution model:
```bash
ollama pull qwen2.5-coder:14b
```

### GitHub CLI not authenticated

```bash
gh auth login
gh auth status
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=ephraim --cov-report=html
```

**Current test status:** 285 tests passing

### Code Style

The project uses standard Python conventions:
- Type hints throughout
- Docstrings for public functions
- Dataclasses for structured data

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Commit with conventional commits (`feat: add amazing feature`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Changelog

### v0.1.1
- Added dual-model architecture (planning + execution models)
- Fixed infinite re-planning loop with smaller models
- Added step-by-step execution progress display
- Added Context.md persistence for plan tracking
- Added repo_root to LLM context
- Improved action visibility in terminal

### v0.1.0
- Initial release
- Core agent loop with planning and execution phases
- Git and CI integration
- Ollama LLM support
- Tool system with safety checks

## Roadmap

- [ ] Multiple LLM provider support (OpenAI, Anthropic)
- [ ] Configurable model selection via Ephraim.md
- [ ] Plugin system for custom tools
- [ ] Web UI option
- [ ] Multi-file refactoring support
- [ ] Integration with more CI systems (GitLab, Jenkins)
- [ ] Code review mode

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [Ollama](https://ollama.ai) for local LLM inference
- Terminal UI powered by [Rich](https://github.com/Textualize/rich)
- Inspired by the need for safer, more controllable AI coding assistants
