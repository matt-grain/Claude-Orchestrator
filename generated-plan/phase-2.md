# Issue-to-Plan Generator Phase 2: Issue Analysis and Quality Scoring

**Status:** Pending
**Master Plan:** [issue-to-plan-MASTER_PLAN.md](issue-to-plan-MASTER_PLAN.md)
**Depends On:** [phase-1.md](phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue-to-plan_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue-to-plan_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass, 10+ new tests)
- coverage: `uv run pytest --cov=src/debussy/planners --cov-report=term` (maintain 66%+)

---

## Overview

This phase implements intelligent issue analysis and quality assessment. After fetching raw GitHub issues in Phase 1, we need to evaluate their completeness before attempting plan generation. The analyzer detects gaps (missing acceptance criteria, tech stack, dependencies, validation requirements) and generates targeted questions to fill those gaps. This prevents generating incomplete or ambiguous plans.

## Dependencies
- Previous phase: [phase-1.md](phase-1.md) - GitHubIssue, IssueSet dataclasses
- External: None (pure Python analysis)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Gap detection too strict (flags minor issues) | Medium | Medium | Use quality score thresholds; allow skipping optional questions |
| Gap detection too lenient (misses critical info) | Low | High | Conservative defaults; require acceptance criteria for score >60 |
| Question generation produces unclear prompts | Medium | Medium | Test with real issue samples; iterate on templates |
| Quality scoring inconsistent across issue types | Medium | Low | Define clear rubric; test with diverse issue samples |

---

## Tasks

### 1. Create Core Data Models
- [ ] 1.1: Create `IssueQuality` dataclass with score (0-100), gaps dict, and generated questions list
- [ ] 1.2: Create `AnalysisReport` dataclass aggregating quality data for all issues in IssueSet
- [ ] 1.3: Create `GapType` enum for categorizing gaps (acceptance_criteria, tech_stack, dependencies, validation, scope)

### 2. Implement Gap Detection Functions
- [ ] 2.1: Implement `detect_acceptance_criteria_gap()` - checks for task lists, criteria, or test plan in issue body
- [ ] 2.2: Implement `detect_tech_stack_gap()` - checks for technology mentions, framework names, language keywords
- [ ] 2.3: Implement `detect_dependencies_gap()` - checks for "depends on", prerequisite mentions, or dependency lists
- [ ] 2.4: Implement `detect_validation_gap()` - checks for test framework mentions, validation steps, or quality gates
- [ ] 2.5: Implement `detect_scope_gap()` - checks for file paths, module names, or architectural boundaries

### 3. Implement Quality Scoring
- [ ] 3.1: Create `calculate_quality_score()` function using weighted rubric (acceptance=40%, validation=20%, tech=15%, deps=15%, scope=10%)
- [ ] 3.2: Implement score penalties for missing critical fields (title, body length <100 chars)
- [ ] 3.3: Add bonus points for well-structured issues (has code blocks, has tables, has checklists)

### 4. Implement Question Generation
- [ ] 4.1: Create `generate_gap_questions()` function that produces AskUserQuestion-compatible question objects
- [ ] 4.2: Implement question templates for each gap type with context from issue content
- [ ] 4.3: Add priority ranking (critical vs optional) for questions based on gap impact

### 5. Create Main Analyzer Interface
- [ ] 5.1: Implement `analyze_issue(issue: GitHubIssue) -> IssueQuality` function orchestrating all detection
- [ ] 5.2: Implement `analyze_issue_set(issue_set: IssueSet) -> AnalysisReport` batch analysis function
- [ ] 5.3: Add configurable quality thresholds (warn_below=60, fail_below=30)

