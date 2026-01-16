# Issue-to-Plan Phase 4: CLI Integration & Audit Loop

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** Phase 1, 2, 3 (Fetcher, Analyzer, Builder) - integrates all components

---

## Process Wrapper (MANDATORY)
- [ ] Read the files listed in "CRITICAL: Read These First" section below
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
- [ ] Write `notes/NOTES_phase7_issue_planner_phase_4.md` with:
  - Summary of CLI integration
  - Audit loop implementation
  - End-to-end flow diagram
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 7.4`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~66%)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **CLI patterns**: `src/debussy/cli.py` - Existing command structure
2. **Convert command**: `src/debussy/cli.py` (convert function) - Similar command pattern
3. **Audit command**: `src/debussy/cli.py` (audit function) - Audit invocation pattern
4. **Plan converter**: `src/debussy/converters/plan_converter.py` - Retry loop pattern

**DO NOT** break existing functionality. Changes should be additive.

---

## Overview

Integrate all Phase 1-3 components into a single `debussy plan-from-issues` CLI command. The command fetches issues, analyzes them, conducts Q&A, generates plans, and runs the audit loop to ensure compliance. This is the user-facing entry point that orchestrates the entire issue-to-plan pipeline.

## Dependencies
- Previous phases: Phase 1 (Fetcher), Phase 2 (Analyzer), Phase 3 (Builder)
- Internal: Compliance checker for audit loop
- External: gh CLI, Claude CLI

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Audit loop fails repeatedly | Medium | Medium | Max 3 retries; show user what's failing |
| Too many CLI flags | Low | Low | Sensible defaults; --source/--milestone minimal |
| Long execution time | Medium | Low | Progress indicators; async where possible |
| User abandons mid-Q&A | Low | Medium | Allow --skip-qa flag; save partial state |

---

## Tasks

### 1. Add CLI Command
- [ ] 1.1: Add `plan-from-issues` command to `src/debussy/cli.py`
- [ ] 1.2: Add `--source` option (gh, jira - jira reserved for future)
- [ ] 1.3: Add `--milestone` option for GH milestone filter
- [ ] 1.4: Add `--label` option for GH label filter (repeatable)
- [ ] 1.5: Add `--output-dir` option (default: plans/)
- [ ] 1.6: Add `--skip-qa` flag to skip interactive questions
- [ ] 1.7: Add `--max-retries` option (default: 3) for audit loop
- [ ] 1.8: Add `--verbose` flag for detailed output

### 2. Implement Command Handler
- [ ] 2.1: Create `src/debussy/planners/command.py` for command logic
- [ ] 2.2: Implement plan_from_issues() main function
- [ ] 2.3: Implement _fetch_phase() using github_fetcher
- [ ] 2.4: Implement _analyze_phase() using analyzer
- [ ] 2.5: Implement _qa_phase() using qa_handler (skip if --skip-qa)
- [ ] 2.6: Implement _generate_phase() using plan_builder
- [ ] 2.7: Implement _audit_loop() with retry logic
- [ ] 2.8: Implement _write_plans() to save files to output directory
- [ ] 2.9: Add progress output (Rich console for interactive mode)
- [ ] 2.10: Add summary output showing generated files and audit status

### 3. Implement Audit Loop
- [ ] 3.1: Reuse audit logic from `src/debussy/checkers/compliance.py`
- [ ] 3.2: Implement _run_audit(plan_dir) returning compliance result
- [ ] 3.3: Implement _get_audit_errors(result) to extract failure reasons
- [ ] 3.4: Implement _inject_errors_to_prompt(errors) for retry context
- [ ] 3.5: Implement retry loop: generate -> audit -> if fail, regenerate with errors
- [ ] 3.6: Add max retry limit with clear failure message

### 4. Write Tests
- [ ] 4.1: Create `tests/test_cli_plan_from_issues.py`
- [ ] 4.2: Test CLI argument parsing (all options)
- [ ] 4.3: Test _fetch_phase() with mocked fetcher
- [ ] 4.4: Test _analyze_phase() with mocked analyzer
- [ ] 4.5: Test _generate_phase() with mocked builder
- [ ] 4.6: Test _audit_loop() with mock audit results (pass and fail)
- [ ] 4.7: Test retry logic (fail twice, succeed third)
- [ ] 4.8: Test max retry exceeded behavior
- [ ] 4.9: Test --skip-qa flag skips Q&A phase
- [ ] 4.10: Integration test with fixture issues (end-to-end mock)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/cli.py` | Modify | Add plan-from-issues command |
| `src/debussy/planners/command.py` | Create | Command implementation logic |
| `tests/test_cli_plan_from_issues.py` | Create | CLI and integration tests (10+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| CLI command | `src/debussy/cli.py` (convert) | Click command with options |
| Retry loop | `src/debussy/converters/plan_converter.py` | Max retries with error injection |
| Audit invocation | `src/debussy/cli.py` (audit) | Running compliance checker |
| Progress output | `src/debussy/cli.py` (run) | Rich console for status |

## Test Strategy

- [ ] Unit tests for CLI argument parsing
- [ ] Unit tests for each pipeline phase
- [ ] Mocked tests for audit loop retry logic
- [ ] Integration test with all mocks for full flow
- [ ] Edge case tests (no issues found, all issues perfect, all audits fail)

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure all type hints are correct and pass pyright strict mode
- Manual test with real GH issues from this repo (Inception test!)

## Acceptance Criteria

**ALL must pass:**

- [ ] `debussy plan-from-issues` command added to CLI
- [ ] --source, --milestone, --label options work
- [ ] Full pipeline executes: fetch -> analyze -> Q&A -> generate -> audit
- [ ] Audit retry loop works (max 3 attempts)
- [ ] Plans written to output directory
- [ ] --skip-qa flag works
- [ ] Progress and summary output clear
- [ ] 10+ tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Phase is additive. Rollback:
1. Remove plan-from-issues command from `src/debussy/cli.py`
2. Remove `src/debussy/planners/command.py`
3. Remove `tests/test_cli_plan_from_issues.py`

No existing functionality affected.

---

## Implementation Notes

**Command Usage:**
```bash
# From GitHub milestone
debussy plan-from-issues --source gh --milestone "v2.0"

# From GitHub labels
debussy plan-from-issues --source gh --label feature --label auth

# Skip Q&A (use defaults/empty)
debussy plan-from-issues --source gh --milestone "v2.0" --skip-qa

# Custom output directory
debussy plan-from-issues --source gh --label "feature:search" --output-dir plans/search-feature
```

**Pipeline Flow:**
```
1. FETCH       gh issue list --milestone X --json ...
     │
     ▼
2. ANALYZE     Detect gaps, generate questions
     │
     ▼
3. Q&A         AskUserQuestion for missing info (unless --skip-qa)
     │
     ▼
4. GENERATE    Claude creates MASTER_PLAN.md + phase-*.md
     │
     ▼
5. AUDIT       debussy audit plans/<feature>/
     │
     ├─ PASS ──► Done! Show summary
     │
     └─ FAIL ──► Inject errors, retry (max 3)
```

**Audit Retry Prompt Injection:**
```
Previous generation failed audit with errors:
- Missing required gate: pyright
- Phase 2 has no acceptance criteria

Please fix these issues in the regenerated plan.
```

**Success Output:**
```
✓ Fetched 5 issues from milestone "v2.0"
✓ Analysis: 3 critical gaps, 2 warnings
✓ Q&A: 4 questions answered
✓ Generated: MASTER_PLAN.md + 4 phase files
✓ Audit: PASSED (attempt 1/3)

Plans written to: plans/my-feature/
  - MASTER_PLAN.md
  - phase-1.md
  - phase-2.md
  - phase-3.md
  - phase-4.md
```
