# Enhanced Audit Error Messages Phase 2: Improved Error Diagnostics

**Status:** Pending
**Master Plan:** [export-plans-better-error-messages-and-dark-mode-MASTER_PLAN.md](export-plans-better-error-messages-and-dark-mode-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase, no prior notes)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  
  # Security scanning
  uv run bandit -r src/
  uv run radon cc src/ -a
  uv run ty
  uv run semgrep --config auto src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-better-error-messages-and-dark-mode_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- bandit: `uv run bandit -r src/` (no high severity)
- radon: `uv run radon cc src/ -a` (maintainability index acceptable)
- ty: `uv run ty` (0 type errors)
- semgrep: `uv run semgrep --config auto src/` (0 critical/high findings)

---

## Overview

This phase enhances Debussy's audit error messages to provide clear, actionable guidance for the three most common failure cases: circular dependencies, missing references, and missing data. Currently, audit failures can be cryptic and difficult to diagnose. By adding structured error messages with specific fix recommendations, users will be able to quickly identify and resolve plan validation issues.

## Dependencies
- Previous phase: N/A (independent phase)
- External: None

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Error messages become too verbose | Low | Low | Keep messages concise, focus only on the 3 specified cases |
| False positive fix suggestions | Medium | Medium | Validate suggestions against test fixtures; iterate based on user feedback |
| Breaking existing error handling | Low | Medium | Add new error classes alongside existing ones; ensure backward compatibility |

---

## Tasks

### 1. Design Enhanced Error Message Structure
- [ ] 1.1: Define error message format (problem description, affected location, suggested fix, example)
- [ ] 1.2: Create error message templates for circular dependencies, missing references, and missing data
- [ ] 1.3: Document error message guidelines in `docs/AUDIT_ERRORS.md`

### 2. Implement Enhanced Error Classes
- [ ] 2.1: Create `CircularDependencyError` with cycle path visualization
- [ ] 2.2: Create `MissingReferenceError` with suggestion for valid reference format
- [ ] 2.3: Create `MissingDataError` with list of required fields and current values
- [ ] 2.4: Add helper methods for generating actionable fix suggestions

### 3. Integrate Error Messages into Audit Logic
- [ ] 3.1: Update compliance checker to use new error classes
- [ ] 3.2: Enhance dependency validator to detect and report circular dependencies with path
- [ ] 3.3: Update reference validator to report missing references with context
- [ ] 3.4: Modify data validator to list missing required fields clearly

### 4. Add Tests and Validation
- [ ] 4.1: Create test fixtures for each of the 3 common failure cases
- [ ] 4.2: Write unit tests for each enhanced error class
- [ ] 4.3: Write integration tests verifying error messages appear in audit output
- [ ] 4.4: Validate error message clarity with manual review

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/audit/errors.py` | Create | Define enhanced error classes with actionable messages |
| `src/debussy/audit/compliance.py` | Modify | Integrate new error classes into audit logic |
| `src/debussy/audit/validators.py` | Modify | Update validators to use enhanced error reporting |
| `docs/AUDIT_ERRORS.md` | Create | Document common error patterns and fix guidance |
| `tests/test_audit_errors.py` | Create | Test suite for enhanced error messages |
| `tests/fixtures/invalid_plans/` | Create | Test fixtures for circular deps, missing refs, missing data |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Exception hierarchy | `src/debussy/audit/exceptions.py` | Extend existing exception base classes |
| Validation error structure | `src/debussy/audit/compliance.py` | Follow existing ValidationResult pattern |
| Test fixture organization | `tests/fixtures/sample_plans/` | Mirror structure for invalid plan fixtures |

## Test Strategy

- [ ] Unit tests for each new error class with various input scenarios
- [ ] Integration tests that trigger each error type during audit and verify message content
- [ ] Regression tests ensuring existing error handling still works
- [ ] Manual testing checklist:
  - [ ] Create plan with circular dependency (A→B→C→A), verify error shows cycle path
  - [ ] Create plan with invalid phase reference, verify error suggests valid format
  - [ ] Create plan missing required field (e.g., Depends On), verify error lists missing fields

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, radon, ty, semgrep)
- [ ] Tests written and passing (>80% coverage for new code)
- [ ] `docs/AUDIT_ERRORS.md` created with examples of all 3 error types
- [ ] No security vulnerabilities introduced
- [ ] Error messages are concise (<5 lines per error) and actionable
- [ ] Manual testing confirms error messages clearly indicate fix steps

## Rollback Plan

If issues arise with the enhanced error messages:

1. **Immediate rollback**: Revert `src/debussy/audit/compliance.py` and `src/debussy/audit/validators.py` to previous commit
2. **Partial rollback**: Keep new error classes in `errors.py` but disable their use in validators (fallback to generic exceptions)
3. **Data preservation**: No database or state changes in this phase - rollback is code-only
4. **Verification**: Run full test suite after rollback to ensure no regressions

---

## Implementation Notes

### Error Message Format

Each enhanced error should follow this structure:
```
[ERROR_TYPE] Problem description

Location: path/to/file.md:line_number
Issue: Specific problem found

Fix: Actionable step to resolve

Example:
  [correct syntax or structure]
```

### Circular Dependency Detection

Use graph traversal (DFS) to detect cycles and format path as:
```
Circular dependency detected:
  Phase 1 → Phase 3 → Phase 5 → Phase 1
```

### Missing Reference Format

Provide both the invalid reference and the expected format:
```
Invalid phase reference: "Phase Three"
Expected format: "Phase 3" or "[Phase 3](phase-3.md)"
```

### Missing Data Reporting

List all missing required fields with current state:
```
Missing required fields in Phase 2:
  - Depends On: (not specified)
  - Status: (not specified)
Found: Title, Overview, Tasks
```
