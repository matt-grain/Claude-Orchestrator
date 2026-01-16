# Export Plans Phase 4: PDF Export Implementation

**Status:** Pending
**Master Plan:** [export-plans-MASTER_PLAN.md](export-plans-MASTER_PLAN.md)
**Depends On:** [phase-3.md](phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_export_plans_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export_plans_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- bandit: `uv run bandit -r src/` (no high severity)
- ty: `uv run ty check src/` (0 errors)
- semgrep: `uv run semgrep --config=auto src/` (no critical/high vulnerabilities in PDF handling)

---

## Overview

Implements PDF export functionality using a secure, free Python library. This phase completes the export feature by adding PDF generation with embedded implementation notes, proper security scanning for PDF vulnerabilities, and comprehensive testing.

## Dependencies
- Previous phase: [phase-3.md](phase-3.md) - Base export command and MD format
- External: N/A

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PDF library has security vulnerabilities | Medium | High | Use semgrep and bandit scans; research library security history before selection |
| PDF rendering fails on complex markdown | Medium | Medium | Comprehensive test suite with edge cases; fallback error handling |
| Large plans cause memory issues during PDF generation | Low | Medium | Stream processing where possible; add file size warnings |
| PDF output is not readable/accessible | Low | Medium | Test with multiple PDF readers; ensure text extraction works |

---

## Tasks

### 1. Research and Select PDF Library
- [ ] 1.1: Evaluate free Python PDF libraries (reportlab, weasyprint, borb, pypdf)
- [ ] 1.2: Check security advisories and CVE databases for each candidate
- [ ] 1.3: Test markdown-to-PDF conversion quality with sample plans
- [ ] 1.4: Document library selection rationale in implementation notes

### 2. Implement PDF Exporter
- [ ] 2.1: Create `src/debussy/exporters/pdf.py` with PDFExporter class
- [ ] 2.2: Implement markdown-to-PDF conversion with proper styling
- [ ] 2.3: Embed implementation notes sections into PDF output
- [ ] 2.4: Add metadata (title, author, creation date) to PDF
- [ ] 2.5: Handle special characters and code blocks correctly

### 3. Integrate PDF Export into CLI
- [ ] 3.1: Add PDF format support to export command
- [ ] 3.2: Update format validation to include 'pdf'
- [ ] 3.3: Wire PDFExporter into ExportService
- [ ] 3.4: Update help text and examples

### 4. Security Hardening
- [ ] 4.1: Add input sanitization for PDF content
- [ ] 4.2: Validate PDF output for malicious content patterns
- [ ] 4.3: Run semgrep scans specifically targeting PDF generation code
- [ ] 4.4: Document security considerations in code comments

### 5. Testing and Validation
- [ ] 5.1: Unit tests for PDFExporter class
- [ ] 5.2: Integration tests for full export workflow with PDF
- [ ] 5.3: Test edge cases (empty plans, special characters, large files)
- [ ] 5.4: Verify PDF readability across multiple readers
- [ ] 5.5: Test that implementation notes are properly embedded

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/exporters/pdf.py` | Create | PDF exporter implementation |
| `src/debussy/exporters/service.py` | Modify | Add PDF format support to ExportService |
| `src/debussy/cli.py` | Modify | Update export command to support PDF format |
| `tests/exporters/test_pdf.py` | Create | Unit tests for PDF exporter |
| `tests/integration/test_export_pdf.py` | Create | Integration tests for PDF export workflow |
| `requirements.txt` or `pyproject.toml` | Modify | Add PDF library dependency |
| `docs/EXPORT.md` | Modify | Document PDF export capabilities and security considerations |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Exporter interface | `src/debussy/exporters/base.py` | PDFExporter must implement BaseExporter interface |
| Service integration | `src/debussy/exporters/service.py` | Follow pattern from MDExporter registration |
| CLI command structure | `src/debussy/cli.py` | Maintain consistency with existing export command patterns |
| Security scanning | Existing bandit/semgrep configs | Extend scanning patterns for PDF-specific vulnerabilities |
| Test fixtures | `tests/fixtures/sample_plans/` | Use existing sample plans for PDF generation tests |

## Test Strategy

- [ ] Unit tests for PDF generation logic (encoding, styling, metadata)
- [ ] Integration tests for end-to-end export workflow with PDF format
- [ ] Security tests verifying no script injection or malicious content in PDFs
- [ ] Edge case tests (Unicode, code blocks, long content, empty plans)
- [ ] Manual testing with multiple PDF readers (Adobe, Preview, browser viewers)
- [ ] Verify text extraction from PDF works correctly
- [ ] Test that implementation notes are embedded and accessible

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit, ty, semgrep)
- [ ] `debussy export --format pdf` generates valid, readable PDF files
- [ ] PDF output includes plan content AND implementation notes
- [ ] PDF files are saved with correct naming convention (.pdf extension)
- [ ] No security vulnerabilities detected in PDF generation code
- [ ] Tests achieve 80%+ coverage for new PDF exporter code
- [ ] Documentation updated with PDF export examples and security notes
- [ ] Manual verification: Generated PDF is readable in at least 3 different PDF viewers

## Rollback Plan

1. Remove PDF library from dependencies in `pyproject.toml`
2. Delete `src/debussy/exporters/pdf.py`
3. Revert changes to `src/debussy/exporters/service.py` (remove PDF format registration)
4. Revert changes to `src/debussy/cli.py` (remove PDF from format choices)
5. Delete test files: `tests/exporters/test_pdf.py` and `tests/integration/test_export_pdf.py`
6. Run `uv pip install -e .` to reinstall without PDF dependencies
7. Verify remaining export functionality (MD format) still works
8. Commit rollback with message: "Revert Phase 4: PDF export implementation"

---

## Implementation Notes

### Library Selection Considerations
- **Security**: Check CVE database, GitHub security advisories, and recent vulnerability reports
- **License**: Must be free and compatible with project license
- **Maintenance**: Prefer actively maintained libraries with recent commits
- **Quality**: Test markdown rendering quality before committing to a library
- **Dependencies**: Minimize transitive dependencies to reduce attack surface

### PDF Security Best Practices
- Sanitize all user input before embedding in PDF
- Avoid JavaScript or executable content in PDFs
- Use semgrep rules to detect common PDF vulnerabilities
- Consider adding file size limits to prevent resource exhaustion
- Document any security trade-offs in the implementation

### Testing Notes
- Use fixture plans from `tests/fixtures/sample_plans/` for realistic testing
- Test with plans that have implementation notes to verify embedding works
- Verify PDF metadata is correctly set (title should match plan name)
- Test error handling when PDF generation fails
