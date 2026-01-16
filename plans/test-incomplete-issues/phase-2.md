# Export Plans & UX Improvements Phase 2: Enhanced Audit Diagnostics

**Status:** Pending
**Master Plan:** [export-plans-ux-improvements-MASTER_PLAN.md](export-plans-ux-improvements-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (independent phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  uv run radon cc src/ -a
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-ux-improvements_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- complexity: `uv run radon cc src/ -a` (maintainability index acceptable)

---

## Overview

This phase enhances the audit command's error reporting to provide actionable diagnostic messages for the three most common audit failures: circular dependencies, missing references, and missing data. Instead of generic error messages, users will receive clear guidance on what to fix and where to fix it, dramatically reducing time spent debugging plan issues.

## Dependencies
- Previous phase: N/A (independent)
- External: None

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking changes to existing audit error format | Low | Medium | Ensure new diagnostics extend (not replace) existing messages; version error schemas if needed |
| Performance regression on large plans | Low | Low | Keep diagnostic logic lightweight; only compute details when errors are found |
| False positive suggestions | Medium | Medium | Thoroughly test diagnostic logic with real broken plans; include edge case tests |

---

## Tasks

### 1. Analyze Current Audit Error Messages
- [ ] 1.1: Review `src/debussy/audit/` module to understand current error detection logic
- [ ] 1.2: Document existing error message formats for circular dependencies, missing references, missing data
- [ ] 1.3: Create test fixtures with deliberately broken plans for each error type
- [ ] 1.4: Identify what additional context is needed to make errors actionable

### 2. Implement Enhanced Diagnostic System
- [ ] 2.1: Create `src/debussy/audit/diagnostics.py` with diagnostic message builder functions
- [ ] 2.2: Implement circular dependency diagnostic (show full cycle path with phase IDs and file locations)
- [ ] 2.3: Implement missing reference diagnostic (show which phase references what, where it should be defined)
- [ ] 2.4: Implement missing data diagnostic (show which required fields are empty, provide examples)
- [ ] 2.5: Add helper function to format file locations (path:line) for easy navigation

### 3. Integrate Diagnostics into Audit Output
- [ ] 3.1: Modify audit error reporting in `src/debussy/audit/compliance.py` to use diagnostic builders
- [ ] 3.2: Add structured error output mode (for programmatic consumption) alongside human-readable format
- [ ] 3.3: Include "How to Fix" section in each enhanced error message
- [ ] 3.4: Add color coding for error types in TUI/CLI output (red for errors, yellow for suggestions)

### 4. Create Documentation and Examples
- [ ] 4.1: Write `docs/AUDIT_ERRORS.md` with common failure patterns and solutions
- [ ] 4.2: Include before/after examples of error messages
- [ ] 4.3: Add troubleshooting flowchart for audit failures
- [ ] 4.4: Document how to read enhanced diagnostic output

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/audit/diagnostics.py` | Create | Diagnostic message builder functions for common audit failures |
| `src/debussy/audit/compliance.py` | Modify | Integrate enhanced diagnostics into existing audit error reporting |
| `src/debussy/parsers/phase.py` | Modify | Add line number tracking for better error location reporting |
| `src/debussy/parsers/master.py` | Modify | Add line number tracking for master plan elements |
| `tests/test_audit_diagnostics.py` | Create | Comprehensive tests for diagnostic message generation |
| `tests/fixtures/broken_plans/` | Create | Test fixtures with circular dependencies, missing refs, missing data |
| `docs/AUDIT_ERRORS.md` | Create | User-facing documentation for audit error troubleshooting |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Error message formatting | `src/debussy/cli.py` (existing error output) | Maintain consistent error display style |
| Line tracking in parsers | `src/debussy/parsers/phase.py` | Extend existing parsing to capture line numbers |
| Test fixture organization | `tests/fixtures/sample_plans/` | Follow existing fixture structure for broken plan examples |
| Rich console formatting | `src/debussy/tui/tui.py` | Use Rich library for colored diagnostic output |

## Test Strategy

- [ ] Unit tests for each diagnostic builder function (circular deps, missing refs, missing data)
- [ ] Integration tests for audit command with broken plan fixtures
- [ ] Regression tests to ensure existing valid plans still pass audit
- [ ] Edge case tests: empty plans, malformed YAML, deeply nested circular dependencies
- [ ] Manual testing: Run audit on real broken plans from previous debugging sessions

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing
- [ ] Circular dependency errors show full cycle path with file:line locations
- [ ] Missing reference errors identify both the referencing phase and expected location
- [ ] Missing data errors list all required fields and provide valid examples
- [ ] Each error message includes a "How to Fix" section
- [ ] `docs/AUDIT_ERRORS.md` created with common failure patterns
- [ ] Tests written and passing (>80% coverage for diagnostics module)
- [ ] No security vulnerabilities introduced
- [ ] Validated with deliberately broken plans from test fixtures

## Rollback Plan

If enhanced diagnostics cause issues:
1. Revert changes to `src/debussy/audit/compliance.py` to restore original error messages
2. Remove or comment out imports of `diagnostics.py` module
3. Keep `docs/AUDIT_ERRORS.md` (documentation is harmless even if code is rolled back)
4. Tag this commit before deployment: `git tag pre-enhanced-diagnostics-v0.x.x`
5. Rollback command: `git revert <commit-hash>` for surgical revert of diagnostic integration

---

## Implementation Notes

**Key Design Decisions:**
- Diagnostics are additive, not replacements - existing error messages remain, enhanced messages provide additional context
- Line number tracking is essential for actionable errors - parsers need lightweight modification to capture source locations
- Structured error output (JSON) enables future IDE integration or CI tooling
- "How to Fix" sections should reference docs/AUDIT_ERRORS.md for detailed guidance

**Circular Dependency Detection Enhancement:**
- Current implementation likely uses graph traversal - enhance to return full cycle path, not just "cycle detected"
- Format: `Phase 2 → Phase 4 → Phase 6 → Phase 2` with file locations for each dependency declaration

**Missing Reference Context:**
- Track not just "Phase X not found" but "Phase 3 references Phase X in section Y (line Z), but Phase X does not exist in master plan"

**Missing Data Examples:**
- For required fields like Gates, provide valid example syntax: `- lint: uv run ruff check . (0 errors)`
