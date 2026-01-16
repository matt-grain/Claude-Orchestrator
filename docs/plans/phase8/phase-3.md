# Issue Tracker Sync Phase 3: Feature Completion Tracking & Re-run Protection

**Status:** Pending
**Master Plan:** [issue-tracker-sync-MASTER_PLAN.md](issue-tracker-sync-MASTER_PLAN.md)
**Depends On:** [Phase 1: GitHub Issue Status Sync](phase-1.md), [Phase 2: Jira Issue Status Sync](phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue_tracker_sync_phase_1.md`
- [ ] Read previous notes: `notes/NOTES_issue_tracker_sync_phase_2.md`
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
- [ ] Write `notes/NOTES_issue_tracker_sync_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass, ≥60% coverage)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase implements SQLite-based completion history to track features that have already been delivered, preventing accidental regeneration of plans for completed work. When users run `plan-from-issues`, Debussy will detect if any linked issues were part of a previously completed feature and prompt for confirmation before proceeding. This reduces wasted effort and maintains historical awareness of what has already been shipped.

The completion tracking integrates with both GitHub and Jira sync mechanisms from Phases 1 and 2, recording issue links when plans complete so future invocations can cross-reference them.

## Dependencies
- Previous phase: [Phase 1: GitHub Issue Status Sync](phase-1.md)
- Previous phase: [Phase 2: Jira Issue Status Sync](phase-2.md)
- External: N/A (uses existing SQLite state.db)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State database corruption prevents completion detection | Low | Medium | Schema validation on read, graceful degradation if table missing, backup recommendations in docs |
| Partial issue matches cause false positives (some issues completed, others new) | Medium | Low | Clear warning message distinguishes fully vs partially completed feature sets, show issue-by-issue breakdown |
| Users bypass confirmation and regenerate anyway | Medium | Low | Log warning even when `--force` used, document best practices for feature evolution vs re-implementation |
| TUI confirmation dialog breaks CLI workflows | Low | Medium | Detect interactive mode, fall back to CLI prompt in non-interactive environments |

---

## Tasks

### 1. Database Schema Extension
- [ ] 1.1: Add `completed_features` table to state.py schema with columns: id (INTEGER PRIMARY KEY), name (TEXT), completed_at (TIMESTAMP), issues_json (TEXT), plan_path (TEXT)
- [ ] 1.2: Create migration function to add table if not exists (for existing Debussy installations)
- [ ] 1.3: Add validation function to ensure issues_json is valid JSON array
- [ ] 1.4: Update StateManager class with methods: `record_completion()`, `find_completed_features()`, `get_completion_details()`

### 2. Completion Recording Integration
- [ ] 2.1: Modify orchestrator completion handler to extract linked issues from plan metadata (github_issues, jira_issues)
- [ ] 2.2: Call `StateManager.record_completion()` when plan execution completes successfully
- [ ] 2.3: Extract feature name from master plan title or plan file path
- [ ] 2.4: Store timestamp using UTC timezone
- [ ] 2.5: Handle cases where no issues are linked (skip recording)

### 3. Detection Logic in plan-from-issues
- [ ] 3.1: Add completion check before analysis phase in `plan_from_issues()` function
- [ ] 3.2: Query `find_completed_features()` with list of GitHub/Jira issue IDs from fetched issues
- [ ] 3.3: Build warning message showing matched issues with completion dates
- [ ] 3.4: Distinguish full matches (all issues completed) vs partial matches (subset completed)
- [ ] 3.5: Handle multiple completed features referencing same issue

### 4. Confirmation Dialog (TUI Mode)
- [ ] 4.1: Create `CompletionWarningScreen` modal in debussy/tui.py (similar to ResumeConfirmScreen)
- [ ] 4.2: Display matched completed features in scrollable list with issue details
- [ ] 4.3: Add "Continue Anyway" and "Cancel" buttons
- [ ] 4.4: Emit message to CLI handler with user choice
- [ ] 4.5: Test modal rendering with multiple completed features

### 5. Confirmation Prompt (CLI Mode)
- [ ] 5.1: Add CLI prompt function in cli.py for non-interactive mode
- [ ] 5.2: Format completion warning for terminal output (color-coded)
- [ ] 5.3: Implement [y/N] input with default to abort
- [ ] 5.4: Add `--force` flag to bypass confirmation entirely
- [ ] 5.5: Log warning message even when `--force` used

