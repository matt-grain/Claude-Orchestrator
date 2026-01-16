# Issue Tracker Sync Phase 4: Bidirectional Sync & Status Dashboard

**Status:** Pending
**Master Plan:** [issue-tracker-sync-MASTER_PLAN.md](issue-tracker-sync-MASTER_PLAN.md)
**Depends On:** [Phase 3: Feature Completion Tracking & Re-run Protection](phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue_tracker_sync_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue_tracker_sync_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase adds bidirectional status awareness between Debussy and external issue trackers (GitHub/Jira). The `debussy status --issues` command will fetch and display current issue states, detect when external changes have created state drift, and provide an optional `debussy sync` command to reconcile Debussy's state with the issue tracker's source of truth.

This completes the issue tracker sync feature by enabling detection of manual issue updates and providing safe reconciliation options when Debussy's state diverges from the tracker.

## Dependencies
- Previous phase: [Phase 3: Feature Completion Tracking & Re-run Protection](phase-3.md)
- External: GitHub API v3, Jira API v3, Phase 1 & 2 sync infrastructure

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting with large issue sets | Medium | Medium | Implement aggressive caching with TTL, batch API calls, respect rate limit headers |
| Network failures during status fetch | Low | Low | Graceful degradation - show cached state with warning, retry with exponential backoff |
| State reconciliation corrupts database | Low | Medium | Dry-run mode by default, explicit `--apply` flag required, transaction rollback on error |
| Conflicting state updates (race condition) | Low | Low | Compare timestamps, show warning when Debussy state is newer than tracker state |

---

## Tasks

### 1. Status Fetching Infrastructure
- [ ] 1.1: Create `src/debussy/sync/status_fetcher.py` with `IssueStatusFetcher` class
- [ ] 1.2: Implement `fetch_github_status(issue_ids: list[str]) -> dict[str, IssueStatus]` using GitHub API
- [ ] 1.3: Implement `fetch_jira_status(issue_ids: list[str]) -> dict[str, IssueStatus]` using Jira API
- [ ] 1.4: Add caching layer with TTL (default 5 minutes) to reduce API calls
- [ ] 1.5: Define `IssueStatus` model with fields: id, state, labels, milestone, last_updated

### 2. State Drift Detection
- [ ] 2.1: Create `src/debussy/sync/drift_detector.py` with `DriftDetector` class
- [ ] 2.2: Implement `detect_drift(run_id: str) -> list[DriftReport]` comparing StateManager vs fetched status
- [ ] 2.3: Define `DriftReport` model with fields: issue_id, expected_state, actual_state, drift_type
- [ ] 2.4: Categorize drift types: LABEL_MISMATCH, STATUS_MISMATCH, CLOSED_EXTERNALLY, REOPENED_EXTERNALLY
- [ ] 2.5: Add timestamp comparison to detect if Debussy or tracker has newer state

### 3. Status Command Implementation
- [ ] 3.1: Add `--issues` flag to `debussy status` command in `src/debussy/cli.py`
- [ ] 3.2: Display issue status table showing: Issue ID, Current State, Expected State, Last Updated
- [ ] 3.3: Show warning banner when drift detected with count of diverged issues
- [ ] 3.4: Add `--json` output format for programmatic access
- [ ] 3.5: Include cache freshness indicator (e.g., "Cached 2m ago, use --refresh to update")

### 4. Sync Command Implementation
- [ ] 4.1: Add `debussy sync` command to CLI with dry-run default
- [ ] 4.2: Implement `--apply` flag to execute reconciliation (conservative default)
- [ ] 4.3: Show reconciliation plan before applying: which states will be updated and why
- [ ] 4.4: Update StateManager phase statuses based on tracker state (if issue closed externally → mark phase Completed)
- [ ] 4.5: Add `--direction` flag: `from-tracker` (default) or `to-tracker` (force push Debussy state)

### 5. Multi-Platform Support
- [ ] 5.1: Handle projects with both GitHub and Jira issues in same plan
- [ ] 5.2: Aggregate drift reports from both platforms into unified view
- [ ] 5.3: Add platform indicator in status output (e.g., `GH-123`, `PROJ-456`)
- [ ] 5.4: Respect per-platform configuration (GitHub enabled but Jira disabled)

### 6. Testing
- [ ] 6.1: Unit tests for `IssueStatusFetcher` with mocked API responses
- [ ] 6.2: Unit tests for `DriftDetector` with various drift scenarios
- [ ] 6.3: Integration tests for `status --issues` command with fixture data
- [ ] 6.4: Integration tests for `sync --apply` with state reconciliation
- [ ] 6.5: Test cache TTL expiration and refresh behavior
- [ ] 6.6: Test error handling for API failures (network errors, auth failures, rate limits)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/sync/status_fetcher.py` | Create | Fetch current issue status from GitHub/Jira APIs with caching |
| `src/debussy/sync/drift_detector.py` | Create | Compare Debussy state vs tracker state, categorize drift types |
| `src/debussy/sync/models.py` | Modify | Add `IssueStatus` and `DriftReport` models |
| `src/debussy/cli.py` | Modify | Add `--issues` flag to status command, add `sync` command |
| `src/debussy/models/state.py` | Modify | Add methods for querying linked issues per run |
| `tests/test_status_fetcher.py` | Create | Unit tests for status fetching with mocked API calls |
| `tests/test_drift_detector.py` | Create | Unit tests for drift detection logic |
| `tests/test_bidirectional_sync.py` | Create | Integration tests for status/sync commands |
| `tests/fixtures/api_responses/` | Create | Mock GitHub/Jira API response JSON files |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| API Client Pattern | `src/debussy/sync/github_sync.py` (Phase 1) | Reuse GitHub client setup, auth, error handling |
| Caching Strategy | `src/debussy/converters/plan_converter.py` | Use similar TTL-based caching for API responses |
| CLI Command Structure | `src/debussy/cli.py` existing commands | Follow Click patterns, `--json` flag, error formatting |
| State Queries | `src/debussy/models/state.py` existing methods | Add methods like `get_linked_issues(run_id)` following existing patterns |
| Model Definitions | `src/debussy/sync/models.py` (Phase 1-3) | Use Pydantic models with validation for API responses |

## Test Strategy

- [ ] Unit tests for status fetcher with mocked HTTP responses (httpx mock)
- [ ] Unit tests for drift detector with various state combinations
- [ ] Integration tests for status command output formatting
- [ ] Integration tests for sync command with dry-run and apply modes
- [ ] Test cache behavior: fresh cache, expired cache, forced refresh
- [ ] Test error scenarios: API rate limits, network failures, invalid auth
- [ ] Test multi-platform projects (GitHub + Jira mixed)
- [ ] Manual testing: Run against real GitHub/Jira project with known drift

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, tests, security)
- [ ] `debussy status --issues` displays current issue states from both GitHub and Jira
- [ ] Warning appears when state drift detected with clear indication of divergence
- [ ] `debussy sync` shows reconciliation plan in dry-run mode by default
- [ ] `debussy sync --apply` updates Debussy state from tracker state correctly
- [ ] Caching reduces API calls (verify with cache hit logs)
- [ ] Works with projects using GitHub only, Jira only, or both
- [ ] JSON output format works for programmatic access
- [ ] Tests achieve ≥60% coverage
- [ ] Documentation updated with examples of status/sync commands

## Rollback Plan

1. **Code Rollback**: Revert commit via `git revert <commit-sha>` - new commands are isolated and won't affect existing orchestration
2. **Configuration Rollback**: No config changes required - feature is opt-in via flags
3. **Database Rollback**: No schema changes in this phase - state reconciliation is in-memory only
4. **Dependency Rollback**: If API client changes break Phase 1/2, restore `src/debussy/sync/github_sync.py` and `jira_sync.py` from previous commit

**Safe Revert**: Since status/sync commands are new and don't modify existing orchestration logic, rollback is low-risk. Cache layer is optional - can disable by setting TTL=0.

---

## Implementation Notes

**Performance Optimization**: Implement batch API requests where possible. GitHub API v3 supports fetching multiple issues in one call via GraphQL (consider migration). Jira API v3 supports JQL queries to fetch multiple issues. Cache aggressively since issue state changes are typically infrequent during a single Debussy run.

**Reconciliation Strategy**: Default to conservative `from-tracker` direction - treat issue tracker as source of truth. The `to-tracker` direction (force push Debussy state) should only be used when Debussy state is known to be correct (e.g., after a manual phase completion that wasn't synced due to network failure).

**Future Enhancement**: Consider adding webhook support in a future phase to enable real-time drift detection instead of polling. This would require a persistent service, which is out of scope for current architecture.

**Cache Invalidation**: Provide `--refresh` flag on status command to bypass cache. Sync command should always fetch fresh state before reconciliation to avoid acting on stale data.
