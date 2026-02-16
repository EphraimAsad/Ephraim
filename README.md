# Ephraim

**A Senior-Engineer Terminal Coding Agent - Local Claude Code Alternative**

[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](https://github.com/EphraimAsad/ephraim)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/powered%20by-Ollama-orange.svg)](https://ollama.ai)

Ephraim is a **free, local, privacy-first** terminal coding agent that provides Claude Code-like capabilities using Ollama. No API keys, no cloud, no costs - just powerful AI-assisted coding running entirely on your machine.

## Key Features

| Feature | Description |
|---------|-------------|
| **100% Local** | Runs on Ollama - no data leaves your machine |
| **Free Forever** | No API costs, no subscriptions |
| **Plan-First** | Proposes plans before making changes |
| **Human Approval** | No code changes without your consent |
| **Streaming Output** | Real-time token display as the LLM thinks |
| **61 Built-in Tools** | File ops, search, git, CI/CD, GitHub, testing, analysis, web, MCP, multi-agent |
| **MCP Integration** | Connect to external tool servers |
| **Multimodal** | Analyze images and PDFs with vision models |
| **Git & CI Aware** | Understands your repo and CI pipeline |
| **Multi-Agent** | Spawn parallel sub-agents for complex tasks |
| **Extensible** | Hooks, skills, commands, training scripts |

## What's New in v0.5.0

- **19 New Tools** - Complete Git, CI/CD, GitHub, Testing, and Analysis workflows
- **Full Git Operations** - `git_push`, `git_pull`, `git_branch`, `git_checkout`, `git_merge`, `git_stash`
- **CI/CD Intelligence** - `wait_for_ci`, `analyze_ci_failure`, `suggest_ci_fix`, `trigger_workflow`, `pr_status`
- **GitHub Integration** - `gh_pr_create`, `gh_pr_list`, `gh_pr_review`, `gh_issue_create`, `gh_issue_list`, `gh_issue_comment`
- **Smart Testing** - `run_tests`, `analyze_test_failure`, `suggest_test_fix`, `coverage_report`
- **Code Analysis** - `find_references`, `find_definition`, `analyze_imports`, `dead_code_check`
- **Training Scripts** - Fine-tune your own models with 600K examples (optional)
- **61 Tools** - Production-ready toolset for complete developer workflows

### Previous: v0.4.0
- Multi-agent coordination, 6 multi-agent tools, 500K training examples

### Previous: v0.3.0
- Streaming token display, MCP integration, multimodal support (images/PDFs), full workflow phases

## Requirements

- **Python 3.10+**
- **Ollama** - Local LLM server ([ollama.ai](https://ollama.ai))
- **Git** - Version control
- **GitHub CLI** (`gh`) - Optional, for CI integration

## Installation

### 1. Install Ollama

Download from [ollama.ai](https://ollama.ai), then pull models:

```bash
# Required: Main model
ollama pull qwen2.5-coder:14b 

# Optional: Vision model for images/PDFs
ollama pull llava
```

### 2. Install Ephraim

```bash
# Clone the repository
git clone https://github.com/EphraimAsad/ephraim.git
cd ephraim

# Install
pip install -e .

# Or with multimodal support (images/PDFs)
pip install -e ".[multimodal]"

# Or with all extras
pip install -e ".[all]"
```

### 3. (Optional) GitHub CLI for CI Integration

```bash
# Windows
winget install GitHub.cli

# macOS
brew install gh

# Authenticate
gh auth login
```

## Quick Start

```bash
cd your-project
Ephraim
```

### Example Session

```
+----------------------------------------------------------+
|  EPHRAIM - Senior Engineer Terminal Agent                |
+----------------------------------------------------------+
>>> Phase: BOOT
Repository root: C:\Projects\my-app
Ollama connected. Model: llama3.1:8b
Features: Vision (llava), PDF Text
------------------------------------------------------------
Ephraim> Add input validation to the registration form

>>> Phase: PLANNING
Thinking... {"reasoning": "I need to first read the current...

+------------------- Execution Plan -----------------------+
| Goal: Add input validation to user registration form     |
|                                                          |
| Steps:                                                   |
|   1. Read the current registration form component        |
|   2. Add email format validation                         |
|   3. Add password strength requirements                  |
|   4. Test the validation                                 |
+----------------------------------------------------------+

Approve plan? (y/n): y
Plan approved. Executing...

>>> Step 1/4: Read the current registration form component
    Action: read_file
    path: src/components/RegisterForm.tsx
Result: Read 45 lines

>>> Step 2/4: Add email format validation
    Action: apply_patch
    path: src/components/RegisterForm.tsx
Result: Patched at line 12 (+5 lines)
...
```

## Available Tools (61 Total)

### File Operations
| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Create new files |
| `apply_patch` | Make surgical edits (find/replace) |
| `delete_file` | Remove files (with backup) |
| `move_file` | Move or rename files |
| `copy_file` | Copy files |

### Directory Operations
| Tool | Description |
|------|-------------|
| `list_directory` | List directory contents |
| `create_directory` | Create folders |
| `delete_directory` | Remove folders |

### Search
| Tool | Description |
|------|-------------|
| `glob_search` | Find files by pattern (`**/*.py`) |
| `grep_search` | Search file contents (regex) |

### Execution
| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands (streaming) |

### Git (10 tools)
| Tool | Description |
|------|-------------|
| `git_status` | Repository status |
| `git_diff` | View changes |
| `git_add` | Stage files |
| `git_commit` | Create commits |
| `git_push` | Push to remote |
| `git_pull` | Pull from remote |
| `git_branch` | Create/list/delete branches |
| `git_checkout` | Switch branches |
| `git_merge` | Merge branches |
| `git_stash` | Stash/pop changes |

### CI/CD (8 tools)
| Tool | Description |
|------|-------------|
| `check_ci_status` | Check pipeline status |
| `get_ci_logs` | Fetch CI logs |
| `check_ci_result` | Check specific run |
| `wait_for_ci` | Wait for CI completion |
| `analyze_ci_failure` | Analyze failure cause |
| `suggest_ci_fix` | Get fix suggestions |
| `trigger_workflow` | Trigger workflow manually |
| `pr_status` | Check PR review/check status |

### GitHub (6 tools) - NEW in v0.5.0
| Tool | Description |
|------|-------------|
| `gh_pr_create` | Create pull request |
| `gh_pr_list` | List pull requests |
| `gh_pr_review` | Submit PR review |
| `gh_issue_create` | Create issue |
| `gh_issue_list` | List issues |
| `gh_issue_comment` | Comment on issue/PR |

### Testing (4 tools) - NEW in v0.5.0
| Tool | Description |
|------|-------------|
| `run_tests` | Run tests with framework detection |
| `analyze_test_failure` | Analyze and explain failures |
| `suggest_test_fix` | Suggest fixes for failing tests |
| `coverage_report` | Generate coverage summary |

### Code Analysis (4 tools) - NEW in v0.5.0
| Tool | Description |
|------|-------------|
| `find_references` | Find all usages of a symbol |
| `find_definition` | Find where symbol is defined |
| `analyze_imports` | Analyze dependencies |
| `dead_code_check` | Find unused code |

### Web (Free, No API Keys)
| Tool | Description |
|------|-------------|
| `web_search` | Search via DuckDuckGo |
| `web_fetch` | Fetch URL content |

### MCP (Model Context Protocol)
| Tool | Description |
|------|-------------|
| `mcp_connect` | Connect to MCP server |
| `mcp_disconnect` | Disconnect from server |
| `mcp_list_tools` | List available tools |
| `mcp_call` | Call an MCP tool |
| `mcp_status` | Connection status |

### Multimodal
| Tool | Description |
|------|-------------|
| `read_image` | Analyze images (requires llava) |
| `read_pdf` | Read PDFs (text or vision) |

### Notebooks
| Tool | Description |
|------|-------------|
| `notebook_read` | Read Jupyter notebooks |
| `notebook_edit` | Edit notebook cells |

### Task Management
| Tool | Description |
|------|-------------|
| `task_create` | Create a task |
| `task_update` | Update task status |
| `task_list` | List all tasks |
| `task_get` | Get task details |

### Multi-Agent
| Tool | Description |
|------|-------------|
| `spawn_agent` | Spawn a sub-agent for focused tasks |
| `wait_agent` | Wait for single agent completion |
| `wait_all_agents` | Wait for multiple agents |
| `get_agent_status` | Check agent progress |
| `cancel_agent` | Cancel running agent |
| `spawn_agents_parallel` | Spawn multiple agents at once |

**Agent Types:** EXPLORE (search codebase), PLAN (design approach), EXECUTE (perform actions), RESEARCH (analysis)

### User Interaction
| Tool | Description |
|------|-------------|
| `ask_user` | Ask clarifying questions |
| `final_answer` | Complete the task |

## Built-in Commands

Type these directly at the prompt:

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/status` | Current state |
| `/tasks` | List tasks |
| `/clear` | Clear screen |
| `/reset` | Reset context |
| `/quit` | Exit |
| `/compact` | Compact history |
| `/background` | List background tasks |

## Skills

Skills expand into full prompts for common tasks:

| Skill | Description |
|-------|-------------|
| `/commit` | Create a git commit |
| `/test` | Run tests |
| `/review` | Code review |
| `/fix` | Fix an issue |
| `/explain` | Explain code |
| `/search` | Search codebase |
| `/init` | Initialize project |
| `/pr` | Create pull request |
| `/debug` | Debug an issue |

## Workflow Phases

```
BOOT -> PLANNING -> AWAITING_APPROVAL -> EXECUTING -> VALIDATING -> CI_CHECK -> COMPLETED
                           |                                              |
                           +<------------ (on failure) -------------------+
```

1. **BOOT** - Initialize, verify Ollama connection
2. **PLANNING** - Analyze task, propose execution plan
3. **AWAITING_APPROVAL** - Wait for user to approve plan
4. **EXECUTING** - Run approved plan steps
5. **VALIDATING** - Run tests, verify changes work
6. **CI_CHECK** - Monitor CI pipeline (if enabled)
7. **COMPLETED** - Task finished

## Configuration

### Ephraim.md

Project-specific rules (created automatically):

```markdown
# Architecture Constraints
- Use React functional components
- State management via Redux

# Coding Standards
- TypeScript strict mode
- ESLint + Prettier

# Protected Areas
- Do not modify: .env, config/

# Validation Expectations
- All PRs must pass CI

# Git Rules
- Conventional commits

# MCP Servers
- sqlite: uvx mcp-server-sqlite --db-path ./data.db

# Hooks
- pre_tool: npm run lint (for apply_patch, write_file)
- post_commit: ./scripts/notify.sh
```

### Context.md

Session state (auto-maintained):

```markdown
# Current Task
Add input validation to registration form

# Phase
executing

# Active Plan
Goal: Add input validation
Steps:
  1. Read form component
  2. Add email validation
  ...
```

## Project Structure

```
ephraim/
├── pyproject.toml
├── README.md
├── ephFinetune_plan.py      # Planning model training (optional)
├── ephFinetune_exec.py      # Execution model training (optional)
├── ephraim/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── boot.py              # Boot sequence
│   ├── state.py             # State model
│   ├── state_manager.py     # Phase transitions
│   ├── agent_loop.py        # Main loop + streaming
│   ├── llm_interface.py     # Ollama integration
│   ├── config.py            # Configuration
│   ├── logging_setup.py     # Rich terminal UI
│   ├── commands.py          # Built-in commands
│   ├── skills.py            # Skill definitions
│   ├── subagents.py         # Parallel task agents
│   ├── hooks.py             # Pre/post hooks
│   ├── tasks.py             # Task management
│   ├── background.py        # Background tasks
│   ├── history.py           # Command history
│   ├── keybindings.py       # Keyboard shortcuts
│   ├── mcp/                 # MCP integration
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── protocol.py
│   └── tools/
│       ├── __init__.py      # Tool registry (42 tools)
│       ├── base.py          # Base tool class
│       ├── read_file.py
│       ├── write_file.py
│       ├── apply_patch.py
│       ├── run_command.py
│       ├── file_operations.py
│       ├── directory_tools.py
│       ├── search_tools.py
│       ├── git_tools.py
│       ├── ci_tools.py
│       ├── web_tools.py
│       ├── mcp_tools.py
│       ├── multimodal_tools.py
│       ├── notebook_tools.py
│       ├── task_tools.py
│       ├── ask_user.py
│       └── final_answer.py
```

## CLI Usage

```bash
# Interactive mode
Ephraim

# Show status
Ephraim status

# Show config
Ephraim config

# Reset context
Ephraim reset

# Version
Ephraim --version
```

## Troubleshooting

### Ollama Not Connected

```bash
# Start Ollama
ollama serve

# Verify models
ollama list

# Pull required model
ollama pull llama3.1:8b
```

### Vision Not Available

```bash
# Pull vision model
ollama pull llava

# Verify
Ephraim  # Should show "Features: Vision (llava)"
```

### GitHub CLI Not Authenticated

```bash
gh auth login
gh auth status
```

## Training Your Own Models (Optional)

Ephraim works with any Ollama model out of the box. For advanced users who want models optimized for Ephraim's JSON schema and workflow:

```bash
# Training scripts included:
ephFinetune_plan.py    # Planning model (600K examples)
ephFinetune_exec.py    # Execution model (600K examples)
```

**Features:**
- 600,000 training examples per model
- All 61 tools fully covered
- Git, CI/CD, GitHub, Testing, Analysis workflows
- Multi-agent coordination patterns
- A100 GPU optimized (~12-14 hours total)
- Exports to GGUF for Ollama

Run on Google Colab with A100 GPU. See training scripts for details.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=ephraim
```

## Changelog

### v0.5.0
- **19 new tools** - Git extended, CI/CD, GitHub, Testing, Analysis
- **Complete Git operations** - push, pull, branch, checkout, merge, stash
- **CI/CD intelligence** - wait_for_ci, analyze_ci_failure, suggest_ci_fix, trigger_workflow, pr_status
- **GitHub integration** - gh_pr_create, gh_pr_list, gh_pr_review, gh_issue_create, gh_issue_list, gh_issue_comment
- **Smart testing** - run_tests, analyze_test_failure, suggest_test_fix, coverage_report
- **Code analysis** - find_references, find_definition, analyze_imports, dead_code_check
- **Training scripts** - Updated to 600K examples with all new tools
- **61 tools total** (up from 42)

### v0.4.0
- **Multi-agent coordination system** - Spawn parallel agents (EXPLORE, PLAN, EXECUTE, RESEARCH)
- **6 new multi-agent tools** - spawn_agent, wait_agent, wait_all_agents, get_agent_status, cancel_agent, spawn_agents_parallel
- **Training scripts** - Fine-tune custom models with 500K examples
- **42 tools total** (up from 36)

### v0.3.0
- Streaming token display (real-time LLM output)
- MCP (Model Context Protocol) integration
- Multimodal support (images/PDFs via llava)
- Fixed VALIDATING/CI_CHECK workflow phases
- Fixed step tracking for all execution tools
- Fixed final_answer tool execution flow
- 36 tools total

### v0.2.0
- File creation/management tools (write, delete, move, copy)
- Directory tools (create, delete)
- Search tools (glob, grep)
- Web search/fetch via DuckDuckGo (free)
- Task management system
- Built-in commands (/help, /status, /tasks, etc.)
- Skills system (/commit, /test, /review, etc.)
- Sub-agent system for parallel tasks
- Hooks system (pre/post tool automation)
- Jupyter notebook support
- Command history with prompt_toolkit
- Enhanced keyboard shortcuts

### v0.1.1
- Dual-model architecture (planning + execution)
- Fixed infinite re-planning loop
- Step-by-step execution progress
- Context.md persistence

### v0.1.0
- Initial release
- Core agent loop
- Git and CI integration
- Ollama support
- Tool system with safety checks

## Roadmap

- [x] ~~Plugin system~~ (Done via MCP)
- [x] ~~Multi-file refactoring~~ (Inherently supported)
- [x] ~~Multi-agent coordination~~ (Done in v0.4.0)
- [x] ~~Custom model training~~ (Done in v0.4.0)
- [x] ~~Full Git operations~~ (Done in v0.5.0)
- [x] ~~CI/CD intelligence~~ (Done in v0.5.0)
- [x] ~~GitHub integration~~ (Done in v0.5.0)
- [x] ~~Smart testing tools~~ (Done in v0.5.0)
- [x] ~~Code analysis tools~~ (Done in v0.5.0)
- [ ] Web UI option
- [ ] More CI systems (GitLab, Jenkins)
- [ ] Model selection via Ephraim.md
- [ ] Code review mode

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM inference
- [Rich](https://github.com/Textualize/rich) - Terminal UI
- [DuckDuckGo](https://duckduckgo.com) - Free web search
- Inspired by Claude Code's capabilities, built for local use

## Creators
Zain Asad & Adam Akhter