### 6. Testing & Edge Cases
- [ ] 6.1: Test with no completed features (should proceed normally)
- [ ] 6.2: Test with fully completed feature set (all issues match)
- [ ] 6.3: Test with partially completed feature set (some issues match)
- [ ] 6.4: Test with multiple overlapping completed features
- [ ] 6.5: Test `--force` flag in both TUI and CLI modes
- [ ] 6.6: Test migration on existing state.db without completed_features table
- [ ] 6.7: Test with corrupted issues_json data (graceful error handling)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/models/state.py` | Modify | Add completed_features table schema and StateManager methods |
| `src/debussy/orchestrator.py` | Modify | Record completion when plan execution finishes |
| `src/debussy/cli.py` | Modify | Add --force flag, CLI confirmation prompt, completion detection in plan-from-issues |
| `src/debussy/tui.py` | Modify | Add CompletionWarningScreen modal for interactive confirmation |
| `tests/test_completion_tracking.py` | Create | Unit and integration tests for completion tracking |
| `tests/test_plan_from_issues_completion.py` | Create | End-to-end tests for plan-from-issues with completion detection |
| `docs/COMPLETION_TRACKING.md` | Create | User-facing documentation on completion tracking behavior |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| State persistence | `src/debussy/models/state.py` | Follow existing StateManager patterns for database access |
| TUI confirmation dialogs | `src/debussy/tui.py:ResumeConfirmScreen` | Mirror resume dialog structure for completion warnings |
| CLI flag handling | `src/debussy/cli.py:--resume/--restart` | Use same pattern for --force flag |
| JSON storage in SQLite | `src/debussy/planners/state.py:phases_json` | Store issues_json as TEXT column with JSON validation |
| Migration on schema changes | `src/debussy/models/state.py:_initialize_db()` | Use CREATE TABLE IF NOT EXISTS for backward compatibility |

## Test Strategy

- [ ] Unit tests for StateManager methods (record_completion, find_completed_features)
- [ ] Unit tests for JSON validation in issues_json column
- [ ] Integration tests for plan-from-issues with mocked completed features
- [ ] TUI modal tests (rendering, button clicks, message emission)
- [ ] CLI prompt tests (y/n input, --force bypass)
- [ ] Migration tests (existing DB without completed_features table)
- [ ] Edge case tests (partial matches, no matches, multiple features, corrupted data)
- [ ] Manual testing checklist:
  - [ ] Complete a plan with linked issues, verify DB entry
  - [ ] Run plan-from-issues with same issues, confirm warning appears
  - [ ] Test --force flag skips confirmation
  - [ ] Test TUI modal in interactive mode
  - [ ] Test CLI prompt in non-interactive mode

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest ≥60%, bandit)
- [ ] Tests written and passing (≥20 tests covering unit + integration + edge cases)
- [ ] Documentation updated (COMPLETION_TRACKING.md created)
- [ ] No security vulnerabilities introduced
- [ ] Completion tracking works for both GitHub and Jira issue IDs
- [ ] TUI modal displays correctly with scrollable issue list
- [ ] CLI prompt works in non-interactive environments
- [ ] `--force` flag bypasses confirmation in both modes
- [ ] Migration handles existing databases without completed_features table
- [ ] Partial matches show clear breakdown of which issues were completed

## Rollback Plan

If completion tracking causes issues:

1. **Database rollback**: The completed_features table is additive only - removing it will not break existing functionality:
   ```bash
   sqlite3 .debussy/state.db "DROP TABLE IF EXISTS completed_features;"
   ```

2. **Code rollback**: 
   - Revert changes to `orchestrator.py` completion handler (remove `record_completion()` call)
   - Revert changes to `cli.py` plan-from-issues (remove completion check)
   - Remove CompletionWarningScreen from tui.py

3. **Feature flag approach** (if partial rollback needed):
   - Add `completion_tracking: false` to config.yaml
   - Wrap detection logic in config check
   - Allow users to disable without code changes

4. **Data preservation**: Completed features are stored with timestamps - if rollback is temporary, data will persist for future re-enablement

No backward-incompatible changes to existing tables or data structures. Rollback is low-risk.

---

## Implementation Notes

**Design Decision: Issues JSON Storage**
Store issues as JSON array of objects `[{"type": "github", "id": "10"}, {"type": "jira", "id": "PROJ-123"}]` instead of separate columns. This allows flexible querying for either platform and handles mixed-platform plans gracefully.

**Design Decision: Partial Match Handling**
When only some issues match completed features, show warning but allow continuation by default. Users may be extending an existing feature with new issues, which is valid. The warning provides awareness without blocking legitimate workflows.

**Design Decision: TUI vs CLI Detection**
Use `hasattr(sys.stdout, 'isatty')` and check for `--non-interactive` flag to determine mode. TUI mode gets modal, CLI mode gets terminal prompt. This ensures compatibility with CI/CD environments.

**Design Decision: Force Flag Logging**
Even when `--force` is used, log a WARNING-level message to debussy.log. This creates an audit trail for bypassed confirmations, which may be useful for debugging "why did we regenerate this?" questions later.
