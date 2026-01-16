# Issue-to-Plan Generator Phase 3: Interactive Plan Builder

**Status:** Pending
**Master Plan:** [issue-to-plan-MASTER_PLAN.md](issue-to-plan-MASTER_PLAN.md)
**Depends On:** [Phase 2: Issue Analyzer and Gap Detection](phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue-to-plan_phase_2.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue-to-plan_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/debussy/planners/` (0 high severity)

---

## Overview

This phase implements the plan generation layer of the issue-to-plan pipeline. After analyzing issues and identifying gaps (Phase 2), we need to generate Debussy-compliant plan documents. This includes conducting interactive Q&A sessions to fill gaps, then using Claude to generate master plans and phase files that conform to Debussy's template structure.

The implementation uses the existing Debussy templates as the single source of truth, ensuring generated plans are audit-compliant from the start.

## Dependencies
- Previous phase: [Phase 2: Issue Analyzer and Gap Detection](phase-2.md)
- External: 
  - Claude CLI (authenticated)
  - src/debussy/resources/templates/ (existing templates)
  - src/debussy/converters/prompts.py (pattern reference)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Generated plans fail audit | Medium | High | Include template structure in prompts, test with actual audit checker |
| Claude unavailable or unauthenticated | Low | High | Error handling with clear user guidance, check auth before generation |
| User fatigue with Q&A sessions | Medium | Medium | Batch questions (max 4), allow skipping optional questions, clear progress indicators |
| Question phrasing ambiguity | Medium | Medium | Include examples in prompts, provide context from issue analysis |

---

## Tasks

### 1. Create Q&A Handler Module
- [ ] 1.1: Create `src/debussy/planners/qa_handler.py` with QAHandler class
- [ ] 1.2: Implement question batching (max 4 questions per batch)
- [ ] 1.3: Add skip functionality for optional questions
- [ ] 1.4: Format questions with context from AnalysisReport
- [ ] 1.5: Store user answers in structured format for prompt injection

### 2. Create Claude Prompt Templates
- [ ] 2.1: Create `src/debussy/planners/prompts.py` module
- [ ] 2.2: Add MASTER_PLAN_PROMPT template with issue context injection
- [ ] 2.3: Add PHASE_PLAN_PROMPT template with Debussy structure requirements
- [ ] 2.4: Include example snippets from existing templates in prompts
- [ ] 2.5: Add prompt helpers for formatting issues, answers, and templates

### 3. Implement PlanBuilder Core
- [ ] 3.1: Create `src/debussy/planners/plan_builder.py` with PlanBuilder class
- [ ] 3.2: Add template loading from `src/debussy/resources/templates/`
- [ ] 3.3: Implement Claude subprocess invocation for plan generation
- [ ] 3.4: Add master plan generation with issue aggregation
- [ ] 3.5: Add phase plan generation (one per phase)
- [ ] 3.6: Write generated plans to output directory

### 4. Integration and Error Handling
- [ ] 4.1: Integrate AnalysisReport and QAHandler outputs into prompts
- [ ] 4.2: Add error handling for Claude CLI failures
- [ ] 4.3: Add validation that Claude returned parseable content
- [ ] 4.4: Add logging for generation steps and token usage

### 5. Testing
- [ ] 5.1: Create `tests/test_qa_handler.py` with 4+ tests (batching, skipping, formatting, storage)
- [ ] 5.2: Create `tests/test_plan_prompts.py` with 3+ tests (template injection, issue formatting, answer injection)
- [ ] 5.3: Create `tests/test_plan_builder.py` with 5+ tests (template loading, Claude invocation, master plan, phase plans, error handling)
- [ ] 5.4: Add integration test with mock AnalysisReport -> QA -> PlanBuilder
- [ ] 5.5: Validate total test count ≥10

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/qa_handler.py` | Create | Interactive Q&A session management with batching and skip logic |
| `src/debussy/planners/prompts.py` | Create | Claude prompt templates for master and phase plan generation |
| `src/debussy/planners/plan_builder.py` | Create | Core plan generation using Claude subprocess and templates |
| `tests/test_qa_handler.py` | Create | Unit tests for Q&A batching, skipping, formatting |
| `tests/test_plan_prompts.py` | Create | Unit tests for prompt template rendering |
| `tests/test_plan_builder.py` | Create | Unit and integration tests for PlanBuilder |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Claude subprocess invocation | `src/debussy/converters/plan_converter.py:_run_claude()` | Use subprocess with --print flag, parse stdout JSON |
| Template loading | `src/debussy/resources/__init__.py` | Use importlib.resources.files() for template access |
| Prompt structure | `src/debussy/converters/prompts.py` | Follow system/user message pattern with clear instructions |
| Error handling | `src/debussy/planners/github_fetcher.py` | Raise specific exceptions with actionable error messages |
| Dataclass usage | `src/debussy/planners/analyzer.py` | Use dataclasses for structured data (answers, build context) |

## Test Strategy

- [ ] Unit tests for QAHandler question batching edge cases (0, 1, 4, 5 questions)
- [ ] Unit tests for QAHandler skip functionality and answer storage
- [ ] Unit tests for prompt template rendering with various issue/answer combinations
- [ ] Unit tests for PlanBuilder template loading (success and missing template cases)
- [ ] Unit tests for PlanBuilder Claude invocation (mock subprocess)
- [ ] Integration test: AnalysisReport with gaps -> QAHandler -> PlanBuilder -> output files exist
- [ ] Manual testing: Generate plan from Phase 7 issues (inception test!)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] ≥10 tests written and passing
- [ ] QAHandler batches questions correctly (max 4 per batch)
- [ ] PlanBuilder loads templates from resources/ (single source of truth)
- [ ] PlanBuilder generates master plan and phase files
- [ ] Generated plans include issue context and user answers
- [ ] Error handling for missing Claude CLI or templates
- [ ] Documentation strings added to all public functions

