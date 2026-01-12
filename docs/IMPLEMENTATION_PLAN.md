# Claude Debussy - Implementation Plan

**Created:** 2026-01-12
**Status:** v0.1.1 Released
**Version:** 0.1.1
**Study:** [STUDY_ORCHESTRATOR_DESIGN.md](STUDY_ORCHESTRATOR_DESIGN.md)

---

## Release History

### v0.1.1 (2026-01-12)
- **ASCII Banner**: Beautiful startup banner with plan info and phase table
- **--output flag**: Choose output mode (terminal, file, both)
- **--model flag**: Select Claude model (haiku, sonnet, opus)
- **Log files**: Per-phase logs saved to `.debussy/logs/` when using file output
- **Bug fixes**: Streaming output format, state persistence, dependency tracking, notes path resolution

### v0.1.0 (2026-01-12)
- Initial release with full MVP functionality
- Master plan and phase parsing
- Claude CLI spawning with streaming output
- Compliance checker with remediation loops
- SQLite state persistence
- All quality gates passing (72 tests, 64% coverage)

---

## Architecture Summary

Python-based debussy that spawns ephemeral Claude CLI sessions to execute implementation phases sequentially, with validation gates and state persistence.

```
┌────────────────────────────────────────────────────────────────────┐
│                    debussy CLI (Python)                         │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ PlanParser  │  │StateMachine │  │ClaudeSpawner│  │ Notifier  │ │
│  │ (markdown)  │  │  (SQLite)   │  │ (subprocess)│  │(ntfy/toast)│ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│         │                │                │                │       │
│         ▼                ▼                ▼                ▼       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      Debussy                            │  │
│  │  - Load master plan → parse phases                          │  │
│  │  - For each phase: spawn Claude → wait → run gates          │  │
│  │  - On completion/failure: notify + update state             │  │
│  └─────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
         │                                      │
         │ reads/writes                         │ spawns
         ▼                                      ▼
┌─────────────────┐                   ┌─────────────────────────────┐
│ .debussy/  │                   │  Claude CLI Worker          │
│   state.db      │                   │  - Phase plan as context    │
│   config.toml   │                   │  - Previous notes injected  │
│   runs/{id}/    │                   │  - Uses project agents      │
│     logs...     │                   │  - LTM for cross-session    │
└─────────────────┘                   │  - Calls `debussy done` │
                                      └─────────────────────────────┘
```

---

## Project Structure

```
claude-debussy/
├── pyproject.toml
├── README.md
├── docs/
│   ├── STUDY_ORCHESTRATOR_DESIGN.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── templates/              # Portable templates
│       ├── plans/
│       │   ├── MASTER_TEMPLATE.md
│       │   ├── PHASE_BACKEND.md
│       │   └── PHASE_FRONTEND.md
│       └── notes/
│           └── NOTES_TEMPLATE.md
├── src/
│   └── debussy/
│       ├── __init__.py
│       ├── cli.py              # Typer CLI entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── debussy.py # Main orchestration logic
│       │   ├── state.py        # State machine + SQLite
│       │   ├── models.py       # Pydantic models
│       │   └── compliance.py   # Compliance checker
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── master.py       # Master plan parser
│       │   └── phase.py        # Phase file parser
│       ├── runners/
│       │   ├── __init__.py
│       │   ├── claude.py       # Claude CLI spawner
│       │   └── gates.py        # Validation gate runner
│       ├── notifications/
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract notifier
│       │   ├── desktop.py      # Windows toast / macOS notification
│       │   └── ntfy.py         # ntfy.sh integration
│       └── config.py           # Configuration loading
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parsers.py
    ├── test_state.py
    ├── test_compliance.py
    ├── test_runners.py
    └── fixtures/
        ├── sample_master.md
        └── sample_phase.md
```

---

## Implementation Phases

### Phase 1: Foundation (MVP) - ✅ COMPLETE

**Goal:** Parse plans, run phases sequentially, basic state tracking

#### 1.1 Project Setup
- [x] Update pyproject.toml with dependencies
- [x] Create src/debussy package structure
- [x] Setup CLI entry point with Typer

**Dependencies to add:**
```toml
dependencies = [
    "typer>=0.12",
    "rich>=13.0",          # Pretty terminal output
    "pydantic>=2.0",       # Data validation
    "pyyaml>=6.0",         # Config files
]
```

