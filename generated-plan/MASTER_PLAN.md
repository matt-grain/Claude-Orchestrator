# Issue-to-Plan Generator - Master Plan

**Created:** 2026-01-15
**Status:** Draft
**Analysis:** N/A

---

## Overview

This feature automates the translation of GitHub issues (and eventually Jira tickets) into Debussy-compliant implementation plans. Currently, developers must manually read issues, understand requirements, and create MASTER_PLAN.md + phase files—a time-consuming and error-prone process. This pipeline will fetch issues, analyze quality, conduct interactive Q&A to fill gaps, generate compliant plans, and validate them through an audit loop.

## Goals

1. **Automated Issue Ingestion** - Fetch GitHub issues by milestone or label using gh CLI with structured data models
2. **Intelligent Gap Detection** - Analyze issue quality and identify missing critical information (acceptance criteria, tech stack, validation)
3. **Interactive Plan Generation** - Use Claude to generate Debussy-compliant plans with Q&A-driven gap filling and audit validation
4. **Quality Assurance** - Ensure generated plans pass compliance checks through automated audit retry loops

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [GitHub Issue Fetcher Module](phase-1.md) | Data ingestion layer | Low | Pending |
| 2 | [Issue Analyzer and Gap Detection](phase-2.md) | Quality analysis | Low | Pending |
| 3 | [Interactive Plan Builder](phase-3.md) | Plan generation with Claude | Medium | Pending |
| 4 | [CLI Integration and Audit Loop](phase-4.md) | End-to-end pipeline orchestration | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| Manual plan creation time | 60+ min | N/A | N/A | N/A | <15 min |
| Issue quality detection | 0% | N/A | 90%+ | 90%+ | 90%+ |
| Plan compliance rate | Manual | N/A | N/A | 80%+ | 95%+ |
| Test coverage | 66.80% | 66%+ | 66%+ | 66%+ | 66%+ |

## Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
   │           │           │
   └─ Deploy ──┴─ Deploy ──┴─ Deploy ──┴─ Deploy
```

Each phase can be independently deployed and tested:
- **Phase 1**: Standalone issue fetcher module with CLI tool
- **Phase 2**: Analyzer consumes Phase 1 output, produces quality reports
- **Phase 3**: Plan builder uses Phase 2 analysis + templates
- **Phase 4**: Orchestrates all components into single command

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| gh CLI unavailable or auth failures | Medium | High | Graceful error handling, clear error messages, documentation for setup |
| Low-quality issues yield poor plans | High | Medium | Gap detection + interactive Q&A to fill missing information before generation |
| Claude generates non-compliant plans | Medium | Medium | Audit retry loop with max 3 attempts, error feedback injection |
| Template drift (resources vs generation) | Low | Medium | Single source of truth: load templates from src/debussy/resources/ |
| User fatigue from too many questions | Medium | Low | Batch questions (max 4 per batch), skip functionality for optional gaps |

## Out of Scope

- Jira integration (deferred to future milestone after Atlassian MCP is stable)
- Multi-repository issue aggregation
- Issue creation or modification via API
- Automatic plan execution (users still manually run `debussy run`)
- Plan versioning or history tracking

## Review Checkpoints

- **After Phase 1**: Verify gh CLI integration works, fetcher handles milestones/labels/state filters correctly
- **After Phase 2**: Validate gap detection accuracy on real issues, ensure quality scoring is meaningful
- **After Phase 3**: Test generated plans against debussy audit, verify Claude produces compliant output
- **After Phase 4**: Run inception test (generate plan for v0.5.0 milestone issues), measure end-to-end time

---

## Quick Reference

**Key Files:**
- `src/debussy/planners/github_fetcher.py` - Issue fetching and filtering
- `src/debussy/planners/analyzer.py` - Quality analysis and gap detection
- `src/debussy/planners/plan_builder.py` - Claude-based plan generation
- `src/debussy/planners/qa_handler.py` - Interactive question batching
- `src/debussy/planners/command.py` - Pipeline orchestration
- `src/debussy/cli.py` - CLI command integration

**Test Locations:**
- `tests/test_issue_fetcher.py`
- `tests/test_issue_analyzer.py`
- `tests/test_plan_builder.py`
- `tests/test_cli_plan_from_issues.py`

**Related Documentation:**
- `docs/CONVERT_TESTS.md` - Quality metrics (pattern for validation)
- `docs/CONVERSION_PROCESS.md` - Audit loop pattern
- `src/debussy/resources/templates/` - Plan templates (single source of truth)
