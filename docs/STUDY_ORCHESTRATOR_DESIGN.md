# Claude Debussy Design Study

**Created:** 2026-01-12
**Author:** Anima + Matt
**Status:** Draft - Awaiting Feedback

---

## Executive Summary

Build a Python-based debussy to automate multi-phase implementation workflows with Claude Code CLI. The system should manage phase execution, validation gates, state persistence, and inter-phase context transfer.

**Inspiration:** Ralph Wiggum (Claude plugin) - a while-true loop pattern where each iteration sees previous work results, continuing until completion.

---

## Current Workflow Analysis

### What We Have

```
Master Plan (assessment-service-refactor-master.md)
    │
    ├── Phase 1: Unit of Work Pattern
    │   ├── Process Wrapper (mandatory steps)
    │   ├── Tasks (checkboxes)
    │   ├── Gates (validation criteria)
    │   └── Notes output → NOTES_*_phase_1.md
    │
    ├── Phase 2: State Model (depends on Phase 1)
    │   └── Reads NOTES_*_phase_1.md
    │
    └── Phase N...
```

### Key Patterns Identified

1. **Process Wrapper** - Consistent pre/post implementation steps
2. **Gates** - Validation commands that must all pass
3. **Notes Chain** - Each phase reads previous phase's notes
4. **Status Tracking** - In master plan table + individual phase files
5. **Dependencies** - Some phases can run in parallel, some are sequential

### Current Manual Flow

1. Human picks next phase from master plan
2. Opens Claude CLI with phase document as context
3. Claude implements tasks
4. Human/Claude runs validation loop
5. Human updates status in plans
6. Repeat for next phase

---

## Problem Statement

**Goal:** Automate the loop while preserving:
- Human oversight for critical decisions
- Ability to pause/resume
- Clear audit trail
- Recovery from failures

**Non-Goals:**
- Full autonomy (we want guardrails)
- Replacing the plan templates

---

## Architecture Options

### Option A: Simple Loop Runner (Minimal)

```
┌─────────────────────────────────────────────┐
│           debussy.py                   │
│                                             │
│  while phases_remaining:                    │
│      phase = get_next_phase()               │
│      spawn_claude(phase.path)               │
│      wait_for_completion_marker()           │
│      run_gates(phase.gates)                 │
│      if gates_pass:                         │
│          update_status(phase, "completed")  │
│      else:                                  │
│          retry_or_pause()                   │
└─────────────────────────────────────────────┘
```

**State:** Single JSON file tracking phase status

**Pros:**
- Simple to implement (~200 LOC)
- Easy to debug
- Familiar pattern

**Cons:**
- No parallelism
- Manual intervention for any deviation
- Limited error recovery

**Implementation Effort:** Low (1 session)

---

### Option B: State Machine with Human Gates

```
                    ┌───────────┐
                    │  PENDING  │
                    └─────┬─────┘
                          │ start
                    ┌─────▼─────┐
              ┌─────│ PLANNING  │─────┐
              │     └───────────┘     │
              │ auto                  │ needs_review
        ┌─────▼─────┐          ┌──────▼──────┐
        │IMPLEMENTING│          │AWAITING_HUMAN│
        └─────┬─────┘          └──────┬──────┘
              │ complete              │ approved
              └──────────┬────────────┘
                   ┌─────▼─────┐
                   │ VALIDATING │
                   └─────┬─────┘
                         │
              ┌──────────┼──────────┐
              │ pass     │ fail     │ critical_fail
        ┌─────▼───┐ ┌────▼────┐ ┌───▼───┐
        │COMPLETED│ │ FIXING  │ │BLOCKED│
        └─────────┘ └────┬────┘ └───────┘
                         │
                         └──► VALIDATING (loop)
```

**State:** SQLite database with full history

**Components:**
```python
class Phase(BaseModel):
    id: str
    status: PhaseStatus
    attempts: int
    last_error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class Debussy:
    def __init__(self, master_plan: Path):
        self.state_db = StateDB(master_plan.stem + ".db")
        self.phases = self.parse_master_plan(master_plan)

    async def run(self):
        while phase := self.get_next_runnable_phase():
            await self.execute_phase(phase)
```

