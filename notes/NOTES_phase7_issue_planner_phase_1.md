# Phase 7.1: GitHub Issue Fetcher - Implementation Notes

## Summary

Successfully implemented the GitHub issue fetcher module for the issue-to-plan pipeline. This module provides async functionality to fetch GitHub issues using the `gh` CLI tool, supporting filtering by milestone, labels, and state.

## Key Decisions

1. **Used dataclasses over Pydantic**: Followed the existing pattern in the codebase where simple data models use `@dataclass` (e.g., `TokenStats` in `runners/claude.py`) rather than Pydantic BaseModel. Pydantic is reserved for more complex models needing validation/serialization.

2. **Async subprocess execution**: Implemented using `asyncio.create_subprocess_exec()` following the pattern from `src/debussy/runners/claude.py` for non-blocking execution.

3. **Custom exception hierarchy**: Created `GHError` as base class with specific subclasses (`GHNotFoundError`, `GHAuthError`, `GHRateLimitError`) for clear error handling.

4. **Warning threshold for large result sets**: Set at 20 issues to encourage users to use more specific filters when planning.

5. **State filtering**: Supported "open", "closed", and "all" states with Literal type for type safety.

## Files Modified

### Created
- `src/debussy/planners/__init__.py` - Module init with exports for models and fetcher functions
- `src/debussy/planners/models.py` - Dataclass models: `GitHubIssue`, `IssueLabel`, `IssueMilestone`, `IssueSet`
- `src/debussy/planners/github_fetcher.py` - Async fetcher module with gh CLI integration
- `tests/test_issue_fetcher.py` - 37 unit tests covering models, parsing, and fetcher functions

### Project Structure
```
src/debussy/planners/
    __init__.py
    models.py
    github_fetcher.py
tests/
    test_issue_fetcher.py
```

## Test Coverage Summary

- **Total new tests**: 37 tests
- **Coverage**: 94% for `github_fetcher.py`, 100% for `models.py`
- **Test categories**:
  - Model dataclass tests (14 tests)
  - JSON parsing tests (8 tests)
  - GH availability check tests (2 tests)
  - Async command runner tests (4 tests)
  - Fetcher function tests (7 tests)
  - Error handling tests (2 tests)

## GH CLI Integration Approach

The module wraps the `gh` CLI tool rather than using the GitHub API directly for several reasons:
1. Leverages existing authentication (no token management needed)
2. Automatic rate limit handling by gh CLI
3. Simpler implementation - just subprocess calls
4. Consistent with other CLI-based integrations in the codebase

### Key gh CLI commands used:
```bash
# List issues by milestone
gh issue list --repo owner/repo --milestone "v1.0" --state open --json number,title,body,labels,state,milestone,assignees,url

# List issues by label(s)
gh issue list --repo owner/repo --label bug --label critical --state open --json ...

# View single issue
gh issue view 42 --repo owner/repo --json ...
```

## Data Structures for Issue Representation

### GitHubIssue
```python
@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    labels: list[IssueLabel]
    state: str = "OPEN"
    milestone: IssueMilestone | None = None
    assignees: list[str] = []
    url: str = ""
```

Properties:
- `is_open` / `is_closed` - State checks (case-insensitive)
- `label_names` - Convenience list of label name strings

### IssueSet
```python
@dataclass
class IssueSet:
    issues: list[GitHubIssue]
    source: str  # e.g., "owner/repo"
    filter_used: str  # e.g., "milestone:v1.0 state:open"
    fetched_at: datetime
```

Properties:
- `__len__` / `__iter__` - Container protocol support
- `open_issues` / `closed_issues` - Filtered issue lists

## Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| ruff | PASS | All checks passed |
| pyright | PASS | 0 errors, 0 warnings |
| pytest | PASS* | 628 tests passed (1 pre-existing failure in test_convert.py unrelated to this phase) |
| coverage | PASS | 67.30% (above 66% baseline) |

*Note: The failing test `test_convert_cli_with_force` is a pre-existing issue in test_convert.py, not related to this phase's changes.

## Learnings

### Errors Encountered and Fixes
1. **Ruff RUF022**: `__all__` must be sorted alphabetically. Fixed by reordering exports in `__init__.py`.
2. **Ruff SIM105**: Prefer `contextlib.suppress(ValueError)` over `try/except/pass`. Fixed in datetime parsing.
3. **Ruff SIM117**: Combined nested `with` statements using parenthesized context managers.

### Project-Specific Patterns Discovered
1. Dataclasses are preferred for simple data models, Pydantic for complex validation needs.
2. Async subprocess patterns are well-established in `runners/claude.py`.
3. Tests use `pytest.mark.asyncio` for async test methods.
4. Log warnings using the `logging` module with `logger.warning()`.

### Tips for Future Phases
1. Run `uv run ruff format . && uv run ruff check --fix .` early and often.
2. The project has a pre-existing failing test in `test_convert.py` - exclude it with `-k "not test_convert_cli_with_force"`.
3. Use `contextlib.suppress()` pattern for ignored exceptions to satisfy ruff.
4. Sort `__all__` exports alphabetically.

## Next Steps (Phase 7.2)

The Issue Analyzer phase will use this fetcher to:
1. Detect gaps in issue descriptions
2. Generate clarifying questions
3. Analyze issue relationships and dependencies
