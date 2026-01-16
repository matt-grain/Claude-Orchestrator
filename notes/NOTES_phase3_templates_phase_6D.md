# Phase 6D: Smart Restart Logic - Implementation Notes

**Date:** 2026-01-15
**Phase:** Context Monitoring Phase 4: Smart Restart Logic

## Summary

This phase integrates the context estimator (Phase 1), checkpoint manager (Phase 2), and auto-commit (Phase 3) into a cohesive restart orchestration system. When context limits are approached, Debussy gracefully stops the current session, commits progress, and restarts with full context about what was already accomplished.

## Implementation Status

### Configuration Added (`src/debussy/config.py`)

Three new configuration fields control the smart restart behavior:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context_threshold` | float | 80.0 | Percentage of context to trigger restart (set to 100 to disable) |
| `tool_call_threshold` | int | 100 | Fallback: restart after N tool calls |
| `max_restarts` | int | 3 | Max restart attempts before failing (set to 0 to disable) |

### ClaudeRunner Enhancements (`src/debussy/runners/claude.py`)

1. **Graceful Stop Mechanism**
   - Added `_should_stop` flag to track stop requests
   - Implemented `request_stop()` method to request graceful termination
   - Implemented `is_stop_requested()` method to check stop state
   - Stop flag is checked in `_stream_json_reader()` loop
   - Flag is reset at start of each `execute_phase()` call

2. **Stream Processing Updates**
   - `_stream_json_reader()` now returns a tuple: `(text, was_stopped)`
   - When `_should_stop` is True, stream reading terminates gracefully
   - Process is killed after graceful stop
   - Special exit code `-2` indicates context limit restart
   - Session log prefixed with `CONTEXT_LIMIT_RESTART` marker

### Orchestrator Restart Logic (`src/debussy/core/orchestrator.py`)

1. **New Method: `_execute_phase_internal()`**
   - Wraps phase execution with restart loop
   - Creates fresh `ContextEstimator` for each attempt
   - Sets up restart callback that calls `runner.request_stop()`
   - Injects checkpoint context into restart prompts
   - Calls `_auto_commit_phase()` before each restart
   - Enforces max restart limit

2. **Restart Flow**
   ```
   1. Phase starts, estimator created with configured thresholds
   2. During execution, estimator tracks context usage
   3. When threshold hit, callback invokes request_stop()
   4. Runner gracefully terminates, returns CONTEXT_LIMIT_RESTART marker
   5. Auto-commit runs to preserve work
   6. Checkpoint context prepared (progress + git diff)
   7. Restart counter incremented, check against max_restarts
   8. New prompt = checkpoint context + original prompt
   9. Fresh execution starts, repeat until complete or max exceeded
   ```

3. **Integration Points**
   - Uses `CheckpointManager.prepare_restart()` for context
   - Uses `_auto_commit_phase()` before restart
   - Disabled for remediation runs (they have their own retry logic)

### CLI Options Added (`src/debussy/cli.py`)

| Flag | Description |
|------|-------------|
| `--context-threshold FLOAT` | Override context threshold (0-100) |
| `--max-restarts INT` | Override max restart attempts (0 to disable) |

## Configuration Reference

### YAML Configuration

```yaml
# .debussy/config.yaml

# Context monitoring (Phase 6)
context_threshold: 80.0  # Restart when estimated usage hits 80%
tool_call_threshold: 100  # Fallback: restart after 100 tool calls
max_restarts: 3  # Give up after 3 restart attempts
```

### CLI Usage Examples

```bash
# Run with context monitoring (default 80%)
debussy run MASTER_PLAN.md

# Run with higher threshold (90%)
debussy run MASTER_PLAN.md --context-threshold 90

# Disable restarts (one-shot mode)
debussy run MASTER_PLAN.md --max-restarts 0

