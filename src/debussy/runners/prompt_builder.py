"""Prompt-building helpers for Claude phase execution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from debussy.core.models import ComplianceIssue, Phase


def _to_posix(p: Path | None) -> str:
    """Convert a path to forward-slash notation (cross-platform safe)."""
    return str(p).replace("\\", "/") if p else ""


def build_phase_prompt(phase: Phase, with_ltm: bool = False) -> str:
    """Build the prompt for a phase execution.

    Args:
        phase: The phase to build a prompt for.
        with_ltm: Whether to include LTM (Long-Term Memory) recall/save steps.

    Returns:
        The fully-formatted prompt string.
    """
    notes_context = ""
    if phase.notes_input and phase.notes_input.exists():
        notes_input_str = _to_posix(phase.notes_input)
        notes_context = f"""
## Previous Phase Notes
Use the Read tool to read context from the previous phase: {notes_input_str}
"""

    required_agents = ""
    if phase.required_agents:
        agents_list = ", ".join(phase.required_agents)
        required_agents = f"""
## Required Agents
You MUST invoke these agents using the Task tool: {agents_list}
"""

    notes_output = ""
    if phase.notes_output:
        notes_output_str = _to_posix(phase.notes_output)
        notes_output = f"""
## Notes Output
Use the Write tool to write notes to: {notes_output_str}
"""

    # LTM context recall for non-first phases
    ltm_recall = ""
    if with_ltm and phase.notes_input:
        ltm_recall = f"""
## Recall Previous Learnings
Run `/recall phase:{phase.id}` to retrieve learnings from previous runs of this phase.
"""

    # LTM learnings section - ADD to Process Wrapper steps
    ltm_learnings = ""
    if with_ltm:
        ltm_learnings = f"""
## ADDITIONAL Process Wrapper Step (LTM Enabled)
**IMPORTANT**: Add this step to the Process Wrapper BEFORE signaling completion:

- [ ] **Output `## Learnings` section in your notes file** with insights from this phase:
  - Errors encountered and how you fixed them
  - Project-specific patterns discovered
  - Gate failures and resolutions
  - Tips for future runs

- [ ] **Save each learning** using `/remember`:
  ```
  /remember --priority MEDIUM --tags phase:{phase.id},agent:Debussy "learning content"
  ```

This step is MANDATORY when LTM is enabled. Do not skip it.
"""

    # Build completion steps - vary based on LTM
    if with_ltm:
        completion_steps = f"""
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path (include `## Learnings` section!)
2. Call `/remember` for each learning you documented
3. Signal completion: `/debussy-done {phase.id}`

**Do NOT signal completion until you have saved your learnings with /remember.**

Fallback (if slash commands unavailable):
- `uv run debussy done --phase {phase.id} --status completed`
"""
    else:
        completion_steps = f"""
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path
2. Signal completion: `/debussy-done {phase.id}`

If you encounter a blocker:
- `/debussy-done {phase.id} blocked "reason for blocker"`

Fallback (if slash commands unavailable):
- `uv run debussy done --phase {phase.id} --status completed`
"""

    phase_path_str = _to_posix(phase.path)

    return f"""Execute the implementation phase defined in the file: {phase_path_str}

**IMPORTANT: Use the Read tool to read this file path. Do NOT try to execute paths as commands.**

Read the phase plan file and follow the Process Wrapper EXACTLY.
{notes_context}{ltm_recall}
{required_agents}
{notes_output}
{ltm_learnings}
{completion_steps}
## Important
- Follow the template Process Wrapper exactly
- Use the Task tool to invoke required agents (don't do their work yourself)
- Run all pre-validation commands until they pass
- The compliance checker will verify your work - be thorough
- **File paths are for reading with the Read tool, not executing with Bash**
- **Slash commands like /debussy-done use the Skill tool, not Bash**
"""


def build_remediation_prompt(phase: Phase, issues: list[ComplianceIssue], with_ltm: bool = False) -> str:
    """Build a remediation prompt for a failed compliance check.

    Args:
        phase: The phase that failed compliance.
        issues: The list of compliance issues found.
        with_ltm: Whether to include LTM recall/save steps.

    Returns:
        The fully-formatted remediation prompt string.
    """
    issues_text = "\n".join(f"- [{issue.severity.upper()}] {issue.type.value}: {issue.details}" for issue in issues)

    notes_output_str = _to_posix(phase.notes_output)
    required_actions: list[str] = []
    for issue in issues:
        if issue.type.value == "agent_skipped":
            agent_name = issue.details.split("'")[1]
            required_actions.append(f"- Invoke the {agent_name} agent using Task tool")
        elif issue.type.value == "notes_missing":
            required_actions.append(f"- Write notes to: {notes_output_str}")
        elif issue.type.value == "notes_incomplete":
            required_actions.append("- Complete all required sections in the notes file")
        elif issue.type.value == "gates_failed":
            required_actions.append(f"- Fix failing gate: {issue.details}")
        elif issue.type.value == "step_skipped":
            required_actions.append(f"- Complete step: {issue.details}")

    default_action = "- Review and fix all issues"
    actions_text = "\n".join(required_actions) if required_actions else default_action

    # LTM recall for remediation context
    ltm_section = ""
    if with_ltm:
        ltm_section = f"""
## Recall Previous Attempts (LTM Enabled)
Use the Skill tool to run: /recall phase:{phase.id}
This may include fixes for similar issues encountered before.
"""

    # LTM learnings for remediation
    ltm_learnings = ""
    if with_ltm:
        ltm_learnings = f"""
## Save Remediation Learnings
After fixing the issues, use the Skill tool to save what you learned:
/remember --priority HIGH --tags phase:{phase.id},agent:Debussy,remediation "description of fix"
High priority ensures this learning persists for future remediation attempts.
"""

    phase_path_str = _to_posix(phase.path)

    return f"""REMEDIATION SESSION for Phase {phase.id}: {phase.title}

The previous attempt FAILED compliance checks.
{ltm_section}
## Issues Found
{issues_text}

## Required Actions
{actions_text}

## Original Phase Plan
Use the Read tool to read: {phase_path_str}
{ltm_learnings}
## When Complete
Use the Skill tool to signal completion: /debussy-done {phase.id}

Fallback: `uv run debussy done --phase {phase.id} --status completed`

IMPORTANT: This is a remediation session. Follow the template EXACTLY.
All required agents MUST be invoked via the Task tool - do not do their work yourself."""
