# Export Plans, Better Error Messages, and Dark Mode - Phase 1: Plan Export Command

**Status:** Pending
**Master Plan:** [Export Plans, Better Error Messages, and Dark Mode-MASTER_PLAN.md](export-plans-better-error-messages-and-dark-mode-MASTER_PLAN.md)
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
  uv run bandit -r src/
  uv run radon cc src/ -a -nb
  
  # Security scanning for PDF vulnerabilities
  uv run ty check src/debussy/exporters/
  uv run semgrep --config auto src/debussy/exporters/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export-plans-better-error-messages-and-dark-mode_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)
- complexity: `uv run radon cc src/ -a -nb` (average complexity < 10)
- ty: `uv run ty check src/debussy/exporters/` (0 vulnerabilities)
- semgrep: `uv run semgrep --config auto src/debussy/exporters/` (0 high/critical findings)

---

## Overview

This phase implements a new `debussy export` CLI command that enables users to export Debussy implementation plans to Markdown (MD) and PDF formats. The exported plans will include all implementation notes documents embedded within them, making the exports suitable for team review, archival, and manual test strategy development. The feature focuses solely on MD and PDF formats with no additional formats or features beyond the core export functionality.

## Dependencies
- Previous phase: N/A (independent phase)
- External: Free Python PDF generation library (to be selected), existing Debussy plan parsers

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF library vulnerabilities | Medium | High | Use ty and semgrep scanning; select well-maintained free libraries (reportlab, weasyprint, or fpdf2); pin versions |
| PDF rendering inconsistencies | Medium | Medium | Test with various plan structures from fixtures; implement fallback to MD export if PDF generation fails |
| Embedded notes not preserving formatting | Low | Medium | Use Markdown parser to convert notes to PDF-compatible format; test with complex code blocks and tables |
| Large plans causing memory issues | Low | Medium | Stream PDF generation when possible; test with large real-world plans |

---

## Tasks

### 1. Research and Select PDF Library
- [ ] 1.1: Evaluate free Python PDF libraries (reportlab, weasyprint, fpdf2) for maintenance status, security history, and Markdown rendering capabilities
- [ ] 1.2: Create proof-of-concept script to render sample Markdown content with code blocks and tables to PDF
- [ ] 1.3: Run ty and semgrep against selected library to verify no known vulnerabilities
- [ ] 1.4: Document library selection rationale in implementation notes

### 2. Implement Export Module
- [ ] 2.1: Create `src/debussy/exporters/__init__.py` with base exporter interface
- [ ] 2.2: Implement `src/debussy/exporters/markdown.py` with `MarkdownExporter` class to export master plan + phase files + notes to single MD file
- [ ] 2.3: Implement `src/debussy/exporters/pdf.py` with `PDFExporter` class to convert combined MD to PDF format
- [ ] 2.4: Create `src/debussy/exporters/notes_embedder.py` to locate and embed implementation notes into phase sections
- [ ] 2.5: Add error handling for missing files, invalid plans, and PDF generation failures with fallback to MD-only

### 3. Add CLI Command
- [ ] 3.1: Add `export` subcommand to `src/debussy/cli.py` with arguments: `--plan-dir`, `--output-dir`, `--format` (md|pdf|both)
- [ ] 3.2: Implement command handler to invoke appropriate exporter based on format flag
- [ ] 3.3: Add validation to ensure plan directory contains valid master plan and phase files
- [ ] 3.4: Add progress feedback for long-running PDF generation

### 4. Testing
- [ ] 4.1: Create `tests/test_export.py` with unit tests for MarkdownExporter (plan parsing, notes embedding, MD concatenation)
- [ ] 4.2: Add unit tests for PDFExporter (MD to PDF conversion, error handling, fallback behavior)
- [ ] 4.3: Add integration tests using existing fixtures from `tests/fixtures/sample_plans/` to verify end-to-end export
- [ ] 4.4: Test with plans containing no notes, partial notes, and full notes coverage
- [ ] 4.5: Test PDF output readability with various plan sizes and complexity levels

