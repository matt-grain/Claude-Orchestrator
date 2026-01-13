# Claude Debussy

A Python (Claude) Debussy for multi-phase Claude CLI sessions with compliance verification, state persistence, and real-time streaming output.

## Overview

Claude Debussy coordinates complex, multi-phase projects by:
- Spawning ephemeral Claude CLI sessions for each phase
- Tracking state and dependencies between phases
- Verifying compliance (gates, required agents, notes)
- Providing real-time streaming output
- Supporting automatic retries with remediation

## Installation

```bash
# Clone the repository
git clone https://github.com/matt-grain/Claude-Debussy.git
cd Claude-Debussy

# Install with uv
uv pip install -e .

# Or add to your project
uv add --dev "claude-debussy @ file:///path/to/Claude-Debussy"

# With LTM support (cross-phase memory)
uv pip install -e ".[ltm]"
```

## Quick Start

### 1. Create a Master Plan

Create `docs/master-plan.md`:

```markdown
# My Project - Master Plan

**Created:** 2026-01-12
**Status:** Draft

## Overview

Description of what you're building.

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Setup](phase1-setup.md) | Create base files | Low | Pending |
| 2 | [Implementation](phase2-impl.md) | Core logic | Medium | Pending |

## Dependencies

Phase 1 --> Phase 2
```

### 2. Create Phase Files

Create `docs/phase1-setup.md`:

```markdown
# Phase 1: Setup

**Status:** Pending
**Master Plan:** [master-plan.md](master-plan.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Write notes to: `notes/NOTES_phase_1.md`

## Gates
- echo: must pass

---

## Tasks

### 1. Create Base Structure
- [ ] 1.1: Create `src/module.py` with basic structure
- [ ] 1.2: Create `tests/test_module.py` placeholder
```

### 3. Run the Debussy

```bash
# Dry run - validate plan without executing
debussy run docs/master-plan.md --dry-run

# Full run with default model (sonnet) - interactive mode
debussy run docs/master-plan.md

# YOLO mode - no interactive dashboard (for CI/automation)
debussy run docs/master-plan.md --yolo
debussy run docs/master-plan.md --no-interactive

# Use haiku for faster/cheaper execution
debussy run docs/master-plan.md --model haiku

# Use opus for complex tasks
debussy run docs/master-plan.md --model opus

# Output to log files instead of terminal
debussy run docs/master-plan.md --output file

# Output to both terminal and log files
debussy run docs/master-plan.md --output both
```

## CLI Commands

### `debussy run`

Start orchestrating a master plan.

```bash
debussy run <master-plan.md> [options]

Options:
  --dry-run, -n       Parse and validate only, don't execute
  --phase, -p         Start from specific phase ID
  --resume, -r        Resume previous run, skip completed phases
  --restart           Start fresh, ignore previous progress
  --model, -m         Claude model: haiku, sonnet, opus (default: sonnet)
  --output, -o        Output mode: terminal, file, both (default: terminal)
  --no-interactive    YOLO mode: disable interactive dashboard (for CI)
  --yolo              Alias for --no-interactive
```

### `debussy status`

Show current orchestration status.

```bash
debussy status [--run RUN_ID]
```

### `debussy history`

List past orchestration runs.

```bash
debussy history [--limit N]
```

### `debussy done`

Signal phase completion (called by Claude worker).

```bash
debussy done --phase 1 --status completed
debussy done --phase 1 --status blocked --reason "Missing dependency"
```

### `debussy resume`

Resume a paused orchestration run.

```bash
debussy resume
```

### `debussy init`

Initialize a target project for Debussy orchestration.

```bash
# Basic setup - installs agent, skill, and commands
debussy init /path/to/project

# With LTM memory support (cross-phase memory)
debussy init /path/to/project --with-ltm

# Force overwrite existing files
debussy init /path/to/project --force
```

This creates:
- `.claude/agents/debussy.md` - Debussy worker agent identity
- `.claude/skills/debussy.md` - Command documentation
- `.claude/commands/debussy-*.md` - Slash commands (`/debussy-done`, `/debussy-progress`, `/debussy-status`)
- `.claude/commands/please-remember.md`, `recall.md` - LTM commands (with `--with-ltm`)

## Configuration

Create `.debussy/config.yaml`:

```yaml
timeout: 1800          # Phase timeout in seconds (default: 30 min)
max_retries: 2         # Max retry attempts per phase
model: sonnet          # Default model: haiku, sonnet, opus
output: terminal       # Output mode: terminal, file, both
interactive: true      # Interactive dashboard (default: true)
strict_compliance: true

notifications:
  enabled: true
  provider: desktop    # desktop, ntfy, none
  ntfy_server: "https://ntfy.sh"  # For ntfy provider
  ntfy_topic: "claude-debussy"    # For ntfy provider
```

When using `file` or `both` output modes, logs are saved to `.debussy/logs/run_{id}_phase_{n}.log`.

