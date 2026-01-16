# Phase 4: Convert Command - Implementation Notes

**Phase Completed:** 2026-01-15
**Status:** COMPLETED

## Summary

Successfully implemented `debussy convert <freeform_plan>` command that uses Claude to transform freeform plans into Debussy's structured format. The conversion includes an audit-gate loop that retries conversion when audit fails, using the issues as feedback for the next iteration.

## What Was Implemented

### 1. Converters Module (src/debussy/converters/)

**__init__.py:**
- Exports `ConversionResult` and `PlanConverter`

**prompts.py:**
- `CONVERSION_PROMPT`: Main prompt template for Claude to convert plans
- `REMEDIATION_SECTION`: Added to prompt when retrying after audit failure
- `INTERACTIVE_QUESTIONS`: Placeholder for future interactive mode

**plan_converter.py:**
- `ConversionResult(BaseModel)`: Result model with success status, iteration count, files created, audit results, and warnings
- `PlanConverter` class:
  - `__init__()`: Takes auditor, templates_dir, max_iterations, model, timeout
  - `convert()`: Main conversion method with audit-retry loop
  - `_load_template()`: Loads template content from file
  - `_build_conversion_prompt()`: Constructs the Claude prompt with templates and previous issues
  - `_run_claude()`: Invokes Claude CLI via subprocess
  - `_parse_file_output()`: Parses `---FILE: name---` blocks from Claude output

### 2. CLI Command (src/debussy/cli.py)

Added `debussy convert` command with options:
- `source`: Path to freeform plan (required argument)
- `--output, -o`: Output directory (default: `structured-{source_stem}`)
- `--interactive, -i`: Ask clarifying questions (placeholder)
- `--model, -m`: Claude model to use (default: haiku)
- `--max-retries`: Max conversion attempts (default: 3)
- `--force, -f`: Overwrite existing output directory

**Rich Output:**
- Progress messages during conversion
- File creation confirmations with checkmarks
- Audit result display (pass/fail with counts)
- Warnings display
- Next steps guide on success

### 3. Test Suite (tests/test_convert.py)

**TestPlanConverter class (10 tests):**
- `test_converter_initialization`: Verify constructor parameters
- `test_convert_source_not_found`: Error handling for missing source
- `test_convert_template_not_found`: Error handling for missing templates
- `test_convert_simple_plan`: Successful conversion with mocked Claude
- `test_convert_retry_on_audit_fail`: Tests retry behavior with audit feedback
- `test_convert_max_retries_exceeded`: Verifies max retry limit
- `test_parse_file_output`: Tests `---FILE:---` block parsing
- `test_parse_file_output_empty`: Empty output handling
- `test_build_conversion_prompt_basic`: Prompt building without issues
- `test_build_conversion_prompt_with_issues`: Prompt with remediation section

**TestConversionResult class (2 tests):**
- `test_result_successful`: Success result model
- `test_result_failed`: Failure result model

**TestConvertCLI class (4 tests):**
- `test_convert_cli_source_not_found`: CLI error for missing source
- `test_convert_cli_output_exists`: CLI error when output exists
- `test_convert_cli_with_force`: `--force` flag behavior
- `test_convert_cli_default_output`: Default output directory behavior

**TestPrompts class (3 tests):**
- `test_conversion_prompt_has_placeholders`: Verifies required placeholders
- `test_remediation_section_has_placeholder`: Verifies issues placeholder
- `test_conversion_prompt_structure`: Key structural elements

### 4. Test Fixtures (tests/fixtures/convert/)

Created three test plans:
- `simple_plan.md`: Basic 3-section plan for user authentication
- `complex_plan.md`: Multi-phase API refactoring plan with detailed sections
- `no_gates_plan.md`: Minimal plan without explicit validation gates

## Design Decisions

1. **Synchronous Implementation**: Used synchronous subprocess calls rather than async, since conversion is typically a one-shot operation and simpler to implement/test.

2. **Audit as Quality Gate**: The key insight from the phase plan - audit validates Claude's output automatically, no need for manual validation. If audit passes, conversion succeeded.

3. **Retry with Feedback**: When audit fails, include the issues in the next prompt so Claude can fix specific problems.

4. **File Output Format**: Claude outputs files in `---FILE: name---` blocks, making them easy to parse and write to disk.

5. **Default Model**: Using `haiku` by default to minimize token costs while still achieving good results.

6. **Separate Templates**: Uses existing templates from `docs/templates/plans/` rather than embedding them in the converter.

7. **Pydantic Model for Results**: `ConversionResult` is a Pydantic model for type safety and easy serialization.

