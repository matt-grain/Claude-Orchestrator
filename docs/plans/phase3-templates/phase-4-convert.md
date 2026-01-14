# Phase 4: Convert Command

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** [Phase 3](phase-3-audit-improvements.md) (verbose audit, JSON output, suggestions for agent)

---

## CRITICAL: Read These First

Before implementing:

1. **Previous phase notes**: `notes/NOTES_phase3_templates_phase_1.md` and `notes/NOTES_phase3_templates_phase_2.md`
2. **Audit implementation**: `src/debussy/core/auditor.py`
3. **Templates**: `docs/templates/plans/`
4. **Claude runner**: `src/debussy/runners/claude.py` - how we spawn Claude

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes from Phase 1 and Phase 2
- [ ] Study Claude runner implementation
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .

  # Type checking
  uv run pyright src/debussy/

  # Tests
  uv run pytest tests/ -x -v

  # Integration: convert a freeform plan and verify it passes audit
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass
- [ ] Write `notes/NOTES_phase3_templates_phase_3.md`
- [ ] Signal completion: `debussy done --phase 3`

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- convert_audit: converted plan passes audit (command: `uv run debussy convert sample.md && uv run debussy audit`)

---

## Overview

Implement `debussy convert <freeform_plan>` command that uses Claude to transform a freeform plan into Debussy's structured format. This is the fallback path for users with existing plans.

**Key constraint**: The convert output MUST pass `debussy audit`. If it doesn't, the conversion failed.

## Dependencies
- Previous phases: Phase 1 (audit), Phase 2 (templates)
- External: Claude CLI (for agent-powered conversion)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Claude produces invalid output | Medium | Medium | Audit gate, retry loop |
| Infinite conversion loop | Low | High | Max iteration limit (3) |
| Token cost | Medium | Low | Use haiku model, efficient prompts |

---

## Tasks

### 1. Design Conversion Strategy

The convert command has two modes:
- **Non-interactive (default)**: Best-effort conversion, user reviews
- **Interactive**: Uses `AskUserQuestion` to clarify ambiguities

- [ ] 1.1: Document conversion flow:
  ```
  Freeform Plan → Claude Analysis → Structured Output → Audit Check
                                                            │
                                                            ├─ Pass → Done
                                                            └─ Fail → Retry (max 3x)
  ```

- [ ] 1.2: Define what Claude needs to do:
  1. Read the freeform plan
  2. Identify logical phases/milestones
  3. Extract or infer validation gates
  4. Generate master plan + phase files
  5. Ensure output matches template structure

### 2. Create Converter Module

- [ ] 2.1: Create `src/debussy/converters/__init__.py`

- [ ] 2.2: Create `src/debussy/converters/plan_converter.py`:
  ```python
  from pathlib import Path
  from debussy.core.auditor import PlanAuditor
  from debussy.runners.claude import ClaudeRunner

  class PlanConverter:
      """Convert freeform plans to Debussy format using Claude."""

      def __init__(
          self,
          auditor: PlanAuditor,
          templates_dir: Path,
          max_iterations: int = 3,
          model: str = "haiku",
      ):
          self.auditor = auditor
          self.templates_dir = templates_dir
          self.max_iterations = max_iterations
          self.model = model

      async def convert(
          self,
          source_plan: Path,
          output_dir: Path,
          interactive: bool = False,
      ) -> ConversionResult:
          """Convert a freeform plan to structured format.

          Args:
              source_plan: Path to freeform plan markdown
              output_dir: Directory to write structured files
              interactive: If True, ask clarifying questions

          Returns:
              ConversionResult with success status and created files.
          """

      def _build_conversion_prompt(
          self,
          source_content: str,
          templates: dict[str, str],
          previous_issues: list[AuditIssue] | None = None,
      ) -> str:
          """Build prompt for Claude to do conversion."""

      async def _run_conversion_iteration(
          self,
          prompt: str,
          output_dir: Path,
      ) -> tuple[list[Path], list[AuditIssue]]:
          """Run one conversion iteration and audit the result."""
  ```

- [ ] 2.3: Create `ConversionResult` model:
  ```python
  class ConversionResult(BaseModel):
      success: bool
      iterations: int
      files_created: list[Path]
      audit_result: AuditResult
      warnings: list[str]
  ```

