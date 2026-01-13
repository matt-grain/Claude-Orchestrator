# Investigation & Future Work

This document tracks investigations and planned features for Debussy.

---

## 1. Subagent Log Capture

**Status:** Investigation needed

**Problem:** When a subagent (e.g., `file-existence-checker`, `Explore`) runs via the Task tool, only its tool calls appear in the logs. The subagent's reasoning text is not captured.

**Current behavior:**
```
[Debussy] Now I'll use the file-existence-checker agent...
(Task: Verify files created)
[Bash: test -f "C:\Users\...\AppData\Local\Temp\t...]  <-- subagent's tool
[Debussy] Excellent! Now let me...
```

**Expected behavior:**
```
[Debussy] Now I'll use the file-existence-checker agent...
(Task: Verify files created)
[file-existence-checker] Checking file existence for required files...
[Bash: test -f "..."]
[file-existence-checker] Both files exist. Verdict: APPROVED ✅
[Debussy] Excellent! Now let me...
```

### Investigation Tasks

- [ ] Capture raw stream-json output when Task tool is invoked
- [ ] Document how subagent output appears in the JSON stream
- [ ] Check if subagent text appears in `tool_result` content
- [ ] Update [CLAUDE_JSON_FORMAT.md](CLAUDE_JSON_FORMAT.md) with Task tool event structure

### Hypothesis

The subagent's output might be embedded in the `tool_result` event when the Task completes:
```json
{
  "type": "user",
  "message": {
    "content": [{
      "type": "tool_result",
      "tool_use_id": "task_xxx",
      "content": "Full subagent output including reasoning..."
    }]
  }
}
```

If so, we could parse and display this content with the agent prefix.

### Implementation Plan (if hypothesis confirmed)

1. In `_display_tool_result()`, check if `tool_use_id` is in `_pending_task_ids`
2. If yes, display the `content` with the subagent's name prefix
3. Then reset to Debussy

---

## 2. Resume & Skip Completed Phases

**Status:** ✅ IMPLEMENTED (2026-01-13)

Debussy now detects previous incomplete runs and offers to resume, skipping completed phases.

### New CLI Flags

```bash
debussy run plan.md --resume    # Auto-skip completed phases
debussy run plan.md --restart   # Force fresh start, ignore history
debussy run plan.md             # Interactive: shows TUI dialog if previous run found
```

### Behavior

| Scenario | Behavior |
|----------|----------|
| Fresh plan (no history) | Normal start |
| Previous incomplete run + `--resume` | Auto-skip completed phases |
| Previous incomplete run + interactive | Shows TUI dialog: "Resume Previous Run?" |
| Previous incomplete run + `--restart` | Ignores history, starts fresh |

### TUI Resume Dialog

When an incomplete run is detected in interactive mode, a modal dialog appears:

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

### Implementation Details

**New StateManager methods:**
- `find_resumable_run(plan_path)` - Finds incomplete runs (paused/failed/running) for same plan
- `get_completed_phases(run_id)` - Returns set of phase IDs with status='completed'

**New Orchestrator parameter:**
- `skip_phases: set[str]` - Phase IDs to skip (marked as completed for dependency checks)

**New TUI components:**
- `ResumeConfirmScreen` - Modal dialog for resume confirmation
- `_handle_resume_confirmation()` - Callback that sets skip_phases based on user choice

**Files modified:**
- [src/debussy/core/state.py](../src/debussy/core/state.py) - New query methods
- [src/debussy/cli.py](../src/debussy/cli.py) - New flags, `_get_resumable_run_info()` helper
- [src/debussy/core/orchestrator.py](../src/debussy/core/orchestrator.py) - Skip logic in `run()`
- [src/debussy/ui/tui.py](../src/debussy/ui/tui.py) - ResumeConfirmScreen, dialog handling

**Tests:** 12 new tests in `tests/test_state.py` (TestResumeAndSkip class)

---

## 3. Memory for Orchestrated Agents

**Status:** Design needed

**Problem:** The Claude sessions spawned by Debussy are ephemeral - they have no memory of:
- Previous runs of the same phase
- Mistakes they made and corrections
- Project-specific learnings

This means the same errors can repeat across runs, and learnings are lost.

### Current Architecture

```
┌─────────────────┐
│  Debussy CLI    │  <- Has LTM (Anima's memories loaded)
│  (Python)       │
└────────┬────────┘
         │ spawns
         ▼
┌─────────────────┐
│  Claude CLI     │  <- NO LTM, ephemeral, stateless
│  (Worker)       │
└─────────────────┘
```

### Design Questions

1. **Who should remember?**
   - Option A: Debussy (Python) aggregates learnings and saves via LTM API
   - Option B: Spawned Claude sessions have LTM hooks installed
   - Option C: Hybrid - workers report learnings, Debussy saves them

2. **What should be remembered?**
   - Errors encountered and how they were fixed
   - Project-specific patterns discovered
   - Phase-specific learnings (e.g., "tests require --no-cache flag")
   - Gate failures and resolutions

3. **Memory scope?**
   - Per-project memories (stored in project region)
   - Per-phase memories (tagged with phase ID)
   - Global orchestration learnings (agent region)

### Proposed Architecture: Option C (Hybrid)

```
┌─────────────────────────────────────────────────────┐
│  Debussy Orchestrator                               │
│  ┌───────────────┐    ┌──────────────────────────┐ │
│  │ Memory        │    │ Claude Worker Session    │ │
│  │ Aggregator    │◄───│ (reports learnings via   │ │
│  │               │    │  structured output)      │ │
│  └───────┬───────┘    └──────────────────────────┘ │
│          │                                          │
│          ▼                                          │
│  ┌───────────────┐                                  │
│  │ LTM Storage   │                                  │
│  │ (project      │                                  │
│  │  memories)    │                                  │
│  └───────────────┘                                  │
└─────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 1: Structured learning reports from workers
- [ ] Add `## Learnings` section to phase completion output
- [ ] Parse learnings from worker output after phase completes
- [ ] Store learnings in a `learnings` table in state.db

#### Phase 2: Inject learnings into future sessions
- [ ] When starting a phase, query previous learnings for that phase
- [ ] Inject relevant learnings into the phase prompt
- [ ] Format: "Previous learnings for this phase: ..."

#### Phase 3: LTM integration (optional)
- [ ] Add `--remember` flag to save learnings to LTM
- [ ] Create Debussy-specific memory kinds (PHASE_LEARNING, GATE_FIX, etc.)
- [ ] Use LTM API to store/retrieve across projects

### Example: Learning Injection

```markdown
## Previous Learnings for Phase 1: Setup

- [2026-01-10] Gate `ruff check` failed due to missing __init__.py - always create package structure first
- [2026-01-12] Tests require `--no-cache` flag on Windows to avoid permission errors
- [2026-01-13] file-existence-checker agent expects absolute paths, not relative
```

---

## Priority Order

1. ~~**Resume & Skip**~~ - ✅ DONE
2. **Subagent Logs** - Better visibility, helps debugging
3. **Memory System** - Longer-term improvement, requires design decisions

---

## Related Files

- [src/debussy/runners/claude.py](../src/debussy/runners/claude.py) - Stream parsing, agent tracking
- [src/debussy/core/state.py](../src/debussy/core/state.py) - State management, run tracking
- [src/debussy/cli.py](../src/debussy/cli.py) - CLI commands, run/resume logic
- [CLAUDE_JSON_FORMAT.md](CLAUDE_JSON_FORMAT.md) - Stream JSON documentation
