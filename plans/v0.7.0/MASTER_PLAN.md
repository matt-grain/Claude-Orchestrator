# Issue Tracker Enhancements - Master Plan

**Created:** 2026-01-16
**Status:** Draft

---

## Overview

This phase enhances Debussy's planning and execution reliability by improving git state handling, validating subagent references at audit time, and enabling seamless Q&A integration when running plan generation inside Claude Code conversations.

## Goals

1. **Improve Developer Experience** - Fix git dirty check to distinguish untracked files from modified tracked files, reducing false positives that block execution
2. **Catch Configuration Errors Early** - Validate custom subagent existence during audit phase rather than discovering missing agents at runtime
3. **Enable Interactive Planning** - Allow plan-from-issues to route Q&A through Claude Code's AskUserQuestion tool for seamless gap-filling

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Add pipe mechanism for plan-from-issues Q&A](phase-1.md) | Interactive planning via IPC | Medium | Pending |
| 2 | [Fix git dirty check: untracked files should not block execution](phase-2.md) | Smarter git state validation | Low | Pending |
| 3 | [Add subagent existence validation to audit](phase-3.md) | Pre-execution agent validation | Low | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| False positive git blocks | High | High | Zero (untracked ignored) | Zero |
| Runtime agent errors | Possible | Possible | Possible | Zero (caught at audit) |
| Q&A integration modes | Terminal only | Terminal + Claude Code pipe | Terminal + Claude Code pipe | Terminal + Claude Code pipe |
| Test coverage | 69% | 60%+ | 60%+ | 60%+ |

## Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3
   │           │           │
   └── Independent ───┴── Independent
```

All phases are independent and can be deployed separately:
- Phase 1 enhances plan-from-issues workflow
- Phase 2 fixes CLI pre-flight checks
- Phase 3 enhances audit command validation

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| IPC pipe mechanism breaks terminal mode | Low | High | Maintain clear fallback path, test both modes explicitly |
| Git status parsing fragile across versions | Low | Medium | Use well-documented `--porcelain` format, test multiple git versions |
| Built-in agent list becomes stale | Medium | Low | Document agent list location clearly, add comment to update when Task tool changes |
| Performance impact from agent directory scanning | Low | Low | Cache scan results during audit run |

## Out of Scope

- Automatic agent installation or scaffolding (phase focuses on validation only)
- Git auto-commit or auto-stash features (phase only validates state)
- Q&A answer persistence beyond current session (covered in existing plan-from-issues)
- Advanced git operations (rebasing, cherry-picking, etc.)

## Review Checkpoints

- After Phase 1: Verify Q&A questions route correctly through both terminal and Claude Code pipe modes
- After Phase 2: Confirm untracked files no longer block execution, modified files still warn
- After Phase 3: Validate audit catches missing custom agents and reports clear file paths

---

## Quick Reference

**Key Files:**
- `src/debussy/planners/qa_handler.py` - Q&A orchestration logic (Phase 1)
- `src/debussy/cli.py` - Git dirty check location (Phase 2)
- `src/debussy/core/auditor.py` - Audit validation logic (Phase 3)

**Test Locations:**
- `tests/planners/` - Q&A and plan generation tests
- `tests/` - CLI and orchestrator tests
- `tests/core/` - Audit command tests

**Related Documentation:**
- Issue #17: Pipe mechanism requirements
- Issue #18: Git dirty check behavior
- Issue #19: Subagent validation requirements
