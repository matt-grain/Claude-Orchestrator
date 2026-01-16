# Context Monitoring & Smart Restart - Master Plan

**Created:** 2026-01-15
**Status:** Draft
**Analysis:** N/A

---

## Overview

Implement context monitoring for long-running phases to prevent quality degradation from auto-compaction. When estimated context usage exceeds a threshold, Debussy gracefully restarts the phase with injected context about prior progress. This solves the problem of Claude Code's auto-compaction degrading quality for complex tasks, especially when stream-json token counts are cumulative and unreliable for current context estimation.

## Goals

1. **Context Usage Estimation** - Build a reliable estimator that tracks file reads, tool outputs, and prompt injections without relying on broken stream-json tokens
2. **Progress Preservation** - Capture checkpoint data (progress logs, git diffs) during execution so restarts can continue from where they left off
3. **Automatic Recovery** - Gracefully restart phases when context limits are approached, with clear boundaries via auto-commits

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Context Estimation](phase-1.md) | Build context usage estimator with token counting and tool call heuristics | Low | Pending |
| 2 | [Progress Checkpoints](phase-2.md) | Capture progress during execution for restart context | Low | Pending |
| 3 | [Auto-Commit Boundaries](phase-3.md) | Automatically commit at phase boundaries for clean checkpoints | Low | Pending |
| 4 | [Smart Restart Logic](phase-4.md) | Orchestrate threshold detection, checkpoint capture, and restart with context | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| Context awareness | None | Token estimation | Progress capture | Auto-commits | Full restart cycle |
| Restart capability | None | Threshold detection | Checkpoint formatting | Clean boundaries | Context injection |
| Test coverage | ~60% | +5-10 tests | +5-10 tests | +5-10 tests | +10-15 tests |

## Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
   │           │           │
   └── Standalone ─┴── Standalone ─┴── Requires all
```

- Phase 1 (Context Estimation) can be developed and tested independently
- Phase 2 (Progress Checkpoints) can be developed independently but works best with Phase 1
- Phase 3 (Auto-Commit) is independent but complements Phase 2
- Phase 4 (Smart Restart) requires all previous phases to integrate them into orchestrator

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Estimation inaccuracy | Medium | Low | Conservative threshold (80%), fallback to tool count heuristic |
| Restart loops | Low | High | Max restart count (3), exponential backoff, clear failure messages |
| Progress not captured | Medium | Medium | Git diff as fallback, warn if no /debussy-progress calls detected |
| Lost work on restart | Low | Medium | Auto-commit before restart, clear warning in logs, checkpoint context injection |
| Breaking existing phases | Low | High | Feature behind config flags, sensible defaults, extensive testing |

## Out of Scope

- Advanced token counting via tiktoken (optional, simple char ratio is sufficient)
- Real-time context monitoring UI in TUI (can be added later)
- Cross-phase checkpoint persistence (each phase gets fresh start)
- Manual checkpoint save/restore commands (fully automatic)
- Integration with external version control beyond git

## Review Checkpoints

- After Phase 1: Verify estimator accurately tracks context growth and triggers threshold detection
- After Phase 2: Verify checkpoint captures progress entries and git state correctly
- After Phase 3: Verify auto-commits create clean phase boundaries without breaking existing workflows
- After Phase 4: Verify full restart cycle works end-to-end with context injection and progress continuation

---

## Quick Reference

**Key Files:**
- `src/debussy/runners/claude.py` - Current stream parsing, where monitoring hooks will go
- `src/debussy/orchestrator.py` - Phase lifecycle, where restart logic lives
- `src/debussy/core/state.py` - State persistence patterns
- `src/debussy/skills/debussy_progress.py` - Existing progress reporting mechanism
- `src/debussy/config.py` - Configuration management

**Test Locations:**
- `tests/test_context_estimator.py`
- `tests/test_checkpoint.py`
- `tests/test_orchestrator.py`
- `tests/test_smart_restart.py`

**Related Documentation:**
- `docs/FUTURE.md` - Token reporting bug context