## Interactive Mode

By default, Debussy runs with an interactive dashboard that shows real-time progress:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Debussy │ Phase 2/5: Backend API │ ● Running │ ⏱ 00:12:34        │
│  [s]tatus  [p]ause  [v]erbose (on)  [k]skip  [q]uit               │
├─────────────────────────────────────────────────────────────────────┤
│ > Reading src/api/routes.py                                         │
│ > Edit: src/api/routes.py:45-52                                     │
│ > Running gate: ruff check... ✓                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Hotkeys

| Key | Action |
|-----|--------|
| `s` | Show detailed status (phase info, gates, progress) |
| `p` | Pause/resume orchestration |
| `v` | Toggle verbose logging on/off |
| `k` | Skip current phase (with confirmation) |
| `q` | Quit gracefully (saves state for resume) |

### Resume Dialog

When you run a plan that has a previous incomplete run (interrupted, failed, or paused), Debussy shows a modal dialog:

```
┌────────────────── Resume Previous Run? ──────────────────┐
│                                                          │
│         Found incomplete run fb8e3176                    │
│         with 2 completed phase(s).                       │
│                                                          │
│              [ Resume ]    [ Start Fresh ]               │
└──────────────────────────────────────────────────────────┘
```

- **Resume**: Skips completed phases, continues from where it left off
- **Start Fresh**: Ignores previous progress, starts a new run

You can bypass this dialog with CLI flags:
```bash
debussy run plan.md --resume   # Auto-resume, skip completed phases
debussy run plan.md --restart  # Force fresh start, ignore history
```

### YOLO Mode

For CI/automation, disable the interactive dashboard:

```bash
debussy run plan.md --yolo
debussy run plan.md --no-interactive
```

## Notifications

Debussy supports desktop and push notifications:

### Desktop Notifications (default)
Cross-platform via plyer (Windows, macOS, Linux):
```yaml
notifications:
  provider: desktop
```

### ntfy Push Notifications
HTTP-based push to ntfy.sh or self-hosted:
```yaml
notifications:
  provider: ntfy
  ntfy_server: "https://ntfy.sh"
  ntfy_topic: "my-debussy"
```

## Phase File Format

### Required Sections

```markdown
# Phase N: Title

**Status:** Pending
**Master Plan:** [link](master-plan.md)
**Depends On:** [Phase N-1](phaseN-1.md) or N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase_N-1.md`  (if applicable)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Write notes to: `notes/NOTES_phase_N.md`

## Gates
- command: description

---

## Tasks
...
```

### Optional: Required Agents

```markdown
## Process Wrapper (MANDATORY)
- [ ] **AGENT:doc-sync-manager** - required agent
- [ ] **[IMPLEMENTATION]**
```

## Streaming Output

The debussy displays real-time output from Claude sessions:

```
[Read: phase1-setup.md]
[TodoWrite: 5 items]
[Write: calculator.py]
[Bash: echo "validation passed"]
[Edit: module.py]
[ERROR: Exit code 1...]
```

## State Persistence

State is stored in `.debussy/state.db` (SQLite) relative to your project root.

```bash
# Check current state
debussy status

# View history
debussy history
```

## LTM Integration (Optional)

Debussy can integrate with [Claude-LTM](https://github.com/matt-grain/Claude-LTM) for cross-phase memory:

```bash
# Install with LTM support
pip install 'claude-debussy[ltm]'

# Initialize project with memory commands
debussy init /path/to/project --with-ltm
```

When enabled, the spawned Debussy agent can:
- `/recall` - Retrieve memories from previous phases before starting
- `/remember` - Save key decisions, blockers, and lessons learned

Memories are **project-scoped** - each orchestrated project has its own memory context.

## Architecture

```
+-------------------------------------------------------------+
|                    Python Debussy                       |
|  - Parses master plan and phase files                       |
|  - Manages state in SQLite                                  |
|  - Coordinates phase execution                              |
|  - Verifies compliance after each phase                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   Claude CLI Sessions                        |
|  - Fresh session per phase (no token limits)                |
|  - --dangerously-skip-permissions for automation            |
|  - --output-format stream-json for real-time output         |
|  - Calls `debussy done` when complete                   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  Compliance Checker                          |
|  - Re-runs all gates independently                          |
|  - Verifies required agents were invoked                    |
|  - Checks notes file exists with required sections          |
|  - Determines remediation strategy on failure               |
+-------------------------------------------------------------+
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run pyright src/
uv run ty check src/

# Run all pre-commit hooks
pre-commit run --all-files
```

## License

MIT

## Credits

Built with Claude Code by @matt-grain and Anima (Claude).

## Why Debussy ?

From Wikipedia, about [Claude Debussy](https://fr.wikipedia.org/wiki/Claude_Debussy)
> Son génie de l’orchestration et son attention aiguë aux couleurs instrumentales font de Debussy le digne héritier de Berlioz et l’égal au moins de son contemporain Ravel.