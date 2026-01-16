# Context Monitoring Phase 4: Smart Restart Logic

**Status:** Pending
**Master Plan:** [context-monitoring-MASTER_PLAN.md](context-monitoring-MASTER_PLAN.md)
**Depends On:** [Phase 1](context-monitoring-phase-1.md), [Phase 2](context-monitoring-phase-2.md), [Phase 3](context-monitoring-phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase3_templates_phase_6A.md`, `notes/NOTES_phase3_templates_phase_6B.md`, `notes/NOTES_phase3_templates_phase_6C.md`
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
- [ ] Write `notes/NOTES_phase3_templates_phase_6D.md` with:
  - Summary of smart restart integration
  - End-to-end restart flow description
  - Configuration reference
  - Test scenarios covered
  - Known limitations or edge cases
- [ ] Signal completion: `debussy done --phase 6D`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~60%)

---

## Overview

Tie it all together: detect context threshold breach, capture checkpoint state, restart phase with injected context, and respect max restart limits. This phase integrates the context estimator (Phase 1), checkpoint manager (Phase 2), and auto-commit (Phase 3) into a cohesive restart orchestration system. When context limits are approached, Debussy gracefully stops the current session, commits progress, and restarts with full context about what was already accomplished.

## Dependencies
- Previous phases: ALL (1, 2, 3) - This phase integrates all previous work
- Internal: Orchestrator, ClaudeRunner, Config, StateManager
- External: None (all components built in previous phases)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Restart loops | Low | High | Max restart count (3), fail after limit exceeded |
| Lost context on restart | Low | Medium | Checkpoint injection, auto-commit before restart |
| Restart mid-critical-operation | Low | High | Graceful stop mechanism, allow phase to finish current tool |
| Config complexity | Medium | Low | Sensible defaults, clear documentation |
| Integration breaks existing phases | Low | High | Feature behind config threshold, extensive testing |

---

## Tasks

### 1. Add Restart Configuration
- [ ] 1.1: Update `src/debussy/config.py` with context_threshold field (default: 80.0)
- [ ] 1.2: Add tool_call_threshold field (default: 100)
- [ ] 1.3: Add max_restarts field (default: 3)
- [ ] 1.4: Document all new configuration fields with examples

### 2. Implement Restart Orchestration
- [ ] 2.1: Create _execute_phase_with_restart() method in `src/debussy/orchestrator.py`
- [ ] 2.2: Implement restart loop with MAX_RESTARTS limit
- [ ] 2.3: Initialize checkpoint manager at start of first attempt
- [ ] 2.4: Prepare restart context from checkpoint on subsequent attempts
- [ ] 2.5: Inject restart context into effective_prompt
- [ ] 2.6: Create context estimator for each attempt with configured thresholds
- [ ] 2.7: Implement on_context_limit callback to trigger restart
- [ ] 2.8: Call runner.request_stop() for graceful termination
- [ ] 2.9: Set estimator and callback on runner before execution
- [ ] 2.10: Auto-commit before each restart attempt
- [ ] 2.11: Log restart attempts with clear messages
- [ ] 2.12: Fail with clear error after max restarts exceeded
- [ ] 2.13: Replace existing execute_phase() call with _execute_phase_with_restart()

### 3. Add ClaudeRunner Request Stop
- [ ] 3.1: Add _should_stop flag to ClaudeRunner
- [ ] 3.2: Implement request_stop() method to set flag
- [ ] 3.3: Check _should_stop in stream processing loop
- [ ] 3.4: Gracefully terminate subprocess when stop requested
- [ ] 3.5: Return partial result with stop indication

### 4. Update CLI with Restart Options
- [ ] 4.1: Add --context-threshold option to run command in `src/debussy/cli.py`
- [ ] 4.2: Add --max-restarts option to run command
- [ ] 4.3: Override config values with CLI flags when provided
- [ ] 4.4: Update help text with clear descriptions and examples

### 5. Write Integration Tests
- [ ] 5.1: Create `tests/test_smart_restart.py`
- [ ] 5.2: Test restart triggered when context threshold exceeded
- [ ] 5.3: Test checkpoint context injected into restart prompt
- [ ] 5.4: Test progress entries appear in restart context
- [ ] 5.5: Test modified files appear in restart context
- [ ] 5.6: Test restart count increments correctly
- [ ] 5.7: Test max restarts limit respected (fails after 3 attempts)
- [ ] 5.8: Test auto-commit happens before each restart
- [ ] 5.9: Test graceful stop via request_stop()
- [ ] 5.10: Test CLI flags override config values
- [ ] 5.11: Test restart disabled when threshold set to 100 (or high value)
- [ ] 5.12: Test tool call fallback triggers restart
- [ ] 5.13: Mock ClaudeRunner and estimator for consistent testing
- [ ] 5.14: Test full end-to-end restart cycle

### 6. Update Documentation
- [ ] 6.1: Add configuration reference to README or docs
- [ ] 6.2: Document CLI flags and usage examples
- [ ] 6.3: Explain restart behavior and thresholds
- [ ] 6.4: Provide troubleshooting guidance

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/config.py` | Modify | Add context_threshold, tool_call_threshold, max_restarts fields |
| `src/debussy/orchestrator.py` | Modify | Add _execute_phase_with_restart() integration logic |
| `src/debussy/runners/claude.py` | Modify | Add request_stop() method and graceful termination |
| `src/debussy/cli.py` | Modify | Add --context-threshold and --max-restarts flags |
| `tests/test_smart_restart.py` | Create | Integration tests for full restart cycle (14+ tests) |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Phase execution | `src/debussy/orchestrator.py` | Wrap existing execute_phase logic in restart loop |
| Config dataclass | `src/debussy/config.py` | Add new fields with type hints and defaults |
| CLI options | `src/debussy/cli.py` | Use click.option with float/int types |
| Callback pattern | `src/debussy/runners/claude.py` | Estimator callback triggers orchestrator action |
| Logging | `src/debussy/orchestrator.py` | Use logger.warning() for restarts, logger.error() for failures |

## Test Strategy

- [ ] Integration tests with mocked ClaudeRunner to simulate threshold breach
- [ ] Test checkpoint context injection (verify restart prompt contains progress)
- [ ] Test max restarts failure path
- [ ] Test graceful stop mechanism
- [ ] Test auto-commit before restart
- [ ] Test CLI flag overrides
- [ ] Test restart disabled (high threshold or max_restarts=0)
- [ ] End-to-end test with all components working together

## Validation

- Use `python-task-validator` to verify code quality before completion
- Use `debussy` to test run command with new flags
- Manually test restart scenario with a long-running phase (if feasible)

## Acceptance Criteria

**ALL must pass:**

- [ ] _execute_phase_with_restart() implements full restart loop
- [ ] Context estimator integrated with callback to trigger restart
- [ ] Checkpoint context injected into restart prompts
- [ ] Auto-commit happens before each restart
- [ ] Max restarts limit prevents infinite loops
- [ ] Graceful stop mechanism works (request_stop)
- [ ] CLI flags added (--context-threshold, --max-restarts)
- [ ] Config fields added with sensible defaults
- [ ] 14+ integration tests written and passing
- [ ] All existing tests still pass
- [ ] ruff check returns 0 errors
- [ ] pyright returns 0 errors
- [ ] Test coverage maintained or increased
- [ ] Documentation updated with configuration and usage

## Rollback Plan

Feature is controlled by config thresholds:
1. Set `context_threshold: 100` to effectively disable (never triggers)
2. Or set `max_restarts: 0` to disable restart capability
3. If critical issues found, revert orchestrator changes and use --context-threshold 100 flag
4. All previous phases (1-3) remain functional independently

No breaking changes since restart is opt-in via threshold configuration.

---

## Implementation Notes

**Configuration Example:**
```yaml
# .debussy/config.yaml

# Context monitoring (Phase 6)
context_threshold: 80.0  # Restart when estimated usage hits 80%
tool_call_threshold: 100  # Fallback: restart after 100 tool calls
max_restarts: 3  # Give up after 3 restart attempts

# Auto-commit
auto_commit: true  # Commit at phase boundaries
commit_on_failure: false  # Only commit successful phases
```

**CLI Usage Examples:**
```bash
# Run with context monitoring (default 80%)
debussy run MASTER_PLAN.md

# Run with higher threshold (90%)
debussy run MASTER_PLAN.md --context-threshold 90

# Run without auto-commit
debussy run MASTER_PLAN.md --no-auto-commit

# Allow dirty working directory
debussy run MASTER_PLAN.md --allow-dirty

# Disable restarts (one-shot mode)
debussy run MASTER_PLAN.md --max-restarts 0
```

**Restart Flow:**
1. Phase starts, checkpoint initialized, estimator created
2. During execution, estimator tracks context usage
3. When threshold hit, callback invoked, request_stop() called
4. Runner gracefully terminates, auto-commit runs
5. Checkpoint context prepared (progress + git diff)
6. Restart counter incremented, check against max_restarts
7. New prompt = checkpoint context + original prompt
8. Fresh estimator created, execution resumes
9. Repeat until phase completes or max restarts exceeded

**Design Decisions:**
- Default threshold 80% (conservative, triggers before quality degradation)
- Max 3 restarts (prevents infinite loops, reasonable for complex phases)
- Graceful stop via request_stop() (allows current tool to complete)
- Auto-commit before restart (creates clean checkpoint)
- Checkpoint context prepended to prompt (ensures visibility)
- Clear error message after max restarts (guides user to review phase complexity)

**Integration Points:**
- ClaudeRunner: estimator hooks, request_stop mechanism
- CheckpointManager: progress capture, restart context formatting
- Config: threshold values, max restarts
- Orchestrator: restart loop, prompt injection, auto-commit