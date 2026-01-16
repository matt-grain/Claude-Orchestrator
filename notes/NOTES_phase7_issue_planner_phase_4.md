# Phase 4 Notes: CLI Integration & Audit Loop

## Summary

Phase 4 implemented the CLI integration for the `plan-from-issues` command, which orchestrates the entire issue-to-plan pipeline. This phase brought together all previous Phase 1-3 components (GitHub fetcher, issue analyzer, plan builder) into a single user-facing command.

## CLI Integration

### Command: `debussy plan-from-issues`

The new command was added to `src/debussy/cli.py` with the following options:

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--source/-s` | str | Issue source (gh, jira) | gh |
| `--repo/-r` | str | Repository (owner/repo) | auto-detect |
| `--milestone/-m` | str | Filter by milestone | None |
| `--label/-l` | list | Filter by labels (repeatable) | None |
| `--output-dir/-o` | Path | Output directory | plans/<feature> |
| `--skip-qa` | bool | Skip interactive Q&A | False |
| `--max-retries` | int | Audit retry limit | 3 |
| `--model` | str | Claude model | haiku |
| `--timeout/-t` | int | Claude timeout (seconds) | 120 |
| `--verbose/-v` | bool | Verbose output | False |

## Command Handler Implementation

Created `src/debussy/planners/command.py` with the main pipeline functions:

### Pipeline Flow

```
1. FETCH       gh issue list --milestone X --json ...
     │
     ▼
2. ANALYZE     Detect gaps, generate questions
     │
     ▼
3. Q&A         AskUserQuestion for missing info (unless --skip-qa)
     │
     ▼
4. GENERATE    Claude creates MASTER_PLAN.md + phase-*.md
     │
     ▼
5. AUDIT       debussy audit plans/<feature>/
     │
     ├─ PASS ──► Done! Show summary
     │
     └─ FAIL ──► Inject errors, retry (max 3)
```

### Key Functions

- `plan_from_issues()` - Main entry point
- `_fetch_phase()` - Fetches issues using GitHub fetcher
- `_analyze_phase()` - Analyzes issues for gaps
- `_qa_phase()` - Interactive Q&A session
- `_generate_phase()` - Generates plan files
- `_audit_loop()` - Runs audit with retry logic
- `_get_current_repo()` - Auto-detects repo from git remote

## Audit Loop Implementation

The audit loop follows the retry pattern from `plan_converter.py`:

1. Run `PlanAuditor.audit()` on generated plans
2. If passed, return success
3. If failed, extract error messages
4. Regenerate with error feedback (placeholder for future)
5. Repeat up to `max_retries` times

### Error Extraction

```python
def _get_audit_errors(result: AuditResult) -> list[str]:
    errors = []
    for issue in result.issues:
        if issue.severity == AuditSeverity.ERROR:
            errors.append(f"[{issue.code}] {issue.message}")
        elif issue.severity == AuditSeverity.WARNING:
            errors.append(f"[WARNING] {issue.message}")
    return errors
```

## Test Coverage

Created `tests/test_cli_plan_from_issues.py` with 27 tests covering:

### Test Categories

1. **PlanFromIssuesResult** (2 tests) - Dataclass creation
2. **_get_current_repo** (4 tests) - Git URL parsing
3. **_fetch_phase** (2 tests) - Issue fetching
4. **_analyze_phase** (2 tests) - Issue analysis
5. **_generate_phase** (1 test) - Plan generation
6. **_audit_loop** (3 tests) - Retry logic
7. **_get_audit_errors** (2 tests) - Error extraction
8. **plan_from_issues** (5 tests) - Main function
9. **CLI Integration** (3 tests) - CLI command tests
10. **Edge Cases** (3 tests) - Error handling

### Test Results

- All 750 tests pass (27 new + 723 existing)
- Coverage maintained at 70%
- Pyright: 0 errors
- Ruff: 0 errors

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/cli.py` | Modified | Added plan-from-issues command |
| `src/debussy/planners/command.py` | Created | Command implementation logic |
| `tests/test_cli_plan_from_issues.py` | Created | CLI and integration tests |

## Gate Results

- **ruff**: 0 errors ✓
- **pyright**: 0 errors ✓
- **pytest**: 750 tests pass ✓
- **coverage**: 70% (maintained) ✓

## Learnings

1. **Mock patching location matters**: When testing functions that use local imports (inside the function), you must patch at the import location (`debussy.planners.plan_builder.PlanBuilder`) not the usage location (`debussy.planners.command.PlanBuilder`).

2. **Positional vs keyword args in mock assertions**: When checking call_args for mocked functions, be aware of whether the function was called with positional or keyword arguments. Use `call_args[0][index]` for positional args.

3. **noqa comments for intentional unused parameters**: Use `# noqa: ARG001` for function parameters that are intentionally unused (reserved for future use) to keep ruff happy while documenting intent.

4. **Context manager syntax**: Python 3.10+ allows combining multiple context managers with parentheses:
   ```python
   with (
       patch("module.A") as a,
       patch("module.B") as b,
   ):
       ...
   ```

5. **Async function testing**: When testing sync functions that call async functions via `asyncio.run()`, you may see "coroutine was never awaited" warnings if the async function is mocked but never actually called. These are harmless in test contexts.