### 3. Build Conversion Prompt

**This is the critical part.** The prompt must be precise enough that Claude produces audit-passing output.

- [ ] 3.1: Create prompt template in `src/debussy/converters/prompts.py`:
  ```python
  CONVERSION_PROMPT = '''
  You are converting a freeform implementation plan into Debussy's structured format.

  ## Source Plan
  {source_content}

  ## Target Structure
  You must create these files:
  1. MASTER_PLAN.md - Master plan with phases table
  2. phase-1.md, phase-2.md, etc. - One file per phase

  ## Master Plan Template (MUST FOLLOW EXACTLY)
  {master_template}

  ## Phase Template (MUST FOLLOW EXACTLY)
  {phase_template}

  ## Critical Requirements
  1. The phases table MUST use this exact format:
     | Phase | Title | Focus | Risk | Status |
     |-------|-------|-------|------|--------|
     | 1 | [Phase Title](phase-1.md) | Brief focus | Low/Medium/High | Pending |

  2. Each phase file MUST have:
     - ## Gates section with validation commands
     - ## Process Wrapper section
     - ## Tasks section with checkbox items

  3. If the source plan doesn't specify validation commands, infer reasonable ones:
     - Python projects: ruff, pyright, pytest
     - JavaScript/TypeScript: eslint, tsc, jest/vitest
     - General: tests, build

  4. Preserve ALL content from the source plan. Do not remove any tasks or details.

  {previous_issues_section}

  ## Output Format
  Output each file in this format:

  ---FILE: MASTER_PLAN.md---
  [content]
  ---END FILE---

  ---FILE: phase-1.md---
  [content]
  ---END FILE---

  Generate the structured plan files now.
  '''

  REMEDIATION_SECTION = '''
  ## IMPORTANT: Previous Attempt Failed Audit
  The previous conversion attempt had these issues:
  {issues}

  You MUST fix these issues in this attempt.
  '''
  ```

### 4. Implement Interactive Mode

- [ ] 4.1: Define questions for interactive mode:
  ```python
  INTERACTIVE_QUESTIONS = {
      "phases": {
          "question": "How many phases should this plan have?",
          "options": ["2 phases", "3 phases", "4 phases", "5+ phases"],
      },
      "gates": {
          "question": "What validation tools should we use?",
          "options": ["Python (ruff, pyright, pytest)", "JavaScript (eslint, tsc)", "Custom"],
          "multi_select": True,
      },
      "notes": {
          "question": "Should phases write handoff notes?",
          "options": ["Yes (recommended)", "No"],
      },
  }
  ```

- [ ] 4.2: Implement question flow using console prompts or structured output

### 5. Add CLI Command

- [ ] 5.1: Add `convert` command to `src/debussy/cli.py`:
  ```python
  @app.command()
  def convert(
      source: Annotated[Path, typer.Argument(help="Path to freeform plan")],
      output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = None,
      interactive: Annotated[bool, typer.Option("--interactive", "-i", help="Ask questions")] = False,
      model: Annotated[str, typer.Option("--model", "-m", help="Claude model")] = "haiku",
      max_retries: Annotated[int, typer.Option("--max-retries", help="Max conversion attempts")] = 3,
  ):
      """Convert a freeform plan to Debussy format.

      Example:
          debussy convert my-plan.md --output plans/my-feature/
          debussy convert my-plan.md --interactive
      """
  ```

- [ ] 5.2: Implement Rich output for conversion progress:
  ```
  debussy convert messy-plan.md --output plans/my-feature/

  Converting: messy-plan.md

  Analyzing plan structure...
  ✓ Found 4 logical sections

  Generating structured files (attempt 1/3)...
  ✓ Created: MASTER_PLAN.md
  ✓ Created: phase-1.md
  ✓ Created: phase-2.md
  ✓ Created: phase-3.md
  ✓ Created: phase-4.md

  Running audit...
  ✗ Audit failed: 1 error

  Retrying with fixes (attempt 2/3)...
  ✓ Created: MASTER_PLAN.md (updated)
  ✓ Created: phase-2.md (updated)

  Running audit...
  ✓ Audit passed!

  Conversion complete: plans/my-feature/

  Next steps:
  1. Review generated files for accuracy
  2. Run: debussy run plans/my-feature/MASTER_PLAN.md
  ```

