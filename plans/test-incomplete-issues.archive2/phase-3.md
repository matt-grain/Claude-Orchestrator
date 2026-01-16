# Theme Customization Phase 3: Dark Mode and Theme System

**Status:** Pending
**Master Plan:** [theme-customization-MASTER_PLAN.md](theme-customization-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_theme_customization_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- bandit: `uv run bandit -r src/` (no high severity)
- ty: `uv run ty check src/` (0 errors)
- semgrep: `semgrep --config auto src/` (no high severity)
- textual-tui-expert: Agent review via `@.claude\agents\textual-tui-expert.md` (approval required)

---

## Overview

This phase implements dark mode and theme customization for Debussy's TUI interface. Users will be able to configure their preferred theme (dark/light) via the YAML config file, with the TUI responding dynamically to theme changes. The implementation leverages Textual's built-in theming system and CSS variables to provide a cohesive, accessible UI experience.

## Dependencies
- Previous phase: N/A
- External: Textual framework (already in project dependencies)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing TUI styling | Medium | Medium | Preserve existing CSS classes, use CSS variables for theme-specific colors, extensive visual testing |
| Config schema changes breaking existing configs | Low | Medium | Add default theme value, make theme optional with fallback to light mode |
| Color contrast issues in different themes | Medium | Low | Follow WCAG color contrast guidelines, test with Textual's built-in dark/light modes |
| Performance impact from theme switching | Low | Low | Textual handles CSS reloading efficiently, minimize custom logic |

---

## Tasks

### 1. Configuration Schema Extension
- [ ] 1.1: Add `theme` field to `DebussyConfig` model in `src/debussy/config.py`
- [ ] 1.2: Define `ThemeMode` enum with values: `dark`, `light`, `auto` (system default)
- [ ] 1.3: Add config validation for theme field with default value `light`
- [ ] 1.4: Update config documentation in docstrings

### 2. CSS Theme System
- [ ] 2.1: Create `src/debussy/tui/themes/dark.tcss` with dark mode color scheme
- [ ] 2.2: Create `src/debussy/tui/themes/light.tcss` with light mode color scheme
- [ ] 2.3: Extract color values from existing `src/debussy/tui/app.tcss` into CSS variables
- [ ] 2.4: Update existing widgets to use theme-aware CSS variables instead of hardcoded colors
- [ ] 2.5: Ensure HUD, log panel, and all custom widgets support both themes

### 3. TUI Theme Application
- [ ] 3.1: Add `theme` reactive attribute to `DebussyTUI` class in `src/debussy/tui/tui.py`
- [ ] 3.2: Implement theme loading logic in `DebussyTUI.__init__()` from config
- [ ] 3.3: Add theme CSS loading in `DebussyTUI.on_mount()` based on configured theme
- [ ] 3.4: Implement `dark` property override to respect user's theme config
- [ ] 3.5: Add hot-reload support for theme changes (optional: watch config file)

### 4. Testing and Validation
- [ ] 4.1: Create unit tests for `ThemeMode` enum and config validation
- [ ] 4.2: Create integration tests for theme application in TUI
- [ ] 4.3: Add snapshot tests for dark and light themes (if feasible)
- [ ] 4.4: Manual testing checklist for visual verification
- [ ] 4.5: Request textual-tui-expert agent review of implementation

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add `theme` field and `ThemeMode` enum to configuration model |
| `src/debussy/tui/themes/dark.tcss` | Create | Dark mode color scheme and styling |
| `src/debussy/tui/themes/light.tcss` | Create | Light mode color scheme and styling |
| `src/debussy/tui/app.tcss` | Modify | Refactor to use CSS variables for theme-aware colors |
| `src/debussy/tui/tui.py` | Modify | Add theme loading and application logic |
| `tests/test_config_theme.py` | Create | Unit tests for theme configuration |
| `tests/test_tui_theme.py` | Create | Integration tests for TUI theme application |
| `docs/configuration.md` | Modify | Document new theme configuration option |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Reactive attributes | `src/debussy/tui/tui.py` (existing reactive props) | Use `reactive()` for theme attribute to enable watchers |
| CSS variable usage | Textual docs (https://textual.textualize.io/guide/CSS/#variables) | Define color variables in theme files, reference in widgets |
| Config loading | `src/debussy/config.py` (existing `load_config()`) | Follow existing pattern for loading and validating config |
| Theme switching | Textual `App.dark` property | Override `dark` property to respect user config instead of system default |

## Test Strategy

- [ ] Unit tests for new code:
  - `ThemeMode` enum values and validation
  - Config schema with theme field (valid/invalid values)
  - Default theme value when not specified
- [ ] Integration tests for modified functionality:
  - TUI initialization with different theme configs
  - Theme CSS loading and application
  - Verify `dark` property reflects configured theme
- [ ] Regression tests for existing functionality:
  - Existing TUI tests still pass with default (light) theme
  - No visual regressions in log panel, HUD, hotkey bar
- [ ] Manual testing checklist:
  - [ ] Create config with `theme: dark`, verify TUI launches in dark mode
  - [ ] Create config with `theme: light`, verify TUI launches in light mode
  - [ ] Config with no theme field defaults to light mode
  - [ ] All text remains readable in both themes (contrast check)
  - [ ] HUD colors, log syntax highlighting, status colors work in both themes
  - [ ] Textual-tui-expert agent review confirms architecture quality

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, ty, semgrep)
- [ ] Textual-tui-expert agent review approved
- [ ] Tests written and passing (>= 90% coverage for new code)
- [ ] Documentation updated with theme configuration examples
- [ ] No security vulnerabilities introduced
- [ ] User can set `theme: dark` or `theme: light` in `.debussy/config.yaml`
- [ ] TUI reflects configured theme on launch
- [ ] All existing TUI functionality works in both themes

## Rollback Plan

If theme system introduces breaking changes:

1. **Immediate rollback**: Revert commits related to theme implementation
   ```bash
   git revert <theme-commit-range>
   git push origin main
   ```

2. **Config compatibility**: Existing configs without `theme` field continue to work (default to light mode)

3. **CSS fallback**: If theme CSS files fail to load, TUI falls back to existing `app.tcss` styling

4. **No database migrations**: This feature is config-only, no state.db changes required

5. **User communication**: If rolled back, document theme feature as experimental in release notes

---

## Implementation Notes

### Architecture Decisions

1. **Textual Native Theming**: Leverage Textual's built-in `dark` mode and CSS system rather than building custom theme engine. This ensures compatibility and reduces maintenance burden.

2. **Config-Driven**: Theme is set via YAML config, not runtime toggle. This aligns with Debussy's configuration philosophy and avoids UI complexity. Future enhancement could add hotkey toggle if needed.

3. **CSS Variables**: Use Textual CSS variables (e.g., `$primary`, `$accent`) to centralize color definitions. This makes themes maintainable and allows easy addition of custom themes later.

4. **Agent Review Requirement**: Since this modifies core TUI architecture, textual-tui-expert agent review is mandatory to ensure proper reactive patterns, CSS best practices, and UI/logic separation.

### Color Scheme Considerations

- Dark theme: Follow Textual's default dark palette (grays, blues) with adjustments for Debussy branding
- Light theme: High contrast background with readable text, accessible color choices
- Status colors (success/warning/error) must work in both themes
- Syntax highlighting in log panel should adapt to theme

### Future Enhancements (Out of Scope)

- Runtime theme switching via hotkey (would require additional reactive logic)
- Custom theme files (user-provided .tcss files)
- `auto` mode that follows system theme (requires OS integration)
