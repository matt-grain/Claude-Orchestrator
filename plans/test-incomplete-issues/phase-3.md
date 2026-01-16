# Export Plans & UX Improvements Phase 3: TUI Theme System

**Status:** Pending
**Master Plan:** [Export Plans & UX Improvements-MASTER_PLAN.md](export-plans-ux-improvements-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase for this feature)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-ux-improvements_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- textual-expert-review: `@textual-tui-expert agent reviews theme implementation for architectural soundness and Textual best practices`

---

## Overview

This phase implements a theme system for Debussy's Textual TUI, allowing users to customize the terminal appearance through a configuration-based theme selection mechanism. The feature enables users to choose between multiple predefined themes (including dark mode options) which persist in the `.debussy/config.yaml` file and apply immediately to the TUI without requiring restart. This improves user comfort during long orchestration sessions by accommodating individual UI preferences.

## Dependencies
- Previous phase: N/A (independent)
- External: Textual framework's built-in theme support

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Theme system complexity in Textual | Low | Low | Leverage Textual's built-in CSS variable system; consult @textual-tui-expert agent for architectural review |
| Theme selection breaking existing TUI layouts | Low | Medium | Add visual regression tests; test all screens with each theme; ensure theme only affects colors/appearance, not layout |
| Configuration loading errors disrupting startup | Low | Medium | Add fallback to default theme if config invalid; validate theme selection at config load time |
| Performance impact from theme switching | Low | Low | Use Textual's reactive CSS updates; profile theme changes to ensure <100ms latency |

---

## Tasks

### 1. Theme Configuration Schema
- [ ] 1.1: Add `theme` field to Config model in `src/debussy/config.py` with default="default" and validation
- [ ] 1.2: Define ThemeChoice enum with initial themes: "default", "dark", "solarized-dark", "monokai"
- [ ] 1.3: Add config validation to ensure theme value is valid ThemeChoice
- [ ] 1.4: Add theme persistence tests to verify config save/load cycle

### 2. Theme CSS Definitions
- [ ] 2.1: Create `src/debussy/tui/themes/` module with `__init__.py` and `registry.py`
- [ ] 2.2: Define base theme structure using Textual CSS variables (background, surface, primary, secondary, accent, text, text-muted, error, success, warning)
- [ ] 2.3: Implement "default" theme (current TUI colors)
- [ ] 2.4: Implement "dark" theme (darker backgrounds, higher contrast)
- [ ] 2.5: Implement "solarized-dark" theme (Solarized Dark color scheme)
- [ ] 2.6: Implement "monokai" theme (Monokai color scheme)
- [ ] 2.7: Create ThemeRegistry class to manage theme loading and application

### 3. TUI Integration
- [ ] 3.1: Add `theme` reactive property to DebussyTUI in `src/debussy/tui/tui.py`
- [ ] 3.2: Create `watch_theme()` method to apply theme changes dynamically via CSS variable updates
- [ ] 3.3: Load theme from config in `DebussyTUI.__init__()` and apply on startup
- [ ] 3.4: Update `src/debussy/tui/textual_ui.py` to pass theme from config to TUI initialization
- [ ] 3.5: Add theme hot-reload support (update TUI when config changes)

### 4. CLI Command
- [ ] 4.1: Add `theme` subcommand to CLI in `src/debussy/cli.py`
- [ ] 4.2: Implement `theme list` command to display available themes with descriptions
- [ ] 4.3: Implement `theme set <theme_name>` command to update config and display confirmation
- [ ] 4.4: Implement `theme show` command to display current theme setting
- [ ] 4.5: Add CLI help text and examples for theme commands

### 5. Testing & Validation
- [ ] 5.1: Create `tests/test_tui_themes.py` with theme registry tests
- [ ] 5.2: Add tests for theme configuration persistence
- [ ] 5.3: Add tests for theme application to TUI (verify CSS variables updated)
- [ ] 5.4: Add tests for CLI theme commands (list, set, show)
- [ ] 5.5: Add visual validation tests (pilot-based) for each theme with all TUI screens
- [ ] 5.6: Invoke @textual-tui-expert agent to review theme architecture and implementation

