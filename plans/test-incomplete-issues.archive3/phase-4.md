# Export Plans, Better Error Messages, and Dark Mode Phase 4: Post-Implementation Validation & Documentation

**Status:** Pending
**Master Plan:** [Export Plans, Better Error Messages, and Dark Mode-MASTER_PLAN.md](export-plans-better-error-messages-and-dark-mode-MASTER_PLAN.md)
**Depends On:** [Phase 1](phase-1.md), [Phase 2](phase-2.md), [Phase 3](phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_export-plans-better-error-messages-and-dark-mode_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  
  # Security scanning
  uv run bandit -r src/
  uv run ty
  uv run semgrep --config=auto src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-better-error-messages-and-dark-mode_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- bandit: `uv run bandit -r src/` (no high severity)
- ty: `uv run ty` (passes type validation)
- semgrep: `uv run semgrep --config=auto src/` (no critical findings)
- integration: All three features work end-to-end with real plans
- documentation: User guides complete and accurate
- textual-tui-expert: `@textual-tui-expert` agent review confirms theme implementation follows best practices

---

## Overview

This phase provides comprehensive validation of all three independent features implemented in Phases 1-3, ensures they work correctly together, and delivers complete user-facing documentation. This includes integration testing across features, performance validation, documentation completeness checks, and final quality assurance before release.

## Dependencies
- Previous phase: [Phase 3](phase-3.md)
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Integration issues between features | Low | Medium | Features are independent; test isolation and interaction scenarios |
| Documentation drift from implementation | Medium | Low | Generate examples from actual working commands; validate all code snippets |
| Performance regression in TUI with themes | Low | Medium | Benchmark TUI startup and rendering times; @textual-tui-expert review |
| Incomplete test coverage for edge cases | Medium | Medium | Audit test coverage reports; add tests for boundary conditions |

---

## Tasks

### 1. Integration Testing
- [ ] 1.1: Test export command with various plan structures (simple, complex, circular dependencies)
- [ ] 1.2: Verify audit error messages appear correctly during `debussy audit` command
- [ ] 1.3: Test TUI theme switching with both light and dark modes
- [ ] 1.4: Validate all three features work when used in same session (config load, export, audit)
- [ ] 1.5: Test error handling when invalid config values provided for theme
- [ ] 1.6: Verify PDF exports pass ty and semgrep scans with zero vulnerabilities

### 2. Performance & Quality Validation
- [ ] 2.1: Benchmark PDF generation time for small (2-3 phase) and large (10+ phase) plans
- [ ] 2.2: Measure TUI startup time with custom theme vs default theme
- [ ] 2.3: Run full test suite and verify ≥95% pass rate for new feature tests
- [ ] 2.4: Generate test coverage report and ensure new code has ≥80% coverage
- [ ] 2.5: Invoke @textual-tui-expert agent to review theme implementation in `src/debussy/tui.py`

### 3. Documentation & User Guides
- [ ] 3.1: Create `docs/EXPORT.md` with export command usage, examples, and troubleshooting
- [ ] 3.2: Create `docs/AUDIT_ERRORS.md` documenting the three enhanced error cases with fixes
- [ ] 3.3: Create `docs/THEMING.md` with theme configuration examples and available options
- [ ] 3.4: Update main `README.md` with links to new feature documentation
- [ ] 3.5: Add example YAML config snippets to documentation showing theme configuration
- [ ] 3.6: Validate all documentation code examples execute successfully

### 4. Edge Case & Boundary Testing
- [ ] 4.1: Test export with empty plan (should fail gracefully with clear message)
- [ ] 4.2: Test export with plan containing special characters in filenames
- [ ] 4.3: Test audit with all three error types simultaneously in one malformed plan
- [ ] 4.4: Test theme config with invalid color values (should fall back to default)
- [ ] 4.5: Test PDF export with very long phase titles and task descriptions (pagination)
- [ ] 4.6: Test MD export preserves all markdown formatting from original plan

### 5. Release Readiness
- [ ] 5.1: Run full validation suite (ruff, pyright, pytest, bandit, ty, semgrep) and confirm zero issues
- [ ] 5.2: Manually test each feature end-to-end following user documentation
- [ ] 5.3: Generate final test coverage report and commit to repository
- [ ] 5.4: Review all three phases' implementation notes for completeness
- [ ] 5.5: Verify Success Metrics from master plan are measurable post-release

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `docs/EXPORT.md` | Create | User guide for plan export feature with MD/PDF examples |
| `docs/AUDIT_ERRORS.md` | Create | Documentation of enhanced error messages and resolution steps |
| `docs/THEMING.md` | Create | TUI theme configuration guide with examples |
| `README.md` | Modify | Add links to new feature documentation in Features section |
| `tests/integration/test_full_workflow.py` | Create | Integration tests covering all three features in combination |
| `tests/test_export_edge_cases.py` | Create | Edge case tests for export functionality |
| `tests/test_audit_error_combinations.py` | Create | Tests for multiple simultaneous audit errors |
| `tests/test_theme_validation.py` | Create | Tests for theme config validation and fallback behavior |
| `.github/workflows/ci.yml` | Modify | Add ty and semgrep to CI pipeline if not already present |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Documentation structure | `docs/CONVERT_TESTS.md` | Follow existing docs format with examples, troubleshooting, and references |
| Integration test structure | `tests/test_convert_samples.py` | Use fixtures for test plans, separate test classes for each feature area |
| CLI documentation | Existing CLI help text in `src/debussy/cli.py` | Ensure docs match actual CLI interface and flags |
| Agent invocation | `.claude/agents/textual-tui-expert.md` | Use Task tool to invoke agent for TUI review, capture output in notes |

## Test Strategy

- [ ] Unit tests: Verify individual validation functions, error message formatters, theme loaders
- [ ] Integration tests: Test feature combinations (export after audit failure, theme + export, etc.)
- [ ] End-to-end tests: Full workflow from plan creation → audit → export with custom theme
- [ ] Performance tests: Benchmark export times, TUI rendering times, memory usage
- [ ] Security tests: ty and semgrep scans on PDF library usage and file I/O operations
- [ ] Manual testing: Follow documentation guides as a new user would

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, ty, semgrep)
- [ ] Integration tests written and passing (≥95% pass rate)
- [ ] Test coverage ≥80% for all new code
- [ ] All three documentation files created and validated
- [ ] README.md updated with feature links
- [ ] @textual-tui-expert agent review completed with no critical issues
- [ ] Manual end-to-end test of each feature completed successfully
- [ ] No security vulnerabilities in PDF generation (ty + semgrep clean)
- [ ] Performance benchmarks recorded in implementation notes

