# Export Plans, Better Error Messages, and Dark Mode - Master Plan

**Created:** 2026-01-16
**Status:** Draft

---

## Overview

This plan implements three independent enhancements to Debussy: (1) exporting implementation plans to MD and PDF formats with embedded notes for team sharing and test planning, (2) improving audit error messages with actionable guidance for common failure cases, and (3) adding dark mode customization to the TUI for better user experience.

## Goals

1. **Plan Export** - Enable users to export plans (with embedded implementation notes) to MD and PDF formats for review, archival, and manual test strategy development
2. **Clear Error Messages** - Provide actionable guidance in audit failure messages for the three most common cases: circular dependencies, missing references, and missing data
3. **UI Customization** - Allow users to configure terminal theme (dark mode) in YAML config and see changes reflected in TUI

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Plan Export Command](phase-1.md) | Add export CLI command with MD/PDF output | Medium | Pending |
| 2 | [Enhanced Audit Error Messages](phase-2.md) | Improve error clarity for common failures | Low | Pending |
| 3 | [Dark Mode UI Customization](phase-3.md) | Add theme configuration to TUI | Low | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Export formats supported | 0 | 2 (MD, PDF) | 2 | 2 |
| Audit error clarity score (user survey) | N/A | N/A | 8/10 | 8/10 |
| TUI theme options | 1 (default) | 1 | 1 | 2+ (light/dark) |
| PDF vulnerability scan coverage | 0% | 100% | 100% | 100% |

## Dependencies

```
Phase 1 (Export)
   └── Can deploy independently

Phase 2 (Errors)
   └── Can deploy independently

Phase 3 (Dark Mode)
   └── Can deploy independently
```

All three phases are independent with no dependencies between them. Each can be deployed separately as per user requirements.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF library vulnerabilities | Medium | High | Use ty and semgrep scanning; select well-maintained free libraries only |
| PDF rendering inconsistencies | Medium | Medium | Test with various plan structures; implement fallback to MD export |
| Theme config breaking existing TUI | Low | Medium | Use Textual's built-in theme system; mandatory @textual-tui-expert review |
| Error message over-verbosity | Low | Low | Focus on 3 most common cases only; keep messages concise |

## Out of Scope

- Export formats beyond MD and PDF (no HTML, JSON, DOCX, etc.)
- Interactive PDF features (annotations, forms)
- Real-time TUI theme switching (requires restart)
- Batch export of multiple plans
- Cloud storage integration for exports
- Email/sharing functionality
- Custom error message templates
- AI-powered error suggestions beyond the three specified cases

## Review Checkpoints

- After Phase 1: Verify MD and PDF exports are readable, contain embedded notes, pass ty/semgrep/bandit/radon/pyright/ruff validation
- After Phase 2: Audit failures for circular dependency, missing reference, and missing data show clear actionable guidance
- After Phase 3: Theme configuration changes in YAML are reflected in TUI; @textual-tui-expert review confirms best practices

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI command definitions (export command, config handling)
- `src/debussy/exporters/` - Export functionality (MD and PDF generators)
- `src/debussy/audit/` - Audit logic and error message generation
- `src/debussy/tui.py` - TUI implementation and theme application
- `src/debussy/config.py` - Configuration schema and validation

**Test Locations:**
- `tests/test_export.py` - Export command tests
- `tests/test_audit_errors.py` - Enhanced error message tests
- `tests/test_tui_themes.py` - Theme configuration tests

**Related Documentation:**
- `docs/EXPORT.md` - Export feature usage guide
- `docs/AUDIT_ERRORS.md` - Common error patterns and fixes
- `docs/THEMING.md` - TUI customization guide
