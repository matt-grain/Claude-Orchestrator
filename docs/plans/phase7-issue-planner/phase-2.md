# Issue-to-Plan Phase 2: Issue Analyzer & Gap Detection

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** Phase 1 (GitHub Fetcher) - needs IssueSet data structures

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
- [ ] Write `notes/NOTES_phase7_issue_planner_phase_2.md` with:
  - Summary of analyzer implementation
  - Gap detection heuristics
  - Question generation approach
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 7.2`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~66%)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **Phase 1 models**: `src/debussy/planners/models.py` - Issue data structures
2. **Phase 1 fetcher**: `src/debussy/planners/github_fetcher.py` - How issues are retrieved
3. **Compliance checker**: `src/debussy/checkers/compliance.py` - Pattern for analyzing content
4. **Quality metrics**: `src/debussy/converters/quality.py` - Pattern for scoring/analysis

**DO NOT** break existing functionality. Changes should be additive.

---

## Overview

Build an analyzer that examines fetched issues and detects missing information critical for plan generation. The analyzer produces a structured report identifying gaps (missing acceptance criteria, no tech hints, unclear scope) and generates questions to fill those gaps. This bridges raw issues and the interactive plan builder.

## Dependencies
- Previous phase: Phase 1 (IssueSet, GitHubIssue dataclasses)
- Internal: Will be used by the Interactive Plan Builder (next phase)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positive gaps | Medium | Low | Conservative detection; user can skip questions |
| Over-questioning | Medium | Medium | Prioritize critical gaps; batch related questions |
| Missing edge cases | Low | Medium | Iterative improvement based on real usage |
| Analysis too slow | Low | Low | Simple string matching, no ML models |

---

## Tasks

### 1. Create Analysis Models
- [ ] 1.1: Create `src/debussy/planners/analyzer.py`
- [ ] 1.2: Create GapType enum (ACCEPTANCE_CRITERIA, TECH_STACK, DEPENDENCIES, VALIDATION, SCOPE, CONTEXT)
- [ ] 1.3: Create Gap dataclass (gap_type, severity: critical|warning, issue_number, description, suggested_question)
- [ ] 1.4: Create IssueQuality dataclass (issue_number, score: 0-100, gaps: list[Gap], has_problem, has_solution, has_criteria, has_validation)
- [ ] 1.5: Create AnalysisReport dataclass (issues: list[IssueQuality], total_gaps, critical_gaps, questions_needed: list[str])

### 2. Implement Gap Detection
- [ ] 2.1: Implement detect_acceptance_criteria_gap() - check for checkbox items, "acceptance", "criteria", "done when"
- [ ] 2.2: Implement detect_tech_stack_gap() - check for framework/language mentions
- [ ] 2.3: Implement detect_dependencies_gap() - check for "depends", "requires", "after", "blocked by"
- [ ] 2.4: Implement detect_validation_gap() - check for "test", "pytest", "jest", "coverage", "validation"
- [ ] 2.5: Implement detect_scope_gap() - warn if body is <100 chars or lacks structure
- [ ] 2.6: Implement detect_context_gap() - check for problem/background description
- [ ] 2.7: Implement calculate_quality_score() - weighted score based on detected fields

### 3. Implement Issue Analyzer
- [ ] 3.1: Implement IssueAnalyzer class with analyze_issue(issue: GitHubIssue) -> IssueQuality
- [ ] 3.2: Implement analyze_issue_set(issues: IssueSet) -> AnalysisReport
- [ ] 3.3: Implement generate_questions() - convert gaps to user-friendly questions
- [ ] 3.4: Implement prioritize_gaps() - sort by severity, group by type
- [ ] 3.5: Add markdown section detection (_has_section() helper for "## Problem", "## Solution", etc.)

### 4. Write Unit Tests
- [ ] 4.1: Create `tests/test_issue_analyzer.py`
- [ ] 4.2: Test Gap and IssueQuality dataclass creation
- [ ] 4.3: Test detect_acceptance_criteria_gap() with/without criteria
- [ ] 4.4: Test detect_tech_stack_gap() with/without tech mentions
- [ ] 4.5: Test detect_validation_gap() with/without test framework
- [ ] 4.6: Test calculate_quality_score() produces expected scores
- [ ] 4.7: Test analyze_issue() returns correct gaps for sample issues
- [ ] 4.8: Test analyze_issue_set() aggregates correctly
- [ ] 4.9: Test generate_questions() produces user-friendly text
- [ ] 4.10: Test edge cases: empty body, minimal issue, perfect issue

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/analyzer.py` | Create | Gap detection and issue analysis |
| `src/debussy/planners/models.py` | Modify | Add Gap, IssueQuality, AnalysisReport dataclasses |
| `tests/test_issue_analyzer.py` | Create | Unit tests for analyzer (10+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass models | `src/debussy/core/models.py` | Use @dataclass for Gap, IssueQuality |
| Compliance analysis | `src/debussy/checkers/compliance.py` | Pattern for checking content |
| Quality scoring | `src/debussy/converters/quality.py` | Pattern for calculating scores |
| Enum types | `src/debussy/core/models.py` | Use Enum for GapType |

## Test Strategy

- [ ] Unit tests for each gap detection function
- [ ] Unit tests for quality score calculation
- [ ] Tests with realistic issue bodies (well-formed and poorly-formed)
- [ ] Tests for edge cases (empty, minimal, perfect)
- [ ] Tests for question generation formatting

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure all type hints are correct and pass pyright strict mode
- Test with real GitHub issues to validate detection heuristics

## Acceptance Criteria

**ALL must pass:**

- [ ] All gap detection functions implemented
- [ ] Quality scoring works (0-100 scale)
- [ ] Analyzer produces AnalysisReport from IssueSet
- [ ] Question generation creates user-friendly prompts
- [ ] Gap prioritization works (critical > warning)
- [ ] 10+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Phase is additive. Rollback:
1. Remove `src/debussy/planners/analyzer.py`
2. Revert changes to `src/debussy/planners/models.py`
3. Remove `tests/test_issue_analyzer.py`

No existing functionality affected.

---

## Implementation Notes

**Gap Detection Heuristics:**

| Gap Type | Detection Pattern | Severity |
|----------|-------------------|----------|
| ACCEPTANCE_CRITERIA | No `- [ ]` checkboxes, no "acceptance", "criteria", "done when" | Critical |
| TECH_STACK | No framework/language keywords (react, python, flask, etc.) | Warning |
| DEPENDENCIES | No "depends", "requires", "blocked", "after" | Warning |
| VALIDATION | No "test", "pytest", "jest", "coverage" | Critical |
| SCOPE | Body < 100 chars or no markdown structure | Warning |
| CONTEXT | No "problem", "background", "context", "currently" | Warning |

**Question Templates:**
```
ACCEPTANCE_CRITERIA: "Issue #{n} '{title}' has no acceptance criteria. What defines 'done' for this issue?"
TECH_STACK: "Issue #{n} '{title}' doesn't mention technologies. What frameworks/languages will be used?"
VALIDATION: "Issue #{n} '{title}' has no validation requirements. What test framework and coverage target?"
```

**Quality Score Weights:**
- Has acceptance criteria: 30 points
- Has tech stack hints: 15 points
- Has dependencies noted: 10 points
- Has validation requirements: 25 points
- Has problem/context: 10 points
- Has structured body (>200 chars, has headers): 10 points
