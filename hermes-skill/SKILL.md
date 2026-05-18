# CLI-Anything for Hermes Agent

## Overview

This skill enables [Hermes Agent](https://github.com/NousResearch/hermes-agent) to use CLI-Anything's methodology for building CLI tools for GUI applications. Hermes is a personal AI agent platform with multi-platform messaging gateway (Telegram, WeChat, Discord, etc.) and a powerful tool system.

## How It Works in Hermes

Hermes agents can execute CLI commands via the built-in `terminal` tool, generate code via `execute_code`, and delegate complex tasks via `delegate_task`. This skill provides the SOP for combining these tools to generate and use CLI harnesses for any target software.

### Available Hermes Tools for Harness Building

| Tool | Purpose in Harness Workflow |
|------|---------------------------|
| `terminal()` | Run shell commands, execute CLI tools, install packages, run tests |
| `execute_code()` | Generate Python code (Click CLI, backend modules, tests) and write files |
| `delegate_task()` | Parallelize analysis and code generation tasks |
| `read_file()` / `write_file()` | Read and write harness files |
| `patch()` | Make targeted edits to generated code |

## General SOP: Building a CLI Harness (7 Phases)

### Phase 1: Codebase Analysis

```python
# In Hermes, use terminal and execute_code to analyze the target software
from hermes_tools import terminal

# 1. Check if software is installed
result = terminal("which <software> 2>/dev/null || echo 'NOT_FOUND'")

# 2. If open source, clone and analyze
terminal("git clone --depth 1 <repo_url> /tmp/<software>-src")
terminal("ls /tmp/<software>-src/")

# 3. Identify the backend engine
# GUI apps typically separate UI from logic — find the core library
# Examples: GIMP → libgimp/pygimp, Blender → bpy, LibreOffice → UNO API
```

### Phase 2: CLI Architecture Design

Design the command structure based on the software's capabilities:

```
cli-anything-<software>
├── project    — Project management (new, open, save, close)
├── <core>     — Core operations (the app's main purpose)
├── io         — Import/Export (file I/O, format conversion)
├── config     — Configuration (settings, preferences)
└── session    — State management (status, undo, redo, history)
```

Key design decisions:
- **Both REPL and subcommand modes** (recommended)
- **JSON output** via `--json` flag for agent consumption
- **Human-readable output** (tables, colors) for interactive use

### Phase 3: Implementation

Generate the CLI using Python Click library:

```python
from hermes_tools import write_file, terminal

# Create the CLI structure
terminal("mkdir -p agent-harness/cli_anything/<software>/{utils,commands,tests}")
terminal("touch agent-harness/cli_anything/<software>/__init__.py")

# Generate the main CLI file
cli_code = '''
import click
...

@click.group(invoke_without_command=True)
@click.option('--json', is_flag=True, help='JSON output')
@click.pass_context
def cli(ctx, json_mode):
    ctx.ensure_object(dict)
    ctx.obj['json'] = json_mode
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)

...
'''

write_file("agent-harness/cli_anything/<software>/cli.py", cli_code)
```

Core modules required:
- `cli.py` — Click CLI entry point with REPL support
- `utils/<software>_backend.py` — Backend wrapper for the real software
- `utils/state.py` — Session state management (project state, undo/redo)
- `commands/project.py`, `commands/core.py` — Command groups

### Phase 4-5: Test Planning & Implementation

```python
# Create TEST.md plan
test_plan = '''
# Test Plan for cli-anything-<software>

## Unit Tests (test_core.py)
- Project creation, opening, saving
- Configuration management
- State serialization

## E2E Tests (test_full_e2e.py)
- Create project, export via real backend, verify output
- Multi-step workflow simulation
- Output format validation (magic bytes, structure)
'''

write_file("agent-harness/cli_anything/<software>/tests/TEST.md", test_plan)

# Run tests
terminal("cd agent-harness && python3 -m pytest cli_anything/<software>/tests/ -v")
```

### Phase 6-7: Installation & Publishing

```bash
# Install the CLI
cd agent-harness && pip install -e .

# Verify
cli-anything-<software> --help
cli-anything-<software> project new -o test_project.json
cli-anything-<software> --json project list
```

## Example: Building a CLI for GIMP

### Step 1: Analyze

```python
from hermes_tools import terminal
terminal("which gimp")  # Check if installed
terminal("gimp --version")
# GIMP backend: pygimp / Script-Fu / ImageMagick for headless ops
```

### Step 2: Design

```
cli-anything-gimp
├── project  — new, open, save, close, list
├── image    — create, resize, crop, rotate, flip
├── layer    — add, remove, duplicate, merge, reorder
├── filter   — apply, blur, sharpen, color-adjust
├── text     — add, edit, format
├── export   — to-png, to-jpg, to-pdf, to-svg
└── selection — select, invert, feather, grow, shrink
```

### Step 3: Implement Backend Wrapper

GIMP's key power: headless batch processing via `gimp -i -b '(command)'` and ImageMagick for image ops.

```python
# utils/gimp_backend.py
def gimp_batch(script):
    return subprocess.run(
        ["gimp", "-i", "-b", script, "-b", "(gimp-quit 0)"],
        capture_output=True, text=True
    )
```

## Existing Harnesses (Reference)

CLI-Anything community has built harnesses for 13+ applications. When building for a new app, check these for patterns:

| Software | Backend Engine | Key Pattern |
|----------|---------------|-------------|
| Blender | bpy (Python API) | Rich Python API, headless rendering |
| GIMP | pygimp + ImageMagick | Script-based batch processing |
| LibreOffice | UNO API + headless CLI | `--headless --convert-to` |
| Shotcut | MLT Framework + melt CLI | `melt` command-line renderer |
| OBS Studio | obs-websocket | WebSocket API for remote control |
| FFmpeg | Native CLI | Direct subprocess wrapper |

## Quick Start Template

When a user says "make <software> controllable by AI", follow this checklist:

```markdown
- [ ] Phase 1: Analyze — `which <software>`, clone repo, find backend
- [ ] Phase 2: Design — Define command groups and state model
- [ ] Phase 3: Implement — Write Click CLI, backend wrapper, state management
- [ ] Phase 4: Test Plan — Create TEST.md
- [ ] Phase 5: Tests — Implement unit + E2E tests
- [ ] Phase 6: Install — `pip install -e .`
- [ ] Phase 7: Verify — Run `--help`, create project, export output
```

## Requirements

- Python 3.10+
- Click 8.0+
- Target software installed locally (or accessible via network)
- Hermes Agent with terminal and execute_code tools enabled
