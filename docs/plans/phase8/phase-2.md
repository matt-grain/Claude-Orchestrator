# Issue Tracker Sync Phase 2: Jira Issue Status Sync

**Status:** Pending
**Master Plan:** [issue-tracker-sync-MASTER_PLAN.md](issue-tracker-sync-MASTER_PLAN.md)
**Depends On:** N/A (Independent - runs in parallel with Phase 1)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (First phase in parallel track)
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
- [ ] Write `notes/NOTES_issue_tracker_sync_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass, ≥60% coverage maintained)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase implements automatic Jira issue workflow transitions triggered by Debussy phase lifecycle events. When a phase starts or completes, linked Jira issues will transition to configured workflow states (e.g., "In Development" → "Code Review" → "Done"). This eliminates manual status updates in Jira and keeps issue tracking synchronized with actual development progress.

The implementation focuses on flexibility (configurable transitions per project), robustness (graceful handling of invalid workflow states), and security (token management via environment variables).

## Dependencies
- Previous phase: N/A (runs in parallel with Phase 1)
- External: 
  - Jira REST API v3 access
  - `JIRA_API_TOKEN` environment variable for authentication
  - `httpx` library for API calls

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Invalid workflow transitions for specific projects | Medium | Low | Log warnings and continue execution without blocking phases; validate transitions in dry-run mode |
| API rate limiting on large issue sets | Medium | Medium | Implement caching for available transitions; batch operations where possible |
| Network failures during API calls | Low | Low | Retry logic with exponential backoff; graceful degradation if sync fails |
| Authentication token exposure | Low | High | Require environment variable only; document secure token management; never log tokens |
| Missing transition states in workflow | Medium | Low | Cache and validate available transitions before attempting; provide clear error messages |

---

## Tasks

### 1. Configuration Schema & Parsing
- [ ] 1.1: Extend `.debussy/config.yaml` schema with `jira` section
- [ ] 1.2: Add Pydantic model for `JiraConfig` (url, transitions mapping, enabled flag)
- [ ] 1.3: Validate transition names are non-empty strings
- [ ] 1.4: Add dry_run support to config

### 2. Jira API Client
- [ ] 2.1: Create `src/debussy/sync/jira_client.py` with `JiraClient` class
- [ ] 2.2: Implement authentication via `JIRA_API_TOKEN` environment variable
- [ ] 2.3: Add method to fetch issue details by key (GET `/rest/api/3/issue/{issueKey}`)
- [ ] 2.4: Add method to get available transitions for issue (GET `/rest/api/3/issue/{issueKey}/transitions`)
- [ ] 2.5: Add method to perform transition (POST `/rest/api/3/issue/{issueKey}/transitions`)
- [ ] 2.6: Implement retry logic with exponential backoff for transient failures
- [ ] 2.7: Add transition name → transition ID resolution (cache per issue)

### 3. Issue Link Parser
- [ ] 3.1: Update plan metadata schema to support `jira_issues: [PROJ-123, PROJ-456]`
- [ ] 3.2: Add helper to extract Jira issue keys from plan YAML frontmatter
- [ ] 3.3: Validate issue key format (PROJECT-NUMBER pattern)

### 4. Sync Orchestration
- [ ] 4.1: Create `src/debussy/sync/jira_sync.py` with `JiraSynchronizer` class
- [ ] 4.2: Implement `on_phase_start(plan, phase_id)` hook
- [ ] 4.3: Implement `on_phase_complete(plan, phase_id)` hook
- [ ] 4.4: Implement `on_plan_complete(plan)` hook
- [ ] 4.5: Add dry-run mode that logs planned transitions without executing
- [ ] 4.6: Add graceful error handling for invalid transitions (log warning, continue)
- [ ] 4.7: Cache available transitions to minimize API calls

### 5. Integration with Orchestrator
- [ ] 5.1: Add Jira sync initialization in `src/debussy/orchestrator.py`
- [ ] 5.2: Call `on_phase_start` before phase execution
- [ ] 5.3: Call `on_phase_complete` after successful phase completion
- [ ] 5.4: Call `on_plan_complete` after all phases complete
- [ ] 5.5: Skip sync if `jira.enabled: false` in config

### 6. Testing
- [ ] 6.1: Unit tests for `JiraClient` with mocked httpx responses
- [ ] 6.2: Unit tests for `JiraSynchronizer` logic
- [ ] 6.3: Integration tests for config parsing
- [ ] 6.4: Test invalid transition handling (non-existent state names)
- [ ] 6.5: Test auth token validation (missing token, invalid token)
- [ ] 6.6: Test dry-run mode output
- [ ] 6.7: Test transition caching behavior

### 7. Documentation
- [ ] 7.1: Add Jira sync configuration examples to README
- [ ] 7.2: Document environment variable setup (`JIRA_API_TOKEN`)
- [ ] 7.3: Document how to find workflow transition names in Jira UI
- [ ] 7.4: Add troubleshooting guide for common errors (auth, invalid transitions)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/sync/__init__.py` | Create | Module initialization for sync subsystem |
| `src/debussy/sync/jira_client.py` | Create | Jira REST API v3 client with auth and retry logic |
| `src/debussy/sync/jira_sync.py` | Create | Synchronizer orchestrating phase events → Jira transitions |
| `src/debussy/models/config.py` | Modify | Add `JiraConfig` Pydantic model |
| `src/debussy/orchestrator.py` | Modify | Integrate Jira sync hooks into phase lifecycle |
| `tests/test_sync_jira.py` | Create | Unit and integration tests for Jira sync |
| `tests/fixtures/jira_responses.json` | Create | Mock API responses for testing |
| `docs/JIRA_SYNC.md` | Create | Configuration guide and troubleshooting |
| `.debussy/config.yaml.example` | Modify | Add Jira configuration example |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Config validation | `src/debussy/models/config.py` | Use Pydantic for type-safe config parsing |
| API client structure | `src/debussy/planners/github_client.py` (if exists) | Consistent auth, retry, error handling patterns |
| Event hooks | `src/debussy/orchestrator.py` | Follow existing pattern for phase lifecycle callbacks |
| Retry logic | Standard exponential backoff | `httpx.AsyncClient` with retry decorator |
| Environment variable access | `os.getenv` with validation | Fail fast if `JIRA_API_TOKEN` missing when Jira enabled |

