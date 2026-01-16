# Phase 2 Notes: Issue Analyzer & Gap Detection

## Summary

Implemented an issue analyzer module (`src/debussy/planners/analyzer.py`) that examines GitHub issues and detects missing information critical for plan generation. The analyzer produces structured reports identifying gaps (missing acceptance criteria, no tech hints, unclear scope, etc.) and generates user-friendly questions to fill those gaps.

## Key Decisions

1. **Used dataclasses instead of Pydantic models**: Followed the pattern from `models.py` in the planners module, using standard Python dataclasses for Gap, IssueQuality, and AnalysisReport.

2. **Gap severity levels**: Implemented two severity levels (critical/warning) matching the compliance module pattern:
   - Critical: Missing acceptance criteria, missing validation requirements
   - Warning: Missing tech stack, dependencies, context, or insufficient scope

3. **Keyword-based detection**: Used frozenset-based keyword matching (similar to `quality.py`) for detecting various aspects like tech stack, validation, dependencies, and context.

4. **Quality score weights**: Designed weights to sum to 100 for easy understanding:
   - Acceptance criteria: 30 points
   - Validation: 25 points
   - Tech stack: 15 points
   - Context: 10 points
   - Dependencies: 10 points
   - Structured body: 10 points

5. **TYPE_CHECKING imports**: Used conditional imports to satisfy ruff's TC001 rule, importing GitHubIssue and IssueSet only for type checking.

## Files Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/analyzer.py` | Created | Gap detection and issue analysis |
| `tests/test_issue_analyzer.py` | Created | 42 unit tests for analyzer |

## Gap Detection Heuristics

| Gap Type | Detection Method | Severity |
|----------|------------------|----------|
| ACCEPTANCE_CRITERIA | Checkbox items, keywords, section headers | Critical |
| TECH_STACK | Technology/framework keywords in title/body | Warning |
| DEPENDENCIES | Dependency keywords or GitHub issue refs (#123) | Warning |
| VALIDATION | Testing keywords or Testing section headers | Critical |
| SCOPE | Body length < 100 chars or no markdown structure | Warning |
| CONTEXT | Context keywords or Problem/Background sections | Warning |

## Question Generation Approach

Each gap type has an associated question template that includes:
- Issue number for reference
- Issue title for context
- Specific question about what's missing

Example: "Issue #42 'Add user authentication with JWT' has no acceptance criteria. What defines 'done' for this issue?"

## Test Coverage Summary

- 42 tests written covering:
  - Dataclass creation and properties
  - Each gap detection function (positive and negative cases)
  - Quality score calculation
  - IssueAnalyzer class methods
  - Edge cases (empty body, perfect issue, etc.)
  - Gap type coverage verification
- All 687 project tests pass
- Overall test coverage: ~69%
- New module coverage: 96%

## Learnings

### 1. Keyword Selection Matters for False Positives
Initially included "should" in ACCEPTANCE_CRITERIA_KEYWORDS, which caused false positives. Common words like "should", "is", "error" appeared in unexpected contexts, triggering incorrect gap detection. Needed to be more selective with keywords.

### 2. TYPE_CHECKING Pattern for Ruff Compliance
Ruff's TC001 rule requires moving application imports into TYPE_CHECKING blocks to avoid circular imports and improve type checking performance. This pattern is:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module import Type
```

### 3. Regex Space Sensitivity
The regex pattern `{1, 3}` (with space) is different from `{1,3}` (no space). The space version creates an invalid quantifier. Always use `{1,3}` without spaces.

### 4. Test Fixture Design
Test fixtures should avoid triggering unintended keyword matches. For "minimal issue" fixtures, use neutral words that don't contain context keywords like "error", "bug", "is", etc.

### 5. Structured Body Detection
Checking for markdown structure (headers OR lists) combined with minimum length (>200 chars) provides a good heuristic for well-formed issue bodies.
