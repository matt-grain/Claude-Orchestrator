# Phase 4: Audit Improvements

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** [Phase 1](phase-1-audit.md) (audit command)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files:

1. **Existing auditor**: `src/debussy/core/auditor.py`
2. **Audit models**: `src/debussy/core/audit.py`
3. **CLI audit command**: `src/debussy/cli.py` (search for `def audit`)
4. **Log insights**: `docs/LOG_INSIGHTS.md`

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase3_templates_phase_3.md` (if exists)
- [ ] Read existing audit code in `src/debussy/core/`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality - run from project root
  uv run ruff format . && uv run ruff check --fix .

  # Type checking (BOTH required)
  uv run pyright src/debussy/
  uv run ty check src/debussy/

  # Tests - ALL tests must pass
  uv run pytest tests/ -x -v
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass
- [ ] Write `notes/NOTES_phase3_templates_phase_4.md`
- [ ] Signal completion: `debussy done --phase 4`

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors (command: `uv run pyright src/debussy/`)
- ty: 0 errors (command: `uv run ty check src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)

---

## Overview

Improve the `debussy audit` command with verbose output, better error messages, and suggestions for fixing issues. The current audit is useful but lacks details to help users understand what's wrong.

## Dependencies
- Previous phase: Phase 1 (audit command exists)
- External: None

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Verbose output too noisy | Medium | Low | Use levels: default, -v, -vv |
| Suggestions incorrect | Low | Medium | Test with real broken plans |

---

## Tasks

### 1. Add Verbose Mode to Audit

The current audit shows counts but not details. Add `--verbose` / `-v` flag.

- [ ] 1.1: Add `--verbose` flag to CLI:
  ```python
  verbose: Annotated[
      int,
      typer.Option("--verbose", "-v", count=True, help="Increase output verbosity"),
  ] = 0,
  ```

- [ ] 1.2: Update audit output for verbose=1:
  - Show file paths for each issue
  - Show line numbers where possible
  - Show the actual content that caused the issue

- [ ] 1.3: Update audit output for verbose=2:
  - Include parsed structure details
  - Show gates detected with their commands
  - Show dependency graph

### 2. Add Fix Suggestions

When audit fails, suggest how to fix each issue.

- [ ] 2.1: Add `suggestion` field to `AuditIssue` model:
  ```python
  @dataclass
  class AuditIssue:
      severity: AuditSeverity
      message: str
      location: str | None = None
      suggestion: str | None = None  # NEW
  ```

- [ ] 2.2: Add suggestions for common issues:
  - Missing gates section: "Add a '## Gates' section with validation commands"
  - Missing phases: "Ensure phase files exist at the paths specified in master plan"
  - Circular dependency: "Remove the dependency from Phase X to Phase Y"
  - Invalid status: "Change status to one of: Pending, Running, Completed, Failed"

- [ ] 2.3: Display suggestions in CLI output:
  ```
  Errors:
    ✗ Phase 2 has no gates defined (phase-2.md)
      Suggestion: Add a '## Gates' section with commands like:
                  - ruff: 0 errors (command: `uv run ruff check .`)
  ```

### 3. Add Machine-Readable Output

Support JSON output for CI integration.

- [ ] 3.1: Add `--format` option:
  ```python
  format: Annotated[
      str,
      typer.Option("--format", "-f", help="Output format: text, json"),
  ] = "text",
  ```

- [ ] 3.2: Implement JSON output:
  ```json
  {
    "passed": false,
    "summary": {
      "errors": 2,
      "warnings": 1
    },
    "issues": [
      {
        "severity": "error",
        "message": "Phase 2 has no gates defined",
        "location": "phase-2.md",
        "suggestion": "Add a '## Gates' section..."
      }
    ]
  }
  ```

### 4. Write Tests

- [ ] 4.1: Add tests for verbose output
- [ ] 4.2: Add tests for suggestions
- [ ] 4.3: Add tests for JSON output

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/core/audit.py` | Modify | Add suggestion field |
| `src/debussy/core/auditor.py` | Modify | Add suggestions to issues |
| `src/debussy/cli.py` | Modify | Add --verbose and --format flags |
| `tests/test_audit.py` | Create/Modify | Test new features |

## Patterns to Follow

### Verbose Level Pattern

```python
if verbose >= 1:
    console.print(f"  Location: {issue.location}")
if verbose >= 2:
    console.print(f"  Context: {issue.context}")
```

### JSON Output Pattern

```python
if format == "json":
    import json
    output = {
        "passed": result.passed,
        "summary": asdict(result.summary),
        "issues": [asdict(i) for i in result.issues],
    }
    console.print(json.dumps(output, indent=2))
    return
```

## Acceptance Criteria

**ALL must pass:**

- [ ] `debussy audit plan.md` - shows current brief output (backwards compatible)
- [ ] `debussy audit -v plan.md` - shows file paths and details
- [ ] `debussy audit -vv plan.md` - shows parsed structure
- [ ] `debussy audit --format json plan.md` - outputs valid JSON
- [ ] Suggestions are shown for common errors
- [ ] Tests exist and pass
- [ ] All linting passes

## Rollback Plan
- Changes are additive (new flags)
- Default behavior unchanged
- Can revert individual features
