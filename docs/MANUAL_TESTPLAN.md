# Manual Test Plan - Claude Orchestrator v0.1.0

**Purpose:** Validate end-to-end orchestration flow before production use.

---

## Prerequisites

```bash
# Ensure package is installed
cd C:\Projects\Claude-Orchestrator
uv pip install -e .

# Verify CLI is available
uv run orchestrate --help
```

---

## Test 1: Dry Run Validation

**Goal:** Verify plan parsing without execution.

### Setup
Create a test project directory:
```bash
mkdir -p /tmp/test-orchestrator
cd /tmp/test-orchestrator
uv add --dev "claude-orchestrator @ file:///C:/Projects/Claude-Orchestrator"
```

### Create Test Master Plan
Create `test-master.md`:
```markdown
# Calculator Feature - Master Plan

**Created:** 2026-01-12
**Status:** Draft

---

## Overview

Add a simple calculator module for testing orchestrator.

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Setup](phase1-setup.md) | Create base files | Low | Pending |
| 2 | [Logic](phase2-logic.md) | Add operations | Low | Pending |

## Dependencies

```
Phase 1 ──► Phase 2
```
```

### Create Phase 1
Create `phase1-setup.md`:
```markdown
# Phase 1: Setup

**Status:** Pending
**Master Plan:** [test-master.md](test-master.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Write notes to: `notes/NOTES_phase_1.md`

## Gates
- echo: must pass

---

## Tasks

### 1. Create Calculator Module
- [ ] 1.1: Create `src/calculator.py` with basic structure
- [ ] 1.2: Create `tests/test_calculator.py` placeholder
```

### Create Phase 2
Create `phase2-logic.md`:
```markdown
# Phase 2: Add Logic

**Status:** Pending
**Master Plan:** [test-master.md](test-master.md)
**Depends On:** [Phase 1](phase1-setup.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Write notes to: `notes/NOTES_phase_2.md`

## Gates
- python: syntax check

---

## Tasks

### 1. Implement Operations
- [ ] 1.1: Add `add()` function
- [ ] 1.2: Add `subtract()` function
```

### Execute Dry Run
```bash
uv run orchestrate run test-master.md --dry-run
```

### Expected Result
- [ ] Plan parsed successfully
- [ ] Shows 2 phases with correct titles
- [ ] Shows dependencies
- [ ] Shows gates count
- [ ] No errors

---

## Test 2: Status Command (Empty State)

**Goal:** Verify status works with no runs.

```bash
uv run orchestrate status
```

### Expected Result
- [ ] Shows "No orchestration run found" or similar
- [ ] No crash

---

## Test 3: History Command (Empty)

**Goal:** Verify history works with no runs.

```bash
uv run orchestrate history
```

### Expected Result
- [ ] Shows "No orchestration runs found" or similar
- [ ] No crash

---

## Test 4: Full Orchestration Run (Happy Path)

**Goal:** Execute a complete orchestration and verify state transitions.

### Setup
Ensure test project from Test 1 exists.

### Execute
```bash
cd /tmp/test-orchestrator
uv run orchestrate run test-master.md
```

### During Execution
The orchestrator will spawn Claude sessions. In each session:
1. Claude should see the phase prompt
2. Claude should complete tasks
3. Claude should call `orchestrate done --phase X --status completed`

### Monitor Progress
In another terminal:
```bash
uv run orchestrate status
```

### Expected Results
- [ ] Phase 1 starts (status: RUNNING)
- [ ] Phase 1 completes (status: COMPLETED)
- [ ] Phase 2 starts (depends on Phase 1)
- [ ] Phase 2 completes
- [ ] Overall run status: COMPLETED
- [ ] State persisted in `.orchestrator/state.db`

---

## Test 5: Status During Run

**Goal:** Verify real-time status monitoring.

While Test 4 is running:
```bash
uv run orchestrate status
```

### Expected Result
- [ ] Shows current run ID
- [ ] Shows current phase
- [ ] Shows phase execution table
- [ ] Updates as phases progress

---

## Test 6: History After Run

**Goal:** Verify run history is recorded.