### 5. Documentation
- [ ] 5.1: Create `docs/EXPORT.md` with usage examples for `debussy export` command
- [ ] 5.2: Document supported formats (MD, PDF), file naming conventions, and directory structure
- [ ] 5.3: Add troubleshooting section for common PDF generation issues
- [ ] 5.4: Update main README.md to mention export functionality

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/exporters/__init__.py` | Create | Define base exporter interface and export registry |
| `src/debussy/exporters/markdown.py` | Create | Implement MD exporter to combine master plan, phases, and notes |
| `src/debussy/exporters/pdf.py` | Create | Implement PDF exporter using selected library |
| `src/debussy/exporters/notes_embedder.py` | Create | Utility to locate and embed implementation notes into phase sections |
| `src/debussy/cli.py` | Modify | Add `export` subcommand with format selection |
| `tests/test_export.py` | Create | Comprehensive unit and integration tests for export functionality |
| `tests/fixtures/sample_plans/` | Modify | Add sample notes files to existing fixtures for testing |
| `docs/EXPORT.md` | Create | User guide for export feature |
| `README.md` | Modify | Add export command to feature list |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Parser reuse | `src/debussy/parsers/master.py`, `src/debussy/parsers/phase.py` | Use existing `MasterPlanParser` and `PhasePlanParser` to read plan files |
| Error handling | `src/debussy/audit/auditor.py` | Follow existing error reporting patterns with actionable messages |
| CLI structure | `src/debussy/cli.py` commands (audit, convert, run) | Match existing command structure with typer decorators and consistent argument naming |
| Testing strategy | `tests/test_conversion_samples.py` | Use fixtures in `tests/fixtures/` for integration tests; mock file I/O for unit tests |

## Test Strategy

- [ ] Unit tests for MarkdownExporter: plan parsing, notes embedding, content concatenation
- [ ] Unit tests for PDFExporter: MD to PDF conversion, error handling, fallback logic
- [ ] Integration tests: export sample plans from fixtures to temp directory, verify output files exist and are readable
- [ ] Security tests: run ty and semgrep against exporter module to catch PDF vulnerabilities
- [ ] Manual testing checklist:
  - [ ] Export plan with no notes files → verify graceful handling
  - [ ] Export plan with all notes files → verify notes are embedded in correct phase sections
  - [ ] Export large plan (10+ phases) → verify performance and memory usage
  - [ ] Export to MD only → verify output is valid Markdown
  - [ ] Export to PDF only → verify output is readable and preserves code blocks/tables
  - [ ] Export to both formats → verify both files are generated correctly

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, bandit, radon, ty, semgrep)
- [ ] Tests written and passing (minimum 80% coverage for new code)
- [ ] `debussy export --plan-dir <path> --output-dir <path> --format md` generates readable MD file with embedded notes
- [ ] `debussy export --plan-dir <path> --output-dir <path> --format pdf` generates readable PDF file with embedded notes
- [ ] `debussy export --plan-dir <path> --output-dir <path> --format both` generates both MD and PDF files
- [ ] Exported files are named correctly (e.g., `my-feature-MASTER_PLAN.md`, `my-feature-MASTER_PLAN.pdf`)
- [ ] Documentation updated in `docs/EXPORT.md` and `README.md`
- [ ] No security vulnerabilities introduced (ty and semgrep scans pass)
- [ ] PDF generation failures fall back to MD-only export with clear error message

## Rollback Plan

1. **Before deployment:** Create git branch for this phase
2. **If export command fails in production:**
   - Remove `export` subcommand from `src/debussy/cli.py`
   - Remove `src/debussy/exporters/` directory
   - Revert changes to `README.md` and docs
   - Git revert commit and push
3. **If PDF library causes security issues:**
   - Disable PDF export format by adding validation check in CLI to reject `--format pdf`
   - Update docs to indicate PDF temporarily unavailable
   - Investigate alternative library or patch
4. **Database/State:** No database changes in this phase, rollback is file-based only

---

## Implementation Notes

**PDF Library Selection Criteria:**
- Must be free/open-source with permissive license (MIT, BSD, Apache 2.0)
- Active maintenance (commits within last 6 months)
- No known high/critical CVEs in latest version
- Good Markdown rendering support (code blocks, tables, lists)
- Reasonable dependencies (avoid pulling in large frameworks)

**Notes Embedding Strategy:**
- Parse master plan to identify all phase files
- For each phase file, look for corresponding notes file in `notes/NOTES_{feature}_phase_{num}.md`
- Embed notes content as appendix section within each phase in the exported document
- Preserve Markdown formatting (code blocks, tables, lists) in both MD and PDF output

**Error Handling:**
- Missing notes files: log warning, continue export without those notes
- Invalid plan structure: fail fast with clear error message
- PDF generation failure: catch exception, log error, fall back to MD-only export with user notification
