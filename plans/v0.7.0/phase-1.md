# Issue Tracker Enhancements Phase 1: Add pipe mechanism for plan-from-issues Q&A

**Status:** Pending
**Master Plan:** [Issue Tracker Enhancements-MASTER_PLAN.md](issue-tracker-enhancements-MASTER_PLAN.md)
**Depends On:** N/A
**GitHub Issues:** #17

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue_tracker_enhancements_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `uv run ruff check .` → 0 errors
- type-check: `uv run pyright src/` → 0 errors
- tests: `uv run pytest tests/ -v` → all pass, 60%+ coverage maintained
- security: `uv run bandit -r src/` → no high severity issues

---

## Overview

This phase enables seamless interactive planning when running `plan-from-issues` inside Claude Code conversations. Currently, Q&A gap-filling only works in terminal mode with direct prompts. This enhancement adds a pipe mechanism that routes questions through Claude Code's `AskUserQuestion` tool, allowing the parent Claude agent to gather answers interactively and pipe them back to the subprocess.

The implementation maintains backward compatibility with terminal mode while adding structured JSON IPC for Claude Code integration.

## Dependencies
- Previous phase: N/A (first phase)
- External: None - uses existing `qa_handler.py` module and stdin/stdout for IPC

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking terminal mode Q&A | Low | High | Maintain clear fallback path, add explicit tests for both modes |
| JSON parsing errors in pipe mode | Medium | Medium | Robust error handling with fallback to terminal prompts |
| Environment detection false positives | Low | Medium | Use explicit `DEBUSSY_QA_PIPE=1` flag instead of implicit detection |
| Stdin blocking on misconfiguration | Low | High | Add timeout and clear error messages for pipe mode setup |

---

## Tasks

### 1. Environment Detection and Mode Selection
- [ ] 1.1: Add `DEBUSSY_QA_PIPE` environment variable detection in `qa_handler.py`
- [ ] 1.2: Create `QAMode` enum: `TERMINAL`, `PIPE`
- [ ] 1.3: Implement mode selection logic in `QAHandler.__init__()` based on environment
- [ ] 1.4: Add logging to indicate which Q&A mode is active

### 2. JSON IPC Protocol Definition
- [ ] 2.1: Define `QAQuestion` Pydantic model with fields: `gap_type`, `question`, `options`, `context`
- [ ] 2.2: Define `QAAnswer` Pydantic model with fields: `gap_type`, `answer`
- [ ] 2.3: Create `QAMessage` union type for structured communication
- [ ] 2.4: Document JSON schema in docstrings and module-level comments

### 3. Pipe Mode Implementation
- [ ] 3.1: Implement `_emit_question_json()` method to write structured question to stdout
- [ ] 3.2: Implement `_read_answer_json()` method to read structured answer from stdin with timeout
- [ ] 3.3: Add error handling for malformed JSON with fallback to terminal mode
- [ ] 3.4: Ensure stdout/stderr separation (questions on stdout, logs on stderr)
- [ ] 3.5: Add support for multiple Q&A rounds in single session

### 4. Terminal Mode Preservation
- [ ] 4.1: Extract existing terminal prompt logic into `_prompt_terminal()` method
- [ ] 4.2: Ensure terminal mode works unchanged when `DEBUSSY_QA_PIPE` not set
- [ ] 4.3: Add clear mode indicator in verbose logging

### 5. Integration with Existing Q&A Flow
- [ ] 5.1: Update `ask_question()` method to route through mode-specific handler
- [ ] 5.2: Ensure gap analysis results work with both modes
- [ ] 5.3: Preserve answer persistence to GitHub issues (existing functionality)
- [ ] 5.4: Test with multiple gap types (tech_stack, dependencies, acceptance_criteria, etc.)

