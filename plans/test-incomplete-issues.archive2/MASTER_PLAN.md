# Multi-Feature Enhancement - Master Plan

**Created:** 2026-01-16
**Status:** Draft

---

## Overview

This plan delivers three independent enhancements to improve Debussy's usability and user experience: plan export functionality for documentation and archival, enhanced error diagnostics for audit failures, and UI customization through theme support.

## Goals

1. **Plan Export** - Enable users to export implementation plans to MD and PDF formats for team sharing, manual test planning, and archival purposes
2. **Improved Error Messages** - Provide actionable diagnostics for common audit failures (circular dependencies, missing references, missing data)
3. **UI Customization** - Allow users to personalize the TUI appearance through theme configuration, improving the overall experience

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Plan Export Command](phase-1.md) | Add CLI command to export plans with notes to MD/PDF | Medium | Pending |
| 2 | [Enhanced Audit Diagnostics](phase-2.md) | Improve error messages with actionable guidance | Low | Pending |
| 3 | [TUI Theme Support](phase-3.md) | Add dark mode and theme customization | Low | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Export formats supported | 0 | 2 (MD, PDF) | 2 | 2 |
| Audit error clarity score | N/A | N/A | 8/10 user rating | 8/10 |
| Theme options available | 1 (default) | 1 | 1 | 2+ (light/dark) |
| User satisfaction | Baseline | +20% | +30% | +50% |

## Dependencies

```
Phase 1 ──► Independent
Phase 2 ──► Independent  
Phase 3 ──► Independent

All phases can be deployed independently
```

No dependencies exist between phases. Each enhancement is self-contained and can be developed, tested, and deployed independently.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF generation vulnerabilities | Medium | High | Use ty and semgrep validation gates; select well-maintained free libraries |
| Export format incompatibility | Low | Medium | Test with various plan structures; validate MD/PDF readability |
| Complex error message logic | Low | Low | Focus on 3 most common failure cases initially |
| Theme CSS conflicts | Low | Medium | Leverage Textual's built-in theming; review by @textual-tui-expert |

## Out of Scope

- Export formats beyond MD and PDF (no HTML, JSON, or other formats)
- Error message improvements beyond the 3 common cases (circular dependency, missing reference, missing data)
- Advanced theme customization beyond light/dark modes
- Integration with external documentation systems
- Real-time error suggestion during plan editing
- Theme preview functionality

## Review Checkpoints

- After Phase 1: Verify MD and PDF exports are readable, contain implementation notes, and work across different plan types
- After Phase 2: Validate that audit errors for circular dependencies, missing references, and missing data provide clear fix guidance
- After Phase 3: Confirm theme switching works via config, TUI reflects changes correctly, and @textual-tui-expert approves implementation

---

## Quick Reference

**Key Files:**
- `src/debussy/cli.py` - CLI command definitions (export, existing commands)
- `src/debussy/audit/` - Audit compliance checker and error reporting
- `src/debussy/ui/tui.py` - Textual TUI implementation
- `.debussy/config.yaml` - User configuration (theme settings)

**Test Locations:**
- `tests/test_export.py` (Phase 1)
- `tests/test_audit_errors.py` (Phase 2)
- `tests/test_tui_themes.py` (Phase 3)

**Related Documentation:**
- `docs/AUDIT.md` - Audit compliance rules
- `docs/CLI.md` - CLI command reference
- `docs/CONFIG.md` - Configuration options