### 6. Write Tests

- [ ] 6.1: Create `tests/test_convert.py`:
  ```python
  def test_convert_simple_plan(tmp_path):
      """Convert a simple freeform plan."""

  def test_convert_output_passes_audit(tmp_path):
      """Converted output passes audit."""

  def test_convert_preserves_content(tmp_path):
      """All tasks from source appear in output."""

  def test_convert_retry_on_audit_fail(tmp_path):
      """Converter retries when audit fails."""

  def test_convert_max_retries_exceeded(tmp_path):
      """Conversion fails after max retries."""
  ```

- [ ] 6.2: Create test fixtures:
  - `tests/fixtures/convert/simple_plan.md` - Simple 3-section plan
  - `tests/fixtures/convert/complex_plan.md` - Plan with many sections
  - `tests/fixtures/convert/no_gates_plan.md` - Plan without explicit gates

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/converters/__init__.py` | Create | Converter module |
| `src/debussy/converters/plan_converter.py` | Create | Conversion logic |
| `src/debussy/converters/prompts.py` | Create | Claude prompts |
| `src/debussy/cli.py` | Modify | Add `convert` command |
| `tests/test_convert.py` | Create | Conversion tests |
| `tests/fixtures/convert/` | Create | Test plan fixtures |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Async runner | `src/debussy/runners/claude.py` | Claude invocation |
| Audit integration | `src/debussy/core/auditor.py` | Validate output |
| Rich output | `src/debussy/cli.py` | Progress display |

### Claude Invocation Pattern

Study `src/debussy/runners/claude.py` for how to spawn Claude:

```python
# The existing ClaudeRunner uses subprocess
# For convert, we might want to use --print mode for simpler output parsing

import subprocess

result = subprocess.run(
    ["claude", "--print", "-p", prompt, "--model", model],
    capture_output=True,
    text=True,
    timeout=120,
)
output = result.stdout
```

### Output Parsing Pattern

Parse Claude's file output:

```python
import re

def parse_file_output(output: str) -> dict[str, str]:
    """Parse ---FILE: name--- blocks from Claude output."""
    files = {}
    pattern = r"---FILE:\s*(.+?)---\n(.*?)---END FILE---"
    for match in re.finditer(pattern, output, re.DOTALL):
        filename = match.group(1).strip()
        content = match.group(2).strip()
        files[filename] = content
    return files
```

## Test Strategy

- [ ] Unit tests for prompt building
- [ ] Unit tests for output parsing
- [ ] Integration tests with mock Claude
- [ ] **End-to-end test**: convert real plan, verify audit passes
- [ ] Test retry behavior

## Acceptance Criteria

**ALL must pass:**

- [ ] `debussy convert plan.md` produces structured output
- [ ] Output passes `debussy audit`
- [ ] `--interactive` mode asks clarifying questions
- [ ] Retry loop attempts conversion up to max-retries times
- [ ] Source plan content is preserved (no tasks lost)
- [ ] Tests exist and pass
- [ ] All linting passes

## Rollback Plan
- Convert writes to new directory, doesn't modify source
- If conversion fails, user still has original plan
- Can always fall back to manual editing

---

## Implementation Notes

### Token Efficiency

Use haiku by default to minimize costs. The conversion prompt should be:
- Clear and structured (Claude follows format better)
- Include templates inline (no need for Claude to fetch)
- Specific about output format (reduces ambiguity)

### Audit as Quality Gate

The key insight: **audit is the quality gate**. We don't need to validate Claude's output manually - audit does it for us.

```python
async def convert(self, source: Path, output: Path) -> ConversionResult:
    for attempt in range(self.max_iterations):
        # Generate files
        files = await self._generate_files(source, output, previous_issues)

        # Audit the output
        result = self.auditor.audit(output / "MASTER_PLAN.md")

        if result.passed:
            return ConversionResult(success=True, ...)

        # Use audit issues to guide next iteration
        previous_issues = result.issues

    return ConversionResult(success=False, ...)
```

### Handling Large Plans

For very large source plans:
1. Summarize first, then generate (two-pass)
2. Or chunk into sections and process sequentially
3. Increase timeout for large plans