```bash
uv run orchestrate history
```

### Expected Result
- [ ] Shows completed run
- [ ] Shows plan name
- [ ] Shows duration
- [ ] Shows final status (COMPLETED)

---

## Test 7: Resume Command (No Paused Run)

**Goal:** Verify resume handles no paused runs gracefully.

```bash
uv run orchestrate resume
```

### Expected Result
- [ ] Shows appropriate message
- [ ] No crash

---

## Test 8: Done Command (Manual Signal)

**Goal:** Test completion signaling manually.

### Start a Run
```bash
uv run orchestrate run test-master.md &
```

### Send Manual Done Signal
```bash
uv run orchestrate done --phase 1 --status completed
```

### Expected Result
- [ ] Signal recorded
- [ ] Orchestrator continues to next phase

---

## Test 9: Done with Blocked Status

**Goal:** Test blocked completion signal.

```bash
uv run orchestrate done --phase 1 --status blocked --reason "Missing dependency"
```

### Expected Result
- [ ] Signal recorded with reason
- [ ] Orchestrator handles appropriately

---

## Test 10: Progress Logging

**Goal:** Test progress logging for stuck detection.

```bash
uv run orchestrate progress --phase 1 --step "implementation:started"
uv run orchestrate progress --phase 1 --step "implementation:50%"
```

### Expected Result
- [ ] Progress logged without error
- [ ] Can be used for stuck detection

---

## Test 11: Gate Failure & Retry

**Goal:** Verify retry behavior on gate failure.

### Modify Phase 1 Gates
Edit `phase1-setup.md` to add a failing gate:
```markdown
## Gates
- false: will fail (command: exit 1)
```

### Execute
```bash
uv run orchestrate run test-master.md
```

### Expected Results
- [ ] Phase 1 attempt 1: FAILED (gate failed)
- [ ] Phase 1 attempt 2: retried
- [ ] After max retries: run FAILED
- [ ] Status shows all attempts

---

## Test 12: Compliance Checker - Missing Agent

**Goal:** Verify agent invocation checking.

### Modify Phase to Require Agent
Edit `phase1-setup.md`:
```markdown
## Process Wrapper (MANDATORY)
- [ ] **AGENT:test-validator** - required agent
- [ ] **[IMPLEMENTATION]**
```

### Execute and Skip Agent
Run orchestration, but in the Claude session, don't invoke the agent.

### Expected Result
- [ ] Compliance check detects missing agent
- [ ] Issues logged
- [ ] Remediation strategy applied

---

## Test 13: Database Persistence

**Goal:** Verify state survives restart.

1. Start a run
2. Kill the orchestrator mid-run (Ctrl+C)
3. Check status:
```bash
uv run orchestrate status
```

### Expected Result
- [ ] State preserved
- [ ] Shows last known status
- [ ] Can potentially resume

---

## Test 14: Concurrent Run Prevention

**Goal:** Verify only one run at a time.

1. Start a run:
```bash
uv run orchestrate run test-master.md &
```

2. Try to start another:
```bash
uv run orchestrate run test-master.md
```

### Expected Result
- [ ] Second run rejected or queued
- [ ] Clear error message

---

## Test Summary Checklist

| Test | Description | Status |
|------|-------------|--------|
| 1 | Dry run validation | [ ] |
| 2 | Status (empty) | [ ] |
| 3 | History (empty) | [ ] |
| 4 | Full orchestration | [ ] |
| 5 | Status during run | [ ] |
| 6 | History after run | [ ] |
| 7 | Resume (no paused) | [ ] |
| 8 | Manual done signal | [ ] |
| 9 | Blocked status | [ ] |
| 10 | Progress logging | [ ] |
| 11 | Gate failure & retry | [ ] |
| 12 | Missing agent check | [ ] |
| 13 | Database persistence | [ ] |
| 14 | Concurrent prevention | [ ] |

---

## Notes

- All tests should be run from the test project directory
- State is stored in `.orchestrator/state.db` relative to project root
- Logs can help debug issues
- Clean state between test runs if needed: `rm -rf .orchestrator/`
