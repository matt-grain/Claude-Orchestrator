# Issue-to-Plan Generator Phase 1: Data Ingestion Layer

**Status:** Pending
**Master Plan:** [issue-to-plan-generator-MASTER_PLAN.md](issue-to-plan-generator-MASTER_PLAN.md)
**Depends On:** N/A (initial phase)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (initial phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue-to-plan-generator_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass, 10+ new tests)
- coverage: `uv run pytest tests/ --cov=src/debussy/planners --cov-report=term` (maintain 66%+)

---

## Overview

This phase establishes the data ingestion layer for the issue-to-plan pipeline by creating a GitHub issue fetcher module. It provides structured access to GitHub issues via the `gh` CLI, with filtering by milestone, label, and state. This is the foundation that subsequent phases (analysis, Q&A, plan generation) will build upon.

## Dependencies
- Previous phase: N/A (initial phase)
- External: 
  - `gh` CLI must be installed and authenticated
  - Python 3.11+ with `subprocess` module
  - Project's existing dataclass patterns

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `gh` CLI not available in environment | Medium | High | Add clear error message with installation instructions; include check in tests |
| `gh` auth failures in CI/automation | Medium | Medium | Document auth requirements; provide --help guidance; graceful error handling |
| GitHub API rate limits | Low | Medium | Use `gh` CLI which handles auth tokens; document rate limit errors |
| Breaking changes in `gh` JSON output format | Low | High | Pin to specific `gh` version in docs; validate JSON schema in tests |

---

## Tasks

### 1. Module Structure Setup
- [ ] 1.1: Create `src/debussy/planners/` package directory
- [ ] 1.2: Create `src/debussy/planners/__init__.py` with public exports
- [ ] 1.3: Create `src/debussy/planners/models.py` for dataclasses
- [ ] 1.4: Create `src/debussy/planners/github_fetcher.py` for fetch logic

### 2. Data Models
- [ ] 2.1: Define `GitHubIssue` dataclass with fields: number, title, body, labels, state, url
- [ ] 2.2: Define `IssueSet` dataclass with fields: issues (list), milestone (optional), labels (optional), source_repo (optional)
- [ ] 2.3: Add `__len__` and `__iter__` methods to `IssueSet` for convenience
- [ ] 2.4: Add validation in `GitHubIssue.__post_init__` for required fields

### 3. GitHub Fetcher Implementation
- [ ] 3.1: Implement `check_gh_available()` helper to verify `gh` CLI is installed
- [ ] 3.2: Implement `fetch_issues_by_milestone(milestone, state="open")` using `gh issue list --milestone X --json`
- [ ] 3.3: Implement `fetch_issues_by_label(labels, state="open")` supporting single and multiple labels
- [ ] 3.4: Add `_parse_gh_json(output)` helper to convert JSON to `GitHubIssue` objects
- [ ] 3.5: Add error handling for subprocess failures (CalledProcessError, FileNotFoundError)
- [ ] 3.6: Add logging using Debussy's existing logger patterns

### 4. Testing
- [ ] 4.1: Create `tests/test_issue_fetcher.py` with 10+ unit tests
- [ ] 4.2: Mock `subprocess.run` for `gh` CLI calls in tests
- [ ] 4.3: Test `fetch_issues_by_milestone()` with open/closed/all states
- [ ] 4.4: Test `fetch_issues_by_label()` with single and multiple labels
- [ ] 4.5: Test error handling for missing `gh` CLI
- [ ] 4.6: Test error handling for auth failures (exit code 1)
- [ ] 4.7: Test `IssueSet` iteration and length methods
- [ ] 4.8: Test `GitHubIssue` validation in `__post_init__`

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/__init__.py` | Create | Package initialization, export public API |
| `src/debussy/planners/models.py` | Create | Define `GitHubIssue` and `IssueSet` dataclasses |
| `src/debussy/planners/github_fetcher.py` | Create | Implement issue fetching via `gh` CLI |
| `tests/test_issue_fetcher.py` | Create | Unit tests for fetcher module (10+ tests) |
| `tests/test_planners_models.py` | Create | Unit tests for dataclasses |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass design | `src/debussy/models.py` | Follow existing dataclass patterns (PhaseConfig, RunConfig) |
| Subprocess handling | `src/debussy/runners/claude.py` | Use similar subprocess error handling patterns |
| Error messages | `src/debussy/converters/plan_converter.py` | Follow existing error message formatting |
| Test mocking | `tests/test_plan_builder.py` | Mock subprocess calls similar to Claude subprocess mocking |
| Logging | `src/debussy/orchestrator.py` | Use `logger = logging.getLogger(__name__)` pattern |

## Test Strategy

- [ ] Unit tests for `GitHubIssue` dataclass validation
- [ ] Unit tests for `IssueSet` iteration and convenience methods
- [ ] Mocked tests for `fetch_issues_by_milestone()` with various states
- [ ] Mocked tests for `fetch_issues_by_label()` with single/multiple labels
- [ ] Error case tests: missing `gh` CLI, auth failures, malformed JSON
- [ ] Integration test fixtures: sample `gh` JSON output for realistic testing
- [ ] Edge case tests: empty results, special characters in titles/bodies

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest)
- [ ] 10+ tests written and passing
- [ ] Coverage maintained at 66%+
- [ ] `GitHubIssue` and `IssueSet` dataclasses created and validated
- [ ] `fetch_issues_by_milestone()` works with open/closed/all filters
- [ ] `fetch_issues_by_label()` works with single and multiple labels
- [ ] Error handling for missing `gh` CLI with clear message
- [ ] Error handling for auth failures
- [ ] Documentation strings added to all public functions
- [ ] No security vulnerabilities introduced

## Rollback Plan

Since this is a new module with no dependencies:

1. **Delete created files:**
   ```bash
   rm -rf src/debussy/planners/
   rm -rf tests/test_issue_fetcher.py tests/test_planners_models.py
   ```

2. **Verify no broken imports:**
   ```bash
   uv run pyright src/
   uv run pytest tests/ -v
   ```

3. **No database migrations or config changes to revert** - this phase only adds new isolated code.

---

## Implementation Notes

**Architecture Decisions:**

1. **Why `gh` CLI instead of PyGitHub library?**
   - Follows Debussy's pattern of shelling out to CLI tools (Claude, audit)
   - Avoids adding heavy dependencies
   - Leverages user's existing `gh` auth setup
   - Consistent with project philosophy

2. **Dataclass design:**
   - `GitHubIssue`: Immutable snapshot of issue data at fetch time
   - `IssueSet`: Collection container with metadata (milestone/labels used)
   - Both frozen for safety, validated in `__post_init__`

3. **Error handling strategy:**
   - Missing `gh` CLI: Clear error with installation link
   - Auth failures: Suggest `gh auth login`
   - Empty results: Return empty `IssueSet`, not error (valid case)

4. **JSON fields from `gh` CLI:**
   ```
   --json number,title,body,labels,state,url
   ```
   - `labels` is array of objects: `[{"name": "bug"}, ...]`
   - Extract just label names in parser

5. **Future extensibility:**
   - `IssueSet.source_repo` reserved for multi-repo support
   - Models can be extended for Jira in future phases (Phase 7.5+)
