# Phase 6C: Auto-Commit Boundaries - Implementation Notes

**Date:** 2026-01-15
**Phase:** Context Monitoring Phase 3: Auto-Commit Boundaries

## Summary

This phase implements automatic git commits at phase boundaries for clean checkpoints. The implementation enables Debussy to create a clean git history where each phase's work is isolated in a commit, making it easy to review changes and providing clean restart points.

## Configuration Options Added

Three new configuration fields were added to `Config` in `src/debussy/config.py`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `auto_commit` | bool | `True` | Commit at phase boundaries for clean checkpoints |
| `commit_on_failure` | bool | `False` | Commit even if phase fails (default: only commit successful phases) |
| `commit_message_template` | str | `"Debussy: Phase {phase_id} - {phase_name} {status}"` | Template for commit messages; supports {phase_id}, {phase_name}, {status} |

## Dirty Directory Handling Approach

Before starting orchestration, the CLI checks for uncommitted changes in the working directory:

1. **Detection**: Uses `git status --porcelain` to detect uncommitted files
2. **Warning Display**: Shows file count and clear warning to user
3. **Options Provided**:
   - Commit or stash changes first
   - Use `--allow-dirty` to proceed anyway
   - Use `--no-auto-commit` to disable auto-commit
4. **Non-interactive Mode**: Exits with error code 1 (requires `--allow-dirty`)
5. **Interactive Mode**: Prompts user for confirmation

## Commit Message Format Examples

### Successful Phase
```
Debussy: Phase 1 - Setup Phase ✓

Co-Authored-By: Claude Opus <noreply@anthropic.com>
```

### Failed Phase (with commit_on_failure=True)
```
Debussy: Phase 2 - Implementation ⚠️

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

### Custom Template
```yaml
commit_message_template: "[{phase_id}] {phase_name}: {status}"
```
Results in: `[1] Setup Phase: ✓`

## CLI Flags Added

| Flag | Description |
|------|-------------|
| `--auto-commit/--no-auto-commit` | Override config for auto-commit (default: from config) |
| `--allow-dirty` | Allow starting with uncommitted changes in working directory |

## Auto-Commit Logic Flow

```
_auto_commit_phase(phase, success):
  1. Check config.auto_commit → skip if disabled
  2. Check success + config.commit_on_failure → skip if failed and not enabled
  3. Check for changes via _git_has_changes() → skip if no changes
  4. Execute commit via _execute_git_commit()
     - Format message using template
     - Add Co-Authored-By with model name
     - git add -A
     - git commit -m "<message>"
```

## Test Coverage Summary

Created 22 new unit tests in `tests/test_auto_commit.py`:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| TestAutoCommitConfig | 6 | Config field defaults and overrides |
| TestAutoCommitPhase | 9 | _auto_commit_phase() behavior |
| TestCheckCleanWorkingDirectory | 5 | Directory check edge cases |
| TestCLIAutoCommitFlags | 3 | CLI flag presence and behavior |
| TestAutoCommitMessageFormat | 3 | Commit message formatting |

**All 568 tests pass.** Total coverage: 67.14%

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `src/debussy/config.py` | Modify | Added auto_commit, commit_on_failure, commit_message_template fields |
| `src/debussy/core/orchestrator.py` | Modify | Added _auto_commit_phase(), _git_has_changes(), _execute_git_commit(), check_clean_working_directory() methods |
| `src/debussy/cli.py` | Modify | Added --auto-commit/--no-auto-commit and --allow-dirty flags, dirty directory check |
| `tests/test_auto_commit.py` | Create | 22 unit tests for auto-commit functionality |

## Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| ruff check | PASS | 0 errors |
| pyright | PASS | 0 errors, 0 warnings |
| pytest | PASS | 568 tests pass |
| coverage | PASS | 67.14% (above 50% threshold) |

## Design Decisions

1. **Default auto_commit to true**: Most users want clean phase boundaries in git history
2. **Default commit_on_failure to false**: Don't pollute history with partial work
3. **Use ✓ and ⚠️ in commit messages**: Visual clarity for success/failure status
4. **Check dirty directory before starting**: Prevents confusion about which changes belong to which phase
5. **Respect git hooks**: Don't use --no-verify; let hooks reject commits if needed
6. **Graceful degradation**: All git operations handle errors gracefully (no crashes)
7. **Refactored into helper methods**: `_git_has_changes()` and `_execute_git_commit()` for maintainability

## Integration Points

Auto-commit is called in three locations within `_execute_phase_with_compliance()`:

1. **compliance.passed** → `_auto_commit_phase(phase, success=True)`
2. **WARN_AND_ACCEPT** → `_auto_commit_phase(phase, success=True)`
3. **Max attempts reached** → `_auto_commit_phase(phase, success=False)`

## Recommendations for Future Work

1. Consider adding `--commit-on-failure` CLI flag to override config
2. May want to add git tag creation at major milestones
3. Could persist commit history to state.db for analytics
4. Consider integration with checkpoint system for restart context
