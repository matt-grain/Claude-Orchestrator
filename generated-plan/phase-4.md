# Issue-to-Plan Generator Phase 4: CLI Integration and Audit Loop

**Status:** Pending
**Master Plan:** [issue-to-plan-MASTER_PLAN.md](issue-to-plan-MASTER_PLAN.md)
**Depends On:** [Phase 3: Interactive Plan Builder](phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue_to_plan_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue_to_plan_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all tests pass)
- security: `uv run bandit -r src/debussy/planners/` (no high severity issues)

---

## Overview

This phase integrates all pipeline components (fetcher, analyzer, builder) into a single `debussy plan-from-issues` CLI command with automated audit validation. The command orchestrates the full workflow: fetch issues → analyze quality → conduct Q&A → generate plans → audit compliance → retry if needed. This provides a seamless end-to-end experience for converting GitHub issues into production-ready Debussy plans.

## Dependencies
- Previous phase: [Phase 3: Interactive Plan Builder](phase-3.md)
- External: 
  - `gh` CLI installed and authenticated
  - `claude` CLI available for plan generation
  - Existing `debussy audit` command for compliance checking

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Audit loop infinite retry on persistent compliance failures | Medium | High | Enforce max 3 attempts with clear error messaging and partial output preservation |
| User abandons interactive Q&A mid-session | Medium | Medium | Add --skip-qa flag for non-interactive mode, save progress checkpoints |
| Generated plans fail audit due to Claude output variance | High | Medium | Inject detailed audit errors into retry prompt, use existing conversion patterns |
| gh CLI authentication failure in CI/CD environments | Low | High | Detect auth early with clear error message, document GH_TOKEN setup |

---

## Tasks

### 1. CLI Command Definition
- [ ] 1.1: Add `plan-from-issues` command to `src/debussy/cli.py` with Click decorator
- [ ] 1.2: Define options: `--source` (github/jira), `--milestone`, `--label`, `--output-dir`, `--skip-qa`, `--max-retries`
- [ ] 1.3: Add `--model` option (opus/sonnet/haiku) with sonnet default
- [ ] 1.4: Implement early validation for gh CLI availability and authentication

### 2. Pipeline Orchestrator
- [ ] 2.1: Create `src/debussy/planners/command.py` with `PlanFromIssuesCommand` class
- [ ] 2.2: Implement `execute()` method orchestrating: fetch → analyze → qa → build → audit
- [ ] 2.3: Add progress reporting using Rich console for each pipeline stage
- [ ] 2.4: Implement state preservation for partial failures (save fetched issues, analysis results)

### 3. Audit Loop Integration
- [ ] 3.1: Import existing compliance checker from `src/debussy/compliance/checker.py`
- [ ] 3.2: Implement `_audit_generated_plans()` method running audit on output directory
- [ ] 3.3: Build retry loop with max attempts (default 3) using `--max-retries` option
- [ ] 3.4: On audit failure, inject compliance errors into PlanBuilder retry prompt
- [ ] 3.5: Track attempt count and display clear success/failure summary

### 4. Non-Interactive Mode
- [ ] 4.1: Implement `--skip-qa` flag bypassing interactive Q&A session
- [ ] 4.2: Add warning when skipping Q&A with low-quality issues detected
- [ ] 4.3: Generate plans with placeholder sections when gaps exist and Q&A skipped

