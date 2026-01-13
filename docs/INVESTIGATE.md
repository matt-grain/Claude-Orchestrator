# Investigation & Future Work

This document tracks investigations and planned features for Debussy.

---

## 1. Subagent Log Capture

**Status:** ✅ IMPLEMENTED (2026-01-13)

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

- [x] Capture raw stream-json output when Task tool is invoked
- [x] Document how subagent output appears in the JSON stream
- [x] Check if subagent text appears in `tool_result` content
- [x] Update [CLAUDE_JSON_FORMAT.md](CLAUDE_JSON_FORMAT.md) with Task tool event structure

### Investigation Findings (2026-01-13)

**HYPOTHESIS CONFIRMED!** ✅

The Task tool result has a **distinct structure** that differs from regular tool results:

#### Task Tool Use (in `assistant` event):
```json
{
  "type": "assistant",
  "message": {
    "content": [{
      "type": "tool_use",
      "id": "toolu_01EMBD2Ez8pt8LWj5ovow1mU",
      "name": "Task",
      "input": {
        "subagent_type": "Explore",
        "description": "Find Python files in current directory",
        "prompt": "Find all Python files (.py)..."
      }
    }]
  }
}
```

#### Task Tool Result (in `user` event):
```json
{
  "type": "user",
  "message": {
    "content": [{
      "type": "tool_result",
      "tool_use_id": "toolu_01EMBD2Ez8pt8LWj5ovow1mU",
      "content": [
        {
          "type": "text",
          "text": "Perfect! I now have a comprehensive understanding..."
        },
        {
          "type": "text",
          "text": "agentId: ae27ebb (for resuming to continue this agent's work if needed)"
        }
      ]
    }]
  }
}
```

**Key Differences from Regular Tool Results:**
1. **Regular tools**: `content` is a **string** (e.g., file contents, bash output)
2. **Task tool**: `content` is a **list** of `{type: "text", text: "..."}` objects

**Content Structure:**
- **Item 0**: Full subagent reasoning/output text (can be thousands of chars)
- **Item 1**: Metadata including `agentId` for resumption

### Implementation Plan

1. **Track Task tool_use_ids**: In `_display_stream_event()`, when we see a `tool_use` with `name="Task"`, store:
   - `tool_use_id` → `subagent_type` mapping in `_pending_task_ids: dict[str, str]`

2. **Detect Task results**: In `_display_tool_result()`:
   ```python
   if tool_use_id in self._pending_task_ids:
       # Content is list format - extract subagent output
       if isinstance(content, list):
           agent_name = self._pending_task_ids[tool_use_id]
           for item in content:
               if item.get("type") == "text":
                   text = item.get("text", "")
                   # Display with agent prefix
                   self._display_subagent_output(agent_name, text)
           del self._pending_task_ids[tool_use_id]
   ```

3. **Display subagent output**: Parse the text for meaningful lines and display with `[AgentName]` prefix

4. **Reset to Debussy**: After processing Task result, reset `current_agent` to "Debussy"

**Files to modify:**
- [src/debussy/runners/claude.py](../src/debussy/runners/claude.py):269 - `_display_stream_event()` and `_display_tool_result()`

**Test prototype:** `scripts/investigate_task_output.py` - captures raw JSON stream for analysis

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

**Status:** ✅ IMPLEMENTED (2026-01-13)

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

### Implementation (Option C - Hybrid with LTM)

The implementation uses Claude-LTM directly via `/remember` and `/recall` commands - no duplicate storage needed!

**New CLI flag:**
```bash
debussy run plan.md --learnings    # Enable LTM learnings
debussy run plan.md -L             # Short form
```

**Prompt changes:**
- Phase prompts include instructions to output `## Learnings` section
- Workers call `/remember` with phase/agent tags: `--tags phase:1,agent:Explore`
- Prompts include `/recall phase:<id>` for retrieving previous learnings
- Remediation prompts recall and save with `--priority HIGH`

**Files modified:**
- [src/debussy/config.py](../src/debussy/config.py) - Added `learnings: bool` field
- [src/debussy/cli.py](../src/debussy/cli.py) - Added `--learnings/-L` flag
- [src/debussy/runners/claude.py](../src/debussy/runners/claude.py) - Updated `_build_phase_prompt()` and `build_remediation_prompt()` with LTM instructions
- [src/debussy/core/orchestrator.py](../src/debussy/core/orchestrator.py) - Pass `with_ltm` to ClaudeRunner

**Tests:** 5 new tests in `tests/test_runners.py` (TestClaudeRunnerPrompts class)

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
2. ~~**Subagent Logs**~~ - ✅ DONE
3. ~~**Memory System**~~ - ✅ DONE (via LTM integration)

**All features on this list are now implemented!** 🎉

---

## Related Files

- [src/debussy/runners/claude.py](../src/debussy/runners/claude.py) - Stream parsing, agent tracking
- [src/debussy/core/state.py](../src/debussy/core/state.py) - State management, run tracking
- [src/debussy/cli.py](../src/debussy/cli.py) - CLI commands, run/resume logic
- [CLAUDE_JSON_FORMAT.md](CLAUDE_JSON_FORMAT.md) - Stream JSON documentation
