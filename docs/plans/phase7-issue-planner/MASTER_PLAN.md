# Issue-to-Plan Generator - Master Plan

**Created:** 2026-01-15
**Status:** Draft
**Analysis:** N/A

---

## Overview

Implement an automated workflow that retrieves issues from GitHub (and later Jira) and generates Debussy-compliant master plans with phase documents. The feature bridges the gap between issue trackers and structured implementation plans, using interactive Q&A to fill gaps in poorly-defined tickets. This solves the problem of manually translating tickets into Debussy plans, reducing planning overhead while ensuring compliance with plan templates.

## Goals

1. **Issue Retrieval** - Fetch and filter issues from GitHub using `gh` CLI (milestone, label, state filters)
2. **Gap Detection** - Analyze issue quality and identify missing critical information (acceptance criteria, tech hints, dependencies)
3. **Interactive Planning** - Use AskUserQuestion to fill gaps before generating plans
4. **Structured Output** - Generate audit-compliant master plans and phase documents following Debussy templates
5. **Jira Support** - Extend to Jira epics via Atlassian MCP (Phase 5, future scope)

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [GitHub Issue Fetcher](phase-1.md) | CLI module to fetch/filter GH issues via gh CLI | Low | Completed |
| 2 | [Issue Analyzer](phase-2.md) | Analyze issue quality, detect gaps, prepare questions | Low | Pending |
| 3 | [Interactive Plan Builder](phase-3.md) | Q&A flow + plan file generation using templates | Medium | Pending |
| 4 | [CLI Integration](phase-4.md) | debussy command, audit loop, end-to-end flow | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| Issue retrieval | None | GH fetch working | With quality analysis | With gap Q&A | Full pipeline |
| Plan generation | Manual | N/A | N/A | Template-compliant | Audit-passing |
| Test coverage | ~66% | +10 tests | +10 tests | +15 tests | +10 tests |

## Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
   │           │           │
   └── Standalone ─┴── Uses Phase 1 ─┴── Integrates all
```

- Phase 1 (GitHub Fetcher) can be developed and tested independently
- Phase 2 (Issue Analyzer) depends on Phase 1's issue data structures
- Phase 3 (Plan Builder) depends on Phase 2's gap analysis output
- Phase 4 (CLI Integration) integrates all phases into `debussy plan-from-issues` command

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Poorly-defined issues | High | Medium | Interactive Q&A fills gaps; best practices doc for "Debussy-ready" issues |
| GH API rate limits | Low | Low | Use gh CLI which handles auth; batch requests where possible |
| Generated plans fail audit | Medium | Low | Audit retry loop like convert command; max 3 attempts |
| Template drift | Low | Medium | Use existing template files as source; single source of truth |
| Over-scoped issues | Medium | Medium | Warn user if issue count high; recommend epic/milestone level |

## Out of Scope

- Jira integration (Phase 5, future - requires MCP setup)
- Automatic plan execution after generation (user should review first)
- Two-way sync (updating GH issues from plan status)
- Support for other issue trackers (GitLab, Linear, Asana)
- AI-powered acceptance criteria generation (user provides via Q&A)

## Review Checkpoints

- After Phase 1: Verify GH fetcher retrieves issues correctly with filters
- After Phase 2: Verify analyzer detects missing fields and generates appropriate questions
- After Phase 3: Verify generated plans follow templates and pass basic audit
- After Phase 4: Verify full `debussy plan-from-issues` command works end-to-end

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI command definitions
- `src/debussy/converters/plan_converter.py` - Existing convert logic to reference
- `src/debussy/converters/prompts.py` - Prompt templates pattern
- `src/debussy/resources/templates/` - Plan templates (source of truth)
- `src/debussy/checkers/compliance.py` - Audit logic

**Test Locations:**
- `tests/test_issue_fetcher.py` - GH fetcher tests
- `tests/test_issue_analyzer.py` - Analyzer tests
- `tests/test_plan_builder.py` - Generator tests
- `tests/test_cli_plan_from_issues.py` - Integration tests

**Related Documentation:**
- `docs/CONVERT_TESTS.md` - Quality metrics approach
- `docs/CONVERSION_PROCESS.md` - Similar pipeline diagram
- `tests/fixtures/sample_plans/` - Reference plans for comparison

---

## "Debussy-Ready" Feature Definition

For best results, GitHub issues should include:

```markdown
## Problem
What pain point or gap does this address?

## Proposed Solution
High-level approach. Tech stack hints if relevant.

## Context & Dependencies
- Prerequisite work
- External systems involved
- Related features

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Validation
Framework: pytest | jest | manual | other
Coverage target: X%
```

Issues missing these fields will trigger interactive Q&A during plan generation.
