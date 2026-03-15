# Architecture

## Overview

Claude-Debussy is a multi-phase orchestration system that drives Claude CLI sessions through structured work plans. It parses Markdown plan files into typed `MasterPlan` / `Phase` models, executes each phase as a supervised Claude subprocess, and enforces post-phase compliance (gate re-execution, notes verification, agent-invocation checks). State is persisted in a local SQLite database, the operator interacts through a real-time Textual TUI or a non-interactive mode, and optional GitHub / Jira sync keeps external trackers aligned with phase progress.

## Tech Stack

| Concern | Library / Tool |
|---|---|
| Language | Python 3.13 |
| CLI entry-point | Typer |
| Terminal UI | Textual + Rich |
| Domain models / config | Pydantic v2 |
| State persistence | sqlite3 (stdlib, synchronous) |
| HTTP clients (sync / GitHub / Jira) | httpx |
| Async runtime | asyncio |
| Docker sandboxing | Docker CLI subprocess |
| Desktop notifications | plyer / ntfy HTTP push |
| Plan files | Markdown (parsed with regex) |
| Package manager | uv |

## Project Structure

```
src/debussy/
├── cli.py                    # Typer app — all CLI commands (run, status, done, resume, …)
├── config.py                 # Pydantic Config + sub-configs (GitHub, Jira, notifications)
├── core/
│   ├── models.py             # All Pydantic domain models and enums (source of truth)
│   ├── orchestrator.py       # Orchestrator class — phase loop, compliance, sync
│   ├── state.py              # StateManager — SQLite persistence of runs & executions
│   ├── checkpoint.py         # CheckpointManager — progress tracking & restart context
│   ├── compliance.py         # ComplianceChecker — gate re-run, notes, agent verification
│   ├── audit.py / auditor.py # Audit trail helpers
│   └── __init__.py
├── runners/
│   ├── claude.py             # ClaudeRunner — subprocess management, stream parsing
│   ├── gates.py              # GateRunner — shell command execution for validation gates
│   ├── stream_parser.py      # JsonStreamParser — parse Claude's JSON event stream
│   ├── context_estimator.py  # Token / context window estimation for restart decisions
│   └── docker_builder.py     # DockerCommandBuilder — Docker run command assembly
├── parsers/
│   ├── master.py             # parse_master_plan() — parse master plan Markdown
│   ├── phase.py              # parse_phase() — parse individual phase Markdown files
│   └── learnings.py          # extract_learnings() — extract LTM learnings from notes
├── converters/
│   ├── plan_converter.py     # Convert GitHub issues → MasterPlan YAML/Markdown
│   ├── prompts.py            # Prompt templates for plan generation
│   └── quality.py            # Quality checks on generated plans
├── planners/
│   ├── analyzer.py           # Analyse issues to determine phases
│   ├── plan_builder.py       # Build plan from analysed issues
│   ├── github_fetcher.py     # Fetch GitHub issues for plan generation
│   ├── qa_handler.py         # Two-pass Q&A flow for plan refinement
│   └── command.py            # CLI planner command wiring
├── sync/
│   ├── github_sync.py        # GitHubSyncCoordinator — label / close issues
│   ├── github_client.py      # Raw GitHub API client (httpx)
│   ├── jira_sync.py          # JiraSynchronizer — transition Jira issues
│   ├── jira_client.py        # Raw Jira REST client (httpx)
│   ├── drift_detector.py     # Detect state drift between Debussy and trackers
│   ├── status_fetcher.py     # Fetch current issue statuses
│   └── label_manager.py      # Create / apply GitHub labels
├── ui/
│   ├── tui.py                # TextualUI — full interactive dashboard (Textual App)
│   ├── base.py               # UIState, UserAction, OrchestratorUI abstract base
│   ├── controller.py         # OrchestrationController — bridges UI ↔ Orchestrator
│   ├── messages.py           # Textual message types for UI event bus
│   └── interactive.py        # NonInteractiveUI — plain-text fallback
├── notifications/
│   ├── base.py               # Notifier ABC + ConsoleNotifier + NullNotifier
│   ├── desktop.py            # DesktopNotifier, CompositeNotifier
│   └── ntfy.py               # NtfyNotifier (HTTP push to ntfy.sh)
├── logging/
│   ├── orchestrator_logger.py # Structured event logger for orchestrator lifecycle
│   └── __init__.py
├── planners/                 # (see above)
├── templates/
│   └── scaffolder.py         # Generate plan file scaffolding
├── resources/
│   ├── loader.py             # Load bundled agents, skills, commands
│   ├── agents/               # Bundled agent CLAUDE.md files
│   ├── skills/               # Bundled Claude Code skill files
│   └── commands/             # Bundled Claude Code command files
└── utils/
    ├── docker.py             # Docker / WSL path helpers
    └── git.py                # Git utility functions
```

