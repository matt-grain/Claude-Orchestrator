# Issue Tracker Sync - Master Plan

**Created:** 2026-01-16
**Status:** Draft
**Analysis:** N/A

---

## Overview

This feature enables bidirectional synchronization between Debussy's orchestration workflow and external issue tracking systems (GitHub Issues and Jira). When Debussy executes phases of a plan, linked issues will automatically update their status, labels, and milestones. Additionally, Debussy can detect when issues have been modified externally and warn about state drift, with optional reconciliation.

This reduces manual project management overhead and ensures issue trackers remain the source of truth for feature status across teams.

## Goals

1. **Automated Status Propagation** - Debussy phase lifecycle events automatically update linked GitHub and Jira issues without manual intervention
2. **Completion Tracking** - Prevent accidental re-planning of already-completed features by tracking historical completions in state database
3. **Bidirectional Awareness** - Detect external issue state changes and provide reconciliation options to keep Debussy state aligned with issue trackers
4. **Safe Defaults with Control** - Conservative defaults (labels only) with opt-in flags for more aggressive actions (auto-close, auto-sync)

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [GitHub Issue Status Sync](phase-1.md) | Automatic label/milestone updates for GitHub issues on phase events | Low | Pending |
| 2 | [Jira Issue Status Sync](phase-2.md) | Automatic workflow transitions for Jira issues on phase events | Low | Pending |
| 3 | [Feature Completion Tracking & Re-run Protection](phase-3.md) | SQLite-based completion history with regeneration warnings | Medium | Pending |
| 4 | [Bidirectional Sync & Status Dashboard](phase-4.md) | External state detection and dashboard view of issue mappings | Low | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| Test Coverage | 69% | ≥60% | ≥60% | ≥60% | ≥60% |
| Manual Issue Updates | 100% | <20% (GitHub) | <20% (Jira) | 0% (warnings) | 0% (sync) |
| Accidental Re-plans | Unknown | Unknown | Unknown | 0 | 0 |
| State Drift Detection | 0% | 0% | 0% | 0% | 100% |

## Dependencies

```
Phase 1 (GitHub) ──┐
                   ├──► Phase 3 (Completion Tracking) ──► Phase 4 (Dashboard)
Phase 2 (Jira) ────┘
```

- **Phase 1 & 2** can run in parallel (independent platforms)
- **Phase 3** depends on both Phase 1 and 2 to track completions from either platform
- **Phase 4** depends on Phase 3 for state reconciliation and on 1 & 2 for synced issue data

Phases 1 and 2 can be deployed independently to enable single-platform workflows. Phase 3 should wait until at least one sync platform is live. Phase 4 is optional enhancement after core sync is stable.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting on large issue sets | Medium | Medium | Implement caching, batch operations, and rate limit handling with retries |
| Invalid Jira workflow transitions | Medium | Low | Graceful error handling - log warnings and continue execution without blocking phases |
| Network failures during issue updates | Low | Low | Retry logic with exponential backoff, dry-run mode for validation |
| Accidental issue closure | Low | High | Conservative default (labels only), require explicit `--auto-close` flag |
| State database corruption | Low | Medium | Schema migrations, validation on read, backup recommendations in docs |
| Authentication token exposure | Low | High | Environment variables only, clear documentation on secure token management |

## Out of Scope

- **Real-time webhooks** - This plan uses polling/on-demand checks, not live webhook listeners
- **Multi-directional sync** - External issue updates do NOT auto-trigger Debussy phase execution (detection only)
- **Advanced dashboard UI** - Phase 4 provides CLI status view, not a web/TUI dashboard
- **Issue creation from plans** - This plan syncs existing issues only, does not auto-create issues from phases
- **Cross-platform issue linking** - No GitHub ↔ Jira reference management

## Review Checkpoints

- **After Phase 1**: Verify GitHub label updates work correctly, milestone percentages accurate, dry-run shows expected changes, no auth token leaks
- **After Phase 2**: Verify Jira transitions trigger correctly, invalid transitions log warnings without blocking, config format is intuitive
- **After Phase 3**: Verify completion tracking detects all linked issues, confirmation dialog works in both TUI and CLI modes, `--force` flag bypasses correctly
- **After Phase 4**: Verify `status --issues` fetches live state accurately, warnings appear for drift, `sync` command reconciles state safely, performance acceptable with cached API calls

---

## Quick Reference

**Key Files:**
- `src/debussy/sync/` - New module for issue tracker sync logic
- `src/debussy/models/state.py` - Extended with completed features table
- `.debussy/config.yaml` - Sync configuration (GitHub/Jira settings)
- `tests/test_sync_*.py` - Sync-related test suites

**Test Locations:**
- `tests/test_sync_github.py` - GitHub sync tests
- `tests/test_sync_jira.py` - Jira sync tests
- `tests/test_completion_tracking.py` - Completion tracking tests
- `tests/test_bidirectional_sync.py` - Dashboard and reconciliation tests

**Related Documentation:**
- GitHub API v3 REST documentation
- Jira API v3 REST documentation
- `gh` CLI reference for GitHub operations
