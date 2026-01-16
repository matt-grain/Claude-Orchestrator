# Multi-Feature Enhancement - Master Plan

**Created:** 2026-01-16
**Status:** Draft
**Analysis:** N/A

---

## Overview

This plan implements three independent enhancements to Debussy: plan export functionality (Issue #12), improved audit error messages (Issue #11), and TUI dark mode support (Issue #10). Each feature improves usability and user experience in different areas of the tool, making Debussy more production-ready and user-friendly.

## Goals

1. **Export Capability** - Enable users to export implementation plans to Markdown and PDF formats for archival and manual test planning
2. **Enhanced Diagnostics** - Provide clear, actionable error messages for common audit failures to reduce debugging time
3. **UI Customization** - Add dark mode theming to the TUI for improved visual comfort and user preference support

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Audit Error Message Improvements](phase-1.md) | Enhanced diagnostics for circular dependency, missing reference, and missing data errors | Low | Pending |
| 2 | [TUI Dark Mode Implementation](phase-2.md) | Theme configuration and Textual CSS integration | Medium | Pending |
| 3 | [Plan Export to Markdown](phase-3.md) | Export plans and implementation notes to MD format | Low | Pending |
| 4 | [Plan Export to PDF](phase-4.md) | PDF generation with security validation | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|---------|
| Audit error clarity (user rating) | Unknown | 4/5 | 4/5 | 4/5 | 4/5 |
| TUI customization options | 0 | 0 | 2 themes | 2 themes | 2 themes |
| Export formats supported | 0 | 0 | 0 | 1 (MD) | 2 (MD+PDF) |
| Test coverage | ~60% | ≥60% | ≥60% | ≥60% | ≥60% |

## Dependencies

```
Phase 1 ──► Can deploy independently
Phase 2 ──► Can deploy independently (requires textual-tui-expert review)
Phase 3 ──► Phase 4
   │           │
   └── Can deploy ───┴── Cannot deploy independently
```

- Phase 1 (Error Messages): Independent, no dependencies
- Phase 2 (Dark Mode): Independent, must be reviewed by textual-tui-expert agent
- Phase 3 (MD Export): Foundation for Phase 4, can deploy alone
- Phase 4 (PDF Export): Depends on Phase 3 export command structure

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF generation library vulnerabilities | Medium | High | Use `ty` and `semgrep` gates; choose well-maintained free library with security track record |
| Textual theme breaking existing UI | Low | Medium | Comprehensive visual testing; fallback to default theme; textual-tui-expert review |
| Export command conflicting with existing CLI | Low | Low | Follow existing CLI patterns; comprehensive command tests |
| Complex audit error messages still unclear | Medium | Medium | Iterative testing with real failure cases; include examples in messages |

## Out of Scope

- Export to formats other than Markdown and PDF (e.g., HTML, DOCX)
- Real-time theme switching in running TUI sessions (requires restart)
- Custom theme creation by users (only light/dark presets)
- Internationalization of error messages
- Export scheduling or automation features

## Review Checkpoints

- After Phase 1: Validate error messages with real audit failures; confirm clarity improvements with test cases
- After Phase 2: textual-tui-expert agent review required; visual verification of both themes across all TUI screens
- After Phase 3: Verify MD export includes all plan sections and implementation notes; test with complex multi-phase plans
- After Phase 4: Security scan PDF outputs with `ty` and `semgrep`; validate PDF readability across platforms

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI command definitions (export, audit)
- `src/debussy/compliance/checker.py` - Audit error message generation
- `src/debussy/tui.py` - TUI implementation and theming
- `src/debussy/config.py` - Configuration schema for theme settings
- `src/debussy/exporters/` - New module for export functionality

**Test Locations:**
- `tests/test_compliance.py` - Error message tests
- `tests/test_tui.py` - Theme switching tests
- `tests/test_exporters.py` - Export functionality tests

**Related Documentation:**
- `docs/AUDIT_ERRORS.md` - Error message reference (to be created in Phase 1)
- `docs/THEMING.md` - Theme configuration guide (to be created in Phase 2)
- `docs/EXPORT.md` - Export command documentation (to be created in Phase 3)