**Pros:**
- Human checkpoints for risky phases
- Full audit trail
- Resumable after crashes
- State visible in DB

**Cons:**
- More complex
- Overhead for simple features

**Implementation Effort:** Medium (2-3 sessions)

---

### Option C: Agent Swarm (Parallel Phases)

```
┌────────────────────────────────────────────────────┐
│                  Coordinator                        │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │   ...   │
│  │ Phase 1  │  │ Phase 2* │  │ Phase 3  │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │                │
│       ▼             ▼             ▼                │
│  [Validation]  [Blocked on 1] [Independent]        │
└────────────────────────────────────────────────────┘

* Phase 2 waits for Phase 1's completion signal
```

**Components:**
- **Coordinator:** Manages worker pool, dependency graph
- **Worker:** Runs single phase in isolated Claude session
- **Message Bus:** Redis/file-based pub/sub for signals
- **Shared State:** PostgreSQL or SQLite with WAL

**Pros:**
- Maximum throughput for independent phases
- Scales to large refactors
- Real-time progress visibility

**Cons:**
- Complexity (race conditions, coordination)
- Resource hungry (multiple Claude sessions)
- Overkill for 4-phase features

**Implementation Effort:** High (1+ week)

---

### Option D: Hybrid (Recommended)

**Core:** Option B's state machine
**Extension:** Optional parallel workers when phases allow

```python
class Debussy:
    def __init__(self, master_plan: Path, max_workers: int = 1):
        self.max_workers = max_workers  # Default: sequential
        ...

    async def run(self):
        if self.max_workers == 1:
            await self._run_sequential()
        else:
            await self._run_parallel()
```

Start simple, add parallelism later.

---

## Key Design Decisions

### 1. Claude CLI Invocation

**Question:** How to spawn and communicate with Claude CLI?

**Option 1A: Subprocess with prompt file**
```python
subprocess.run([
    "claude",
    "--print",  # Non-interactive
    "-p", f"Execute phase plan: {phase_path}"
], capture_output=True)
```

**Option 1B: Claude CLI's `--continue` for session persistence**
```python
# First call creates session
result = subprocess.run(["claude", "-p", prompt, "--output-file", session_file])
# Later calls continue
subprocess.run(["claude", "--continue", session_file, "-p", "Continue..."])
```

**Option 1C: MCP Server as coordination layer**
- Debussy runs as MCP server
- Claude connects and receives instructions
- Bidirectional communication

**Recommendation:** Start with 1A, evolve to 1B if context needs persist.

---

### 2. Completion Detection

**Question:** How does debussy know a phase is done?

**Option 2A: Marker file**
```python
# Claude writes at end of phase:
# Path(f"notes/.phase_{n}_complete").touch()

while not marker_file.exists():
    time.sleep(10)
```

**Option 2B: Parse Claude output for signal**
```
[PHASE COMPLETE] assessment-service-refactor-phase1
```

**Option 2C: Poll plan file for status change**
```python
# Claude updates the plan:
# **Status:** Pending → **Status:** Complete
```

**Option 2D: Explicit handoff command**
- Debussy provides a `/handoff` or `/phase-complete` command
- Claude invokes when done

**Recommendation:** 2C (parse plan file) + 2D (explicit command) as backup.

---

### 3. Validation Gate Execution

**Question:** Who runs the validation gates?

**Option 3A: Debussy runs gates externally**
```python
def run_gates(phase: Phase) -> GateResult:
    for cmd in phase.gate_commands:
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            return GateResult.FAILED
    return GateResult.PASSED
```

**Option 3B: Claude runs gates, debussy verifies**
- Claude runs validation as part of process wrapper
- Debussy re-runs to verify (trust but verify)

**Option 3C: Claude runs gates, reports results**
- Debussy trusts Claude's self-reported results
- Only re-runs on failure for debugging

**Recommendation:** 3B - Claude runs first (can fix issues), debussy verifies.

---

### 4. State Persistence

**Question:** Where to store orchestration state?

| Option | Pros | Cons |
|--------|------|------|
| JSON file | Simple, readable | No concurrency, corruption risk |
| SQLite | Robust, queryable | Slightly more complex |
| In plan files | Self-documenting | Parsing complexity |
| Redis | Fast, pub/sub | External dependency |

