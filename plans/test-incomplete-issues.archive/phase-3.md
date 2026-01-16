# Export Plans Phase 3: Export to Markdown Format

**Status:** Pending
**Master Plan:** [export-plans-MASTER_PLAN.md](export-plans-MASTER_PLAN.md)
**Depends On:** [Phase 2: Export Format Configuration](phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_export-plans_phase_2.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase implements the core export functionality that transforms Debussy plans and implementation notes into shareable Markdown format. Building on the configuration system from Phase 2, we'll create exporters that handle master plans, individual phase files, and implementation notes with appropriate formatting, metadata preservation, and output organization.

The export system will support both single-file and directory exports, with options for including/excluding completed phases, notes, and metadata. This enables teams to share plans via documentation sites, wikis, or version control.

## Dependencies
- Previous phase: [Phase 2: Export Format Configuration](phase-2.md)
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| File path resolution issues across platforms | Medium | Medium | Use pathlib.Path throughout, test on Windows/Linux/macOS |
| Large plans causing memory issues during export | Low | Medium | Stream file writes, process phases individually |
| Markdown rendering inconsistencies | Low | Low | Test with common renderers (GitHub, GitLab, MkDocs) |
| Loss of metadata during format conversion | Medium | High | Preserve YAML frontmatter, validate round-trip capability |

---

## Tasks

### 1. Core Export Models
- [ ] 1.1: Create `src/debussy/exporters/models.py` with ExportedPlan, ExportedPhase, ExportedNote dataclasses
- [ ] 1.2: Add metadata fields (exported_at, debussy_version, source_paths)
- [ ] 1.3: Implement to_dict/from_dict for serialization support

### 2. Markdown Exporter Implementation
- [ ] 2.1: Create `src/debussy/exporters/markdown.py` with MarkdownExporter class
- [ ] 2.2: Implement export_master_plan() - reads master plan, formats with metadata header
- [ ] 2.3: Implement export_phase() - converts phase file to standalone markdown
- [ ] 2.4: Implement export_notes() - formats implementation notes with phase context
- [ ] 2.5: Add _format_metadata_header() helper for YAML frontmatter generation

### 3. Export Orchestration
- [ ] 3.1: Create export_full_plan() in MarkdownExporter - exports master + all phases + notes
- [ ] 3.2: Add filtering options (include_completed, include_notes, phase_ids)
- [ ] 3.3: Implement directory structure creation (master-plan.md, phases/, notes/)
- [ ] 3.4: Add progress callbacks for CLI integration

### 4. File Operations & Safety
- [ ] 4.1: Implement safe_write() with atomic file writes (write to temp, then rename)
- [ ] 4.2: Add overwrite protection with confirmation prompts
- [ ] 4.3: Create backup functionality for existing files before overwrite
- [ ] 4.4: Add dry-run mode that shows what would be exported without writing

### 5. Content Formatting
- [ ] 5.1: Preserve task checkboxes and status across export
- [ ] 5.2: Format tables with proper alignment
- [ ] 5.3: Convert relative links to work in export location
- [ ] 5.4: Add table of contents generation for master plans

### 6. Testing
- [ ] 6.1: Unit tests for ExportedPlan/Phase/Note models (tests/test_exporters_models.py)
- [ ] 6.2: Integration tests for MarkdownExporter (tests/test_exporters_markdown.py)
- [ ] 6.3: Fixture-based tests using sample plans from tests/fixtures/
- [ ] 6.4: Test edge cases (empty phases, missing notes, special characters in filenames)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/exporters/__init__.py` | Create | Package init, expose MarkdownExporter |
| `src/debussy/exporters/models.py` | Create | Data models for exported content |
| `src/debussy/exporters/markdown.py` | Create | Core Markdown export implementation |
| `src/debussy/exporters/base.py` | Create | Abstract BaseExporter for future formats |
| `tests/test_exporters_models.py` | Create | Tests for export data models |
| `tests/test_exporters_markdown.py` | Create | Tests for Markdown exporter |
| `tests/fixtures/export_plans/` | Create | Sample plans for testing exports |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Parser pattern | `src/debussy/parsers/phase.py` | Read phase files using existing PhaseParser |
| Config integration | `src/debussy/config.py` | Read export settings from ExportConfig |
| Path resolution | `src/debussy/utils.py` | Use resolve_path() for cross-platform compatibility |
| Error handling | `src/debussy/exceptions.py` | Raise ExportError for export-specific failures |

## Test Strategy

- [ ] Unit tests for each model's serialization/deserialization
- [ ] Unit tests for metadata header formatting
- [ ] Integration tests for full plan export workflow
- [ ] Fixture-based tests using real plan examples from Phase 1
- [ ] Edge case tests: empty content, missing files, permission errors
- [ ] Manual testing: Export a real Debussy plan and render in GitHub

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Tests written and passing (>80% coverage for new code)
- [ ] Can export master plan to standalone markdown file
- [ ] Can export individual phase files with metadata preserved
- [ ] Can export full plan directory structure (master + phases + notes)
- [ ] Exported markdown renders correctly on GitHub
- [ ] No data loss during export (all tasks, gates, metadata preserved)
- [ ] Dry-run mode works without writing files

## Rollback Plan

If critical issues arise during implementation:

1. **Immediate rollback:**
   ```bash
   git checkout HEAD~1 src/debussy/exporters/
   git checkout HEAD~1 tests/test_exporters*
   ```

2. **Partial rollback (keep models, remove exporters):**
   ```bash
   git checkout HEAD~1 src/debussy/exporters/markdown.py
   git checkout HEAD~1 src/debussy/exporters/base.py
   ```

3. **Database/state cleanup:** N/A (this phase doesn't modify state.db)

4. **Dependency rollback:** No new dependencies added

5. **User communication:** If exported files were corrupted, users can regenerate from original plans in `.debussy/plans/`

---

## Implementation Notes

**Architectural Decisions:**

- Use composition over inheritance: MarkdownExporter wraps PhaseParser rather than extending it
- Keep exporters stateless: all context passed via method parameters
- Separate concerns: models handle data, exporters handle formatting, CLI handles I/O

**Metadata Preservation:**

Export metadata header format:
```yaml
---
exported_by: debussy
version: 0.5.1
exported_at: 2026-01-16T10:30:00Z
source_plan: /path/to/.debussy/plans/feature-name/
phases: [1, 2, 3]
includes_notes: true
---
```

**Future Considerations:**

- Phase 4 will add HTML export, which should reuse ExportedPlan/Phase/Note models
- Consider adding template support for custom markdown formatting
- May need streaming for very large plans (>100 phases)
