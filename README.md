# Claude Debussy

> **Status:** Portfolio project — demonstrates multi-phase AI orchestration patterns.
> Built before official Claude orchestration features existed (late 2025).

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design and [decisions.md](decisions.md) for architectural decision records.

## The Problem

When using AI coding assistants on large projects, a single session hits limits quickly: context windows fill up, the model loses track of earlier decisions, and there's no guarantee it followed the plan. Breaking work into phases helps, but manually managing phase dependencies, verifying outputs, and handling failures across dozens of sessions is tedious and error-prone.

## The Solution

**Claude Debussy** is a Python orchestrator that automates multi-phase Claude CLI sessions with built-in compliance verification. You write a plan (phases, dependencies, acceptance gates), and Debussy executes each phase as an isolated Claude session, verifies the output, retries on failure, and tracks progress across restarts.

**Key capabilities:**
- **Phase orchestration** — Dependency-aware execution with automatic retry and remediation strategies
- **Compliance gates** — Never trust the model's claim of success; re-run all gates independently after each phase
- **Docker sandboxing** — Optionally run Claude workers in network-restricted containers (GitHub, npm, PyPI whitelisted only)
- **Real-time TUI** — Interactive Textual dashboard with pause, skip, verbose toggle, and graceful quit
- **Smart restart** — Context usage monitoring triggers automatic session restart with checkpoint context, so long phases don't hit token limits
- **State persistence** — SQLite-backed state allows resuming interrupted runs exactly where they left off
- **Issue tracker sync** — Bidirectional sync with GitHub Issues and Jira for plan-driven development
- **Cross-phase memory** — Optional [Anima](https://github.com/matt-grain/Anima) integration lets workers persist learnings (`/remember`) and recall context (`/recall`) across phases

## How It Works

```
                        Master Plan (Markdown)
                               │
                    ┌──────────┴──────────┐
                    │     Orchestrator     │
                    │  Parse plan, resolve │
                    │  dependencies, track │
                    │  state in SQLite     │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
          Phase 1          Phase 2          Phase 3
        (isolated         (isolated         (isolated
      Claude session)   Claude session)   Claude session)
               │               │               │
               ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  Compliance  │ │  Compliance  │ │  Compliance  │
        │    Gates     │ │    Gates     │ │    Gates     │
        │ (re-run all  │ │ (re-run all  │ │ (re-run all  │
        │  checks)     │ │  checks)     │ │  checks)     │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
            ✓ Pass          ✗ Fail → Retry   ✓ Pass
               │               │               │
            Commit          Remediate        Commit
```

## Architecture Highlights

| Component | Responsibility | Tech |
|-----------|---------------|------|
| **CLI Layer** | User interface, 7 command modules | Typer |
| **Orchestrator Core** | Phase execution, retry, completion tracking | asyncio, mixins |
| **Compliance Checker** | Gate verification, remediation strategy | subprocess |
| **Claude Runner** | Session management, streaming, prompt building | Claude CLI, JSON streaming |
| **TUI Dashboard** | Real-time monitoring with keyboard controls | Textual |
| **State Manager** | Run persistence, phase status tracking | SQLite (aiosqlite) |
| **Sync Layer** | GitHub/Jira bidirectional issue sync | httpx |

The codebase follows a modular architecture with clear layer separation. Large modules have been split into focused sub-modules (e.g., `cli.py` → 6 command files, `orchestrator.py` → 3 mixins). See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Quick Start

```bash
# Install as dev dependency in your project
uv add --dev git+https://github.com/matt-grain/Claude-Debussy.git

# Initialize orchestration support
uv run debussy init .

# Dry run — validate plan without executing
uv run debussy run docs/master-plan.md --dry-run

# Full run with interactive TUI
uv run debussy run docs/master-plan.md

# CI/automation mode (no TUI)
uv run debussy run docs/master-plan.md --yolo
```

## Interactive TUI

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

## Lessons Learned

This project was built to explore how far you can push AI-assisted development with structured orchestration. Key takeaways:

- **Compliance verification is non-negotiable** — The gate pattern ("never trust the model's claim") caught issues that would have compounded across phases
- **Context management matters** — Smart restart with checkpoint context was essential for phases exceeding token limits
- **Sandbox isolation adds real value** — Network-restricted Docker containers prevented unexpected external calls
- **API key management** — The project originally used Claude Code's OAuth session tokens in containers, which violated Anthropic's terms of service. The architecture now requires `ANTHROPIC_API_KEY` environment variables instead. This experience directly informed the security design of subsequent projects

## Tech Stack

Python 3.13 | Typer | Textual | Pydantic | SQLite | Docker | httpx | asyncio

## Development

```bash
uv sync                          # Install dependencies
uv run pytest                    # 1042 tests, 68% coverage
uv run ruff check src/           # Linting
uv run pyright src/              # Type checking
pre-commit run --all-files       # Full validation
```

## License

MIT

## Credits

Built with Claude Code by [@matt-grain](https://github.com/matt-grain) and Anima (Claude).

### Why "Debussy"?

From Wikipedia, about [Claude Debussy](https://fr.wikipedia.org/wiki/Claude_Debussy):
> Son génie de l'orchestration et son attention aiguë aux couleurs instrumentales font de Debussy le digne héritier de Berlioz et l'égal au moins de son contemporain Ravel.

*His genius for orchestration and acute attention to instrumental colors make Debussy the worthy heir of Berlioz.*
A fitting name for a Claude orchestrator.