### 6. Testing
- [ ] 6.1: Unit tests for `QAMode` detection with mocked environment variables
- [ ] 6.2: Unit tests for JSON serialization/deserialization of Q&A messages
- [ ] 6.3: Integration tests for pipe mode with simulated stdin/stdout
- [ ] 6.4: Integration tests for terminal mode (existing behavior)
- [ ] 6.5: End-to-end test simulating Claude Code parent process
- [ ] 6.6: Test timeout handling for pipe mode
- [ ] 6.7: Test fallback from pipe to terminal on errors

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/planners/qa_handler.py` | Modify | Add pipe mode detection, JSON IPC implementation, mode routing |
| `src/debussy/planners/models.py` | Modify | Add `QAQuestion`, `QAAnswer`, `QAMode` Pydantic models |
| `tests/planners/test_qa_pipe_mode.py` | Create | Unit and integration tests for pipe mode Q&A |
| `tests/planners/test_qa_terminal_mode.py` | Create | Regression tests ensuring terminal mode unchanged |
| `docs/QA_PIPE_PROTOCOL.md` | Create | Document JSON protocol for Claude Code integration |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Pydantic models for IPC | `src/debussy/sync/models.py` | Use for `QAQuestion` and `QAAnswer` validation |
| Async context managers | `src/debussy/sync/github.py` (`GitHubClient`) | Not needed here (synchronous I/O sufficient) |
| Environment-based config | `src/debussy/config.py` | Follow pattern for `DEBUSSY_QA_PIPE` detection |
| Stdin/stdout separation | Standard practice | Questions to stdout, logs to stderr in pipe mode |

## Test Strategy

- [ ] Unit tests for new code (QAMode selection, JSON serialization)
- [ ] Integration tests for pipe mode with mocked stdin/stdout
- [ ] Regression tests for terminal mode (existing functionality)
- [ ] Manual testing with Claude Code integration (document in notes)

### Test Cases
1. **Terminal mode**: Verify existing prompt behavior unchanged
2. **Pipe mode - happy path**: Question emitted as JSON, answer parsed correctly
3. **Pipe mode - malformed answer**: Fallback to terminal prompt
4. **Pipe mode - stdin timeout**: Clear error message and fallback
5. **Multiple Q&A rounds**: Sequential questions in same session
6. **All gap types**: Tech stack, dependencies, acceptance criteria, validation

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Tests written and passing (60%+ coverage maintained)
- [ ] Documentation updated (`docs/QA_PIPE_PROTOCOL.md`)
- [ ] No security vulnerabilities introduced
- [ ] Terminal mode works exactly as before when `DEBUSSY_QA_PIPE` not set
- [ ] Pipe mode successfully emits JSON questions and parses answers
- [ ] Fallback to terminal mode works on pipe errors
- [ ] Manual test with Claude Code integration successful (document in notes)

## Rollback Plan

**Safe rollback steps:**

1. Revert commit if merged:
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

2. If partially deployed (environment variable set in production):
   ```bash
   unset DEBUSSY_QA_PIPE
   # Or remove from deployment configuration
   ```

3. No database migrations or state changes in this phase - rollback is clean

4. If issues found in production:
   - Pipe mode opt-in means terminal mode always available as fallback
   - Users can simply not set `DEBUSSY_QA_PIPE` to use stable terminal mode

---

## Implementation Notes

### JSON Schema Example

```json
// Question (stdout from plan-from-issues)
{
  "type": "question",
  "gap_type": "tech_stack",
  "question": "Which database will this project use?",
  "options": ["PostgreSQL", "MySQL", "SQLite", "MongoDB"],
  "context": "No database mentioned in issues"
}

// Answer (stdin to plan-from-issues)
{
  "type": "answer",
  "gap_type": "tech_stack",
  "answer": "PostgreSQL"
}
```

### Environment Variable Convention

Use explicit opt-in flag:
```bash
export DEBUSSY_QA_PIPE=1  # Enable pipe mode
debussy plan-from-issues ...
```

### Stdout/Stderr Separation

- **Stdout**: JSON questions only (machine-readable)
- **Stderr**: Logs, progress, errors (human-readable)

This separation allows parent process to parse stdout for questions while showing logs to user.

### Timeout Handling

Default 30-second timeout for stdin reads in pipe mode. Configurable via `DEBUSSY_QA_TIMEOUT` environment variable.
