# Issue Tracker Sync Phase 1: GitHub Issue Status Sync

**Status:** Pending
**Master Plan:** [issue-tracker-sync-MASTER_PLAN.md](issue-tracker-sync-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue_tracker_sync_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass, coverage ≥60%)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase establishes automated GitHub issue status synchronization with Debussy's orchestration workflow. When phases start and complete, linked GitHub issues will automatically receive label updates reflecting execution state (e.g., `debussy:in-progress`, `debussy:completed`). Milestone completion percentages will update based on phase completion ratios. An optional `--auto-close` flag enables automatic issue closure when all plan phases complete, with conservative defaults (labels only) to prevent accidental closures.

This foundation enables reduced manual project management overhead and ensures GitHub issues remain synchronized with Debussy execution state.

## Dependencies
- Previous phase: N/A (foundation phase)
- External: GitHub API v3 or `gh` CLI for issue operations

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GitHub API rate limiting on large issue sets | Medium | Medium | Implement request caching, batch operations where possible, add rate limit detection with retry logic |
| Invalid issue references in plan metadata | Low | Low | Validate issue links on plan load, log warnings for unreachable issues, graceful degradation |
| Authentication token exposure | Low | High | Use environment variables only (`GITHUB_TOKEN`), document secure token management, never log tokens |
| Network failures during updates | Low | Low | Implement retry logic with exponential backoff, provide dry-run mode for validation |
| Accidental issue closure | Low | High | Conservative default (labels only), require explicit `--auto-close` flag, confirmation in TUI mode |

---

## Tasks

### 1. Configuration & Metadata Schema
- [ ] 1.1: Extend `.debussy/config.yaml` schema with `github` sync settings (enabled flag, label names, auto-close behavior)
- [ ] 1.2: Define plan frontmatter schema for `github_issues: [#10, #11]` linking format
- [ ] 1.3: Add config validation in `src/debussy/models/config.py` for GitHub sync settings
- [ ] 1.4: Document GitHub token authentication via `GITHUB_TOKEN` environment variable

### 2. GitHub API Client
- [ ] 2.1: Create `src/debussy/sync/github_client.py` with GitHub API wrapper using `httpx`
- [ ] 2.2: Implement authentication via `GITHUB_TOKEN` environment variable
- [ ] 2.3: Add methods: `get_issue()`, `update_labels()`, `close_issue()`, `get_milestone()`, `update_milestone_progress()`
- [ ] 2.4: Implement rate limit detection and retry logic with exponential backoff
- [ ] 2.5: Add dry-run mode flag to log planned changes without executing

### 3. Label Management
- [ ] 3.1: Create `src/debussy/sync/label_manager.py` for label lifecycle operations
- [ ] 3.2: Implement label creation if not exists (default: `debussy:in-progress`, `debussy:completed`, `debussy:failed`)
- [ ] 3.3: Add label color configuration (configurable in `.debussy/config.yaml`)
- [ ] 3.4: Implement atomic label updates (remove old state, add new state)

### 4. Issue Sync Orchestration
- [ ] 4.1: Create `src/debussy/sync/github_sync.py` main sync coordinator
- [ ] 4.2: Parse `github_issues` from plan metadata and validate references
- [ ] 4.3: Hook into orchestrator phase lifecycle events (phase start, phase complete, plan complete)
- [ ] 4.4: Implement sync on phase start: add `debussy:in-progress` label
- [ ] 4.5: Implement sync on phase complete: replace with `debussy:completed` label
- [ ] 4.6: Implement sync on phase failure: add `debussy:failed` label
- [ ] 4.7: Implement sync on plan complete with `--auto-close`: close all linked issues with completion comment