### 6. Documentation
- [ ] 6.1: Create `docs/THEMES.md` with theme customization guide
- [ ] 6.2: Document available themes with screenshots or color descriptions
- [ ] 6.3: Document CLI commands for theme management
- [ ] 6.4: Add theme configuration examples to main documentation
- [ ] 6.5: Update README.md with theme feature mention

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add `theme` field to Config model with ThemeChoice enum and validation |
| `src/debussy/tui/themes/__init__.py` | Create | Export theme registry and theme names |
| `src/debussy/tui/themes/registry.py` | Create | ThemeRegistry class to manage theme definitions and application |
| `src/debussy/tui/themes/default.py` | Create | Default theme definition (current TUI colors) |
| `src/debussy/tui/themes/dark.py` | Create | Dark theme definition |
| `src/debussy/tui/themes/solarized_dark.py` | Create | Solarized Dark theme definition |
| `src/debussy/tui/themes/monokai.py` | Create | Monokai theme definition |
| `src/debussy/tui/tui.py` | Modify | Add theme reactive property and watch_theme() method |
| `src/debussy/tui/textual_ui.py` | Modify | Pass theme from config to TUI initialization |
| `src/debussy/cli.py` | Modify | Add theme subcommand with list/set/show operations |
| `tests/test_tui_themes.py` | Create | Test suite for theme system (registry, config, application, CLI) |
| `tests/test_config.py` | Modify | Add tests for theme configuration persistence |
| `docs/THEMES.md` | Create | Theme customization guide and reference |
| `README.md` | Modify | Add theme feature to features list |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Textual CSS Variables | [Textual docs: CSS Variables](https://textual.textualize.io/guide/CSS/#css-variables) | Define theme colors as CSS variables for dynamic updates |
| Reactive Properties | `src/debussy/tui/tui.py` (existing reactive props) | Use reactive `theme` property with watcher for dynamic theme switching |
| Config Model Extension | `src/debussy/config.py` (existing Config model) | Add theme field with Pydantic validation and default value |
| CLI Subcommand Pattern | `src/debussy/cli.py` (existing subcommands like `audit`, `convert`) | Add `theme` subcommand with list/set/show operations |
| Registry Pattern | Similar to test fixture patterns | Use ThemeRegistry class to manage theme definitions and lookup |

## Test Strategy

- [ ] Unit tests for ThemeRegistry (theme loading, validation, lookup)
- [ ] Unit tests for Config model theme field (validation, persistence)
- [ ] Integration tests for CLI theme commands (list, set, show)
- [ ] Integration tests for TUI theme application (CSS variable updates)
- [ ] Pilot-based visual tests for each theme with all TUI screens (HUD, logs, dialogs)
- [ ] Manual testing checklist:
  - [ ] Start TUI with default theme, verify appearance
  - [ ] Run `debussy theme list`, verify all themes shown
  - [ ] Run `debussy theme set dark`, restart TUI, verify dark theme applied
  - [ ] Change theme in config.yaml manually, restart TUI, verify theme applied
  - [ ] Test invalid theme name in config, verify fallback to default
  - [ ] Invoke @textual-tui-expert agent to review architecture and implementation

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, tests, bandit)
- [ ] @textual-tui-expert agent review completed and recommendations addressed
- [ ] Tests written and passing (>95% coverage for theme module)
- [ ] Documentation updated (THEMES.md created, README updated)
- [ ] No security vulnerabilities introduced
- [ ] Theme selection persists in `.debussy/config.yaml`
- [ ] TUI updates appearance when theme changed via CLI or config
- [ ] At least 3 themes available beyond default (dark, solarized-dark, monokai)
- [ ] All TUI screens render correctly with all themes
- [ ] Invalid theme values fall back gracefully to default theme

## Rollback Plan

If theme system introduces issues:

1. **Immediate mitigation**: Set `theme: default` in `.debussy/config.yaml` to restore original appearance
2. **Code rollback**:
   ```bash
   git revert <commit-hash>  # Revert theme system commit
   uv run pytest tests/ -v    # Verify tests pass after revert
   ```
3. **Config cleanup**: Remove `theme` field from Config model and regenerate config files
4. **Module removal**: Delete `src/debussy/tui/themes/` directory if theme module causes import errors
5. **Verify TUI**: Run `debussy run` with a test plan to confirm TUI functionality restored

No database migrations or destructive changes involved in this phase.

---

## Implementation Notes

**Textual Theme Architecture Considerations:**
- Use Textual's CSS variable system (`$variable_name`) for theme colors to enable runtime updates without full app reload
- Define theme colors for: `$background`, `$surface`, `$primary`, `$secondary`, `$accent`, `$text`, `$text-muted`, `$error`, `$success`, `$warning`
- Ensure theme changes only affect appearance (colors, borders) and NOT layout (spacing, alignment)
- Use `watch_theme()` to call `self.refresh(layout=False)` for efficient updates

**Theme Registry Design:**
- ThemeRegistry should be a singleton providing `get_theme(name: str) -> dict[str, str]` method
- Each theme module (default.py, dark.py, etc.) exports a `THEME` dict mapping CSS variable names to color values
- Registry validates theme names and provides fallback to default theme on invalid selection

**CLI UX:**
- `debussy theme list` should show theme names with brief descriptions (e.g., "dark - High contrast dark theme")
- `debussy theme set <name>` should update config.yaml and print confirmation: "Theme set to 'dark'. Restart TUI to apply changes."
- `debussy theme show` should print current theme name from config

**@textual-tui-expert Review Focus Areas:**
- Verify reactive property usage for theme switching is correct
- Confirm CSS variable approach aligns with Textual best practices
- Check for any threading issues with theme application
- Validate that theme system doesn't introduce UI/logic mixing
- Ensure proper separation between theme definitions (data) and application logic (registry)
