# Issue-to-Plan Phase 1: GitHub Issue Fetcher

**Status:** Completed
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** None (can run independently)

---

## Process Wrapper (MANDATORY)
- [ ] Read the files listed in "CRITICAL: Read These First" section below
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
- [ ] Write `notes/NOTES_phase7_issue_planner_phase_1.md` with:
  - Summary of GitHub fetcher implementation
  - GH CLI integration approach
  - Data structures for issue representation
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 7.1`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~66%)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **CLI patterns**: `src/debussy/cli.py` - How commands are structured
2. **Subprocess handling**: `src/debussy/runners/claude.py` - asyncio subprocess patterns
3. **Data models**: `src/debussy/core/models.py` - Dataclass patterns used in project
4. **Convert command**: `src/debussy/converters/plan_converter.py` - Similar external tool integration

**DO NOT** break existing functionality. Changes should be additive.

---

## Overview

Build a module to fetch GitHub issues using the `gh` CLI. The fetcher should support filtering by milestone, label, and state. It returns structured data that the analyzer can process to detect gaps and generate questions. This is the data ingestion layer of the issue-to-plan pipeline.

## Dependencies
- Previous phase: None (independent feature)
- External: `gh` CLI (assumed installed and authenticated)
- Internal: Will be used by the Issue Analyzer (next phase)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GH CLI not installed | Low | High | Check availability at startup, clear error message |
| Auth failures | Low | Medium | Let gh CLI handle auth; surface errors clearly |
| Rate limiting | Low | Low | gh CLI handles rate limits internally |
| Large issue counts | Medium | Medium | Warn if >20 issues; recommend more specific filters |

---

## Tasks

### 1. Create Issue Data Models
- [ ] 1.1: Create `src/debussy/planners/__init__.py` (new module)
- [ ] 1.2: Create `src/debussy/planners/models.py` with GitHubIssue dataclass (number, title, body, labels, state, milestone, assignee, url)
- [ ] 1.3: Add IssueLabel dataclass (name, description)
- [ ] 1.4: Add IssueMilestone dataclass (title, description, due_on)
- [ ] 1.5: Add IssueSet dataclass to hold collection of issues with metadata (source, filter_used, fetched_at)

### 2. Create GitHub Fetcher Module
- [ ] 2.1: Create `src/debussy/planners/github_fetcher.py`
- [ ] 2.2: Implement check_gh_available() function to verify gh CLI is installed
- [ ] 2.3: Implement fetch_issues_by_milestone(repo, milestone) using `gh issue list --milestone X --json`
- [ ] 2.4: Implement fetch_issues_by_label(repo, label) using `gh issue list --label X --json`
- [ ] 2.5: Implement fetch_issues_by_labels(repo, labels: list) for multiple labels (AND logic)
- [ ] 2.6: Implement fetch_issue_detail(repo, issue_number) for single issue deep fetch
- [ ] 2.7: Add state filter support (open, closed, all) to all fetch functions
- [ ] 2.8: Implement _parse_gh_json() to convert gh output to GitHubIssue objects
- [ ] 2.9: Add proper error handling: GHNotFoundError, GHAuthError, GHRateLimitError
- [ ] 2.10: Add warning log if issue count > 20

### 3. Write Unit Tests
- [ ] 3.1: Create `tests/test_issue_fetcher.py`
- [ ] 3.2: Test GitHubIssue dataclass creation and properties
- [ ] 3.3: Test IssueSet dataclass with multiple issues
- [ ] 3.4: Test _parse_gh_json() with sample gh output
- [ ] 3.5: Test check_gh_available() (mock subprocess)
- [ ] 3.6: Test fetch_issues_by_milestone() with mocked gh output
- [ ] 3.7: Test fetch_issues_by_label() with mocked gh output
- [ ] 3.8: Test fetch_issue_detail() with mocked gh output
- [ ] 3.9: Test error handling: GH not installed, auth failure
- [ ] 3.10: Test warning for large issue counts (>20)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/__init__.py` | Create | Module init, exports |
| `src/debussy/planners/models.py` | Create | Issue data models (GitHubIssue, IssueSet) |
| `src/debussy/planners/github_fetcher.py` | Create | GH CLI integration for fetching issues |
| `tests/test_issue_fetcher.py` | Create | Unit tests for fetcher (10+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass models | `src/debussy/core/models.py` | Use @dataclass for GitHubIssue, IssueSet |
| Subprocess execution | `src/debussy/runners/claude.py` | Use asyncio.create_subprocess_exec for gh calls |
| Error handling | `src/debussy/checkers/compliance.py` | Custom exception classes |
| JSON parsing | `src/debussy/converters/plan_converter.py` | Handle subprocess stdout as JSON |

## Test Strategy

- [ ] Unit tests for all dataclass models
- [ ] Unit tests for _parse_gh_json() with realistic gh CLI output
- [ ] Mocked subprocess tests for fetch functions
- [ ] Error condition tests (gh missing, auth failure, rate limit)
- [ ] Edge case tests (empty results, single issue, many issues)

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure all type hints are correct and pass pyright strict mode
- Verify gh CLI JSON output format matches expected schema

## Acceptance Criteria

**ALL must pass:**

- [ ] GitHubIssue and IssueSet dataclasses created with all fields
- [ ] Fetcher can retrieve issues by milestone
- [ ] Fetcher can retrieve issues by label(s)
- [ ] Fetcher can retrieve single issue details
- [ ] State filtering works (open/closed/all)
- [ ] Error handling covers gh missing, auth failures
- [ ] 10+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Phase is purely additive. Rollback:
1. Remove `src/debussy/planners/` directory
2. Remove `tests/test_issue_fetcher.py`

No existing functionality affected.

---

## Implementation Notes

**GH CLI JSON Fields:**
```bash
gh issue list --json number,title,body,labels,state,milestone,assignees,url
```

Returns:
```json
[
  {
    "number": 4,
    "title": "Issue title",
    "body": "Issue description...",
    "labels": [{"name": "feature", "description": "..."}],
    "state": "OPEN",
    "milestone": {"title": "v1.0", "description": "..."},
    "assignees": [{"login": "user"}],
    "url": "https://github.com/..."
  }
]
```

**Design Decisions:**
- Using `gh` CLI instead of GitHub API directly (handles auth, rate limits)
- Async subprocess for non-blocking execution
- IssueSet wrapper allows metadata (what filter was used, when fetched)
- Warning threshold at 20 issues (suggests user narrow scope)