## Rollback Plan

This phase only adds tests and documentation, so rollback is low-risk:

1. **Documentation rollback**: Revert commits to `docs/` directory
   ```bash
   git checkout HEAD~1 -- docs/EXPORT.md docs/AUDIT_ERRORS.md docs/THEMING.md
   git checkout HEAD~1 -- README.md
   ```

2. **Test rollback**: Remove new test files if they cause CI failures
   ```bash
   git rm tests/integration/test_full_workflow.py
   git rm tests/test_*_edge_cases.py
   ```

3. **CI rollback**: If ty/semgrep break CI, comment out in `.github/workflows/ci.yml` temporarily

4. **No feature code changes**: This phase doesn't modify feature implementation, so no functional rollback needed

---

## Implementation Notes

**Integration Testing Focus:**
- Test features in isolation first, then in combination
- Pay special attention to config loading order (theme config must not interfere with export paths)
- Validate that audit error messages appear in both TUI and non-interactive modes

**Documentation Strategy:**
- Include working code examples that can be copy-pasted
- Add troubleshooting sections for common issues (PDF library not found, theme config syntax errors)
- Link to related Debussy concepts (master plans, audit system, config schema)

**Performance Baselines:**
- Establish baseline metrics for comparison in future releases
- Document any performance trade-offs (e.g., PDF generation slower than MD)

**Agent Review Notes:**
- @textual-tui-expert should validate theme application doesn't block main thread
- Ensure CSS changes follow Textual best practices
- Verify theme switching doesn't cause memory leaks or widget lifecycle issues
