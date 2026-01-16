# Issue Tracker Enhancements Phase 3: Add subagent existence validation to audit

**Status:** Pending
**Master Plan:** [issue-tracker-enhancements-MASTER_PLAN.md](issue-tracker-enhancements-MASTER_PLAN.md)
**Depends On:** N/A (Independent)
**GitHub Issues:** #19

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_issue_tracker_enhancements_phase_2.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  uv run bandit -r src/
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_issue_tracker_enhancements_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `uv run ruff check .` (0 errors)
- type-check: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)
- security: `uv run bandit -r src/` (no high severity)

---

## Overview

This phase enhances the audit command to validate that custom subagents referenced in plan files actually exist in the `.claude/agents/` directory before execution begins. Currently, missing agents cause runtime failures during orchestration. By catching these errors during the audit phase, we improve developer experience and catch configuration errors early.

## Dependencies
- Previous phase: Independent (can be deployed separately)
- External: None

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Built-in agent list becomes stale | Medium | Low | Document list location clearly, add comment to update when Task tool changes |
| Performance impact from directory scanning | Low | Low | Cache scan results during audit run |
| False positives for valid agent references | Low | Medium | Maintain comprehensive built-in agent list, test edge cases |

---

## Tasks

### 1. Implement Agent Reference Parser
- [ ] 1.1: Add method to extract subagent references from phase files (patterns: `subagent_type: agent-name`, `subagent_type="agent-name"`)
- [ ] 1.2: Create built-in agent list constant (Bash, Explore, Plan, general-purpose, statusline-setup, claude-code-guide, debussy, llm-security-expert, python-task-validator, textual-tui-expert)
- [ ] 1.3: Filter out built-in agents from validation list

### 2. Implement Agent Existence Validator
- [ ] 2.1: Add method to scan `.claude/agents/` directory for agent files
- [ ] 2.2: Cache agent directory scan results during audit run
- [ ] 2.3: Compare referenced agents against discovered agent files
- [ ] 2.4: Generate clear error messages with expected file paths for missing agents

### 3. Integrate into Audit Command
- [ ] 3.1: Add agent validation check to existing audit flow in `src/debussy/core/auditor.py`
- [ ] 3.2: Report missing agents as audit errors with file paths
- [ ] 3.3: Add `--verbose` mode output listing all detected agent references
- [ ] 3.4: Ensure audit passes when all referenced agents exist

### 4. Add Comprehensive Tests
- [ ] 4.1: Test valid custom agents are recognized
- [ ] 4.2: Test missing custom agents are reported as errors
- [ ] 4.3: Test built-in agents are not flagged
- [ ] 4.4: Test plans with no agent references pass
- [ ] 4.5: Test error messages include expected file paths
- [ ] 4.6: Test verbose mode lists detected agents
- [ ] 4.7: Test agent directory caching behavior

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/core/auditor.py` | Modify | Add agent validation logic to audit checks |
| `tests/core/test_auditor_agents.py` | Create | Unit tests for agent validation |
| `tests/fixtures/agent_validation/` | Create | Mock agent files and plans for testing |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Glob pattern matching | `src/debussy/planners/analyzer.py` | Use Glob for `.claude/agents/*.md` discovery |
| Audit error reporting | `src/debussy/core/auditor.py` | Follow existing error message format and severity |
| Temp directory testing | `tests/core/test_auditor.py` | Use pytest tmp_path fixture for mock agent directories |

## Test Strategy

- [ ] Unit tests for agent reference parsing (various pattern formats)
- [ ] Unit tests for agent existence validation (valid, missing, built-in)
- [ ] Integration tests for full audit flow with agent validation
- [ ] Edge case tests (empty plans, malformed references, case sensitivity)
- [ ] Manual testing checklist:
  - [ ] Audit detects missing custom agent and reports file path
  - [ ] Audit passes when all agents exist
  - [ ] Built-in agents are not flagged as missing
  - [ ] Verbose mode shows all detected agent references

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (ruff, pyright, pytest, bandit)
- [ ] Test coverage remains at 60%+ baseline
- [ ] Audit detects missing custom agents with clear error messages
- [ ] Built-in agents are recognized and not flagged
- [ ] `--verbose` mode lists all detected agent references
- [ ] Error messages include expected file path (`.claude/agents/{agent-name}.md`)
- [ ] Documentation updated (if audit command help text needs changes)
- [ ] No security vulnerabilities introduced

## Rollback Plan

If agent validation causes issues:

1. **Immediate rollback**: Revert `src/debussy/core/auditor.py` changes
   ```bash
   git revert <commit-hash>
   ```

2. **Disable validation**: Add `--skip-agent-validation` flag if partial rollback needed

3. **Data safety**: No database migrations or persistent state changes in this phase

4. **Testing**: Run full test suite to verify rollback:
   ```bash
   uv run pytest tests/core/test_auditor.py -v
   ```

---

## Implementation Notes

**Agent Reference Patterns to Detect:**
- YAML-style: `subagent_type: agent-name`
- JSON-style: `subagent_type="agent-name"` or `subagent_type='agent-name'`
- Consider case-insensitive matching for agent names

**Built-in Agents List** (as of 2026-01-16):
- Bash
- general-purpose
- statusline-setup
- Explore
- Plan
- claude-code-guide
- debussy
- llm-security-expert
- python-task-validator
- textual-tui-expert

**Performance Optimization:**
- Cache `.claude/agents/` directory scan once per audit run
- Only scan when custom agents are referenced
- Consider adding audit timing output in verbose mode

**Error Message Format:**
```
ERROR: Missing custom agent 'my-agent'
  Expected file: .claude/agents/my-agent.md
  Referenced in: phase-3.md
```