# Disable context-based restart (threshold 100)
debussy run MASTER_PLAN.md --context-threshold 100
```

## End-to-End Restart Flow

1. **Phase Starts**
   - Checkpoint initialized for phase
   - Context estimator created with configured thresholds
   - Restart callback wired to orchestrator

2. **During Execution**
   - Estimator tracks file reads, tool outputs, tool call count
   - After each tool result, `should_restart()` is checked
   - If threshold exceeded, callback triggers `request_stop()`

3. **When Threshold Hit**
   - `_should_stop` flag set on runner
   - Stream processing loop detects flag, terminates
   - Process tree killed gracefully
   - Result returned with `CONTEXT_LIMIT_RESTART` marker

4. **Restart Preparation**
   - Auto-commit preserves current work
   - Checkpoint captures git state and progress entries
   - Restart context formatted with:
     - Session reset warning
     - Phase info and restart count
     - Progress logged before reset
     - Modified files list
     - Instructions to continue (not redo)

5. **Restart Execution**
   - Restart count incremented
   - Fresh estimator created
   - Context prepended to phase prompt
   - Phase re-executed with context awareness

6. **Termination Conditions**
   - Phase completes successfully → done
   - Max restarts exceeded → fail with clear message
   - Other failure → propagate normally

## Test Coverage Summary

Created 40+ tests in `tests/test_smart_restart.py`:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| TestClaudeRunnerRequestStop | 3 | request_stop() and is_stop_requested() |
| TestContextEstimatorIntegration | 3 | Estimator integration with runner |
| TestConfigRestartFields | 6 | Config field defaults and customization |
| TestCheckpointManagerRestartContext | 5 | Restart context generation |
| TestExecutePhaseInternalRestart | 3 | Restart enable/disable logic |
| TestContextLimitMarker | 3 | CONTEXT_LIMIT_RESTART marker |
| TestCLIFlagOverrides | 3 | CLI flag override behavior |
| TestAutoCommitBeforeRestart | 1 | Auto-commit calling convention |
| TestGracefulStopMechanism | 2 | Stop mechanism verification |
| TestMaxRestartsEnforcement | 4 | Max restarts limit |
| TestRestartContextInjection | 2 | Context prepended to prompt |
| TestEndToEndScenarios | 3 | Mocked end-to-end scenarios |
| TestRemediationSkipsRestart | 2 | Remediation skip logic |

**All 608 tests pass.** Total coverage: 66.62%

## Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| ruff check | PASS | 0 errors |
| pyright | PASS | 0 errors, 0 warnings |
| pytest | PASS | 608 tests pass |
| coverage | PASS | 66.62% (above 50% threshold) |

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `src/debussy/config.py` | Modified | Added context_threshold, tool_call_threshold, max_restarts fields |
| `src/debussy/core/orchestrator.py` | Modified | Added _execute_phase_internal() with restart loop |
| `src/debussy/runners/claude.py` | Modified | Added request_stop(), is_stop_requested(), graceful stop mechanism |
| `src/debussy/cli.py` | Modified | Added --context-threshold and --max-restarts flags |
| `tests/test_smart_restart.py` | Created | 40+ integration tests for smart restart |
| `README.md` | Modified | Updated configuration and CLI documentation |

## Design Decisions

1. **Exit Code -2 for Context Restart**: Distinguishes context limit restarts from timeouts (-1) and other failures (non-zero)

2. **CONTEXT_LIMIT_RESTART Marker**: Session log prefix allows orchestrator to detect restart-needed condition without inspecting exit code

3. **Remediation Skips Restart**: Remediation runs already have their own retry logic; adding restart would create confusing nested loops

4. **Fresh Estimator Per Attempt**: Each restart gets a fresh context estimate since it's a new Claude session

5. **Auto-Commit Before Restart**: Ensures work is preserved even if restart fails; creates clean checkpoint

6. **Context Prepended, Not Appended**: Restart context at the start ensures Claude sees it first and understands the situation

## Known Limitations

1. **Estimation Accuracy**: Token counting is approximate (4 chars ≈ 1 token with 1.3x overhead). Actual usage may vary.

2. **No Response Token Tracking**: We can only track observable inputs (files, tool outputs), not Claude's response tokens.

3. **Restart Lag**: There's a delay between threshold detection and stop; some additional context may be used.

4. **No Incremental Checkpoint**: Checkpoint only captures state at restart time, not continuous progress.

## Recommendations for Future Work

1. Consider adding real-time context usage display in the TUI HUD

2. May want to persist restart metrics to state.db for analytics

3. Could add configurable restart delay to avoid rapid restart loops

4. Consider integration with LTM for cross-restart memory persistence
