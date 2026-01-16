# Notes: Issue Tracker Enhancements Phase 2

## Phase Summary

**Phase:** 2 - Fix git dirty check: untracked files should not block execution
**Status:** Completed
**GitHub Issues:** #18
**Date:** 2026-01-16

## Implementation Summary

This phase fixed the overly strict git dirty check that was blocking execution when untracked files existed. The key change is distinguishing between untracked files (which are now ignored) and modified tracked files (which trigger a warning with file list).

### Key Changes

1. **New Git Utils Module** (`src/debussy/utils/git.py`):
   - `GitStatusResult` dataclass: Holds parsed git status with `untracked` and `modified` lists
   - `parse_git_status_output()`: Parses `git status --porcelain` format correctly
   - `get_git_status()`: Runs git command and returns structured result
   - `check_working_directory()`: High-level function returning `(is_clean, count, files)` tuple
   - Properties: `is_clean` (ignores untracked), `has_tracked_changes`

2. **Updated Orchestrator** (`src/debussy/core/orchestrator.py`):
   - `check_clean_working_directory()` now returns 3-tuple instead of 2-tuple
   - Delegates to new `check_working_directory()` utility function
   - Only considers modified/staged/deleted tracked files as "dirty"

3. **Updated CLI** (`src/debussy/cli.py`):
   - Now shows list of modified files (up to 10) in the warning
   - Message changed from "uncommitted file(s)" to "modified tracked file(s)"
   - Clearer UX with bullet-point file list

4. **Test Coverage** (`tests/test_git_utils.py`):
   - 33 new tests covering all git status parsing scenarios
   - Tests for: clean repo, untracked only, modified only, mixed state
   - Tests for: renamed, copied, added, deleted files
   - Tests for: git unavailable, timeout, non-repo scenarios
   - Integration tests for full dirty check flow

5. **Updated Existing Tests** (`tests/test_auto_commit.py`):
   - Updated 5 tests to handle new 3-tuple return type
   - Fixed assertions for new "untracked ignored" behavior
   - Corrected git status porcelain format in test mocks

### Files Modified/Created

| File | Action | Lines Changed |
|------|--------|---------------|
| `src/debussy/utils/git.py` | Created | ~130 lines |
| `src/debussy/utils/__init__.py` | Modified | +12 lines |
| `src/debussy/core/orchestrator.py` | Modified | Simplified to ~15 lines |
| `src/debussy/cli.py` | Modified | +10 lines |
| `tests/test_git_utils.py` | Created | ~340 lines |
| `tests/test_auto_commit.py` | Modified | ~30 lines |
| `README.md` | Modified | +3 lines |

## Validation Results

### Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| ruff format | PASS | All files formatted |
| ruff check | PASS | No linting errors |
| pyright | PASS | 0 errors, 0 warnings |
| pytest | PASS | 1011 tests passed, 67.96% coverage |
| bandit | PASS | No high severity issues (58 low severity - pre-existing subprocess usage) |

### Test Results

- All 1011 tests pass
- Coverage at 67.96% (above 60% threshold)
- New git utils tests: 33 tests
- 100% coverage on new `src/debussy/utils/git.py`

## Technical Decisions

1. **Created separate utils module**: Chose to create `src/debussy/utils/git.py` rather than inline in orchestrator for:
   - Better testability with mocked subprocess
   - Reusability across CLI and orchestrator
   - Cleaner separation of concerns

2. **Return 3-tuple instead of 2-tuple**: Extended return type to include file list:
   - `(is_clean, count, files)` instead of `(is_clean, count)`
   - Allows CLI to show which files are modified
   - Limited to 10 files for display sanity

3. **Untracked files completely ignored**: Made the decision to not even mention untracked files:
   - They are never committed by git add .
   - Common for notes/, .debussy/, temp files
   - Users creating these files shouldn't be warned

4. **Porcelain format parsing**: Used well-documented `--porcelain` format:
   - Stable across git versions
   - Two-character prefix (XY) for status
   - `??` for untracked, other prefixes for tracked changes

## Learnings

1. **Git status porcelain format**: The format is `XY PATH` where X=index status, Y=worktree status. Key prefixes:
   - `??` = untracked (ignored by dirty check)
   - `M ` or ` M` or `MM` = modified (tracked change)
   - `A ` = added (tracked change)
   - `D ` or ` D` = deleted (tracked change)
   - `R ` or `C ` = renamed/copied with `old -> new` format

2. **Test mock formatting matters**: When mocking git status output, must use correct porcelain format including the space between status and path (`" M file.py"` not `"M file.py"`).

3. **Dataclass properties for computed values**: Using `@property` in dataclasses provides computed values without storage while maintaining immutability.

4. **Return type changes break tests**: Changing function return types requires updating all call sites including tests. The 2-tuple to 3-tuple change required updating 5 existing tests.

## Rollback Instructions

If issues are found:
1. Revert changes to `cli.py` and `orchestrator.py`
2. Remove `src/debussy/utils/git.py`
3. Remove `tests/test_git_utils.py`
4. Revert changes to `tests/test_auto_commit.py`
5. Revert changes to `src/debussy/utils/__init__.py`

No database migrations or state changes - rollback is clean.

## Next Phase

Phase 3 should continue with remaining issue tracker enhancements as defined in the master plan.