#### 1.2 Models (src/debussy/core/models.py)
- [x] Define `MasterPlan` model
- [x] Define `Phase` model with status enum
- [x] Define `Gate` model
- [x] Define `Task` model
- [x] Define `RunState` model

```python
from enum import Enum
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class Gate(BaseModel):
    name: str
    command: str
    blocking: bool = True

class Task(BaseModel):
    id: str
    description: str
    completed: bool = False

class Phase(BaseModel):
    id: str
    title: str
    path: Path
    status: PhaseStatus = PhaseStatus.PENDING
    depends_on: list[str] = []
    gates: list[Gate] = []
    tasks: list[Task] = []
    notes_input: Path | None = None
    notes_output: Path | None = None

class MasterPlan(BaseModel):
    name: str
    path: Path
    phases: list[Phase]
    created_at: datetime
```

#### 1.3 Plan Parsers (src/debussy/parsers/)
- [x] Master plan parser: extract phase table
- [x] Phase parser: extract gates, tasks, notes paths
- [x] Handle frontmatter (YAML) if present

**Master plan parsing targets:**
```markdown
| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Unit of Work](phase1.md) | ... | Low | Pending |
```

**Phase parsing targets:**
```markdown
## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_*_phase_1.md`
...
## Gates
- bandit: 0 HIGH/MEDIUM findings
- ruff: 0 errors
```

#### 1.4 State Management (src/debussy/core/state.py)
- [x] SQLite connection manager
- [x] Create tables: runs, phase_executions, gate_results
- [x] CRUD operations for run state
- [x] Transaction support for atomic updates

```python
class StateManager:
    def __init__(self, db_path: Path): ...
    def create_run(self, master_plan: MasterPlan) -> str: ...
    def get_run(self, run_id: str) -> RunState: ...
    def update_phase_status(self, run_id: str, phase_id: str, status: PhaseStatus): ...
    def record_gate_result(self, run_id: str, phase_id: str, gate: Gate, passed: bool, output: str): ...
    def get_current_run(self) -> RunState | None: ...
```

#### 1.5 Claude Runner (src/debussy/runners/claude.py)
- [x] Build prompt from phase + notes
- [x] Spawn Claude CLI subprocess
- [x] Capture stdout/stderr to log files
- [x] Handle timeout with configurable duration
- [x] Kill subprocess on timeout
- [x] Streaming JSON output parsing (v0.1.1)
- [x] Dual output mode (terminal/file/both) (v0.1.1)

```python
class ClaudeRunner:
    def __init__(self, project_root: Path, timeout: int = 1800): ...

    async def execute_phase(self, phase: Phase) -> ExecutionResult:
        prompt = self._build_prompt(phase)
        # Spawn claude --print -p "{prompt}"
        ...

    def _build_prompt(self, phase: Phase) -> str:
        return f"""
Execute the implementation phase defined in: {phase.path}

Previous phase notes: {phase.notes_input or 'N/A (first phase)'}

Instructions:
1. Read and follow the Process Wrapper exactly
2. Complete all tasks in the Tasks section
3. Run pre-validation commands until all pass
4. Write notes to: {phase.notes_output}
5. When complete, run: debussy done --phase {phase.id}
6. If blocked, run: debussy done --phase {phase.id} --status blocked --reason "..."
"""
```

#### 1.6 Gate Runner (src/debussy/runners/gates.py)
- [x] Parse gate commands from phase
- [x] Execute each gate command
- [x] Capture pass/fail + output
- [x] Return structured results

```python
class GateRunner:
    def __init__(self, project_root: Path): ...

    async def run_gates(self, phase: Phase) -> list[GateResult]:
        results = []
        for gate in phase.gates:
            result = await self._run_gate(gate)
            results.append(result)
        return results
```

#### 1.7 CLI Commands (src/debussy/cli.py)
- [x] `debussy run <master_plan>` - Start orchestration
- [x] `debussy status` - Show current run status
- [x] `debussy done --phase N [--status] [--reason]` - Signal completion (called by Claude)
- [x] `debussy resume` - Resume paused run
- [x] `debussy history` - List past runs
- [x] `debussy progress` - Log progress (for stuck detection)

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def run(master_plan: Path, phase: int | None = None, dry_run: bool = False):
    """Start orchestrating a master plan."""
    ...

@app.command()
def done(phase: str, status: str = "completed", reason: str | None = None):
    """Signal phase completion (called by Claude worker)."""
    ...

@app.command()
def status():
    """Show current orchestration status."""
    ...
```