## Layer Responsibilities

### CLI (`cli.py`)
**Does:** Parse user arguments, resolve paths, call `run_orchestration()` or `StateManager` for status queries, display Rich tables for output.
**Must NOT:** Contain business logic, directly access SQLite, or make Claude subprocess calls.

```python
# cli.py — thin entry-point pattern
app = typer.Typer(name="debussy", help="Orchestrate multi-phase Claude CLI sessions…")

@app.command()
def run(plan: Annotated[Path, typer.Argument(...)], …) -> None:
    asyncio.run(run_orchestration(plan, config=Config.load(), …))
```

---

### Core — Orchestrator (`core/orchestrator.py`)
**Does:** Own the phase execution loop, coordinate all subsystems (runner, compliance, sync, UI, notifications, checkpoint), manage run lifecycle transitions.
**Must NOT:** Parse Markdown directly, issue raw SQL queries, or render UI widgets.

```python
# orchestrator.py — central coordination
class Orchestrator:
    def __init__(self, master_plan_path, config, …):
        self.state   = StateManager(orchestrator_dir / "state.db")
        self.claude  = ClaudeRunner(…)
        self.gates   = GateRunner(self.project_root)
        self.checker = ComplianceChecker(self.gates, …)
        self.ui      = TextualUI() if config.interactive else NonInteractiveUI()

    async def run(self, start_phase=None, skip_phases=None) -> str:
        run_id = self.state.create_run(self.plan)
        for phase in phases_to_run:
            success = await self._execute_phase_with_compliance(run_id, phase)
            if not success:
                self.state.update_run_status(run_id, RunStatus.FAILED)
                return run_id
        self.state.update_run_status(run_id, RunStatus.COMPLETED)
        return run_id
```

---

### Core — State (`core/state.py`)
**Does:** Persist and query all orchestration state (runs, phase executions, gate results, completion signals, progress log, completed features) in a local SQLite database.
**Must NOT:** Contain business logic, call Claude, or know about UI or compliance rules.

```python
# state.py — SQLite persistence with PRAGMA synchronous=FULL
class StateManager:
    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA synchronous=FULL")  # Required for Docker volume mounts
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
```

---

