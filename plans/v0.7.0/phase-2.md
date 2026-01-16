# Issue Tracker Enhancements Phase 2: Fix git dirty check: untracked files should not block execution

**Status:** Pending
**Master Plan:** [issue-tracker-enhancements-MASTER_PLAN.md](issue-tracker-enhancements-MASTER_PLAN.md)
**Depends On:** [Phase 1: Add pipe mechanism for plan-from-issues Q&A](phase-1.md)
**GitHub Issues:** #18

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue_tracker_enhancements_phase_1.md`
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
- [ ] Write `notes/NOTES_issue_tracker_enhancements_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase fixes the overly strict git dirty check that blocks execution when untracked files exist. The current implementation treats untracked files (notes/, scripts/, temp files) the same as modified tracked files, causing false positives that prevent orchestration. This phase distinguishes between untracked files (which should be ignored) and modified tracked files (which should warn but allow continuation with confirmation).

## Dependencies
- Previous phase: [Phase 1: Add pipe mechanism for plan-from-issues Q&A](phase-1.md)
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Git status parsing fragile across versions | Low | Medium | Use well-documented `--porcelain` format, test with multiple git version outputs |
| Breaking existing workflows expecting dirty check | Low | Medium | Maintain warning for modified files, just remove blocking for untracked |
| Edge cases in git status output | Low | Low | Comprehensive test coverage of mixed states (staged, modified, untracked, deleted) |

---

## Tasks

### 1. Locate and Analyze Current Implementation
- [ ] 1.1: Search for git dirty check implementation (likely in `src/debussy/cli.py` or orchestrator startup)
- [ ] 1.2: Document current behavior and identify where blocking logic occurs
- [ ] 1.3: Review how `--force` flag currently bypasses the check

### 2. Implement Smarter Git Status Parsing
- [ ] 2.1: Create helper function to parse `git status --porcelain` output
- [ ] 2.2: Categorize changes by prefix: `??` (untracked), `M ` or ` M` (modified), `A ` (staged), `D ` (deleted)
- [ ] 2.3: Return structured result with separate lists for untracked vs tracked changes

### 3. Update Dirty Check Logic
- [ ] 3.1: Modify dirty check to ignore untracked files entirely
- [ ] 3.2: Warn for modified/staged tracked files but allow confirmation to proceed
- [ ] 3.3: Display clear messaging distinguishing between untracked vs modified files
- [ ] 3.4: Preserve existing `--force` flag behavior (bypass all checks)
- [ ] 3.5: Consider adding `--allow-dirty` flag as alternative to `--force`

### 4. Add Comprehensive Tests
- [ ] 4.1: Test clean repository (no dirty check triggered)
- [ ] 4.2: Test untracked files only (no blocking, no warning)
- [ ] 4.3: Test modified tracked files only (warning + confirmation prompt)
- [ ] 4.4: Test mixed state (untracked + modified)
- [ ] 4.5: Test staged changes (warning + confirmation prompt)
- [ ] 4.6: Test `--force` flag bypasses all checks
- [ ] 4.7: Mock git commands using subprocess mocks

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/cli.py` | Modify | Update git dirty check logic to filter untracked files |
| `src/debussy/utils/git.py` | Create | New module with git status parsing helper functions |
| `tests/utils/test_git.py` | Create | Unit tests for git status parsing |
| `tests/test_cli.py` | Modify | Add integration tests for dirty check behavior |
| `docs/TROUBLESHOOTING.md` | Modify | Document new dirty check behavior and `--allow-dirty` flag if added |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Git porcelain format parsing | `git status --help` (XY format) | Parse two-character prefix to categorize changes |
| Subprocess mocking | `tests/test_runners.py` | Mock `subprocess.run` for git command tests |
| User confirmation prompts | `src/debussy/cli.py` (existing resume prompt) | Reuse confirmation pattern for dirty check override |

## Test Strategy

- [ ] Unit tests for git status parsing with various porcelain outputs
- [ ] Integration tests for CLI dirty check with mocked git repositories
- [ ] Test matrix covering all combinations: clean, untracked-only, modified-only, staged-only, mixed
- [ ] Test flag behavior: no flags, `--force`, `--allow-dirty` (if implemented)
- [ ] Manual testing: Create temp repo with notes/ folder and verify no blocking

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing
- [ ] Untracked files do not trigger dirty check failure
- [ ] Modified tracked files show warning with list of affected files
- [ ] User can confirm to proceed with dirty working directory for modified files
- [ ] `--force` flag bypasses dirty check entirely
- [ ] Clear distinction in output between untracked vs modified files
- [ ] Test coverage maintains 60%+ baseline
- [ ] Documentation updated with new behavior
- [ ] No security vulnerabilities introduced

## Rollback Plan

1. **Revert code changes:**
   ```bash
   git revert <commit-hash>
   ```

2. **If new module created (`utils/git.py`):**
   ```bash
   git rm src/debussy/utils/git.py tests/utils/test_git.py
   git commit -m "Rollback: Remove git utils module"
   ```

3. **Restore original dirty check:**
   - Revert changes to `cli.py` to restore original blocking behavior
   - Remove any new flags (`--allow-dirty`) from argument parser

4. **Verify rollback:**
   ```bash
   uv run pytest tests/ -v
   git status  # Should show clean working directory
   ```

---

## Implementation Notes

### Git Status Porcelain Format
- Format: `XY PATH` where X=index status, Y=worktree status
- Key prefixes:
  - `??` = untracked
  - `M ` = modified in index
  - ` M` = modified in worktree
  - `MM` = modified in both
  - `A ` = added to index
  - `D ` = deleted

### Example Parsing Logic
```python
def parse_git_status() -> dict[str, list[str]]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True
    )
    
    untracked = []
    modified = []
    
    for line in result.stdout.splitlines():
        if line.startswith("??"):
            untracked.append(line[3:])
        elif any(line.startswith(p) for p in ["M ", " M", "MM", "A ", "D "]):
            modified.append(line[3:])
    
    return {"untracked": untracked, "modified": modified}
```

### User Messaging Examples
- **Untracked only:** (silent, no blocking)
- **Modified tracked:** 
  ```
  Warning: Working directory has uncommitted changes:
    - src/debussy/cli.py (modified)
    - tests/test_cli.py (modified)
  
  Continue anyway? [y/N]:
  ```
