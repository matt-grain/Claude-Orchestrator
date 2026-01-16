# Export, Error Messages, Dark Mode Phase 5: CLI Output Enhancements & Export

**Status:** Pending
**Master Plan:** [export-error-dark-MASTER_PLAN.md](export-error-dark-MASTER_PLAN.md)
**Depends On:** [phase-4.md](phase-4.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_export_error_dark_phase_4.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export_error_dark_phase_5.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- export-validation: `debussy export --help && debussy export --format json sample.md` (succeeds)
- color-validation: Manual verification of dark mode color scheme readability

---

## Overview

This phase implements the final CLI output enhancements: applying the dark mode color scheme to all CLI output, implementing the export command with multiple format support, and ensuring error messages use the improved formatter. This completes the user-facing improvements for better usability and interoperability.

## Dependencies
- Previous phase: [phase-4.md](phase-4.md) - Error formatter, color scheme, validation
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Color scheme conflicts with existing Rich styling | Medium | Low | Test all CLI commands with new scheme; provide --no-color fallback |
| Export format breaks on malformed plans | Medium | Medium | Comprehensive validation before export; clear error messages |
| Performance degradation with colored output | Low | Low | Use Rich's optimized rendering; allow disabling colors |

---

## Tasks

### 1. Apply Dark Mode Color Scheme CLI-Wide
- [ ] 1.1: Create color theme manager in `src/debussy/ui/theme.py`
- [ ] 1.2: Apply color scheme to all CLI commands (run, audit, status, etc.)
- [ ] 1.3: Update TUI to respect color scheme configuration
- [ ] 1.4: Add `--no-color` flag to disable colored output globally

### 2. Implement Export Command
- [ ] 2.1: Create `src/debussy/commands/export.py` with export logic
- [ ] 2.2: Implement JSON export format (structured plan data)
- [ ] 2.3: Implement Markdown export format (cleaned/formatted)
- [ ] 2.4: Implement HTML export format (styled with templates)
- [ ] 2.5: Add export validation (ensure output is well-formed)
- [ ] 2.6: Wire export command into CLI in `src/debussy/cli.py`

### 3. Integration and Error Handling
- [ ] 3.1: Ensure all error messages use ErrorFormatter with colors
- [ ] 3.2: Add export-specific error messages for invalid formats
- [ ] 3.3: Update help text and documentation for export command
- [ ] 3.4: Add integration tests for export + color + errors together

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/ui/theme.py` | Create | Color theme manager with dark mode scheme and --no-color support |
| `src/debussy/commands/export.py` | Create | Export command implementation with JSON/Markdown/HTML formats |
| `src/debussy/exporters/json.py` | Create | JSON export logic (structured plan data) |
| `src/debussy/exporters/markdown.py` | Create | Markdown export logic (cleaned/formatted) |
| `src/debussy/exporters/html.py` | Create | HTML export logic (styled templates) |
| `src/debussy/exporters/base.py` | Create | Base exporter interface and validation |
| `src/debussy/cli.py` | Modify | Add export command and --no-color global flag |
| `src/debussy/ui/textual_ui.py` | Modify | Apply theme to TUI components |
| `src/debussy/ui/non_interactive.py` | Modify | Apply theme to non-interactive output |
| `tests/test_theme.py` | Create | Unit tests for theme manager |
| `tests/test_export_command.py` | Create | Unit tests for export command |
| `tests/test_exporters.py` | Create | Unit tests for all export formats |
| `tests/integration/test_cli_colors.py` | Create | Integration tests for color scheme across commands |
| `tests/integration/test_export_integration.py` | Create | Integration tests for export with real plans |
| `docs/EXPORT.md` | Create | Documentation for export command and formats |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Rich Theme Configuration | `src/debussy/config.py` | Use consistent Rich console with custom theme |
| Error Formatting | `src/debussy/ui/error_formatter.py` | Apply ErrorFormatter to export errors |
| Command Structure | `src/debussy/commands/audit.py` | Follow existing command pattern for export |
| Export Interface | Similar to serializers in web frameworks | Define base exporter with format() method |

## Test Strategy

- [ ] Unit tests for theme manager (color application, --no-color flag)
- [ ] Unit tests for each export format (JSON, Markdown, HTML)
- [ ] Unit tests for export validation (malformed plans, missing fields)
- [ ] Integration tests for export command with sample plans
- [ ] Integration tests for color scheme across all CLI commands
- [ ] Manual testing checklist:
  - [ ] Run `debussy run` with dark mode colors in light/dark terminals
  - [ ] Run `debussy export sample.md --format json` and verify output
  - [ ] Run `debussy export sample.md --format html` and open in browser
  - [ ] Verify `--no-color` disables all colored output
  - [ ] Test error messages with colors in various failure scenarios

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing
- [ ] Tests written and passing (unit + integration)
- [ ] Export command supports JSON, Markdown, HTML formats
- [ ] Dark mode color scheme applied to all CLI output
- [ ] `--no-color` flag works globally
- [ ] Error messages use ErrorFormatter with colors
- [ ] Documentation updated (EXPORT.md, CLI help text)
- [ ] No security vulnerabilities introduced

## Rollback Plan

1. Revert CLI color changes:
   ```bash
   git revert <commit-hash-for-theme-application>
   ```

2. Remove export command:
   ```bash
   git revert <commit-hash-for-export-command>
   rm -rf src/debussy/exporters/
   rm src/debussy/commands/export.py
   ```

3. Database state: No database changes in this phase, no migrations to reverse

4. Config rollback: Remove `color_scheme` and `export_defaults` from `.debussy/config.yaml`

5. Verify rollback:
   ```bash
   uv run pytest tests/ -v
   debussy --help  # Should not show export command
   ```

---

## Implementation Notes

**Color Scheme Application:**
- Use Rich's Theme API to define a global color scheme
- Apply theme to Console instances across all CLI commands
- TUI should use Rich's Color class for consistency
- Consider terminal background detection for better contrast

**Export Format Details:**
- JSON: Structured representation (phases, tasks, gates, metadata)
- Markdown: Clean, formatted output without execution state
- HTML: Styled with CSS, collapsible sections, print-friendly

**Performance Considerations:**
- Rich's rendering is fast, but test with large plans
- HTML export should use templates (Jinja2 or similar)
- Consider streaming for large exports

**Accessibility:**
- Ensure color scheme meets WCAG contrast ratios
- Provide --no-color for screen readers and plain terminals
- HTML export should have semantic structure