## Files Created/Modified

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/debussy/converters/__init__.py` | Created | 7 | Module exports |
| `src/debussy/converters/prompts.py` | Created | 63 | Claude prompts for conversion |
| `src/debussy/converters/plan_converter.py` | Created | 265 | Core conversion logic |
| `src/debussy/cli.py` | Modified | +117 | Added convert command |
| `tests/test_convert.py` | Created | 570 | Comprehensive test suite |
| `tests/fixtures/convert/simple_plan.md` | Created | 17 | Simple test fixture |
| `tests/fixtures/convert/complex_plan.md` | Created | 69 | Complex test fixture |
| `tests/fixtures/convert/no_gates_plan.md` | Created | 9 | Minimal test fixture |

**Total:** 8 files created/modified, ~1100 lines of code (production + tests)

## Validation Results

### Code Quality
```bash
uv run ruff format .      # All files formatted
uv run ruff check .       # All checks passed (0 errors)
```

### Type Checking
```bash
uv run pyright src/debussy/  # 0 errors, 0 warnings, 0 informations
```

### Tests
```bash
uv run pytest tests/ -v --no-cov  # 344 passed, 2 warnings
```

All 19 new convert tests pass, and all 344 total tests pass.

## Example Usage

```bash
# Basic usage - convert a freeform plan
debussy convert my-plan.md --output plans/my-feature/

# With custom model and retry settings
debussy convert messy-plan.md --model sonnet --max-retries 5

# Force overwrite existing directory
debussy convert old-plan.md --output plans/existing/ --force

# Interactive mode (placeholder - not fully implemented)
debussy convert plan.md --interactive
```

## Conversion Flow

```
┌─────────────────┐
│ Read source     │
│ Load templates  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Build prompt    │<──────────────────┐
│ (with issues    │                   │
│  if retry)      │                   │
└────────┬────────┘                   │
         │                            │
         v                            │
┌─────────────────┐                   │
│ Run Claude      │                   │
│ Parse output    │                   │
└────────┬────────┘                   │
         │                            │
         v                            │
┌─────────────────┐                   │
│ Write files     │                   │
└────────┬────────┘                   │
         │                            │
         v                            │
┌─────────────────┐     ┌───────────────────┐
│ Run audit       │────>│ Audit failed?     │
└────────┬────────┘     │ iterations < max? │
         │              └─────────┬─────────┘
         │                        │ yes
         │                        │
    (audit passed)                │
         │                        │
         v                        │
┌─────────────────┐               │
│ Return success  │               │
└─────────────────┘               │
                                  │
         ┌────────────────────────┘
         │
         v
┌─────────────────┐
│ Return failure  │
│ (max retries)   │
└─────────────────┘
```

## Acceptance Criteria Status

- [x] `debussy convert plan.md` produces structured output
- [x] Output is validated with `debussy audit`
- [x] Retry loop attempts conversion up to max-retries times
- [x] Previous audit issues included in retry prompts
- [x] Tests exist and pass (19 new tests, all passing)
- [x] All linting passes (ruff: 0 errors)
- [x] Type checking passes (pyright: 0 errors)
- [ ] `--interactive` mode asks clarifying questions (placeholder - basic structure exists)

## Limitations and Future Work

1. **Interactive Mode**: Not fully implemented. The `--interactive` flag is accepted but doesn't change behavior. Future work to add `AskUserQuestion`-style prompts for clarifying ambiguities.

2. **Large Plans**: No special handling for very large source plans. Could add chunking or summarization for plans exceeding token limits.

3. **Custom Templates**: Currently uses generic template. Could extend to auto-detect project type and use backend/frontend templates.

4. **Streaming Output**: Could add Rich progress bar for conversion attempts instead of simple messages.

5. **Dry Run**: Could add `--dry-run` flag to preview what would be generated without writing files.

## Lessons Learned

1. **Mock Placement**: When mocking `subprocess.run` for CLI tests, need to patch at the correct import location (`debussy.converters.plan_converter.subprocess.run` not `subprocess.run`).

2. **Temporary Directories**: CLI tests that use default output directories can leave artifacts. Better to use `tmp_path` fixture and explicit output paths.

3. **Return Statement Limit**: Ruff's `PLR0911` rule limits return statements to 6. For complex flow control, either refactor into helper methods or add `# noqa: PLR0911` comment.

4. **Test Independence**: Each test should clean up after itself or use isolated paths to avoid interference.

## Conclusion

Phase 4 implementation is **COMPLETE** and **VALIDATED**. The `debussy convert` command provides a fallback path for users with existing freeform plans, using Claude to transform them into Debussy's structured format with audit validation. All gates pass, all tests pass, and the feature is ready for use.

The conversion includes an intelligent retry loop that feeds audit failures back to Claude, allowing it to self-correct common issues like missing gates or invalid phase table formats.