## Test Strategy

- [ ] Unit tests for `JiraClient`:
  - Mock httpx responses for issue fetch, transitions fetch, transition execution
  - Test auth header construction
  - Test retry behavior on 5xx errors
  - Test transition name → ID resolution
- [ ] Unit tests for `JiraSynchronizer`:
  - Test hook calls with various plan states
  - Test dry-run mode (no API calls)
  - Test invalid transition handling (logs warning, continues)
  - Test caching behavior
- [ ] Integration tests:
  - End-to-end config → sync flow with mocked Jira API
  - Test multiple issues transitioning simultaneously
  - Test plan with no Jira issues (no-op)
- [ ] Manual testing:
  - Dry-run against real Jira instance
  - Verify transitions appear in Jira UI after phase completion
  - Test with various workflow configurations

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Test coverage ≥60% maintained
- [ ] Jira transitions configurable via `.debussy/config.yaml`
- [ ] Phase start/complete triggers configured transitions
- [ ] Invalid transitions log warnings without blocking execution
- [ ] Dry-run mode shows planned transitions without executing
- [ ] `JIRA_API_TOKEN` read securely from environment
- [ ] Documentation includes setup guide and troubleshooting
- [ ] No tokens logged or exposed in error messages

## Rollback Plan

Since this phase introduces new functionality without modifying existing orchestrator logic (hooks are opt-in via config), rollback is straightforward:

1. **Disable sync**: Set `jira.enabled: false` in `.debussy/config.yaml`
2. **Remove code** (if needed):
   ```bash
   git revert <commit-hash>  # Revert this phase's commits
   uv run pytest tests/ -v   # Verify existing tests still pass
   ```
3. **Database**: No database changes in this phase - no migrations to reverse
4. **Dependencies**: If `httpx` was added, remove from `pyproject.toml` and re-lock:
   ```bash
   uv remove httpx
   uv lock
   ```

No data loss risk since this phase only adds outbound API calls (no Debussy state changes).

---

## Implementation Notes

**Jira Workflow Discovery:**
- Transition names vary by project - provide clear docs on finding them in Jira UI (Issue → More → "Workflow" view)
- Consider adding `debussy jira-info PROJ-123` CLI command to list available transitions for debugging

**Performance Considerations:**
- Cache available transitions per issue key (transitions usually stable per workflow)
- Batch issue lookups if Jira API supports it (investigate bulk endpoints)
- Consider async/await for parallel issue updates

**Error Handling Philosophy:**
- Sync failures should NEVER block phase execution
- Log warnings prominently but continue orchestration
- Dry-run mode should be the default for first-time users (add `--sync` flag to enable)

**Security Notes:**
- Document token scoping (minimal permissions: read issues, transition issues)
- Warn about token exposure in CI logs if debugging enabled
- Consider supporting Jira API key files as alternative to env var
