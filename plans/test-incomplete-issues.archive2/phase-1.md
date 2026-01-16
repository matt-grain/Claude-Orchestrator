# UI Customization Phase 1: Theme System & Dark Mode

**Status:** Pending
**Master Plan:** [ui-customization-MASTER_PLAN.md](ui-customization-MASTER_PLAN.md)
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
  uv run ty check src/
  uv run bandit -r src/
  uv run radon cc src/ -n C
  uv run semgrep --config auto src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_ui_customization_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- ty: `uv run ty check src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- radon: `uv run radon cc src/ -n C` (no functions with grade worse than C)
- semgrep: `uv run semgrep --config auto src/` (no high severity)
- textual-tui-expert: Agent review of TUI implementation for best practices

---

## Overview

This phase implements a theme system for Debussy's TUI that supports light and dark modes. Users can configure their preferred terminal theme in the YAML configuration file, and the TUI will automatically apply the appropriate color scheme. This lays the foundation for broader UI customization in future phases.

## Dependencies
- Previous phase: N/A
- External: Textual framework (already a dependency)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Theme changes break existing TUI layout | Low | Medium | Comprehensive testing of all screens in both modes; use Textual's built-in theme support |
| Configuration migration breaks existing setups | Medium | High | Add backward compatibility; default to existing behavior if theme not specified |
| Performance impact from theme switching | Low | Low | Themes are loaded once at startup; no runtime overhead |
| Accessibility issues with color choices | Medium | Medium | Follow Textual's built-in theme standards; test with color contrast tools |

---

## Tasks

### 1. Configuration Schema Extension
- [ ] 1.1: Add `theme` field to config schema in `src/debussy/config/schema.py` with values: "light", "dark", "auto"
- [ ] 1.2: Update `Config` dataclass to include theme property with default "dark"
- [ ] 1.3: Add theme validation in config loader
- [ ] 1.4: Update example config in `docs/` with theme option

### 2. Textual Theme Integration
- [ ] 2.1: Create `src/debussy/tui/themes.py` with light and dark theme definitions
- [ ] 2.2: Map config theme values to Textual theme names
- [ ] 2.3: Apply theme in `DebussyTUI.__init__()` before app initialization
- [ ] 2.4: Update CSS files to use theme-aware color variables

### 3. TUI Component Updates
- [ ] 3.1: Review all custom widgets for hardcoded colors
- [ ] 3.2: Replace hardcoded colors with theme-aware CSS variables
- [ ] 3.3: Test HUD header in both themes
- [ ] 3.4: Test log panel syntax highlighting in both themes
- [ ] 3.5: Test hotkey bar visibility in both themes

### 4. Testing & Validation
- [ ] 4.1: Add unit tests for config theme parsing
- [ ] 4.2: Add integration tests for theme application
- [ ] 4.3: Create visual regression test suite for both themes
- [ ] 4.4: Invoke @textual-tui-expert agent for TUI architecture review

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config/schema.py` | Modify | Add theme field to configuration schema |
| `src/debussy/tui/themes.py` | Create | Define light and dark theme configurations |
| `src/debussy/tui/tui.py` | Modify | Apply theme on TUI initialization |
| `src/debussy/tui/styles.css` | Modify | Replace hardcoded colors with theme variables |
| `tests/test_config_theme.py` | Create | Unit tests for theme configuration |
| `tests/test_tui_theme.py` | Create | Integration tests for theme application |
| `docs/CONFIGURATION.md` | Modify | Document theme configuration option |
| `.debussy/config.yaml` | Modify | Add theme example to default config |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Config loading | `src/debussy/config/loader.py` | Follow existing pattern for adding new config fields |
| Textual theming | [Textual docs - Design system](https://textual.textualize.io/guide/design/) | Use built-in theme system and CSS variables |
| CSS variables | `src/debussy/tui/styles.css` | Define colors as CSS variables for easy theme switching |
| Widget initialization | `src/debussy/tui/tui.py` | Apply theme before mounting widgets |

## Test Strategy

- [ ] Unit tests for theme config validation (invalid values, defaults)
- [ ] Integration tests for theme application at TUI startup
- [ ] Manual testing checklist:
  - [ ] Light theme renders correctly on all screens
  - [ ] Dark theme renders correctly on all screens
  - [ ] HUD header is readable in both themes
  - [ ] Log panel syntax highlighting works in both themes
  - [ ] Hotkey bar is visible in both themes
  - [ ] No color contrast issues in either theme
- [ ] Agent review: Invoke textual-tui-expert to validate TUI implementation

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, ty, bandit, radon, semgrep)
- [ ] Tests written and passing (>80% coverage for new code)
- [ ] textual-tui-expert agent review completed with no critical issues
- [ ] Documentation updated with theme configuration examples
- [ ] No security vulnerabilities introduced
- [ ] User can set theme to "light" or "dark" in YAML config
- [ ] TUI correctly applies selected theme at startup
- [ ] All TUI components are readable and properly styled in both themes
- [ ] Backward compatibility: existing configs without theme field work correctly (default to dark)

## Rollback Plan

If theme implementation causes issues:

1. **Immediate rollback**: 
   ```bash
   git revert <commit-hash>
   git push
   ```

2. **Config migration issues**: 
   - Remove `theme` field from config schema
   - Deploy hotfix that ignores theme field if present
   - Users can continue with existing configs

3. **TUI rendering issues**:
   - Add feature flag `enable_themes: false` to disable theme system
   - Default to original hardcoded colors
   - Allow gradual rollout per user

4. **Backup configuration**:
   - Before deployment, backup existing `.debussy/config.yaml` files
   - Provide migration script if schema changes are incompatible

---

## Implementation Notes

### Architecture Decisions
- Use Textual's built-in theme system rather than custom CSS per theme
- Theme is loaded once at startup, not dynamically switched (future enhancement)
- Default to "dark" to maintain existing user experience
- CSS variables provide single source of truth for theme colors

### Textual Theme Integration
- Textual 0.40+ has improved theme support with `App.theme` property
- Use `textual.design.ColorSystem` for consistent color palettes
- Consider Textual's built-in themes as starting point (textual-dark, textual-light)

### Agent Review Requirements
After implementation, invoke textual-tui-expert agent with:
- All modified TUI files
- Request review for: theme application patterns, CSS variable usage, widget readability, separation of theme logic from UI logic
