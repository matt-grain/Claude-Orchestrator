# Export Feature Phase 4: PDF Export with Security Validation

**Status:** Pending
**Master Plan:** [export-feature-MASTER_PLAN.md](export-feature-MASTER_PLAN.md)
**Depends On:** [Phase 3: HTML Export with Styling](phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_export_feature_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_export_feature_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/debussy/exporters/ -ll` (no high/medium severity issues)

---

## Overview

This phase implements secure PDF generation from Debussy plans with comprehensive security validation. PDF export is critical for professional documentation and sharing with stakeholders who require non-editable formats. The implementation prioritizes security to prevent XML injection attacks, path traversal vulnerabilities, and resource exhaustion from malicious plan content.

## Dependencies
- Previous phase: [Phase 3: HTML Export with Styling](phase-3.md)
- External: 
  - `weasyprint` library for HTML-to-PDF conversion
  - HTML exporter output as intermediate format
  - File system write permissions

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| XML/HTML injection in PDF rendering | Medium | High | Input sanitization, HTML escaping, CSP-style restrictions |
| Path traversal via embedded file references | Low | High | Strict path validation, sandboxed resource loading |
| Memory exhaustion from large plans | Medium | Medium | Page limits, streaming processing, resource constraints |
| Dependency vulnerability (weasyprint) | Low | Medium | Pin versions, regular security audits, minimal API surface |
| Font rendering security issues | Low | Medium | Restrict font sources, use safe defaults only |

---

## Tasks

### 1. PDF Exporter Core Implementation
- [ ] 1.1: Create `src/debussy/exporters/pdf.py` with PDFExporter class
- [ ] 1.2: Implement HTML-to-PDF conversion using weasyprint
- [ ] 1.3: Add error handling for rendering failures (missing fonts, CSS issues)
- [ ] 1.4: Implement page size/orientation configuration options

### 2. Security Sanitization Layer
- [ ] 2.1: Create `src/debussy/exporters/security.py` with ContentSanitizer class
- [ ] 2.2: Implement HTML content sanitization (strip dangerous tags/attributes)
- [ ] 2.3: Add path validation for embedded resources (images, CSS)
- [ ] 2.4: Implement resource size limits and timeout protections
- [ ] 2.5: Add content length validation to prevent DoS via large inputs

### 3. CLI Integration
- [ ] 3.1: Add `--format pdf` option to existing export command
- [ ] 3.2: Add PDF-specific flags: `--page-size`, `--orientation`, `--no-toc`
- [ ] 3.3: Implement progress indicators for large PDF generations
- [ ] 3.4: Add validation warnings when security sanitization modifies content

### 4. Testing & Documentation
- [ ] 4.1: Unit tests for PDFExporter class (valid/invalid inputs)
- [ ] 4.2: Security tests for injection attempts and path traversal
- [ ] 4.3: Integration tests for full plan-to-PDF workflow
- [ ] 4.4: Performance tests with large plans (500+ tasks)
- [ ] 4.5: Update docs/EXPORT.md with PDF usage examples and security notes

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/exporters/pdf.py` | Create | PDF exporter implementation using weasyprint |
| `src/debussy/exporters/security.py` | Create | Content sanitization and validation utilities |
| `src/debussy/exporters/__init__.py` | Modify | Export PDFExporter class |
| `src/debussy/cli.py` | Modify | Add PDF format option and flags to export command |
| `tests/test_pdf_exporter.py` | Create | Unit tests for PDF generation |
| `tests/test_export_security.py` | Create | Security validation tests (injection, traversal, DoS) |
| `tests/test_export_integration.py` | Modify | Add PDF format to end-to-end export tests |
| `docs/EXPORT.md` | Modify | Add PDF export documentation and security guidance |
| `pyproject.toml` | Modify | Add weasyprint dependency |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| HTML Exporter Pattern | `src/debussy/exporters/html.py` | Reuse HTML generation as intermediate step |
| Security Validator Pattern | `src/debussy/compliance/checker.py` | Apply similar validation approach to user content |
| CLI Export Pattern | `src/debussy/cli.py` export command | Extend existing format selection mechanism |
| Resource Path Resolution | `src/debussy/parsers/phase.py` | Use same path resolution for embedded resources |

## Test Strategy

- [ ] Unit tests for PDFExporter.export() with valid/invalid plans
- [ ] Unit tests for ContentSanitizer with malicious HTML payloads
- [ ] Security tests for XML injection (e.g., `<?xml-stylesheet>`, `<!DOCTYPE>`)
- [ ] Security tests for path traversal (e.g., `../../../../etc/passwd` in image src)
- [ ] DoS tests with massive plans (10,000 tasks, 5MB markdown)
- [ ] Integration tests: master plan → HTML → PDF with all phases
- [ ] Manual testing: visual inspection of PDF output (fonts, layout, TOC)
- [ ] Manual testing: open PDFs in multiple viewers (Adobe, Preview, Chrome)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Tests written and passing (minimum 95% coverage for new code)
- [ ] Documentation updated with usage examples
- [ ] Security review: no high/medium vulnerabilities from bandit
- [ ] Generated PDFs render correctly in major PDF viewers
- [ ] CLI command `debussy export --format pdf plan.md output.pdf` works
- [ ] Sanitization warnings logged when dangerous content is stripped

## Rollback Plan

1. **Revert code changes:**
   ```bash
   git revert <phase-4-commit-hash>
   ```

2. **Remove dependency:**
   ```bash
   uv remove weasyprint
   uv lock
   ```

3. **Remove CLI command:** No action needed if using feature flag pattern. If integrated directly, revert `cli.py` changes.

4. **Database/State:** No schema changes in this phase - no migrations to reverse.

5. **Rollback verification:**
   ```bash
   uv run pytest tests/
   debussy export --help  # Should not show PDF format
   ```

---

## Implementation Notes

### Architecture Decision: HTML as Intermediate Format
PDF generation will use the HTML exporter as an intermediate step, then convert HTML→PDF using weasyprint. This approach:
- Reuses existing HTML styling and layout logic
- Simplifies maintenance (one source of truth for visual rendering)
- Enables future PDF customization via CSS modifications

### Security Design: Defense in Depth
1. **Input layer:** Sanitize markdown during parsing
2. **HTML layer:** Strip dangerous tags/attributes before PDF conversion
3. **PDF layer:** Restrict weasyprint resource loading to safe paths only
4. **Output layer:** Validate generated PDF size/page count limits

### Performance Considerations
- Weasyprint can be slow for large documents (100+ pages)
- Consider adding progress callbacks for better UX
- May need streaming/chunking for 500+ task plans

### Future Enhancements (out of scope for this phase)
- Custom PDF templates with company branding
- Digital signatures for verified exports
- Encrypted PDFs with password protection
- PDF/A format for long-term archival
