# Phase 6A: Context Estimation - Implementation Notes

**Date:** 2026-01-15
**Phase:** Context Monitoring Phase 1: Context Estimation

## Summary

This phase implements the context usage estimator that provides token counting and threshold detection without relying on Claude Code's broken stream-json cumulative tokens (see docs/FUTURE.md for the known bug). The implementation was found to already exist in the codebase, so the primary work was creating comprehensive unit tests.

## Implementation Status

### Pre-existing Components Found

The context estimator module (`src/debussy/runners/context_estimator.py`) and its integration into `ClaudeRunner` (`src/debussy/runners/claude.py`) were already implemented:

1. **ContextEstimate dataclass** - Container for tracking:
   - `file_tokens`: Tokens from Read tool outputs
   - `tool_output_tokens`: Tokens from other tool results
   - `prompt_tokens`: Tokens from injected prompts
   - `tool_call_count`: Fallback heuristic counter
   - `total_estimated` property: Applies 1.3x reasoning overhead
   - `usage_percentage` property: Percentage of 200k context window

2. **ContextEstimator class** - Tracks context usage with methods:
   - `add_file_read(content)`: Track file content reads
   - `add_tool_output(content)`: Track tool outputs + increment call count
   - `add_prompt(content)`: Track injected prompts
   - `should_restart()`: Primary (token %) + fallback (tool count) detection
   - `get_estimate()`: Returns current estimate snapshot
   - `reset()`: Clear all counters for fresh session

3. **ClaudeRunner integration** - Already wired up:
   - Lines 269-270: `_context_estimator` and `_restart_callback` fields
   - Lines 317-331: `set_context_estimator()` and `set_restart_callback()` methods
   - Lines 735-745: Hooks in `_display_tool_result()` for tracking and restart checks
   - Lines 896-900: Reset estimator and add initial prompt at phase start

## Token Counting Approach

The implementation uses a simple but effective approach:

- **Character-to-token ratio**: 4:1 (conservative estimate)
- **Reasoning overhead**: 1.3x multiplier to account for Claude's internal token usage
- **Context limit**: 200,000 tokens (Claude's context window)
- **Default threshold**: 80% to trigger restart before quality degrades
- **Fallback threshold**: 100 tool calls as heuristic

### Accuracy Considerations

1. The 4:1 char-to-token ratio is conservative - actual ratios vary by content type
2. The 1.3x overhead accounts for chain-of-thought and tool formatting
3. The system cannot track Claude's actual response tokens (only observable inputs)
4. The fallback tool count heuristic provides safety net when token estimate is low but activity is high

## Integration Points in ClaudeRunner

The estimator is hooked into the stream processing pipeline:

1. **Initial prompt**: Added via `add_prompt()` when phase starts
2. **File reads**: Tracked via `add_file_read()` when Read tool results arrive
3. **Tool outputs**: Tracked via `add_tool_output()` for all non-Read tools
4. **Restart check**: `should_restart()` called after each tool result
5. **Reset**: Estimator reset at start of each phase execution

## Test Coverage Summary

Created 39 comprehensive unit tests in `tests/test_context_estimator.py`:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| TestContextEstimateDataclass | 7 | Dataclass fields and properties |
| TestContextEstimatorInit | 3 | Initialization and defaults |
| TestContextEstimatorAddFileRead | 3 | File read token tracking |
| TestContextEstimatorAddToolOutput | 3 | Tool output + call count |
| TestContextEstimatorAddPrompt | 3 | Prompt token tracking |
| TestContextEstimatorShouldRestart | 6 | Threshold detection (primary + fallback) |
| TestContextEstimatorReset | 3 | Reset functionality |
| TestContextEstimatorGetEstimate | 1 | Returns copy of estimate |
| TestContextEstimatorEstimateTokens | 3 | Token estimation logic |
| TestContextEstimatorConstants | 5 | Module constants |
| TestContextEstimatorIntegration | 2 | Realistic session scenarios |

**All 39 tests pass.** Coverage for `context_estimator.py` is 100%.

## Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| ruff check | PASS | 0 errors |
| pyright | PASS | 0 errors, 0 warnings |
| pytest | PASS | 411 tests pass (excluding pre-existing convert test failures) |
| coverage | PASS | 56.05% (above 50% threshold) |

## Code Changes Made

1. **src/debussy/runners/claude.py**: Moved `ContextEstimator` import to TYPE_CHECKING block to satisfy ruff TC001 lint rule (the import is only used for type hints)

2. **tests/test_context_estimator.py**: Created comprehensive test suite (39 tests)

## Pre-existing Issues Found

The test `tests/test_convert.py::TestConvertCLI::test_convert_cli_with_force` was failing due to a quality check prompt in the convert CLI that required user input. This was fixed during remediation by providing `input="n\n"` to the CLI runner.

## Key Decisions

1. **Character-to-token ratio (4:1)**: Chose a conservative estimate over using tiktoken to avoid external dependencies. Actual ratios vary (English ~4:1, code ~3:1) but erring on the side of caution is preferred.

2. **Reasoning overhead multiplier (1.3x)**: Claude uses tokens for chain-of-thought reasoning that we cannot observe. The 30% overhead accounts for this "hidden" token usage.

3. **Dual threshold approach**: Primary check is token percentage (default 80%), but a fallback tool call count (default 100) catches cases where many small operations accumulate.

4. **Passive observer pattern**: The estimator hooks into stream parsing without modifying or blocking data flow. This ensures zero impact on existing functionality.

5. **Reset per phase**: The estimator resets at the start of each phase execution, treating each phase as a fresh context window.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `tests/test_convert.py` | Modified | Fixed `test_convert_cli_with_force` test to provide input for quality retry prompt (line 508) |

## Recommendations for Phase 4

When integrating the restart logic in Phase 4 (Automatic Restart):

1. The orchestrator should call `set_context_estimator()` and `set_restart_callback()` before executing phases
2. The callback should trigger graceful phase interruption and re-queue
3. Consider persisting context estimate to state.db for debugging/metrics
4. May want to add logging of restart triggers to the phase log file
