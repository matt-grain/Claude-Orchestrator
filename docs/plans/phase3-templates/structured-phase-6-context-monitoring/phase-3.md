# Context Monitoring Phase 3: Auto-Commit Boundaries

**Status:** Pending
**Master Plan:** [context-monitoring-MASTER_PLAN.md](context-monitoring-MASTER_PLAN.md)
**Depends On:** [Phase 2: Progress Checkpoints](context-monitoring-phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase3_templates_phase_6B.md`
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
- [ ] Write `notes/NOTES_phase3_templates_phase_6C.md` with:
  - Summary of auto-commit implementation
  - Configuration options added
  - Dirty directory handling approach
  - Commit message format examples
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 6C`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~60%)

---

## Overview

Automatically commit at phase boundaries for clean checkpoints. This creates clear git history where each phase's work is isolated in a commit, making it easy to review changes and providing clean restart points. Includes configuration for enabling/disabling auto-commit, handling failures, and checking for dirty working directory before starting.

## Dependencies
- Previous phase: [Phase 2: Progress Checkpoints](context-monitoring-phase-2.md) - Complements checkpoint capture
- Internal: Uses existing config system, integrates with orchestrator lifecycle
- External: Git for commit operations

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Uncommitted changes warning | Medium | Low | --allow-dirty flag, clear warning message |
| Commit on failure unwanted | Low | Medium | Default to commit_on_failure: false |
| Commit message formatting | Low | Low | Use heredoc pattern like existing git commit code |
| Git hooks rejection | Low | Medium | Respect hook failures, log error but continue |

---

## Tasks

### 1. Add Auto-Commit Configuration
- [ ] 1.1: Update `src/debussy/config.py` with auto_commit field (default: True)
- [ ] 1.2: Add commit_on_failure field (default: False)
- [ ] 1.3: Add commit_message_template field (default: "Debussy: Phase {phase_id} - {phase_name} {status}")
- [ ] 1.4: Document configuration options in docstring

### 2. Implement Auto-Commit Logic
- [ ] 2.1: Create _auto_commit_phase() method in `src/debussy/orchestrator.py`
- [ ] 2.2: Check config.auto_commit flag before proceeding
- [ ] 2.3: Implement commit_on_failure logic (skip commit if phase failed unless enabled)
- [ ] 2.4: Check for changes using git status --porcelain
- [ ] 2.5: Skip commit if no changes detected
- [ ] 2.6: Format commit message using template with phase_id, phase_name, status
- [ ] 2.7: Add Co-Authored-By attribution with Claude model
- [ ] 2.8: Execute git add -A and git commit with heredoc message format
- [ ] 2.9: Add logging for commit success/skip/failure
- [ ] 2.10: Call _auto_commit_phase() after each phase completes

### 3. Add CLI Flags
- [ ] 3.1: Update `src/debussy/cli.py` run command with --auto-commit/--no-auto-commit option
- [ ] 3.2: Add --allow-dirty flag to bypass working directory check
- [ ] 3.3: Override config values with CLI flags when provided
- [ ] 3.4: Update CLI help text with clear descriptions

### 4. Handle Dirty Working Directory
- [ ] 4.1: Create _check_clean_working_directory() method in orchestrator
- [ ] 4.2: Use git status --porcelain to detect uncommitted changes
- [ ] 4.3: Count uncommitted files and display warning
- [ ] 4.4: Return False if dirty and --allow-dirty not set
- [ ] 4.5: Call check before starting orchestration (in run command)
- [ ] 4.6: Add clear error message recommending commit/stash or --allow-dirty