### 5. Milestone Progress Tracking
- [ ] 5.1: Detect milestone from linked issues (use first issue's milestone if multiple)
- [ ] 5.2: Calculate completion ratio: `completed_phases / total_phases`
- [ ] 5.3: Update milestone description or use GitHub API to reflect progress percentage
- [ ] 5.4: Handle milestone-less issues gracefully (skip milestone update)

### 6. CLI Integration
- [ ] 6.1: Add `--auto-close` flag to `debussy run` command
- [ ] 6.2: Add `--dry-run-sync` flag to preview sync operations without executing
- [ ] 6.3: Add TUI confirmation modal for auto-close when enabled (similar to sandbox warning)
- [ ] 6.4: Display sync status in orchestration logs (e.g., "Updated GitHub issue #10: in-progress")

### 7. Testing
- [ ] 7.1: Create `tests/test_sync_github.py` with mocked GitHub API responses
- [ ] 7.2: Unit tests for `GitHubClient` methods (auth, label updates, rate limiting, retries)
- [ ] 7.3: Unit tests for `LabelManager` (creation, atomic updates, color config)
- [ ] 7.4: Integration tests for sync coordinator (phase lifecycle hooks, issue parsing)
- [ ] 7.5: Test dry-run mode output matches expected operations
- [ ] 7.6: Test `--auto-close` behavior (only triggers on plan complete, not individual phases)
- [ ] 7.7: Test error handling (invalid issue refs, network failures, auth errors)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/sync/__init__.py` | Create | New sync module initialization |
| `src/debussy/sync/github_client.py` | Create | GitHub API wrapper with auth and rate limiting |
| `src/debussy/sync/label_manager.py` | Create | Label lifecycle operations (create, update, atomic state changes) |
| `src/debussy/sync/github_sync.py` | Create | Main sync coordinator for GitHub issue updates |
| `src/debussy/models/config.py` | Modify | Add GitHub sync config schema validation |
| `src/debussy/orchestrator.py` | Modify | Hook sync coordinator into phase lifecycle events |
| `src/debussy/cli.py` | Modify | Add `--auto-close` and `--dry-run-sync` flags |
| `tests/test_sync_github.py` | Create | Comprehensive test suite for GitHub sync |
| `.debussy/config.yaml` | Modify | Add example GitHub sync configuration |
| `docs/GITHUB_SYNC.md` | Create | Documentation for GitHub sync setup and usage |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Config validation | `src/debussy/models/config.py` | Use Pydantic models for GitHub sync settings |
| Async HTTP client | `src/debussy/planners/github_fetcher.py` | Follow httpx patterns for API calls with retries |
| TUI confirmation dialogs | `src/debussy/tui.py` ResumeConfirmScreen | Create similar modal for auto-close confirmation |
| Environment variable auth | Existing LTM patterns | Use `os.getenv("GITHUB_TOKEN")` with clear error messages |
| Phase lifecycle hooks | `src/debussy/orchestrator.py` | Hook into existing phase start/complete/failed events |

## Test Strategy

- [ ] Unit tests for GitHub API client (mocked responses, rate limiting, auth failures)
- [ ] Unit tests for label manager (creation, atomic updates, color validation)
- [ ] Integration tests for sync coordinator (end-to-end phase → label flow)
- [ ] Manual testing checklist:
  - [ ] Create test repo with milestone and issues
  - [ ] Link issues in plan metadata
  - [ ] Run plan with `--dry-run-sync` and verify output
  - [ ] Run plan normally and verify labels update in GitHub
  - [ ] Test `--auto-close` with confirmation dialog
  - [ ] Test rate limit handling (simulate via API mocking)
  - [ ] Test invalid issue refs and network failures

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest ≥60% coverage, bandit)
- [ ] Tests written and passing for GitHub client, label manager, sync coordinator
- [ ] Documentation created in `docs/GITHUB_SYNC.md` with setup instructions
- [ ] No security vulnerabilities introduced (no token logging, secure env var usage)
- [ ] Dry-run mode accurately shows planned operations
- [ ] `--auto-close` only triggers on plan complete with explicit flag
- [ ] Labels create automatically if missing
- [ ] Milestone progress updates correctly based on phase completion ratio

## Rollback Plan

If issues arise during deployment:

1. **Disable sync in config**: Set `github.enabled: false` in `.debussy/config.yaml` to stop all sync operations
2. **Remove hooks**: Comment out sync coordinator hooks in `src/debussy/orchestrator.py` phase lifecycle events
3. **Manual cleanup**: Use `gh` CLI to remove `debussy:*` labels from affected issues:
   ```bash
   gh issue edit <issue-number> --remove-label "debussy:in-progress,debussy:completed,debussy:failed"
   ```
4. **Revert commits**: Use `git revert <commit-hash>` to roll back sync module introduction
5. **Database**: No state database changes in this phase - rollback is configuration-only

---

## Implementation Notes

**Architecture Decision**: Use `httpx` for GitHub API instead of `gh` CLI to enable better error handling, retries, and testability. The `gh` CLI can be added as an alternative backend later if needed.

**Label Atomicity**: Always remove old state labels before adding new ones to prevent issues from accumulating multiple state labels (e.g., both `in-progress` and `completed`).

**Milestone Strategy**: Use first linked issue's milestone as canonical. If issues have different milestones, log a warning and use the first detected. Consider supporting explicit milestone override in plan metadata for future enhancement.

**Rate Limiting**: GitHub API allows 5000 requests/hour for authenticated users. With typical plans having 3-5 phases and 2-5 linked issues, rate limits are unlikely to trigger. Still implement detection and retry for safety.

**Testing with Real GitHub**: Consider adding integration test marker (`@pytest.mark.integration`) for optional tests against real GitHub API (requires test repo and token). Default tests should use mocked responses.
