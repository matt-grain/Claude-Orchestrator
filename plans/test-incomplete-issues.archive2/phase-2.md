# Better Error Messages Phase 2: Improve error messages with actionable guidance

**Status:** Pending
**Master Plan:** [better-error-messages-MASTER_PLAN.md](better-error-messages-MASTER_PLAN.md)
**Depends On:** [Phase 1: Analyze current error messages and categorize failure modes](phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_better_error_messages_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_better_error_messages_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- ty: `uv run ty check src/` (0 errors)
- semgrep: `uv run semgrep --config=auto src/` (0 high severity)

---

## Overview

This phase implements enhanced error messaging for the three most common audit failure cases: circular dependencies, missing references, and missing data. Each error will include clear, actionable guidance on what needs to be changed and where to find the issue in the source plans. This builds on the analysis from Phase 1 to provide concrete fixes that improve the developer experience.

## Dependencies
- Previous phase: [Phase 1: Analyze current error messages and categorize failure modes](phase-1.md)
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Error messages become too verbose and hard to read | Medium | Medium | Design concise format with optional --verbose flag for details |
| Complex audit failures may have multiple root causes | High | Medium | Prioritize the most actionable issue first, list others as secondary |
| Line number references may be off if plans are edited | Low | Medium | Include context snippets in addition to line numbers |

---

## Tasks

### 1. Error Message Infrastructure
- [ ] 1.1: Create structured error classes with actionable guidance fields
- [ ] 1.2: Add error formatter that outputs user-friendly messages with fix suggestions
- [ ] 1.3: Implement context extraction to show relevant plan snippets in errors

### 2. Circular Dependency Detection Enhancement
- [ ] 2.1: Update dependency parser to track the full dependency chain
- [ ] 2.2: Implement cycle detection that shows the complete circular path (e.g., Phase 1 → Phase 3 → Phase 2 → Phase 1)
- [ ] 2.3: Add actionable guidance: "Remove the dependency from Phase X to Phase Y" with file and line reference
- [ ] 2.4: Include visualization of the dependency graph in verbose mode

### 3. Missing Reference Detection Enhancement
- [ ] 3.1: Enhance reference validation to identify what type of reference is missing (agent, file, dependency, etc.)
- [ ] 3.2: Add suggestions for valid references based on context (e.g., "Did you mean '@python-task-validator'?")
- [ ] 3.3: Include file path and line number where the invalid reference appears
- [ ] 3.4: Provide examples of correct reference formats in the error message

### 4. Missing Data Detection Enhancement
- [ ] 4.1: Categorize missing data types (required sections, mandatory fields, empty values)
- [ ] 4.2: Add specific guidance for each missing data type with template examples
- [ ] 4.3: Include the expected format/schema for missing fields
- [ ] 4.4: Show diff between current state and required state when applicable

### 5. Testing and Validation
- [ ] 5.1: Create test fixtures for each error type with known issues
- [ ] 5.2: Write unit tests verifying error messages contain actionable guidance
- [ ] 5.3: Add integration tests that validate error messages against real plan failures
- [ ] 5.4: Test error message readability with sample plans from Phase 1 analysis

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/errors/__init__.py` | Create | New errors module for structured error classes |
| `src/debussy/errors/audit_errors.py` | Create | Specific error classes for circular deps, missing refs, missing data |
| `src/debussy/errors/formatter.py` | Create | Error formatter with actionable guidance rendering |
| `src/debussy/parsers/dependency.py` | Modify | Add cycle detection with full path tracking |
| `src/debussy/validators/audit.py` | Modify | Integrate new error classes with enhanced messaging |
| `src/debussy/validators/reference_validator.py` | Modify | Add suggestion logic for missing/invalid references |
| `src/debussy/validators/schema_validator.py` | Modify | Add detailed missing data guidance with examples |
| `tests/test_audit_errors.py` | Create | Unit tests for error classes and formatting |
| `tests/test_error_guidance.py` | Create | Integration tests for actionable error messages |
| `tests/fixtures/error_plans/` | Create | Sample plans with known errors for testing |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Structured Error Classes | `src/debussy/errors/` (existing error patterns in codebase) | Use inheritance from base AuditError with required actionable_guidance field |
| Context Extraction | `src/debussy/parsers/phase.py` | Follow existing pattern for extracting line numbers and context from markdown |
| Validator Integration | `src/debussy/validators/audit.py` | Maintain existing validator interface while enhancing error return types |
| Test Fixtures | `tests/fixtures/sample_plans/` | Follow established pattern for creating test plans with known issues |

## Test Strategy

- [ ] Unit tests for error class creation and field validation
- [ ] Unit tests for error formatter output in various scenarios
- [ ] Unit tests for cycle detection algorithm with different graph structures
- [ ] Integration tests for audit command with plans containing each error type
- [ ] Regression tests ensuring existing valid plans still pass audit
- [ ] Manual testing: Run audit on Phase 1 documented error cases and verify guidance quality

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, ty, semgrep)
- [ ] Tests written and passing (minimum 90% coverage for new error modules)
- [ ] Documentation updated in docs/AUDIT.md with error message examples
- [ ] No security vulnerabilities introduced
- [ ] For circular dependency errors: message includes full cycle path and specific fix suggestion
- [ ] For missing reference errors: message includes line number, context, and valid alternatives
- [ ] For missing data errors: message includes expected schema/format and example
- [ ] Manual validation: Each error type tested with sample plans shows clear, actionable guidance

## Rollback Plan

If enhanced error messaging causes issues:

1. Revert commits for this phase using git:
   ```bash
   git revert <phase-2-commits>
   ```

2. Remove new error modules:
   ```bash
   rm -rf src/debussy/errors/
   ```

3. Restore original validator files from Phase 1 completion:
   ```bash
   git checkout HEAD~<n> -- src/debussy/validators/
   git checkout HEAD~<n> -- src/debussy/parsers/dependency.py
   ```

4. Run full test suite to ensure stability:
   ```bash
   uv run pytest tests/ -v
   ```

5. If partial rollback needed: Keep infrastructure (`src/debussy/errors/`) but disable enhanced messaging in validators by adding feature flag `use_enhanced_errors=False` in config

---

## Implementation Notes

**Key Design Decisions:**
- Error messages should follow the pattern: "Problem → Location → Fix"
- Use ANSI colors for terminal output (red for errors, yellow for warnings, green for suggestions)
- Implement `--verbose` flag for detailed debugging information (dependency graphs, full traces)
- Store error guidance templates in structured format for easy maintenance and i18n future-proofing

**Performance Considerations:**
- Context extraction should be lazy-loaded only when formatting errors for display
- Cycle detection algorithm should use memoization to avoid redundant graph traversals
- Consider caching parsed plan structure if audit is run multiple times

**Future Extensions:**
- Phase 3 will add suggestions for fixes based on common patterns
- Consider adding machine-readable error codes for programmatic error handling
- Potential for LLM-based error analysis for complex multi-issue failures
