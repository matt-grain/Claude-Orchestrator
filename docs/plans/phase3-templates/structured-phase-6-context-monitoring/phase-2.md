# Context Monitoring Phase 2: Progress Checkpoints

**Status:** Pending
**Master Plan:** [context-monitoring-MASTER_PLAN.md](context-monitoring-MASTER_PLAN.md)
**Depends On:** [Phase 1: Context Estimation](context-monitoring-phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase3_templates_phase_6A.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality - run from project root
  uv run ruff format . && uv run ruff check --fix .

  # Type checking
  uv run pyright src/debussy/

  # Tests - ALL tests must pass, not just new ones
  uv run pytest tests/ -x -v
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass with 0 errors
- [ ] Write `notes/NOTES_phase3_templates_phase_6B.md` with:
  - Summary of checkpoint implementation
  - Progress capture mechanisms
  - Git integration approach
  - Restart context format examples
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 6B`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~60%)

---

## Overview

Capture progress during phase execution so restarts can continue from where they left off. Implements checkpoint management that tracks progress entries from /debussy-progress skill calls, captures git state (modified files, diffs), and formats readable restart context. This ensures that when a phase restarts due to context limits, Claude can see exactly what was already accomplished and avoid redoing work.

## Dependencies
- Previous phase: [Phase 1: Context Estimation](context-monitoring-phase-1.md) - Works best with context monitoring but can function independently
- Internal: Uses existing StateManager patterns, integrates with progress skill
- External: Git for capturing file state

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Progress not captured | Medium | Medium | Git diff as fallback, warn if no /debussy-progress calls |
| Git state capture fails | Low | Low | Graceful degradation, log warning but continue |
| Restart context too verbose | Low | Medium | Limit to 20 files, summarize progress entries |
| No progress skill calls | Medium | Low | Git diff still provides context, add recommendation in docs |

---

## Tasks

### 1. Create Checkpoint Data Models
- [ ] 1.1: Create `src/debussy/core/checkpoint.py`
- [ ] 1.2: Implement ProgressEntry dataclass (timestamp, message, phase_id)
- [ ] 1.3: Implement PhaseCheckpoint dataclass (phase_id, phase_name, start_commit, progress_entries, modified_files, restart_count)
- [ ] 1.4: Implement PhaseCheckpoint.add_progress() method to append progress entries
- [ ] 1.5: Implement PhaseCheckpoint.capture_git_state() method using git diff --name-only
- [ ] 1.6: Implement PhaseCheckpoint.format_restart_context() method with structured output
- [ ] 1.7: Add proper error handling for git command failures

### 2. Implement Checkpoint Manager
- [ ] 2.1: Create CheckpointManager class with project_root initialization
- [ ] 2.2: Implement start_phase() method to initialize checkpoint and capture start commit
- [ ] 2.3: Implement get_current() method to retrieve active checkpoint
- [ ] 2.4: Implement record_progress() method to add progress entries
- [ ] 2.5: Implement prepare_restart() method that captures git state and formats context
- [ ] 2.6: Implement _get_head_commit() helper using git rev-parse HEAD
- [ ] 2.7: Add logging for checkpoint lifecycle events

### 3. Hook Progress Skill to Checkpoint Manager
- [ ] 3.1: Update orchestrator initialization to create CheckpointManager instance
- [ ] 3.2: Parse stream events for Skill tool invocations with skill="debussy-progress"
- [ ] 3.3: Extract progress message from skill call arguments
- [ ] 3.4: Call checkpoint_manager.record_progress() when progress skill detected
- [ ] 3.5: Add logging to show progress entries being captured

### 4. Write Unit Tests
- [ ] 4.1: Create `tests/test_checkpoint.py`
- [ ] 4.2: Test ProgressEntry dataclass creation and fields
- [ ] 4.3: Test PhaseCheckpoint.add_progress() adds entries correctly
- [ ] 4.4: Test PhaseCheckpoint.format_restart_context() produces readable output
- [ ] 4.5: Test restart context includes progress entries with checkmarks
- [ ] 4.6: Test restart context includes modified files (limited to 20)
- [ ] 4.7: Test restart context includes restart count
- [ ] 4.8: Test CheckpointManager.start_phase() captures git HEAD
- [ ] 4.9: Test CheckpointManager.record_progress() appends to current checkpoint
- [ ] 4.10: Test CheckpointManager.prepare_restart() captures git diff
- [ ] 4.11: Test graceful handling when git commands fail
- [ ] 4.12: Test checkpoint with no progress entries (git diff only)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/core/checkpoint.py` | Create | Checkpoint data models and manager |
| `src/debussy/orchestrator.py` | Modify | Add checkpoint_manager initialization and progress skill parsing |
| `tests/test_checkpoint.py` | Create | Unit tests for checkpoint functionality (12+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass models | `src/debussy/core/models.py` | Use @dataclass with field() for defaults |
| Subprocess calls | `src/debussy/core/compliance.py` | Safe git command patterns with error handling |
| Logging | `src/debussy/orchestrator.py` | Use logger.debug() for captures, logger.warning() for failures |
| Manager classes | `src/debussy/core/state.py` | Follow StateManager pattern for lifecycle management |

## Test Strategy

- [ ] Unit tests for ProgressEntry and PhaseCheckpoint dataclasses
- [ ] Unit tests for checkpoint context formatting (verify output structure)
- [ ] Unit tests for CheckpointManager lifecycle (start, record, prepare)
- [ ] Mock git subprocess calls for consistent testing
- [ ] Test graceful degradation when git unavailable
- [ ] Integration with progress skill parsing (verify messages extracted correctly)

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure subprocess calls are safe and handle errors gracefully
- Verify restart context format is human-readable and actionable

## Acceptance Criteria

**ALL must pass:**

- [ ] PhaseCheckpoint dataclass captures all required fields
- [ ] format_restart_context() produces clear, actionable output
- [ ] CheckpointManager tracks progress entries from /debussy-progress
- [ ] Git state capture works (modified files list)
- [ ] Git command failures are handled gracefully (no crashes)
- [ ] Restart context limits file list to 20 entries
- [ ] 12+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

This phase is self-contained and not active until Phase 4 orchestration:
1. Remove `src/debussy/core/checkpoint.py`
2. Remove checkpoint_manager references from `src/debussy/orchestrator.py`
3. Remove `tests/test_checkpoint.py`

No breaking changes to existing functionality since checkpoint manager is not invoked by default.

---

## Implementation Notes

**Restart Context Format Example:**
```
⚠️ SESSION RESET: Context limit reached, fresh session started.
Phase: 1 - Setup Phase
Restart attempt: 2

Progress logged before reset:
  ✓ Created project structure
  ✓ Installed dependencies
  ✓ Configured environment

Files modified (do not recreate):
  - src/main.py
  - pyproject.toml
  - .env.example

IMPORTANT:
- Continue from where you stopped
- Do NOT redo completed work
- Review modified files to understand current state
- Use /debussy-progress to log significant progress
```

**Design Decisions:**
- Using git diff --name-only instead of full diffs to keep context compact
- Limiting file list to 20 entries to prevent overwhelming the restart prompt
- Progress entries shown with checkmarks for visual clarity
- Clear warnings about not redoing work
- Restart count helps Claude understand iteration history

**Git Integration:**
- capture_git_state() runs at restart preparation time (not continuously)
- Uses git diff without arguments (compares working directory to HEAD)
- Graceful failure if git unavailable (checkpoint still contains progress entries)
- start_commit captured at phase start for potential future diffing