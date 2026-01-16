# Dark Mode UI Customization Phase 3: Add theme configuration to TUI

**Status:** Pending
**Master Plan:** [Export Plans, Better Error Messages, and Dark Mode - Master Plan](export-plans-better-error-messages-and-dark-mode-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (independent phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  uv run radon cc src/ -a -nb
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_dark-mode-ui-customization_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- complexity: `uv run radon cc src/ -a -nb` (maintainability)
- textual-tui-expert: Agent review of TUI theme implementation (MANDATORY)

---

## Overview

This phase adds dark mode and theme customization to Debussy's TUI. Users will be able to configure their preferred terminal theme (light/dark) in `.debussy/config.yaml`, and the TUI will reflect these changes. The implementation leverages Textual's built-in theme system to ensure consistency and maintainability. A mandatory @textual-tui-expert agent review ensures adherence to Textual best practices.

## Dependencies
- Previous phase: N/A (independent phase)
- External: Textual framework's theme system

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Theme config breaking existing TUI | Low | Medium | Use Textual's built-in theme system; mandatory @textual-tui-expert review |
| Invalid theme names causing crashes | Low | Low | Add schema validation in Config; provide clear error messages |
| Theme not applied consistently | Low | Medium | Centralize theme application logic; comprehensive test coverage |

---

## Tasks

### 1. Configuration Schema Update
- [ ] 1.1: Add `theme` field to Config model in `src/debussy/config.py` with validation
- [ ] 1.2: Define allowed theme values (e.g., "dark", "light", "textual-dark", "textual-light")
- [ ] 1.3: Set sensible default theme (e.g., "textual-dark")
- [ ] 1.4: Add validation to reject invalid theme names

### 2. TUI Theme Application
- [ ] 2.1: Modify `DebussyTUI.__init__()` or `on_mount()` to read theme from config
- [ ] 2.2: Apply theme using Textual's `self.theme` property
- [ ] 2.3: Ensure theme is applied before TUI renders
- [ ] 2.4: Add logging for theme application (debug level)

### 3. Documentation
- [ ] 3.1: Create `docs/THEMING.md` with available themes and configuration examples
- [ ] 3.2: Update `README.md` or user guide to reference theming support
- [ ] 3.3: Document that theme changes require TUI restart (not real-time)

### 4. Testing
- [ ] 4.1: Unit tests for Config theme validation (valid/invalid values)
- [ ] 4.2: Integration tests verifying theme application in TUI
- [ ] 4.3: Manual testing with different theme values in config.yaml

### 5. Agent Review
- [ ] 5.1: Invoke @textual-tui-expert agent to review TUI theme implementation
- [ ] 5.2: Address any recommendations from agent review
- [ ] 5.3: Document agent review outcome in implementation notes

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add `theme` field with validation to Config model |
| `src/debussy/tui.py` | Modify | Apply theme from config in DebussyTUI initialization |
| `docs/THEMING.md` | Create | Document available themes and configuration usage |
| `tests/test_tui_themes.py` | Create | Test theme configuration and application |
| `tests/test_config.py` | Modify | Add tests for theme field validation |
| `.debussy/config.yaml` (example) | Modify | Add example theme configuration |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Config validation | `src/debussy/config.py` (existing patterns) | Use Pydantic validators for theme field |
| TUI initialization | `src/debussy/tui.py` (DebussyTUI.__init__) | Apply theme in `on_mount()` or constructor |
| Textual theme system | [Textual docs - Theming](https://textual.textualize.io/) | Use `self.theme = "theme-name"` pattern |

## Test Strategy

- [ ] Unit tests for Config model with valid/invalid theme values
- [ ] Unit tests verifying default theme when not specified
- [ ] Integration tests that instantiate DebussyTUI with various themes
- [ ] Manual testing: modify `.debussy/config.yaml` with different themes, launch TUI, verify visual changes
- [ ] Regression tests ensuring existing TUI functionality unaffected

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, radon)
- [ ] @textual-tui-expert agent review completed and recommendations addressed
- [ ] User can set `theme: "dark"` or `theme: "light"` in `.debussy/config.yaml`
- [ ] TUI applies configured theme on startup
- [ ] Invalid theme names trigger clear validation error
- [ ] `docs/THEMING.md` documents available themes and usage
- [ ] Tests written and passing (unit + integration)
- [ ] No security vulnerabilities introduced

## Rollback Plan

If theme implementation causes TUI failures:

1. Revert changes to `src/debussy/tui.py` and `src/debussy/config.py`
2. Remove `theme` field from Config model
3. Delete `tests/test_tui_themes.py` and related test modifications
4. Remove `docs/THEMING.md`
5. Run full test suite to confirm stability: `uv run pytest tests/ -v`
6. Commit rollback: `git revert <commit-hash>` or `git reset --hard <previous-commit>`

Backup strategy:
- Create feature branch `feature/dark-mode-phase3` before starting
- Tag stable state before applying changes: `git tag pre-phase3-theme`

---

## Implementation Notes

**Textual Theme System:**
- Textual provides built-in themes: "textual-dark", "textual-light", etc.
- Custom themes can be registered but are out of scope per user requirements
- Theme changes require TUI restart (no real-time switching per user clarification)

**Agent Review Focus:**
- Verify theme application doesn't block main thread
- Ensure theme selection follows Textual best practices
- Confirm no UI/logic mixing in theme application code
- Validate proper error handling for invalid theme values

**Configuration Strategy:**
- Theme defaults to "textual-dark" for backward compatibility
- Config schema validation prevents invalid theme names at load time
- Clear error message guides users to valid theme options