### 6. Testing
- [ ] 6.1: Create fixtures with sample issues (minimal, good, excellent quality)
- [ ] 6.2: Test each gap detection function with positive and negative cases
- [ ] 6.3: Test quality scoring with known-score fixtures
- [ ] 6.4: Test question generation produces valid AskUserQuestion format
- [ ] 6.5: Integration test: full analysis pipeline on multi-issue set

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/analyzer.py` | Create | Core analysis logic, gap detection, quality scoring |
| `src/debussy/planners/models.py` | Modify | Add IssueQuality, AnalysisReport, GapType to existing models |
| `tests/test_issue_analyzer.py` | Create | Unit tests for analyzer functions (10+ tests) |
| `tests/fixtures/sample_issues.py` | Create | Sample issue data for testing (minimal/good/excellent) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass models | `src/debussy/planners/models.py` (from Phase 1) | Use @dataclass for IssueQuality, AnalysisReport |
| Enum for categorization | `src/debussy/models/state.py` (PhaseStatus enum) | Use GapType enum for gap categories |
| Quality scoring rubric | `src/debussy/converters/quality.py` (ConversionQuality) | Similar weighted scoring approach |
| Question generation | `src/debussy/converters/plan_converter.py` (Q&A flow) | Format compatible with AskUserQuestion tool |

## Test Strategy

- [ ] Unit tests for gap detection (test each detector independently)
- [ ] Unit tests for quality scoring (verify rubric weights, edge cases)
- [ ] Unit tests for question generation (validate format, content relevance)
- [ ] Integration tests for full analysis pipeline (issue -> IssueQuality)
- [ ] Batch analysis tests (IssueSet -> AnalysisReport aggregation)
- [ ] Edge case tests (empty body, malformed markdown, very long issues)
- [ ] Manual testing checklist:
  - [ ] Run on real Debussy issues from GitHub (test self-dogfooding)
  - [ ] Verify questions make sense to human reviewer
  - [ ] Check quality scores align with intuitive assessment

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest)
- [ ] 10+ tests written and passing
- [ ] IssueQuality dataclass with score, gaps, questions
- [ ] AnalysisReport aggregates multi-issue analysis
- [ ] Gap detection for: acceptance criteria, tech stack, dependencies, validation, scope
- [ ] Quality score range 0-100 with documented rubric
- [ ] Question generation produces AskUserQuestion-compatible format
- [ ] Coverage maintained at 66%+ overall
- [ ] No security vulnerabilities introduced (ruff security checks pass)

## Rollback Plan

If analysis logic produces incorrect results or breaks existing functionality:

1. **Revert git commits:**
   ```bash
   git revert HEAD~1  # Revert last commit
   # Or for multiple commits:
   git revert <commit-hash-before-phase-2>..HEAD
   ```

2. **Remove new files:**
   ```bash
   rm src/debussy/planners/analyzer.py
   rm tests/test_issue_analyzer.py
   rm tests/fixtures/sample_issues.py
   ```

3. **Restore models.py if modified:**
   ```bash
   git checkout HEAD~1 -- src/debussy/planners/models.py
   ```

4. **Verify rollback:**
   ```bash
   uv run pytest tests/  # All Phase 1 tests should still pass
   ```

5. **Database/state:** No database changes in this phase, no migrations to reverse.

---

## Implementation Notes

**Quality Score Rubric (0-100):**
- Base: 0
- Has acceptance criteria: +40
- Has validation/testing strategy: +20
- Has tech stack mentioned: +15
- Has dependencies identified: +15
- Has scope/files defined: +10
- Penalty: Missing title (-20), body <100 chars (-20)
- Bonus: Code blocks (+5), tables (+3), checklists (+5)

**Gap Detection Strategy:**
Use keyword matching and structural analysis (not NLP). For example:
- Acceptance criteria: Look for `- [ ]`, "acceptance", "criteria", "must", "should"
- Tech stack: Common framework names (React, Django, FastAPI, PostgreSQL, etc.)
- Dependencies: "depends on", "requires", "prerequisite", issue references (#123)
- Validation: "test", "pytest", "jest", "validate", "verify"
- Scope: File paths (`src/`, `*.py`), module names, architectural terms

**Question Format:**
Generated questions must be compatible with AskUserQuestion tool:
```python
{
    "question": "What acceptance criteria define success for this feature?",
    "header": "Criteria",
    "options": [
        {"label": "Define now", "description": "Provide criteria interactively"},
        {"label": "Skip", "description": "Generate plan without explicit criteria"}
    ],
    "multiSelect": False
}
```

**Integration with Phase 3:**
The AnalysisReport output will be consumed by PlanBuilder (Phase 3) to:
1. Display quality summary to user
2. Conduct interactive Q&A for gaps
3. Inject answers into plan generation context