### 5. Testing
- [ ] 5.1: Create `tests/test_cli_plan_from_issues.py` with 10+ test cases
- [ ] 5.2: Mock gh CLI subprocess calls and responses
- [ ] 5.3: Test full pipeline with mocked Claude responses
- [ ] 5.4: Test audit retry loop with failing then passing compliance
- [ ] 5.5: Test --skip-qa mode and --max-retries limits
- [ ] 5.6: Add integration test using real v0.5.0 milestone issues (inception test)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/command.py` | Create | Pipeline orchestrator class coordinating fetch/analyze/build/audit |
| `src/debussy/cli.py` | Modify | Add `plan-from-issues` Click command with options |
| `tests/test_cli_plan_from_issues.py` | Create | Comprehensive test suite with 10+ test cases |
| `tests/fixtures/issues/v0_5_0_milestone.json` | Create | Sample issue data from v0.5.0 milestone for inception test |
| `docs/PLAN_FROM_ISSUES.md` | Create | User guide for new command with examples |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Subprocess-based Claude invocation | `src/debussy/converters/plan_converter.py` | Use same pattern for PlanBuilder subprocess calls |
| Audit retry loop with error injection | `src/debussy/converters/plan_converter.py:_convert_with_retry()` | Inject compliance errors into retry prompt, max 3 attempts |
| Click command structure | `src/debussy/cli.py` existing commands | Follow existing patterns for options, help text, error handling |
| Rich console progress | `src/debussy/tui.py` | Use Rich Status/Progress for pipeline stage updates |
| Dataclass-based state | `src/debussy/planners/analyzer.py` | Use dataclasses for command state and results |

## Test Strategy

- [ ] Unit tests for PlanFromIssuesCommand class methods (mocked dependencies)
- [ ] Integration tests for full pipeline with mocked gh/claude subprocesses
- [ ] Parametrized tests for option combinations (--skip-qa, --max-retries, --model)
- [ ] Error path tests (gh auth failure, audit failures, max retries exceeded)
- [ ] Regression test using real v0.5.0 milestone issues (inception test - generates plan from own issues)
- [ ] Manual testing checklist:
  - [ ] Run on v0.5.0 milestone: `debussy plan-from-issues --milestone v0.5.0 --output-dir test-plans/`
  - [ ] Verify interactive Q&A prompts appear and work
  - [ ] Test --skip-qa mode generates valid plans
  - [ ] Confirm audit loop retries on compliance failure
  - [ ] Validate generated plans pass `debussy audit`

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] 10+ tests written and passing
- [ ] Command works: `debussy plan-from-issues --milestone v0.5.0`
- [ ] Filters work: `--milestone`, `--label` options filter correctly
- [ ] Full pipeline executes: fetch → analyze → Q&A → generate → audit
- [ ] Audit retry loop with max 3 attempts implemented
- [ ] `--skip-qa` flag bypasses interactive Q&A
- [ ] Plans written to output directory with correct structure
- [ ] Documentation updated in docs/PLAN_FROM_ISSUES.md
- [ ] No security vulnerabilities introduced
- [ ] Inception test passes: command successfully generates plan from v0.5.0 milestone issues

## Rollback Plan

If critical issues are discovered:

1. **Revert CLI command registration:**
   ```bash
   git revert <commit-hash>  # Revert cli.py changes
   ```

2. **Remove new module:**
   ```bash
   rm src/debussy/planners/command.py
   rm tests/test_cli_plan_from_issues.py
   ```

3. **Restore previous CLI state:**
   ```bash
   git checkout HEAD~1 src/debussy/cli.py
   uv run pytest tests/test_cli.py -v  # Verify existing commands still work
   ```

4. **Clean up any generated test artifacts:**
   ```bash
   rm -rf test-plans/
   rm tests/fixtures/issues/v0_5_0_milestone.json
   ```

5. **Verify rollback success:**
   ```bash
   debussy --help  # Should not show plan-from-issues command
   uv run pytest tests/ -v  # All existing tests pass
   ```

No database migrations or persistent state to revert - command is stateless except for output files.

---

## Implementation Notes

**Architectural Decisions:**

1. **Subprocess vs API SDK:** Following existing pattern from `plan_converter.py`, use subprocess calls to `gh` and `claude` CLIs rather than API SDKs. This maintains consistency and leverages existing authentication.

2. **Audit Integration:** Reuse existing compliance checker rather than duplicating validation logic. The checker already has comprehensive phase/master plan validation.

3. **Error Recovery:** On audit failure, preserve generated plans in `<output-dir>/.failed/` directory so users can inspect and manually fix if needed.

4. **Progress Reporting:** Use Rich Status context manager for each pipeline stage to provide clear feedback without verbose logging.

5. **Inception Test Value:** The v0.5.0 milestone inception test (generating a plan from the issues that define this feature) serves as both validation and dogfooding - if it works, we can use the generated plan to guide implementation!

**Performance Considerations:**

- Batch issue fetching with single `gh issue list` call rather than per-issue requests
- Cache analysis results to avoid re-analyzing on audit retry
- Stream Claude output during plan generation for responsiveness

**Future Enhancements (out of scope for this phase):**

- Jira integration using Atlassian MCP server
- Plan templates selection (--template flag)
- Parallel phase generation for large issue sets
- Git branch creation with generated plans