**Recommendation:** SQLite for orchestration state + plan files for human-readable status.

---

### 5. Context Transfer Between Phases

**Question:** How to pass learnings from phase N to phase N+1?

**Current:** Notes files (`NOTES_*_phase_N.md`)

**Enhancement Options:**
- Structured JSON summary in addition to prose
- Key decisions extracted automatically
- Dependency tree of files modified

```python
class PhaseContext:
    notes_path: Path
    files_modified: List[Path]
    key_decisions: List[str]
    warnings_for_next_phase: List[str]
```

---

## Proposed Architecture (Option D)

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│  debussy run master.md [--parallel] [--phase N] [--dry-run] │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Debussy                              │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ PlanParser  │  │ StateManager│  │ PhaseExecutor           │  │
│  │             │  │ (SQLite)    │  │                         │  │
│  │ - master    │  │             │  │  ┌───────────────────┐  │  │
│  │ - phases    │  │ - status    │  │  │ ClaudeRunner      │  │  │
│  │ - deps      │  │ - attempts  │  │  │ - spawn session   │  │  │
│  │ - gates     │  │ - history   │  │  │ - monitor output  │  │  │
│  └─────────────┘  └─────────────┘  │  │ - detect complete │  │  │
│                                     │  └───────────────────┘  │  │
│                                     │                         │  │
│                                     │  ┌───────────────────┐  │  │
│                                     │  │ GateRunner        │  │  │
│                                     │  │ - run validations │  │  │
│                                     │  │ - parse results   │  │  │
│                                     │  │ - report status   │  │  │
│                                     │  └───────────────────┘  │  │
│                                     └─────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ EventBus                                                     │ │
│  │ - phase_started, phase_completed, gate_failed, human_needed │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Outputs                                   │
│                                                                  │
│  📁 .debussy/                                               │
│     ├── state.db              # SQLite state                     │
│     ├── runs/                 # Run logs                         │
│     │   └── 2026-01-12_143022/                                  │
│     │       ├── phase1.log                                       │
│     │       ├── phase1_gates.json                               │
│     │       └── phase2.log                                       │
│     └── config.toml           # Debussy settings            │
│                                                                  │
│  📁 claude-docs/plans/        # Updated by debussy          │
│     ├── master.md             # Status column updated            │
│     └── phase*.md             # Status field updated             │
│                                                                  │
│  📁 claude-docs/notes/        # Written by Claude                │
│     └── NOTES_*_phase_*.md                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### PlanParser

Parses master plan and phase files to extract:
- Phase list with dependencies
- Gate commands
- Status fields
- Task checkboxes

```python
@dataclass
class ParsedPhase:
    id: str
    title: str
    path: Path
    status: str  # Pending, In Progress, Complete, Blocked
    depends_on: List[str]
    gates: List[GateCommand]
    tasks: List[Task]
    notes_input: Optional[Path]  # Previous phase notes to read
    notes_output: Path  # Notes this phase should write
```

### StateManager

SQLite-backed state with these tables:

```sql
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    master_plan TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT  -- running, completed, failed, paused
);

CREATE TABLE phase_executions (
    id INTEGER PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    phase_id TEXT,
    attempt INTEGER,
    status TEXT,  -- pending, running, validating, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    claude_session_id TEXT,
    error_message TEXT
);

CREATE TABLE gate_results (
    id INTEGER PRIMARY KEY,
    phase_execution_id INTEGER REFERENCES phase_executions(id),
    gate_name TEXT,
    command TEXT,
    passed BOOLEAN,
    output TEXT,
    executed_at TIMESTAMP
);
```

### ClaudeRunner

Spawns and monitors Claude CLI sessions:

```python
class ClaudeRunner:
    async def execute_phase(self, phase: ParsedPhase) -> ExecutionResult:
        prompt = self._build_prompt(phase)

        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "-p", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_root
        )

        stdout, stderr = await process.communicate()

        return ExecutionResult(
            success=process.returncode == 0,
            output=stdout.decode(),
            errors=stderr.decode()
        )

    def _build_prompt(self, phase: ParsedPhase) -> str:
        return f"""
        Execute the implementation phase defined in: {phase.path}

        Context from previous phase: {phase.notes_input or 'N/A'}

        Requirements:
        1. Follow the Process Wrapper exactly
        2. Complete all tasks in the Tasks section
        3. Run pre-validation commands
        4. Write notes to: {phase.notes_output}
        5. Update the Status field to 'Complete' when done

        Signal completion by updating the phase file status.
        """
```

