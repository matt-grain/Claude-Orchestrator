# CLI Theming Phase 2: Theme Configuration and Textual CSS Integration

**Status:** Pending
**Master Plan:** [cli-theming-MASTER_PLAN.md](cli-theming-MASTER_PLAN.md)
**Depends On:** [phase-1.md](phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_cli_theming_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_cli_theming_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity issues)

---

## Overview

This phase implements the configuration layer and CSS theme integration for the Debussy TUI. It builds on the theme model created in Phase 1 by adding persistent user configuration, dynamic theme switching, and Textual CSS generation. Users will be able to configure their preferred theme via CLI and config files, with changes applying immediately to the TUI.

## Dependencies
- Previous phase: [phase-1.md](phase-1.md) - Theme data model and built-in themes
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Config file corruption breaks TUI startup | Medium | High | Add validation on config load with fallback to defaults; include config repair command |
| CSS generation produces invalid Textual syntax | Low | Medium | Unit test CSS output against known-good samples; validate with Textual's CSS parser |
| Theme switching during active run causes visual glitches | Medium | Low | Implement reactive properties correctly; test hot-reload scenarios thoroughly |

---

## Tasks

### 1. Configuration Schema and Persistence
- [ ] 1.1: Add `theme` field to `Config` dataclass in `src/debussy/config.py`
- [ ] 1.2: Implement `load_theme_config()` method with validation and fallback to "default"
- [ ] 1.3: Implement `save_theme_config(theme_name: str)` method with atomic write
- [ ] 1.4: Add config migration logic for existing configs without theme field

### 2. CSS Generation Engine
- [ ] 2.1: Create `src/debussy/themes/css_generator.py` with `generate_css(theme: Theme) -> str` function
- [ ] 2.2: Map theme colors to Textual CSS variables (background, surface, primary, text, dim_text, accent, success, warning, error)
- [ ] 2.3: Generate CSS rules for HUDHeader, LogPanel, HotkeyBar, ResumeConfirmScreen
- [ ] 2.4: Add CSS validation helper to catch syntax errors before application

### 3. Dynamic Theme Switching in TUI
- [ ] 3.1: Add `current_theme` reactive property to `DebussyTUI` class
- [ ] 3.2: Implement `apply_theme(theme_name: str)` method that regenerates CSS and updates stylesheet
- [ ] 3.3: Hook theme application into TUI initialization (read from config)
- [ ] 3.4: Add theme reload on config change detection (optional: watch file)

### 4. CLI Theme Commands
- [ ] 4.1: Add `debussy theme list` command to display available themes with color previews
- [ ] 4.2: Add `debussy theme set <name>` command to change active theme
- [ ] 4.3: Add `debussy theme show [name]` command to display theme details
- [ ] 4.4: Update `--help` text to document theme commands

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add theme field and persistence methods |
| `src/debussy/themes/css_generator.py` | Create | Generate Textual CSS from Theme objects |
| `src/debussy/tui.py` | Modify | Add reactive theme switching and CSS application |
| `src/debussy/cli.py` | Modify | Add theme subcommands (list, set, show) |
| `tests/test_config_theme.py` | Create | Test config persistence and migration |
| `tests/test_css_generator.py` | Create | Test CSS generation for all built-in themes |
| `tests/test_tui_theme_switching.py` | Create | Test dynamic theme changes in TUI |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Reactive properties | `src/debussy/tui.py` (existing reactives like `current_phase`) | Use for `current_theme` to trigger CSS regeneration |
| Atomic file writes | `src/debussy/state.py` (StateManager patterns) | Apply to config save to prevent corruption |
| CLI subcommands | `src/debussy/cli.py` (existing `audit`, `convert` commands) | Use `@click.group()` for theme command group |
| CSS hot-reload | Textual docs on `refresh_css()` | Call on theme change to update without restart |

## Test Strategy

- [ ] Unit tests for CSS generation (validate output for each built-in theme)
- [ ] Unit tests for config persistence (save, load, migration, validation)
- [ ] Integration tests for theme switching (verify TUI updates correctly)
- [ ] Manual testing: Run TUI, switch themes via CLI, verify colors change immediately
- [ ] Regression tests: Ensure existing TUI functionality unaffected by theme system

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Can set theme via `debussy theme set dark` and see change in next TUI run
- [ ] Can list themes via `debussy theme list` with visual preview
- [ ] CSS generator produces valid Textual CSS for all built-in themes
- [ ] Config file validates and repairs gracefully on corruption
- [ ] No visual glitches when switching themes
- [ ] Code coverage maintained or improved

## Rollback Plan

**If critical issues arise:**

1. **Config corruption:** Run `debussy config reset` (to be added) or manually delete `~/.debussy/config.yaml` to restore defaults
2. **CSS generation bugs:** Revert `css_generator.py` changes and fall back to hardcoded default CSS in TUI
3. **Git revert:** `git revert <commit-hash>` for this phase's changes
4. **Database safety:** No database changes in this phase, only config file affected
5. **Backup recommendation:** Users should back up `~/.debussy/config.yaml` before upgrading

**Recovery commands:**
```bash
# Remove corrupted config (will regenerate with defaults)
rm ~/.debussy/config.yaml

# Force theme reset
debussy theme set default

# Full rollback
git revert HEAD
uv pip install -e .
```

---

## Implementation Notes

**Architectural Decisions:**

1. **CSS Generation vs Static Files:** Generating CSS dynamically allows unlimited theme customization without shipping multiple CSS files. Trade-off: slight startup cost for CSS generation (negligible with caching).

2. **Config vs CLI Args:** Theme is persisted in config for convenience (survives sessions), but can be overridden with `--theme` flag for one-off runs.

3. **Validation Strategy:** Config validation happens at load time with automatic fallback to defaults. Invalid theme names log a warning and use "default" theme.

4. **Textual CSS Mapping:** The theme's color palette maps to Textual's semantic variables:
   - `background` → `$background`
   - `surface` → `$surface`
   - `primary` → `$primary`
   - `accent` → `$accent`
   - `success/warning/error` → `$success/$warning/$error`

5. **Hot-Reload Consideration:** Textual's `refresh_css()` allows theme changes without restart, but this phase focuses on config persistence. Hot-reload via file watching is deferred to Phase 3 if time allows.

**Notes Space:**
- Document any theme rendering issues discovered during implementation
- Track performance of CSS generation (should be <10ms)
- Note any Textual CSS limitations encountered
