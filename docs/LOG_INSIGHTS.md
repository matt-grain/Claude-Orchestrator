# Log Analysis Insights

Insights gathered from analyzing Debussy orchestration logs, to inform future improvements.

---

## Phase 3.2 Run Analysis (run_c216ce7b)

**Date:** 2026-01-14
**Model:** Sonnet
**Outcome:** Worker completed remediation (fixing ty gate) but did NOT implement the actual feature (implementation was already done in a previous run). Max attempts (3) reached.

### Key Observations

#### 1. No End Message / Unclear Termination

**Issue:** The worker completed its remediation work and signaled `debussy done --phase 2`, but the overall run ended with "max attempts reached" notification without clear success indication.

**Root Cause:** The worker thought it was doing the phase implementation, but the implementation was already complete from a previous run. The orchestrator kept retrying because the worker was doing gate fixes, not new implementation.

**Recommendation:**
- Add clearer distinction between "remediation mode" (fixing gate failures) vs "implementation mode" (doing the actual work)
- Add verbose output option to show what the worker accomplished
- Consider detecting when implementation is already complete and skipping to validation

#### 2. Worker Tried to Access sqlite3

**Issue:** Worker attempted to query the state database:
```bash
sqlite3 .debussy/state.db "SELECT phase_number, gate_name..."
```
But `sqlite3` is not installed in the Docker container.

**Error:**
```
/bin/bash: line 1: sqlite3: command not found
```

**Recommendation:**
- Either install `sqlite3` in the sandbox container
- Or provide a `debussy query` command that the worker can use
- Or document that workers should use `debussy status` instead of raw DB queries

#### 3. Worker Modified MASTER_TEMPLATE.md

**Issue:** The worker modified the template file to try to make it audit-compliant:
```
Now let me update the MASTER_TEMPLATE.md to ensure it's audit-compliant.
The main issue is the phases table format needs to be consistent.
[Edit: MASTER_TEMPLATE.md]
```

**Impact:** Template files are source of truth - workers shouldn't modify them without explicit instruction.

**Recommendation:**
- Add template files to a "protected files" list that workers can't modify
- Or make templates read-only in the Docker mount
- Add clear guidance in phase plans: "DO NOT modify templates, only use them"

#### 4. CLI Command Discovery Issues

**Issue:** Worker tried invalid CLI flags:
```bash
uv run debussy status --phase 2  # Error: No such option: --phase
uv run debussy progress 2        # Error: Missing option '--phase' / '-p'
```

**Root Cause:** Worker didn't know the exact CLI syntax.

**Recommendation:**
- Add command examples in phase plans
- Consider adding `--help` output to the worker's context
- Make CLI more forgiving (positional vs named arguments)

#### 5. Type Checker Conflict: ty vs pyright

**Issue:** Worker removed `type: ignore[misc]` comment from `desktop.py:71` because `ty` said it was unused. But `pyright` requires that comment.

**Root Cause:** Different type checkers have different behaviors. `ty` is more lenient, `pyright` is stricter on `plyer.notification.notify` typing.

**Impact:** After worker's fix, `ty` passed but `pyright` failed during the commit hook.

**Recommendation:**
- Run ALL type checkers (ty AND pyright) as gates, not just one
- Document when to use tool-specific ignore comments: `# type: ignore[pyright-code]`
- Consider prioritizing pyright over ty since it's stricter

#### 6. Worker Did Remediation Instead of Implementation

**Issue:** The phase plan was for implementing `plan-init`, but the worker focused entirely on fixing the `ty` gate failure (removing unused type ignore comments).

**Root Cause:** The orchestrator launched the worker in "remediation mode" because the gate was failing, but the worker didn't understand the broader context.

**Recommendation:**
- Improve worker prompt to distinguish between:
  - "Implement these tasks from scratch"
  - "Fix this specific gate failure"
- Add explicit mode indicator in the worker's system prompt
- Track whether implementation tasks are complete vs just gates passing

### Token/Cost Analysis

From the JSONL log:
- Total turns: ~50 assistant messages
- Most turns were reading files and making small edits
- Cache hit rate was high (cache_read_input_tokens >> cache_creation_input_tokens)
- Average turn: ~28k cached tokens read, ~300-700 new tokens created

---

## Recommendations Summary

### High Priority (Phase 4)

1. **Verbose Audit Option** - Add `--verbose` to show detailed issue descriptions and affected files
2. **Type Checker Unification** - Run both `ty` and `pyright` gates, document conflicts
3. **Worker Mode Clarity** - Clear distinction between implementation vs remediation mode

### Medium Priority

4. **Protected Files** - Prevent workers from modifying templates and other source-of-truth files
5. **Better CLI Discovery** - Include `--help` snippets in phase plans or worker context
6. **sqlite3 Alternative** - Either install it in container or provide `debussy query` command

### Low Priority

7. **Implementation Completion Detection** - Detect when feature is already implemented
8. **Clearer Termination Messages** - "Phase completed with remediation" vs "Phase implemented"

---

## Future Log Analysis

When analyzing future runs, look for:
- [ ] Command errors (exit codes, missing tools)
- [ ] File modification outside expected scope
- [ ] Token efficiency (cache hit rates)
- [ ] Worker confusion patterns (wrong CLI flags, wrong files)
- [ ] Gate conflicts between different tools
