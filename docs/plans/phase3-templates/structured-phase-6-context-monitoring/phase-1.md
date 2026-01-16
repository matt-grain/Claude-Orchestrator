# Context Monitoring Phase 1: Context Estimation

**Status:** Pending
**Master Plan:** [context-monitoring-MASTER_PLAN.md](context-monitoring-MASTER_PLAN.md)
**Depends On:** None (can run independently)

---

## Process Wrapper (MANDATORY)
- [ ] Read the files listed in "CRITICAL: Read These First" section below
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality - run from project root
  uv run ruff format . && uv run ruff check --fix .

  # Type checking
  uv run pyright src/debussy/

  # Tests - ALL tests must pass, not just new ones
  uv run pytest tests/ -x -v
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass with 0 errors
- [ ] Write `notes/NOTES_phase3_templates_phase_6A.md` with:
  - Summary of context estimator implementation
  - Token counting approach and accuracy considerations
  - Integration points in ClaudeRunner
  - Test coverage summary
- [ ] Signal completion: `debussy done --phase 6A`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~60%)

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **FUTURE.md**: `docs/FUTURE.md` - Token reporting bug context (why we can't trust stream-json tokens)
2. **ClaudeRunner**: `src/debussy/runners/claude.py` - Current stream parsing, where monitoring hooks will go
3. **Orchestrator**: `src/debussy/orchestrator.py` - Phase lifecycle, where restart logic lives
4. **State Manager**: `src/debussy/core/state.py` - How to persist checkpoint data
5. **Progress Skill**: `src/debussy/skills/debussy_progress.py` - Existing progress reporting mechanism

**DO NOT** break existing phase execution. Changes should be additive with sensible defaults.

---

## Overview

Build the context usage estimator that doesn't rely on broken stream-json tokens. Since stream-json reports cumulative tokens (not current context), we estimate context growth from observable signals: file content read, tool output sizes, prompt sizes we inject, and a heuristic for Claude's reasoning overhead. This provides a reliable trigger for phase restarts before quality degrades.

## Dependencies
- Previous phase: None (independent feature)
- Internal: Will integrate with ClaudeRunner stream parsing
- External: None (avoiding tiktoken for simplicity, using char-to-token ratio)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Estimation inaccuracy | Medium | Low | Conservative threshold (80%), fallback to tool count, reasoning overhead multiplier |
| False positives | Low | Medium | High threshold, tool call fallback heuristic for validation |
| Integration breaks streaming | Low | High | Hook into existing stream parser, no changes to display logic |
| Performance overhead | Low | Low | Simple arithmetic on strings, no ML models or heavy processing |

---

## Tasks

### 1. Create Context Estimator Module
- [ ] 1.1: Create `src/debussy/runners/context_estimator.py` with ContextEstimate dataclass (file_tokens, tool_output_tokens, prompt_tokens, tool_call_count)
- [ ] 1.2: Implement ContextEstimate.total_estimated property with reasoning overhead multiplier (1.3x)
- [ ] 1.3: Implement ContextEstimate.usage_percentage property
- [ ] 1.4: Create ContextEstimator class with threshold_percent, context_limit, tool_call_threshold configuration
- [ ] 1.5: Implement add_file_read() method to track tokens from Read tool outputs
- [ ] 1.6: Implement add_tool_output() method to track tokens from other tool results
- [ ] 1.7: Implement add_prompt() method to track tokens from injected prompts
- [ ] 1.8: Implement should_restart() method with primary (token percentage) and fallback (tool call count) checks
- [ ] 1.9: Implement get_estimate() and reset() methods
- [ ] 1.10: Add _estimate_tokens() static method using CHARS_TO_TOKENS_RATIO (4:1)

### 2. Integrate Estimator into ClaudeRunner
- [ ] 2.1: Import ContextEstimator in `src/debussy/runners/claude.py`
- [ ] 2.2: Add _context_estimator and _restart_callback optional fields to ClaudeRunner.__init__()
- [ ] 2.3: Add set_context_estimator() and set_restart_callback() methods to ClaudeRunner
- [ ] 2.4: Hook estimator into stream parsing: detect Read tool results and call add_file_read()
- [ ] 2.5: Hook estimator for other tool outputs: call add_tool_output() for all non-Read tools
- [ ] 2.6: Add threshold check after each tool result: if should_restart(), invoke callback
- [ ] 2.7: Add logging for estimator state (debug level) showing cumulative tokens

### 3. Write Unit Tests
- [ ] 3.1: Create `tests/test_context_estimator.py`
- [ ] 3.2: Test ContextEstimate dataclass: verify total_estimated calculation with overhead
- [ ] 3.3: Test ContextEstimate.usage_percentage: verify percentage calculation
- [ ] 3.4: Test ContextEstimator.add_file_read(): verify token counting from file content
- [ ] 3.5: Test ContextEstimator.add_tool_output(): verify token counting and tool call increment
- [ ] 3.6: Test ContextEstimator.add_prompt(): verify prompt token tracking
- [ ] 3.7: Test threshold detection: verify should_restart() returns True at 80% threshold
- [ ] 3.8: Test tool call fallback: verify should_restart() triggers after 100 tool calls
- [ ] 3.9: Test reset(): verify all counters return to zero
- [ ] 3.10: Test _estimate_tokens(): verify char-to-token ratio (4:1)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/runners/context_estimator.py` | Create | Context usage estimation logic with token counting and thresholds |
| `src/debussy/runners/claude.py` | Modify | Integrate estimator hooks into stream parsing |
| `tests/test_context_estimator.py` | Create | Unit tests for estimator (10+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Dataclass models | `src/debussy/core/models.py` | Use @dataclass with property methods for ContextEstimate |
| Stream parsing | `src/debussy/runners/claude.py` | Hook into existing _display_stream_event() or parser methods |
| Logging | `src/debussy/orchestrator.py` | Use logger.debug() for estimator state, logger.warning() for threshold breach |
| Configuration | `src/debussy/config.py` | Accept threshold parameters in constructor for Phase 4 integration |

## Test Strategy

- [ ] Unit tests for ContextEstimate dataclass properties (total_estimated, usage_percentage)
- [ ] Unit tests for ContextEstimator methods (add_file_read, add_tool_output, add_prompt)
- [ ] Unit tests for threshold detection logic (primary token-based, fallback tool-count)
- [ ] Unit tests for reset functionality
- [ ] Integration tests will come in Phase 4 (full restart cycle)

## Validation

- Use `python-task-validator` to verify code quality before completion
- Ensure all type hints are correct and pass pyright strict mode
- Verify no performance regression in stream parsing (estimator is low overhead)

## Acceptance Criteria

**ALL must pass:**

- [ ] ContextEstimator module created with all required methods
- [ ] Estimator integrated into ClaudeRunner stream parsing
- [ ] Token counting uses simple char ratio (no external dependencies)
- [ ] Both primary (token %) and fallback (tool count) threshold detection work
- [ ] Reset clears all state for fresh sessions
- [ ] 10+ unit tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased

## Rollback Plan

Since this phase is purely additive (estimator is not active until orchestrator hooks it up in Phase 4), rollback is simple:
1. Remove `src/debussy/runners/context_estimator.py`
2. Remove estimator hooks from `src/debussy/runners/claude.py` (revert _context_estimator fields)
3. Remove `tests/test_context_estimator.py`

No configuration changes or breaking changes to existing functionality.

---

## Implementation Notes

**Constants to Define:**
- DEFAULT_CONTEXT_LIMIT = 200_000 (Claude's 200k token window)
- CHARS_TO_TOKENS_RATIO = 4 (conservative estimate)
- REASONING_OVERHEAD = 1.3 (30% overhead for CoT and tool formatting)

**Design Decisions:**
- Using simple char-to-token ratio instead of tiktoken to avoid external dependency
- Conservative threshold (80%) to trigger restart before quality degradation
- Tool call count as fallback heuristic (100 calls typically means high context usage)
- Reasoning overhead multiplier accounts for Claude's internal token usage

**Integration Approach:**
- Estimator is passive observer of stream events
- Does not modify or block stream processing
- Callback pattern allows orchestrator to decide restart timing in Phase 4