### Core — Checkpoint (`core/checkpoint.py`)
**Does:** Track in-flight progress entries (from `/debussy-progress` skill calls) and git state so restarted sessions can resume intelligently.
**Must NOT:** Persist to SQLite (that is `StateManager`'s role), or communicate with Claude.

```python
# checkpoint.py — restart context builder
class CheckpointManager:
    def prepare_restart(self) -> str:
        self._current.restart_count += 1
        self._current.capture_git_state(self.project_root)
        return self._current.format_restart_context()
```

---

### Core — Compliance (`core/compliance.py`)
**Does:** Independently re-run gates, verify notes file structure, check that required agents were invoked, determine remediation strategy.
**Must NOT:** Trust Claude's own completion report without verification; must NOT write to state.

```python
# compliance.py — independent verification
async def verify_completion(self, phase, session_log, completion_report) -> ComplianceResult:
    gate_results = await self._verify_gates(phase)   # 1. Re-run gates
    notes_issues = self._check_notes(phase)           # 2. Verify notes file
    agent_issues = self._check_agent_invocations(…)  # 3. Check agent usage
    step_issues  = self._check_required_steps(…)     # 4. Check required steps
    remediation  = self._determine_remediation(issues)
    return ComplianceResult(passed=len(issues)==0, …)
```

---

### Runners (`runners/`)
**Does:** `ClaudeRunner` spawns Claude CLI as a subprocess, streams JSON events, tracks PIDs in a global `PIDRegistry`, detects context limits, and triggers restarts. `GateRunner` executes shell gate commands. `DockerCommandBuilder` assembles Docker run arguments for sandboxed execution.
**Must NOT:** Access SQLite, modify phase status, or call compliance logic.

```python
# runners/claude.py — subprocess management
SANDBOX_IMAGE = "debussy-sandbox:latest"

class PIDRegistry:
    """Global registry of spawned Claude subprocess PIDs — safety net for orphan cleanup."""
    def register(self, pid: int) -> None: …
    def unregister(self, pid: int) -> None: …
```

---

### Parsers (`parsers/`)
**Does:** Convert Markdown plan files into `MasterPlan` and `Phase` Pydantic models. `parse_master_plan()` handles the top-level plan, `parse_phase()` enriches individual phase files with gates, tasks, and agent requirements.
**Must NOT:** Execute any I/O other than reading files, or know about orchestration state.

---

### Converters (`converters/`)
**Does:** Transform GitHub issues into draft `MasterPlan` Markdown files using Claude as a generation backend.
**Must NOT:** Directly modify existing plan files or write state.

---

### Planners (`planners/`)
**Does:** Implement the two-pass plan generation flow — fetch issues, analyse them, generate a plan, run a Q&A refinement round, write the output file.
**Must NOT:** Execute phases or access state.

---

### Sync (`sync/`)
**Does:** Keep GitHub and Jira issue trackers aligned with phase status. On phase start/complete the coordinator applies labels (GitHub) or triggers workflow transitions (Jira). Drift detection identifies divergence between Debussy state and external tracker state.
**Must NOT:** Modify plan files or phase execution logic; must NOT block phase execution on sync failures.

---

### UI (`ui/`)
**Does:** `TextualUI` (interactive) provides a live Textual dashboard with HUD, log panel, and keyboard bindings. `NonInteractiveUI` prints plain-text output. `OrchestrationController` bridges the Orchestrator coroutine into Textual's worker system. `messages.py` defines the Textual message types used for cross-widget communication.
**Must NOT:** Contain orchestration logic or write to state.

```python
# ui/tui.py — Textual dashboard wired into orchestration
from textual import work
from textual.app import App

class TextualUI(App):
    # Receives LogMessage, PhaseChanged, TokenStatsUpdated, etc.
    # via Textual's on_* message dispatch system
    ...
```

---

### Notifications (`notifications/`)
**Does:** Send human-readable alerts at key lifecycle events (start, phase complete, failure). `CompositeNotifier` fans out to multiple providers. Providers: console, desktop (plyer), ntfy (HTTP push).
**Must NOT:** Affect execution flow; notification failures must never crash orchestration.

---

### Logging (`logging/`)
**Does:** Emit structured JSON events to `.debussy/orchestrator.log` for machine-readable audit trails (run init, phase start/complete/skip, config snapshot).
**Must NOT:** Replace Python's standard `logging`; it is an additional audit layer.

---

### Docker / Utils (`runners/docker_builder.py`, `utils/docker.py`)
**Does:** Build Docker run commands for `devcontainer` sandbox mode, detect whether Docker is available, translate Windows/WSL paths.
**Must NOT:** Know about plan content or phase semantics.

## Data Flow

A typical plan execution progresses through these steps:

1. **CLI invocation** — `debussy run plan.md` calls `run_orchestration(plan_path, config)`.
2. **Plan parsing** — `Orchestrator.load_plan()` calls `parse_master_plan()` then enriches each phase with `parse_phase()`, producing a typed `MasterPlan`.
3. **Run creation** — `StateManager.create_run()` inserts a row in `runs` and returns a short UUID `run_id`.
4. **UI start** — `TextualUI` (or `NonInteractiveUI`) initialises its display. `ClaudeRunner` callbacks route log output and token stats into the UI via message passing.
5. **External sync init** — `GitHubSyncCoordinator` and `JiraSynchronizer` are initialised if enabled in config; they fetch and validate linked issue IDs.
6. **Phase loop** — For each `Phase` in `MasterPlan.phases`:
   a. Dependency check: skip if `depends_on` phases are not `COMPLETED`.
   b. `StateManager.create_phase_execution()` writes a `RUNNING` record.
   c. `CheckpointManager.start_phase()` captures the HEAD commit.
   d. `ClaudeRunner.run_phase()` spawns Claude as a subprocess, streams JSON events, and returns an `ExecutionResult`.
   e. If context threshold is exceeded mid-phase, `CheckpointManager.prepare_restart()` formats a restart prompt and `ClaudeRunner` relaunches Claude.
   f. **Compliance verification** — `ComplianceChecker.verify_completion()` re-runs gates, checks notes file, verifies agent invocations. Returns a `ComplianceResult`.
   g. Remediation: `WARN_AND_ACCEPT` (log and continue), `TARGETED_FIX` (spawn remediation session), or `FULL_RETRY` (fresh Claude session).
   h. On success: `StateManager.update_phase_status(COMPLETED)`, optional `git commit`, GitHub/Jira label/transition applied.
   i. On failure after all retries: `StateManager.update_run_status(FAILED)`, early exit.
7. **Run completion** — `StateManager.update_run_status(COMPLETED)`, GitHub issues optionally closed, `StateManager.record_completion()` written for re-run protection.
8. **Notifications** — `Notifier` sends a final success or failure alert.

## Key Domain Concepts

**`MasterPlan`** — Top-level container parsed from a Markdown file. Holds a list of `Phase` objects plus optional GitHub / Jira issue references.

```python
class MasterPlan(BaseModel):
    name: str
    path: Path
    phases: list[Phase]
    github_issues: list[int] | str | None = None
    github_repo: str | None = None
    jira_issues: list[str] | str | None = None
```

**`Phase`** — One unit of work executed in a single Claude session. Carries the path to its Markdown instruction file, dependency list, gates, tasks, required agents/steps, and notes file paths.

```python
class Phase(BaseModel):
    id: str
    title: str
    path: Path
    status: PhaseStatus = PhaseStatus.PENDING
    depends_on: list[str] = []
    gates: list[Gate] = []
    tasks: list[Task] = []
    required_agents: list[str] = []
    required_steps: list[str] = []
    notes_input: Path | None = None
    notes_output: Path | None = None
```

**`ExecutionResult`** — Outcome of one Claude subprocess invocation.

```python
class ExecutionResult(BaseModel):
    success: bool
    session_log: str
    exit_code: int
    duration_seconds: float
    pid: int | None = None
```

**`ComplianceIssue`** — A single violation found during post-phase verification.

```python
class ComplianceIssue(BaseModel):
    type: ComplianceIssueType   # NOTES_MISSING | NOTES_INCOMPLETE | GATES_FAILED | AGENT_SKIPPED | STEP_SKIPPED
    severity: Literal["low", "high", "critical"]
    details: str
    evidence: str | None = None
```

**`RunState`** — Snapshot of an orchestration run as stored in SQLite.

```python
class RunState(BaseModel):
    id: str
    master_plan_path: Path
    started_at: datetime
    status: RunStatus
    current_phase: str | None = None
    phase_executions: list[PhaseExecution] = []
```

## State Machines

### `PhaseStatus` — per-phase execution state

```
PENDING
  │
  ▼
RUNNING ──── context limit ──► (restart: back to RUNNING)
  │
  ├──► VALIDATING   (compliance check in progress)
  │         │
  │         ├──► COMPLETED   (all checks pass)
  │         ├──► FAILED      (unrecoverable / max retries exceeded)
  │         └──► BLOCKED     (Claude reported blocked; human intervention needed)
  │
  └──► AWAITING_HUMAN   (paused for human decision)
```

Valid transitions enforced by the orchestrator (not an explicit FSM guard):

| From | To | Trigger |
|---|---|---|
| `PENDING` | `RUNNING` | Phase starts |
| `RUNNING` | `VALIDATING` | Claude subprocess exits |
| `RUNNING` | `FAILED` | Subprocess error / timeout |
| `VALIDATING` | `COMPLETED` | Compliance passes |
| `VALIDATING` | `RUNNING` | `TARGETED_FIX` or `FULL_RETRY` remediation |
| `VALIDATING` | `FAILED` | Compliance fails after max retries |
| `VALIDATING` | `BLOCKED` | `CompletionSignal.status == "blocked"` |
| `RUNNING` | `AWAITING_HUMAN` | User pauses via TUI (`p` key) |
| `AWAITING_HUMAN` | `RUNNING` | User resumes |

### `RunStatus` — per-orchestration-run state

```
RUNNING
  │
  ├──► COMPLETED   (all phases completed)
  ├──► FAILED      (a phase failed and was not recovered)
  └──► PAUSED      (KeyboardInterrupt / user quit / CancelledError)
```

`PAUSED` and `FAILED` runs are resumable via `debussy resume` — `StateManager.find_resumable_run()` locates them and `get_completed_phases()` lets the orchestrator skip already-finished phases.