## Rollback Plan

This phase only adds new modules without modifying existing code. Rollback is straightforward:

1. Delete new files:
   ```bash
   rm src/debussy/planners/qa_handler.py
   rm src/debussy/planners/prompts.py
   rm src/debussy/planners/plan_builder.py
   rm tests/test_qa_handler.py
   rm tests/test_plan_prompts.py
   rm tests/test_plan_builder.py
   ```

2. Verify clean state:
   ```bash
   git status  # Should show deleted files only
   uv run pytest tests/ -v  # Should pass (no dependencies broken)
   ```

3. Commit rollback:
   ```bash
   git add -A
   git commit -m "Rollback Phase 3: Remove plan builder implementation"
   ```

No database migrations, no config changes, no external dependencies to clean up.

---

## Implementation Notes

**Key Architectural Decisions:**

1. **Template as Source of Truth**: Load templates from `src/debussy/resources/templates/` at runtime rather than duplicating structure in prompts. This ensures generated plans match current Debussy standards even as templates evolve.

2. **Batching Strategy**: Max 4 questions per batch aligns with AskUserQuestion tool limits. Display progress (e.g., "Batch 1 of 3") to manage user expectations.

3. **Optional vs Required Questions**: Gap questions from analyzer should be tagged as optional/required. Required questions block generation, optional can be skipped.

4. **Claude Model Selection**: Use `haiku` for plan generation (faster, cheaper) but provide `--model` override flag. Plan generation is more structured than conversion, so haiku should suffice.

5. **Prompt Engineering**: Include concrete examples from existing phase files in prompts to guide Claude's output structure. Reference the template format explicitly (e.g., "Follow the exact section structure in {template_name}").

6. **Answer Injection**: Format user answers as a bulleted "Additional Context" section in prompts rather than trying to merge them into issue bodies. This preserves traceability.
