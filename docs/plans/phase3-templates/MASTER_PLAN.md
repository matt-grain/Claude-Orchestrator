# Phase 3: Templates & Documentation - Master Plan

**Created:** 2026-01-14
**Status:** Draft
**Parent:** [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md)

---

## Overview

Add plan validation (`audit`), scaffolding (`init`), and conversion (`convert`) commands to Debussy. These features bridge the gap between how users naturally create plans and Debussy's required format.

## Goals

1. **Validation** - Fast, deterministic audit of plan structure before execution
2. **Scaffolding** - Generate correct plan templates with `debussy init`
3. **Conversion** - Transform freeform plans to Debussy format with agent assistance

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Audit Command](phase-1-audit.md) | Deterministic plan validation | Low | Completed |
| 2 | [Templates & Init](phase-2-templates-init.md) | Scaffold from templates | Low | Completed |
| 3 | [Audit Improvements](phase-3-audit-improvements.md) | Verbose output, suggestions, JSON | Low | Pending |
| 4 | [Convert Command](phase-4-convert.md) | Agent-powered plan conversion | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Plan validation | None | Deterministic audit | Audit + examples | Full pipeline |
| User onboarding | Manual | Audit feedback | `init` scaffolding | `convert` fallback |
| Test coverage | ~64% | 70% | 75% | 80% |

## Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
(Audit)    (Init)    (Audit++)   (Convert)
```

- Phase 1 (Audit): Independent, can be deployed alone
- Phase 2 (Templates + Init): Independent of audit, but audit validates output
- Phase 3 (Audit Improvements): Enhances audit with verbose output, suggestions, JSON
- Phase 4 (Convert): Requires Phase 3's JSON output and suggestions for agent guidance

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Parser edge cases | Medium | Low | Comprehensive test fixtures |
| Convert agent loops | Medium | Medium | Max iteration limit, audit gate |
| Template maintenance burden | Low | Low | Keep templates minimal |

## Out of Scope

- Modifying Claude Code's plan mode
- Skills for guided planning (P2 - future)
- Silver-tier "fuzzy" plan support (rejected - garbage in, garbage out)
- Security audit of plan content (future: cybersec agent to detect malicious gates like `rm -rf /`)

## Review Checkpoints

- After Phase 1: Audit passes on Grain_API plans, fails on malformed plans
- After Phase 2: `debussy init` produces audit-passing plans
- After Phase 3: `debussy convert` transforms freeform → audit-passing plans

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI entry points
- `src/debussy/parsers/` - Plan parsing logic
- `src/debussy/core/` - Core models and logic

**Test Locations:**
- `tests/test_parsers.py` - Parser tests
- `tests/fixtures/` - Sample plan files

**Related Documentation:**
- [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) - Original roadmap
- [docs/templates/](../../templates/) - Existing templates
