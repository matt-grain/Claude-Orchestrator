# Export Plans & UX Improvements - Master Plan

**Created:** 2026-01-16
**Status:** Draft

---

## Overview

This plan implements three independent UX and documentation enhancements to Debussy: plan export functionality (MD/PDF), improved audit error diagnostics, and TUI dark mode customization. These features improve plan shareability, developer experience, and UI personalization without modifying core orchestration logic.

## Goals

1. **Plan Export** - Enable users to export implementation plans (with embedded notes) to Markdown and PDF formats for team sharing and manual test planning
2. **Audit Clarity** - Provide actionable guidance for the most common audit failures (circular dependencies, missing references, missing data)
3. **UI Customization** - Allow users to personalize the TUI appearance with theme selection to improve comfort during long orchestration sessions

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Plan Export Command](phase-1.md) | Export plans to MD/PDF with embedded notes | Medium | Pending |
| 2 | [Enhanced Audit Diagnostics](phase-2.md) | Actionable error messages for common failures | Low | Pending |
| 3 | [TUI Theme System](phase-3.md) | Dark mode and theme customization | Low | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Plan export formats supported | 0 | 2 (MD, PDF) | 2 | 2 |
| Audit errors requiring manual investigation | ~80% | ~80% | ~30% | ~30% |
| TUI themes available | 1 (default) | 1 | 1 | 3+ |
| User-reported audit confusion issues | Baseline | Baseline | -50% | -50% |

## Dependencies

```
Phase 1 ──► (no dependencies)
Phase 2 ──► (no dependencies)  
Phase 3 ──► (no dependencies)

All phases can deploy independently
```

Each phase addresses a distinct feature from a separate GitHub issue with no cross-dependencies. They can be implemented and deployed in any order based on priority.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF generation library vulnerabilities | Medium | High | Use ty and semgrep security scans; select well-maintained free libraries; sandbox PDF generation |
| PDF rendering quality issues (formatting, fonts) | Medium | Medium | Prototype with sample plans early; include visual regression tests |
| Theme system complexity in Textual | Low | Low | Leverage Textual's built-in theme support; consult @textual-tui-expert agent |
| Breaking changes to audit error format | Low | Medium | Ensure new diagnostics extend (not replace) existing messages; version error schemas |

## Out of Scope

- Export to formats beyond MD and PDF (no HTML, JSON, DOCX, etc.)
- Real-time collaborative editing of plans
- Automated test generation from exported plans
- Custom theme creation UI (only selection from predefined themes)
- Internationalization of error messages
- Integration with external documentation systems

## Review Checkpoints

- **After Phase 1:** Verify exported PDFs are readable, contain all plan content plus embedded notes, and pass ty/semgrep scans. Confirm MD exports match source fidelity.
- **After Phase 2:** Validate that circular dependency, missing reference, and missing data errors include clear "how to fix" guidance. Test with deliberately broken plans.
- **After Phase 3:** Confirm theme selection persists in config YAML, TUI updates correctly on theme change, and @textual-tui-expert agent approves architecture.

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI command definitions (add export, theme subcommands)
- `src/debussy/exporters/` - New module for MD/PDF export logic
- `src/debussy/audit/` - Audit and compliance checking (enhance error messages)
- `src/debussy/tui/` - Textual UI components (theme system integration)
- `src/debussy/config.py` - Configuration management (theme settings)

**Test Locations:**
- `tests/test_exporters.py` - Export functionality tests
- `tests/test_audit_diagnostics.py` - Enhanced error message tests
- `tests/test_tui_themes.py` - Theme system tests

**Related Documentation:**
- `docs/EXPORT.md` - Export command usage guide (create in Phase 1)
- `docs/AUDIT_ERRORS.md` - Common audit failures reference (create in Phase 2)
- `docs/THEMES.md` - Theme customization guide (create in Phase 3)
