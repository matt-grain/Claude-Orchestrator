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

# Full run with default model (sonnet)
debussy run docs/master-plan.md

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
  --dry-run, -n     Parse and validate only, don't execute
  --phase, -p       Start from specific phase ID
  --model, -m       Claude model: haiku, sonnet, opus (default: sonnet)
  --output, -o      Output mode: terminal, file, both (default: terminal)
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

## Configuration

Create `.debussy/config.yaml`:

```yaml
timeout: 1800          # Phase timeout in seconds (default: 30 min)
max_retries: 2         # Max retry attempts per phase
model: sonnet          # Default model: haiku, sonnet, opus
output: terminal       # Output mode: terminal, file, both
strict_compliance: true

notifications:
  enabled: true
  provider: desktop    # desktop, ntfy, none
```

When using `file` or `both` output modes, logs are saved to `.debussy/logs/run_{id}_phase_{n}.log`.

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