#### 1.8 Compliance Checker (src/debussy/core/compliance.py)
- [x] Define `ComplianceIssue` and `ComplianceResult` models
- [x] File-based checks (notes exist, structure valid)
- [x] Agent invocation detection (parse session logs)
- [x] Gate re-verification (always re-run, don't trust claims)
- [x] Progress file monitoring (stuck detection)
- [x] Remediation strategy determination

```python
class ComplianceIssueType(str, Enum):
    NOTES_MISSING = "notes_missing"
    NOTES_INCOMPLETE = "notes_incomplete"
    GATES_FAILED = "gates_failed"
    AGENT_SKIPPED = "agent_skipped"
    STEP_SKIPPED = "step_skipped"

class ComplianceIssue(BaseModel):
    type: ComplianceIssueType
    severity: Literal["low", "high", "critical"]
    details: str
    evidence: str | None = None

class RemediationStrategy(str, Enum):
    WARN_AND_ACCEPT = "warn"       # Minor issues, log and continue
    TARGETED_FIX = "fix"           # Spawn remediation session
    FULL_RETRY = "retry"           # Fresh session, restart phase
    HUMAN_REQUIRED = "human"       # Pause for human decision

class ComplianceChecker:
    def __init__(self, gate_runner: GateRunner):
        self.gate_runner = gate_runner

    async def verify_completion(
        self,
        phase: Phase,
        session_log: str,
        completion_report: dict
    ) -> ComplianceResult:
        issues = []

        # 1. Re-run gates (NEVER trust Claude's claim)
        gate_results = await self.gate_runner.run_gates(phase)
        for gate in gate_results:
            if not gate.passed:
                issues.append(ComplianceIssue(
                    type=ComplianceIssueType.GATES_FAILED,
                    severity="critical",
                    details=f"Gate '{gate.name}' failed",
                    evidence=gate.output[:500]
                ))

        # 2. Check notes file exists and has required sections
        if phase.notes_output:
            notes_issues = self._check_notes(phase.notes_output)
            issues.extend(notes_issues)

        # 3. Check required agents were invoked
        agent_issues = self._check_agent_invocations(
            session_log,
            phase.required_agents,
            completion_report.get("agents_used", [])
        )
        issues.extend(agent_issues)

        # 4. Check required steps were completed
        step_issues = self._check_required_steps(
            phase.required_steps,
            completion_report.get("steps_completed", [])
        )
        issues.extend(step_issues)

        return ComplianceResult(
            passed=len(issues) == 0,
            issues=issues,
            remediation=self._determine_remediation(issues)
        )

    def _check_agent_invocations(
        self,
        session_log: str,
        required: list[str],
        claimed: list[str]
    ) -> list[ComplianceIssue]:
        issues = []
        for agent in required:
            # Check if Task tool was called with this agent
            pattern = rf'<invoke name="Task">.*?subagent_type.*?{agent}'
            found_in_log = bool(re.search(pattern, session_log, re.DOTALL))
            claimed_used = agent in claimed

            if not found_in_log and not claimed_used:
                issues.append(ComplianceIssue(
                    type=ComplianceIssueType.AGENT_SKIPPED,
                    severity="critical",
                    details=f"Required agent '{agent}' was not invoked"
                ))
            elif claimed_used and not found_in_log:
                issues.append(ComplianceIssue(
                    type=ComplianceIssueType.AGENT_SKIPPED,
                    severity="high",
                    details=f"Agent '{agent}' claimed but no evidence in logs"
                ))

        return issues

    def _determine_remediation(self, issues: list[ComplianceIssue]) -> RemediationStrategy:
        if not issues:
            return None

        critical_count = sum(1 for i in issues if i.severity == "critical")
        high_count = sum(1 for i in issues if i.severity == "high")

        if critical_count >= 2:
            return RemediationStrategy.FULL_RETRY
        elif critical_count == 1 or high_count >= 2:
            return RemediationStrategy.TARGETED_FIX
        else:
            return RemediationStrategy.WARN_AND_ACCEPT
```

#### 1.9 Debussy with Compliance Loop (src/debussy/core/debussy.py)
- [x] Load master plan
- [x] Sequential phase execution loop
- [x] Completion detection via `debussy done` command
- [x] **Compliance verification after completion**
- [x] **Remediation loop (fresh sessions with state injection)**
- [x] Retry logic (configurable, default 2)

```python
class Debussy:
    def __init__(self, master_plan: Path, config: Config):
        self.plan = PlanParser.parse_master(master_plan)
        self.state = StateManager(self._get_db_path())
        self.claude = ClaudeRunner(master_plan.parent, config.timeout)
        self.gates = GateRunner(master_plan.parent)
        self.checker = ComplianceChecker(self.gates)
        self.config = config

    async def run(self):
        run_id = self.state.create_run(self.plan)

        for phase in self.plan.phases:
            if not self._dependencies_met(phase):
                continue

            await self._execute_phase_with_compliance(run_id, phase)

    async def _execute_phase_with_compliance(self, run_id: str, phase: Phase):
        attempts = 0
        max_attempts = self.config.max_retries + 1
        is_remediation = False
        previous_issues: list[ComplianceIssue] = []

        while attempts < max_attempts:
            attempts += 1
            self.state.update_phase_status(run_id, phase.id, PhaseStatus.RUNNING)

            # Build prompt (normal or remediation)
            if is_remediation:
                prompt = self._build_remediation_prompt(phase, previous_issues)
            else:
                prompt = self._build_phase_prompt(phase)

            # Spawn Claude worker
            result = await self.claude.execute_phase(phase, prompt)

            if not result.success:
                self.state.update_phase_status(run_id, phase.id, PhaseStatus.FAILED)
                self.notify.error(f"Phase {phase.id} execution failed")
                return

            # Wait for completion signal
            signal = await self._wait_for_completion_signal(phase)

            # COMPLIANCE CHECK
            self.state.update_phase_status(run_id, phase.id, PhaseStatus.VALIDATING)
            compliance = await self.checker.verify_completion(
                phase,
                result.session_log,
                signal.report
            )

            if compliance.passed:
                self.state.update_phase_status(run_id, phase.id, PhaseStatus.COMPLETED)
                self.notify.success(f"Phase {phase.id} completed")
                return

            # Handle non-compliance
            previous_issues = compliance.issues

            match compliance.remediation:
                case RemediationStrategy.WARN_AND_ACCEPT:
                    self._log_warnings(compliance.issues)
                    self.state.update_phase_status(run_id, phase.id, PhaseStatus.COMPLETED)
                    return

                case RemediationStrategy.TARGETED_FIX | RemediationStrategy.FULL_RETRY:
                    is_remediation = True
                    self.notify.warn(
                        f"Phase {phase.id} compliance failed, attempt {attempts}/{max_attempts}"
                    )
                    # Loop continues with fresh session

                case RemediationStrategy.HUMAN_REQUIRED:
                    self.state.update_phase_status(run_id, phase.id, PhaseStatus.AWAITING_HUMAN)
                    self.notify.alert(f"Phase {phase.id} needs human intervention")
                    return

        # Max attempts reached
        self.state.update_phase_status(run_id, phase.id, PhaseStatus.FAILED)
        self.notify.error(f"Phase {phase.id} failed after {max_attempts} attempts")

    def _build_remediation_prompt(
        self,
        phase: Phase,
        issues: list[ComplianceIssue]
    ) -> str:
        return f"""
REMEDIATION SESSION for Phase {phase.id}: {phase.title}

The previous attempt FAILED compliance checks.

## Issues Found
{self._format_issues(issues)}

## What You Must Do Now
{self._format_required_actions(issues)}

## Original Phase Plan
Read and follow: {phase.path}

## When Complete
Run: debussy done --phase {phase.id} --report '{{...}}'

IMPORTANT: This is a remediation session. Follow the template EXACTLY.
All required agents MUST be invoked via the Task tool.
"""
```

---

### Phase 2: Polish & Notifications

**Goal:** Better UX, notifications, configuration

#### 2.1 Configuration (src/debussy/config.py)
- [x] Load from `.debussy/config.yaml` (v0.1.0)
- [x] Configurable: timeout, max_retries, model, output mode, notification settings (v0.1.1)
- [ ] Support user-level config (~/.debussy/config.yaml)

```toml
# .debussy/config.toml
[debussy]
timeout = 1800  # 30 minutes
max_retries = 2

[notifications]
enabled = true
provider = "desktop"  # or "ntfy"

[notifications.ntfy]
server = "https://ntfy.sh"
topic = "my-debussy"
```

#### 2.2 Desktop Notifications (src/debussy/notifications/desktop.py)
- [x] Cross-platform notifications via plyer (Windows, macOS, Linux)
- [x] CompositeNotifier for multiple providers (desktop + console)
- [x] Fallback to logging when notifications unavailable

#### 2.3 ntfy Integration (src/debussy/notifications/ntfy.py)
- [x] POST to ntfy server on events via httpx
- [x] Configurable server + topic
- [x] Priority levels mapped from notification levels (info=3, warning=4, error/alert=5)
- [x] Emoji tags for visual differentiation

#### 2.4 Rich Terminal Output
- [x] ASCII art banner at startup (v0.1.1)
- [x] Plan info display (name, model, phases, retries, output mode, timeout)
- [x] Phase table with status and dependencies (v0.1.1)
- [x] Colored status indicators (v0.1.1)
- [x] Run history display (v0.1.0)
- [ ] Progress bars for phase execution
- [ ] Live status table during execution

#### 2.5 Interactive Mode
- [ ] `--interactive` flag for manual approval between phases
- [ ] Prompt before risky phases
- [ ] Option to skip/retry phases

---

### Phase 3: Templates & Documentation

**Goal:** Portable templates, good docs

#### 3.1 Template System
- [ ] Create docs/templates/plans/ with master + phase templates
- [ ] Create docs/templates/notes/NOTES_TEMPLATE.md
- [ ] Template variables: `{feature}`, `{phase_num}`, `{date}`
- [ ] `debussy init <feature>` command to scaffold from templates

#### 3.2 Notes Template

```markdown
# Phase {N} Notes: {Title}

**Phase:** {phase_path}
**Completed:** {timestamp}
**Duration:** {duration}

---

## Summary
{Brief description of what was accomplished}

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| {decision} | {why} |

## Files Modified
| File | Change | Purpose |
|------|--------|---------|
| `{path}` | {Created/Modified/Deleted} | {why} |

## Test Results
- Tests run: {count}
- Tests passed: {passed}
- Coverage: {coverage}%

## Warnings for Next Phase
- {Any issues or considerations for the next phase}

## Blockers Encountered
- {None or list of blockers and how they were resolved}

## Gate Results
| Gate | Status | Notes |
|------|--------|-------|
| {gate} | {✅/❌} | {details} |
```

#### 3.3 Documentation
- [ ] README.md with quick start
- [ ] Usage examples
- [ ] Configuration reference

---

### Phase 4: Advanced Features (Future)

**Goal:** Parallel execution, better integration

#### 4.1 Parallel Phase Execution
- [ ] Dependency graph analysis
- [ ] Worker pool for independent phases
- [ ] Proper synchronization

#### 4.2 Human Approval Gates
- [ ] Flag risky phases in plan
- [ ] Pause and wait for explicit approval
- [ ] Approval via CLI or notification response

#### 4.3 LTM Integration
- [ ] Optional: store orchestration memories
- [ ] Cross-project learnings

---

## CLI Reference

```bash
# Start orchestration
debussy run path/to/master-plan.md

# Start from specific phase
debussy run path/to/master-plan.md --phase 2

# Dry run (parse and validate only)
debussy run path/to/master-plan.md --dry-run

# Select Claude model (haiku, sonnet, opus)
debussy run path/to/master-plan.md --model haiku

# Output mode: terminal (default), file, or both
debussy run path/to/master-plan.md --output both

# Combined example
debussy run path/to/master-plan.md --model haiku --output file --phase 2

# Interactive mode (confirm each phase) [NOT YET IMPLEMENTED]
debussy run path/to/master-plan.md --interactive

# Signal phase completion (called by Claude worker)
# Simple completion:
debussy done --phase 1

# With full compliance report (RECOMMENDED):
debussy done --phase 1 --report '{
  "steps_completed": ["read_notes", "doc_sync", "implementation", "validation", "write_notes"],
  "agents_used": ["doc-sync-manager", "task-validator"],
  "files_modified": ["src/foo.py", "tests/test_foo.py"],
  "notes_path": "notes/NOTES_feature_phase_1.md"
}'

# If blocked:
debussy done --phase 1 --status blocked --reason "Need legacy refactor first"

# Check status
debussy status
debussy status --run abc123

# Resume paused run (after human intervention)
debussy resume

# Initialize new feature from templates
debussy init my-feature --phases 3

# List past runs
debussy history

# Log progress during execution (optional, for stuck detection)
debussy progress --phase 1 --step "implementation:started"
debussy progress --phase 1 --step "task_validator:started"
```

## Completion Report Schema

The `--report` JSON enables compliance verification:

```json
{
  "steps_completed": [
    "read_previous_notes",
    "doc_sync_manager",
    "implementation",
    "pre_validation",
    "task_validator",
    "write_notes"
  ],
  "agents_used": [
    "doc-sync-manager",
    "task-validator"
  ],
  "files_modified": [
    "backend/services/foo.py",
    "backend/repositories/foo_repo.py",
    "tests/unit/test_foo.py"
  ],
  "gates_run": {
    "ruff": "passed",
    "pyright": "passed",
    "bandit": "passed",
    "tests": "passed"
  },
  "notes_path": "claude-docs/notes/NOTES_feature_phase_1.md",
  "warnings": [
    "Legacy auth code needs attention in phase 2"
  ]
}
```

The debussy will:
1. **Verify claimed steps** against progress log (if available)
2. **Verify agents_used** against session log (Task tool patterns)
3. **Re-run all gates** independently (never trust self-reported results)
4. **Check notes file** exists and has required sections
5. **Flag discrepancies** between claimed and verified

---

## Database Schema

```sql
-- Orchestration runs
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    master_plan_path TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- running, completed, failed, paused
    current_phase TEXT
);

-- Individual phase executions
CREATE TABLE phase_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES runs(id),
    phase_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    claude_pid INTEGER,
    log_path TEXT,
    error_message TEXT,
    UNIQUE(run_id, phase_id, attempt)
);

-- Gate results per execution
CREATE TABLE gate_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_execution_id INTEGER REFERENCES phase_executions(id),
    gate_name TEXT NOT NULL,
    command TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    output TEXT,
    executed_at TIMESTAMP NOT NULL
);

-- Completion signals from Claude workers
CREATE TABLE completion_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES runs(id),
    phase_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- completed, blocked, failed
    reason TEXT,
    signaled_at TIMESTAMP NOT NULL
);
```

---

## Testing Strategy

### Unit Tests
- Parser tests with fixture markdown files
- State manager tests with in-memory SQLite
- Model validation tests

### Integration Tests
- Full orchestration with mock Claude runner
- Gate execution with real commands
- Notification delivery (mocked)

### Fixtures
- `tests/fixtures/sample_master.md` - Valid master plan
- `tests/fixtures/sample_phase.md` - Valid phase file
- `tests/fixtures/invalid_*.md` - Edge cases

---

## Success Criteria

### MVP (Phase 1) - ✅ COMPLETE (v0.1.0)
- [x] Can parse Grain_API assessment-service-refactor plans
- [x] Spawns Claude CLI for each phase
- [x] Detects completion via `debussy done`
- [x] Runs validation gates
- [x] **Compliance checker verifies template adherence**
- [x] **Detects skipped agents via session log parsing**
- [x] **Remediation loop spawns fresh sessions with state injection**
- [x] Tracks state in SQLite
- [x] Basic CLI works (`run`, `done`, `status`, `progress`)

### V1 (Phase 1+2) - In Progress
- [ ] Notifications working (desktop + ntfy)
- [x] Configuration system (YAML) (v0.1.0)
- [ ] Interactive mode
- [x] Rich terminal output (banner, phase table) (v0.1.1)
- [x] Configurable retry/timeout (v0.1.0)
- [x] Configurable model selection (v0.1.1)
- [x] Configurable output mode (terminal/file/both) (v0.1.1)

### V2 (Phase 1+2+3)
- [ ] Template system with `debussy init`
- [ ] Full documentation
- [ ] Notes template standardized
- [ ] Tested on Grain_API assessment-service-refactor

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Claude CLI API changes | Low | Pin claude version, abstract runner |
| Markdown parsing fragile | Medium | Strict format requirements, good tests |
| Timeout too aggressive | Medium | Configurable, notify on timeout |
| State corruption | Low | SQLite transactions, backups |

---

## Next Steps

1. ~~**Implement Phase 1** - Foundation~~ ✅ Complete (v0.1.0)
2. **Test on Grain_API** - Use assessment-service-refactor as guinea pig
3. **Add Notifications** - Desktop toast and ntfy integration
4. **Interactive Mode** - Manual approval between phases
5. **Templates** - `debussy init` command to scaffold from templates

---

## Dependencies Summary

```toml
[project]
dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "aiosqlite>=0.19",  # Async SQLite
    "plyer>=2.1",       # Cross-platform notifications
    "httpx>=0.27",      # For ntfy (async HTTP)
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ltm",
]
```
