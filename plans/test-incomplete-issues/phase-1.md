# Export Plans & UX Improvements Phase 1: Plan Export Command

**Status:** Pending
**Master Plan:** [export-plans-ux-improvements-MASTER_PLAN.md](export-plans-ux-improvements-MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-ux-improvements_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- ty: `uv run ty analyze src/debussy/exporters/` (no vulnerabilities)
- semgrep: `uv run semgrep --config=auto src/debussy/exporters/` (no high/critical findings)

---

## Overview

This phase implements plan export functionality, enabling users to export Debussy implementation plans (master plans and phase plans) with embedded implementation notes to Markdown and PDF formats. This supports team collaboration, plan archival, and manual test strategy development. The export command will be a new CLI subcommand that reads plan files, merges associated notes, and generates formatted output files in the user-specified directory.

## Dependencies
- Previous phase: N/A (independent)
- External: Free Python PDF generation library (to be selected), Markdown processing library

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF library has security vulnerabilities | Medium | High | Use ty and semgrep scans; research well-maintained libraries; sandbox PDF generation if possible |
| PDF rendering quality issues (fonts, formatting) | Medium | Medium | Prototype with sample plans early; include visual regression tests; validate with real-world plans |
| Notes embedding breaks plan structure | Low | Medium | Parse plans carefully; preserve markdown structure; add integration tests with various plan formats |
| Large plans exceed PDF page limits | Low | Low | Implement pagination; test with large sample plans from fixtures |

---

## Tasks

### 1. Research and Select PDF Library
- [ ] 1.1: Research free Python PDF libraries (ReportLab, WeasyPrint, FPDF2, borb) for markdown-to-PDF conversion
- [ ] 1.2: Evaluate security posture (recent CVEs, maintenance status, dependency count)
- [ ] 1.3: Test rendering quality with sample Debussy plans (code blocks, tables, headers)
- [ ] 1.4: Document selection rationale in implementation notes

### 2. Implement Core Export Module
- [ ] 2.1: Create `src/debussy/exporters/__init__.py` with public export API
- [ ] 2.2: Create `src/debussy/exporters/base.py` with `PlanExporter` abstract base class
- [ ] 2.3: Implement `src/debussy/exporters/markdown.py` - `MarkdownExporter` class
- [ ] 2.4: Implement `src/debussy/exporters/pdf.py` - `PDFExporter` class using selected library
- [ ] 2.5: Create `src/debussy/exporters/notes_merger.py` - logic to embed notes into plans

### 3. Implement Plan Reader and Notes Merging
- [ ] 3.1: Add `read_plan_file()` utility to parse master/phase plan markdown
- [ ] 3.2: Add `read_notes_file()` utility to parse implementation notes markdown
- [ ] 3.3: Implement `merge_notes_into_plan()` - insert notes into "Implementation Notes" section
- [ ] 3.4: Handle missing notes files gracefully (export plan without notes)
- [ ] 3.5: Preserve markdown structure (headers, tables, code blocks, lists)

### 4. Add CLI Export Command
- [ ] 4.1: Add `export` subcommand to `src/debussy/cli.py` with `click` decorator
- [ ] 4.2: Add `--format` option (choices: md, pdf) defaulting to md
- [ ] 4.3: Add `--output-dir` option for export destination
- [ ] 4.4: Add `--plan-path` required argument (path to master or phase plan)
- [ ] 4.5: Add `--include-notes / --no-notes` flag (default: include)
- [ ] 4.6: Wire CLI command to exporter module, handle errors with clear messages

### 5. Implement Export Logic
- [ ] 5.1: Validate plan file exists and is readable
- [ ] 5.2: Detect associated notes file based on plan filename conventions
- [ ] 5.3: Merge notes if `--include-notes` and notes file exists
- [ ] 5.4: Instantiate appropriate exporter (MarkdownExporter or PDFExporter)
- [ ] 5.5: Write exported file to output directory with correct extension
- [ ] 5.6: Print success message with output file path

### 6. Add Comprehensive Tests
- [ ] 6.1: Create `tests/test_exporters.py` with 20+ unit/integration tests
- [ ] 6.2: Test MarkdownExporter with sample plans (with and without notes)
- [ ] 6.3: Test PDFExporter with sample plans (verify PDF is valid and readable)
- [ ] 6.4: Test notes merging logic (correct section insertion, structure preservation)
- [ ] 6.5: Test CLI command (argument parsing, file I/O, error handling)
- [ ] 6.6: Test edge cases (missing notes, invalid plan format, write permission errors)
- [ ] 6.7: Add security tests for PDF library (malicious markdown input)

### 7. Documentation
- [ ] 7.1: Create `docs/EXPORT.md` with usage examples and format specifications
- [ ] 7.2: Document export command in main README.md
- [ ] 7.3: Add docstrings to all exporter classes and public functions
- [ ] 7.4: Document notes embedding format and conventions

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/exporters/__init__.py` | Create | Public API for export functionality |
| `src/debussy/exporters/base.py` | Create | Abstract base class for exporters |
| `src/debussy/exporters/markdown.py` | Create | Markdown exporter implementation |
| `src/debussy/exporters/pdf.py` | Create | PDF exporter implementation |
| `src/debussy/exporters/notes_merger.py` | Create | Notes embedding logic |
| `src/debussy/cli.py` | Modify | Add export subcommand |
| `tests/test_exporters.py` | Create | Test suite for export functionality |
| `docs/EXPORT.md` | Create | Export command usage guide |
| `README.md` | Modify | Add export command documentation |
| `pyproject.toml` | Modify | Add PDF library dependency |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| CLI command structure | `src/debussy/cli.py` (existing commands) | Use click decorators, consistent option naming, error handling |
| Config loading | `src/debussy/config.py` | Load default output directory from config if not specified |
| File path handling | `src/debussy/parsers/master.py` | Use pathlib.Path for cross-platform compatibility |
| Test fixtures | `tests/fixtures/sample_plans/` | Reuse existing sample plans for export tests |
| Error messaging | Existing CLI commands | Provide actionable error messages with file paths |

## Test Strategy

- [ ] Unit tests for MarkdownExporter (plan parsing, notes merging, output generation)
- [ ] Unit tests for PDFExporter (PDF generation, formatting, font handling)
- [ ] Unit tests for notes_merger (section insertion, structure preservation)
- [ ] Integration tests for CLI command (end-to-end export with real plans)
- [ ] Security tests for PDF library (malicious input, injection attacks)
- [ ] Regression tests using existing sample plans (plan1, plan2, plan3)
- [ ] Manual testing checklist:
  - [ ] Export master plan to MD and PDF
  - [ ] Export phase plan with notes to MD and PDF
  - [ ] Verify PDF is readable in multiple viewers (Preview, Adobe, Chrome)
  - [ ] Verify code blocks, tables, and lists render correctly in PDF
  - [ ] Test with large plans (10+ phases, 100+ tasks)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, tests, bandit, ty, semgrep)
- [ ] `debussy export --format md --output-dir ./exports plan.md` generates valid MD file
- [ ] `debussy export --format pdf --output-dir ./exports plan.md` generates readable PDF
- [ ] Exported files include embedded notes when present
- [ ] PDF renders code blocks, tables, headers, and lists correctly
- [ ] Tests written and passing (20+ tests, 80%+ coverage for exporter module)
- [ ] Documentation created (docs/EXPORT.md, README.md updated)
- [ ] No security vulnerabilities introduced (ty and semgrep clean)
- [ ] PDF library dependency is free and well-maintained

## Rollback Plan

If critical issues arise during or after implementation:

1. **Revert Git Commit:**
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

2. **Remove CLI Command:**
   - Delete export subcommand from `src/debussy/cli.py`
   - Remove import statements for exporter module

3. **Remove Exporter Module:**
   ```bash
   rm -rf src/debussy/exporters/
   rm tests/test_exporters.py
   ```

4. **Remove PDF Dependency:**
   - Remove PDF library from `pyproject.toml` dependencies
   - Run `uv lock` to update lockfile
   - Run `uv sync` to clean environment

5. **Revert Documentation:**
   ```bash
   git checkout HEAD~1 -- docs/EXPORT.md README.md
   ```

6. **Verify Rollback:**
   ```bash
   uv run pytest tests/ -v
   debussy --help  # Verify export command is gone
   ```

---

## Implementation Notes

**PDF Library Selection Criteria:**
- Free and open-source license (MIT, BSD, Apache 2.0)
- Active maintenance (commits within last 6 months)
- Good markdown-to-PDF support (or HTML-to-PDF with markdown preprocessing)
- Minimal security vulnerabilities (check Snyk, CVE databases)
- Reasonable dependency count (avoid bloated dependency trees)

**Notes Embedding Strategy:**
- Parse plan markdown to locate "## Implementation Notes" section
- If section exists, append notes content preserving markdown structure
- If section missing, create section at end of plan before final separator
- Prepend "### Embedded Notes from {notes_file}" header for clarity
- Preserve all original plan content unchanged

**PDF Rendering Considerations:**
- Use monospace font for code blocks (Courier or DejaVu Sans Mono)
- Ensure tables fit within page width (may require font size reduction)
- Add page numbers and plan title in footer
- Use syntax highlighting for code blocks if library supports it
- Test with plans containing Unicode characters (emojis, special symbols)
