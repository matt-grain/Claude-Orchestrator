# Issue-to-Plan Phase 3: Interactive Plan Builder

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** Phase 2 (Issue Analyzer) - needs AnalysisReport and gap questions

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
- [ ] Write `notes/NOTES_phase7_issue_planner_phase_3.md` with:
  - Summary of plan builder implementation
  - Template rendering approach
  - Interactive Q&A flow design
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 7.3`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~66%)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **Phase 2 analyzer**: `src/debussy/planners/analyzer.py` - Gap detection and questions
2. **Plan templates**: `src/debussy/resources/templates/` - Master and phase templates
3. **Convert prompts**: `src/debussy/converters/prompts.py` - Claude prompt patterns
4. **Plan converter**: `src/debussy/converters/plan_converter.py` - File generation patterns

**DO NOT** break existing functionality. Changes should be additive.

---

## Overview

Build the interactive plan generator that takes analyzed issues and gap questions, conducts Q&A to fill missing information, then generates Debussy-compliant master plan and phase documents. This uses Claude as the underlying generator, with structured prompts that include issue content, user answers, and template requirements.

## Dependencies
- Previous phase: Phase 2 (AnalysisReport, questions_needed)
- External: Claude CLI for plan generation
- Internal: Debussy templates from resources/templates/

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Poor plan quality | Medium | Medium | Include templates in prompt; audit loop catches issues |
| Too many questions | Medium | Low | Batch related questions; skip if user chooses |
| Template format drift | Low | Medium | Load templates dynamically; single source of truth |
| Claude hallucination | Low | Medium | Include real issue content; user reviews before execution |

---

## Tasks

### 1. Create Plan Builder Prompts
- [ ] 1.1: Create `src/debussy/planners/prompts.py`
- [ ] 1.2: Define SYSTEM_PROMPT for plan generation (role: expert plan architect)
- [ ] 1.3: Define MASTER_PLAN_PROMPT template with placeholders for issues, answers, template
- [ ] 1.4: Define PHASE_PLAN_PROMPT template for individual phase generation
- [ ] 1.5: Define ISSUE_SUMMARY_TEMPLATE for formatting issue content in prompts
- [ ] 1.6: Define QA_CONTEXT_TEMPLATE for including user answers in prompts

### 2. Create Plan Builder Module
- [ ] 2.1: Create `src/debussy/planners/plan_builder.py`
- [ ] 2.2: Create PlanBuilder class with __init__(issues: IssueSet, analysis: AnalysisReport)
- [ ] 2.3: Implement set_answers(answers: dict[str, str]) to store Q&A responses
- [ ] 2.4: Implement _load_templates() to read master and phase templates from resources
- [ ] 2.5: Implement _build_master_prompt() combining issues, answers, template
- [ ] 2.6: Implement _build_phase_prompt(phase_num, phase_focus) for phase docs
- [ ] 2.7: Implement generate_master_plan() -> str using Claude subprocess
- [ ] 2.8: Implement generate_phase_plan(phase_num) -> str using Claude subprocess
- [ ] 2.9: Implement generate_all() -> dict[str, str] returning all plan files
- [ ] 2.10: Add _estimate_phase_count() heuristic based on issue complexity

### 3. Create Interactive Q&A Handler
- [ ] 3.1: Create `src/debussy/planners/qa_handler.py`
- [ ] 3.2: Create QAHandler class with __init__(questions: list[str])
- [ ] 3.3: Implement ask_questions_interactive() for terminal Q&A
- [ ] 3.4: Implement format_question_for_tui() for AskUserQuestion tool format
- [ ] 3.5: Implement batch_questions() to group related questions (max 4 per batch)
- [ ] 3.6: Implement skip_question() to allow users to skip optional questions
- [ ] 3.7: Store answers in dict keyed by question hash

### 4. Write Unit Tests
- [ ] 4.1: Create `tests/test_plan_builder.py`
- [ ] 4.2: Test prompt template construction
- [ ] 4.3: Test _load_templates() finds and reads templates
- [ ] 4.4: Test _build_master_prompt() includes all required sections
- [ ] 4.5: Test _estimate_phase_count() heuristic
- [ ] 4.6: Test QAHandler question batching
- [ ] 4.7: Test QAHandler skip functionality
- [ ] 4.8: Test format_question_for_tui() output format
- [ ] 4.9: Mock test generate_master_plan() with fake Claude output
- [ ] 4.10: Mock test generate_all() produces expected file structure

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/prompts.py` | Create | Prompt templates for Claude |
| `src/debussy/planners/plan_builder.py` | Create | Plan generation logic |
| `src/debussy/planners/qa_handler.py` | Create | Interactive Q&A management |
| `tests/test_plan_builder.py` | Create | Unit tests (10+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Prompt templates | `src/debussy/converters/prompts.py` | String templates with placeholders |
| Claude subprocess | `src/debussy/converters/plan_converter.py` | Subprocess pattern for Claude calls |
| Template loading | `src/debussy/resources/templates/` | importlib.resources for package data |
| AskUserQuestion | Claude tool format | Dict with question, options, header |

## Test Strategy

- [ ] Unit tests for prompt construction
- [ ] Unit tests for template loading
- [ ] Unit tests for Q&A batching and formatting
- [ ] Mocked tests for Claude generation calls
- [ ] Integration tests with fixture issues

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure all type hints are correct and pass pyright strict mode
- Test generated plans against `debussy audit` (preliminary check)

## Acceptance Criteria

**ALL must pass:**

- [ ] Prompt templates defined for master and phase plans
- [ ] PlanBuilder generates plans using Claude subprocess
- [ ] Templates loaded from resources (single source of truth)
- [ ] QAHandler batches and formats questions correctly
- [ ] Skip functionality works for optional questions
- [ ] Phase count estimation works
- [ ] 10+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Phase is additive. Rollback:
1. Remove `src/debussy/planners/prompts.py`
2. Remove `src/debussy/planners/plan_builder.py`
3. Remove `src/debussy/planners/qa_handler.py`
4. Remove `tests/test_plan_builder.py`

No existing functionality affected.

---

## Implementation Notes

**Phase Count Heuristic:**
- 1-2 issues: 2-3 phases (small feature)
- 3-5 issues: 3-4 phases (medium feature)
- 6+ issues: 4-5 phases (large feature, warn user)

**Prompt Structure:**
```
SYSTEM: You are an expert software architect creating Debussy implementation plans...

USER:
## Source Issues
{formatted_issues}

## User-Provided Context
{qa_answers}

## Template to Follow
{master_plan_template}

## Instructions
Generate a MASTER_PLAN.md following the template exactly...
```

**Q&A Batching:**
- Group by gap type (all tech questions together, all validation questions together)
- Max 4 questions per AskUserQuestion call (tool limit)
- Critical gaps first, then warnings
- Allow "Skip all optional" shortcut

**File Output:**
```
plans/<feature-name>/
  MASTER_PLAN.md
  phase-1.md
  phase-2.md
  ...
```