### 5. Write Unit Tests
- [ ] 5.1: Add tests to `tests/test_orchestrator.py` for auto-commit
- [ ] 5.2: Test commits on successful phase completion
- [ ] 5.3: Test skips commit when config.auto_commit is False
- [ ] 5.4: Test skips commit on failure when commit_on_failure is False
- [ ] 5.5: Test commits on failure when commit_on_failure is True
- [ ] 5.6: Test skips commit when no changes detected
- [ ] 5.7: Test commit message formatting with phase variables
- [ ] 5.8: Test --no-auto-commit CLI flag overrides config
- [ ] 5.9: Test dirty directory detection and warning
- [ ] 5.10: Test --allow-dirty bypasses dirty check
- [ ] 5.11: Mock git subprocess calls for consistent testing

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add auto_commit, commit_on_failure, commit_message_template fields |
| `src/debussy/orchestrator.py` | Modify | Add _auto_commit_phase() and _check_clean_working_directory() methods |
| `src/debussy/cli.py` | Modify | Add --auto-commit/--no-auto-commit and --allow-dirty flags |
| `tests/test_orchestrator.py` | Modify | Add 11+ tests for auto-commit functionality |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Config dataclass | `src/debussy/config.py` | Add new fields with sensible defaults |
| CLI options | `src/debussy/cli.py` | Use click.option with clear help text |
| Git commands | `src/debussy/orchestrator.py` | Follow existing commit patterns (heredoc for messages) |
| Subprocess calls | `src/debussy/core/compliance.py` | Safe subprocess.run() with error handling |

## Test Strategy

- [ ] Unit tests for _auto_commit_phase() with various config combinations
- [ ] Unit tests for _check_clean_working_directory() with mock git output
- [ ] Unit tests for commit message formatting
- [ ] Unit tests for CLI flag overrides
- [ ] Mock all git subprocess calls for consistent test results
- [ ] Verify no commits made when auto_commit disabled
- [ ] Verify commit content includes Co-Authored-By attribution

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure git subprocess calls match existing patterns in codebase
- Verify commit message format matches Claude Code's commit conventions

## Acceptance Criteria

**ALL must pass:**

- [ ] Config fields added (auto_commit, commit_on_failure, commit_message_template)
- [ ] _auto_commit_phase() respects all config options
- [ ] Commits only made when changes present
- [ ] Commit messages use template format with proper attribution
- [ ] CLI flags override config values correctly
- [ ] Dirty directory check warns user and prevents start
- [ ] --allow-dirty bypasses dirty check
- [ ] 11+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Auto-commit is controlled by config flag (default: true):
1. Set `auto_commit: false` in config to disable
2. Or use `--no-auto-commit` flag on run command
3. If issues found, revert orchestrator changes and remove config fields
4. Git history already created can be squashed/rebased manually

No breaking changes since feature can be disabled via config.

---

## Implementation Notes

**Commit Message Format Example:**
```
Debussy: Phase 1 - Setup Phase ✓

Co-Authored-By: Claude <opus@anthropic.com>
```

Or for partial completion:
```
Debussy: Phase 2 - Implementation ⚠️ partial

Co-Authored-By: Claude <sonnet@anthropic.com>
```

**Configuration Example:**
```yaml
# .debussy/config.yaml

# Auto-commit
auto_commit: true  # Commit at phase boundaries
commit_on_failure: false  # Only commit successful phases
commit_message_template: "Debussy: Phase {phase_id} - {phase_name} {status}"
```

**CLI Usage Examples:**
```bash
# Run with auto-commit (default)
debussy run MASTER_PLAN.md

# Run without auto-commit
debussy run MASTER_PLAN.md --no-auto-commit

# Allow dirty working directory
debussy run MASTER_PLAN.md --allow-dirty

# Commit even on failure
# (requires config change: commit_on_failure: true)
debussy run MASTER_PLAN.md
```

**Design Decisions:**
- Default auto_commit to true (most users want clean phase boundaries)
- Default commit_on_failure to false (don't pollute history with partial work)
- Use ✓ and ⚠️ in commit messages for visual clarity
- Check dirty directory before starting (prevents confusion)
- Respect git hooks (don't use --no-verify)
- Use heredoc for commit messages (matches existing patterns)