### GateRunner

Executes validation commands:

```python
class GateRunner:
    async def run_gates(self, phase: ParsedPhase) -> List[GateResult]:
        results = []

        for gate in phase.gates:
            result = await self._run_single_gate(gate)
            results.append(result)

            if not result.passed and gate.blocking:
                break  # Stop on first blocking failure

        return results

    async def _run_single_gate(self, gate: GateCommand) -> GateResult:
        process = await asyncio.create_subprocess_shell(
            gate.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_root
        )

        stdout, stderr = await process.communicate()

        return GateResult(
            name=gate.name,
            command=gate.command,
            passed=process.returncode == 0,
            output=stdout.decode() + stderr.decode()
        )
```

---

## CLI Interface

```bash
# Run all phases sequentially
debussy run plans/feature-master.md

# Run specific phase only
debussy run plans/feature-master.md --phase 2

# Dry run (parse and validate only)
debussy run plans/feature-master.md --dry-run

# Run with parallel workers (for independent phases)
debussy run plans/feature-master.md --parallel --workers 3

# Resume after pause/failure
debussy resume

# Show status
debussy status

# Interactive mode (confirm before each phase)
debussy run plans/feature-master.md --interactive
```

---

## Open Questions

### Q1: Human Approval Gates

Should certain phases require human approval before starting?

```yaml
# In phase file metadata?
requires_human_approval: true
approval_reason: "High-risk database migration"
```

### Q2: Retry Strategy

How many times to retry failed validations before pausing for human?

```python
max_gate_retries: int = 3
retry_backoff: Literal["none", "linear", "exponential"] = "linear"
```

### Q3: Notification Integration

Should the debussy notify humans?

- Slack webhook on completion/failure?
- Desktop notification?
- Email?

### Q4: Claude Model Selection

Should different phases use different models?

```yaml
# Phase complexity might warrant different models
phase1:  # Simple
  model: claude-sonnet
phase3:  # Complex architecture
  model: claude-opus
```

### Q5: Resource Limits

Should we limit concurrent Claude sessions? Cost considerations?

### Q6: Integration with Existing Agents

How does this interact with the existing agent system (task-validator, doc-sync-manager, etc.)?

- Debussy invokes agents?
- Agents are used within Claude session?
- Separate orchestration layer?

---

## Implementation Roadmap

### MVP (Session 1)
- [ ] PlanParser for master + phase files
- [ ] Simple sequential runner
- [ ] Basic state tracking (JSON)
- [ ] Gate execution
- [ ] CLI with `run` and `status` commands

### V1 (Session 2-3)
- [ ] SQLite state management
- [ ] Proper state machine
- [ ] Retry logic with backoff
- [ ] Run history and logs
- [ ] `--interactive` mode

### V2 (Future)
- [ ] Parallel phase execution
- [ ] Notification integrations
- [ ] Web dashboard?
- [ ] Integration with LTM for cross-session context?

---

## Alternatives Considered

### Why Not Shell Script (like Ralph Wiggum)?

- Python gives us:
  - Proper state management
  - Async for parallelism later
  - Rich parsing libraries
  - Better error handling
  - Testability

### Why Not Extend Claude Code Directly?

- Separation of concerns
- Can debussy non-Claude tools too
- Independent evolution

### Why Not Use Existing Workflow Tools (Temporal, Airflow)?

- Overkill for this use case
- Heavy dependencies
- Learning curve

---

## Next Steps

1. **Matt's Input:** Review this study, answer open questions
2. **Prototype:** Build MVP to validate assumptions
3. **Test:** Run on assessment-service-refactor as guinea pig
4. **Iterate:** Add features based on real usage

---

## References

- [Ralph Wiggum DeepWiki](https://deepwiki.com/anthropics/claude-plugins-official/5.1.4-ralph-wiggum)
- [Claude Code CLI Documentation](https://docs.anthropic.com/claude-code)
- [Grain_API Plan Templates](../../../Grain_API/claude-docs/plans/)
