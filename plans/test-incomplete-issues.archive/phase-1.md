# diagnostics-improvements Phase 1: Enhanced diagnostics for circular dependency, missing reference, and missing data errors

**Status:** Pending
**Master Plan:** [diagnostics-improvements-MASTER_PLAN.md](diagnostics-improvements-MASTER_PLAN.md)
**Depends On:** N/A (First phase)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (First phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_diagnostics_improvements_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity issues)

---

## Overview

This phase enhances error diagnostics for three critical error types that users frequently encounter: circular dependencies, missing references, and missing data errors. Currently, these errors produce generic messages that don't help users identify the root cause or resolution path. We'll implement rich contextual error messages with actionable suggestions, file locations, and visual representations where helpful.

## Dependencies
- Previous phase: N/A (First phase)
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing error handling | Medium | High | Add new error classes alongside existing ones; maintain backward compatibility |
| Performance impact from detailed diagnostics | Low | Low | Only compute detailed context when errors occur (not on happy path) |
| Inconsistent error format across error types | Medium | Medium | Create shared ErrorContext base class and formatter utilities |

---

## Tasks

### 1. Error Context Infrastructure
- [ ] 1.1: Create `src/debussy/errors/context.py` with ErrorContext base class
- [ ] 1.2: Implement ErrorFormatter utility for consistent rich output
- [ ] 1.3: Add error context helpers (extract file locations, format suggestions, create snippets)

### 2. Circular Dependency Diagnostics
- [ ] 2.1: Enhance circular dependency detection in `src/debussy/parsers/phase.py`
- [ ] 2.2: Create CircularDependencyError with full cycle path visualization
- [ ] 2.3: Add suggestion engine for breaking cycles (remove dependency, reorder phases, split phase)
- [ ] 2.4: Update tests in `tests/test_parsers.py` for new error format

### 3. Missing Reference Diagnostics
- [ ] 3.1: Enhance reference validation in dependency parser
- [ ] 3.2: Create MissingReferenceError with "did you mean?" suggestions using fuzzy matching
- [ ] 3.3: Include available valid references in error message
- [ ] 3.4: Add file location and line number context

### 4. Missing Data Diagnostics
- [ ] 4.1: Identify all missing data error locations (plan parsing, config loading, state validation)
- [ ] 4.2: Create MissingDataError with field name, expected type, and example values
- [ ] 4.3: Add validation context (which file, which section, what was being parsed)
- [ ] 4.4: Include template snippets showing correct format

### 5. Integration and Testing
- [ ] 5.1: Update existing error throw sites to use new error classes
- [ ] 5.2: Add comprehensive error message tests
- [ ] 5.3: Create example error outputs in documentation
- [ ] 5.4: Update CLI error handler to use rich formatting

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/errors/__init__.py` | Modify | Export new error classes |
| `src/debussy/errors/context.py` | Create | ErrorContext base class and formatter utilities |
| `src/debussy/errors/diagnostics.py` | Create | CircularDependencyError, MissingReferenceError, MissingDataError classes |
| `src/debussy/parsers/phase.py` | Modify | Enhanced circular dependency detection with context |
| `src/debussy/parsers/master.py` | Modify | Add missing reference validation with suggestions |
| `src/debussy/parsers/base.py` | Modify | Add missing data validation with examples |
| `src/debussy/cli.py` | Modify | Update error handler to format rich diagnostic output |
| `tests/test_error_diagnostics.py` | Create | Comprehensive error message and formatting tests |
| `tests/test_parsers.py` | Modify | Update tests for new error formats |
| `docs/ERROR_DIAGNOSTICS.md` | Create | Documentation with example error outputs |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Error class hierarchy | `src/debussy/errors/__init__.py` | Inherit from DebussyError base class |
| Rich text formatting | `src/debussy/tui.py` | Use rich.console for colored, formatted output |
| Fuzzy string matching | Python `difflib.get_close_matches()` | Implement "did you mean?" suggestions |
| Parser error context | `src/debussy/parsers/phase.py` | Include file path, line number, and surrounding context |

## Test Strategy

- [ ] Unit tests for ErrorContext and ErrorFormatter utilities
- [ ] Unit tests for each error class with various scenarios
- [ ] Integration tests for parser error detection and formatting
- [ ] Manual testing: Create plans with intentional errors and verify output
- [ ] Regression tests: Ensure existing error handling still works
- [ ] Visual verification: Review terminal output for readability and clarity

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing
- [ ] Tests written and passing (minimum 90% coverage for new error modules)
- [ ] Documentation updated with example error outputs
- [ ] No security vulnerabilities introduced
- [ ] Manual testing confirms error messages are actionable and clear
- [ ] Backward compatibility maintained for existing error handling

## Rollback Plan

Since this phase only adds new error classes and enhances existing diagnostics without changing core logic:

1. **If errors are too verbose:** Add `--verbose-errors` flag to CLI and default to simpler messages
2. **If breaking changes occur:** Revert commits in reverse order:
   ```bash
   git log --oneline --grep="Phase 1: Enhanced diagnostics"
   git revert <commit-hash>...
   ```
3. **Database/State:** No state changes in this phase - safe to revert
4. **Dependencies:** No new external dependencies added - safe to revert

---

## Implementation Notes

### Circular Dependency Visualization
Consider ASCII art representation of dependency cycles:
```
Phase 1 → Phase 2 → Phase 3
  ↑                    ↓
  └────────────────────┘
```

### Fuzzy Matching Threshold
Use 0.6 similarity threshold for "did you mean?" suggestions (configurable).

### Error Message Philosophy
Follow the pattern: **What went wrong → Why it matters → How to fix it**

### Performance Considerations
Only compute detailed context (file reading, fuzzy matching) when errors actually occur. Keep happy path fast.
