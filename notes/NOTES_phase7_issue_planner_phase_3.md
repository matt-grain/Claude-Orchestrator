# Phase 7.3 Implementation Notes: Interactive Plan Builder

**Date:** 2026-01-16
**Phase:** Issue-to-Plan Phase 3: Interactive Plan Builder
**Status:** Completed

---

## Summary

Implemented the interactive plan builder module that generates Debussy-compliant implementation plans from analyzed GitHub issues. The implementation includes:

1. **Prompt Templates** (`src/debussy/planners/prompts.py`)
   - SYSTEM_PROMPT for Claude's plan architect role
   - MASTER_PLAN_PROMPT for master plan generation
   - PHASE_PLAN_PROMPT for individual phase generation
   - Helper functions for formatting issues and Q&A answers

2. **Plan Builder** (`src/debussy/planners/plan_builder.py`)
   - PlanBuilder class with Claude subprocess integration
   - Template loading from docs/templates/plans/
   - Phase count estimation based on issue complexity
   - Phase focus extraction from generated master plans

3. **Q&A Handler** (`src/debussy/planners/qa_handler.py`)
   - QAHandler class for interactive gap-filling
   - Question batching by gap type and severity (max 4 per batch)
   - AskUserQuestion tool format support
   - Skip functionality for optional questions

---

## Template Rendering Approach

Templates are loaded from `docs/templates/plans/` directory using Path operations with importlib.resources as fallback for installed packages. The approach:

1. First attempts to load from relative path (for development)
2. Falls back to importlib.resources (for installed package)
3. Caches templates after first load to avoid repeated disk I/O

Templates are injected directly into prompts for Claude to use as structural guides, ensuring generated plans match Debussy's expected format.

---

## Interactive Q&A Flow Design

The Q&A flow is designed for Claude Code's AskUserQuestion tool:

1. **Question Batching**: Groups related questions by gap type (acceptance criteria, tech stack, etc.)
2. **Priority Ordering**: Critical gaps are asked first, then warnings
3. **Batch Size Limit**: Max 4 questions per AskUserQuestion call (tool limit)
4. **Skip Support**: Users can skip individual questions or all optional (warning-severity) questions
5. **Hash-Based Tracking**: Questions are keyed by MD5 hash for consistent storage

Flow:
```
AnalysisReport.questions_needed -> QAHandler -> batch_questions()
  -> format_batch_for_tui() -> Claude Tool Call -> record_answer()
  -> PlanBuilder.set_answers() -> generate_all()
```

---

## Test Coverage Summary

Created 32 test cases across 13 test classes:

- **TestPromptTemplates**: 6 tests for prompt formatting functions
- **TestPlanBuilderTemplateLoading**: 2 tests for template loading and caching
- **TestPlanBuilderPromptConstruction**: 3 tests for prompt building
- **TestPhaseCountEstimation**: 4 tests for heuristic phase count calculation
- **TestQAHandler**: 9 tests for batching, skipping, and formatting
- **TestPlanBuilderGeneration**: 5 tests (mocked Claude calls)
- **TestPlanBuilderSetAnswers**: 2 tests for answer storage
- **TestSystemPrompt**: 3 tests for prompt content validation

All tests pass with 70% overall project coverage (unchanged from baseline).

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/debussy/planners/prompts.py` | 166 | Prompt templates for Claude |
| `src/debussy/planners/plan_builder.py` | 249 | Plan generation logic |
| `src/debussy/planners/qa_handler.py` | 303 | Interactive Q&A management |
| `tests/test_plan_builder.py` | ~580 | Unit tests (32 test cases) |

---

## Gate Results

| Gate | Status | Command |
|------|--------|---------|
| ruff | PASS | `uv run ruff check .` - All checks passed |
| pyright | PASS | `uv run pyright src/debussy/` - 0 errors |
| tests | PASS | `uv run pytest tests/ -v` - 723 passed |
| coverage | PASS | 69.89% (target: 50%) |

---

## Learnings

### 1. Template Path Resolution Pattern
When loading package resources, always try multiple strategies in order:
1. Relative path from __file__ (development)
2. importlib.resources (installed package)
3. Graceful error with clear message

This pattern is already used in plan_converter.py but was worth understanding for consistent implementation.

### 2. Question Hash Key Strategy
Using MD5 hash of question text as dictionary keys provides:
- Consistent keys regardless of question ordering
- Easy comparison across different runs
- Compact storage in state

The hash[:12] truncation is sufficient for uniqueness in typical use cases.

### 3. TypedDict for Claude Tool Format
Using TypedDict for AskUserQuestion format provides:
- Type safety for complex nested structures
- Clear documentation of expected shape
- IDE completion support

### 4. Phase Count Heuristic
The 1-2/3-5/6+ issue count thresholds work well for typical features:
- Small (2-3 phases): Quick features
- Medium (3-4 phases): Standard features
- Large (4-5 phases): Complex refactors

Critical gaps can bump up the phase count by 1 for more thorough coverage.

### 5. Mocking Subprocess for Tests
Using `@patch("debussy.planners.plan_builder.subprocess.run")` effectively isolates Claude CLI calls while still testing prompt construction and output parsing logic.

---

## Next Steps (Phase 4)

Phase 4 will integrate these components into a CLI command:
- `debussy issue-to-plan` command
- Interactive mode with TUI question prompts
- Non-interactive mode with answers file
- Output directory configuration
