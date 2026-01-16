"""Prompts for Claude-powered plan generation from GitHub issues.

This module defines prompt templates for generating Debussy-compliant
implementation plans from analyzed GitHub issues.
"""

from __future__ import annotations

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are an expert software architect creating Debussy implementation plans.

Your role is to transform GitHub issues and user context into well-structured
implementation plans that follow Debussy's phase-based execution model.

Key principles:
1. Plans must be actionable and specific
2. Each phase should be independently deployable when possible
3. Tasks should be granular enough to track progress
4. Gates must include concrete validation commands
5. Risk assessment should inform phase ordering
"""

# =============================================================================
# Master Plan Prompt
# =============================================================================

MASTER_PLAN_PROMPT = """## Source Issues

{formatted_issues}

## User-Provided Context

{qa_answers}

## Template to Follow

{master_template}

## Instructions

Generate a MASTER_PLAN.md following the template structure exactly.

Requirements:
1. Synthesize all issues into a coherent feature/project plan
2. Determine appropriate number of phases based on complexity
3. Each phase in the table MUST link to exactly "phase-N.md" (e.g., phase-1.md, phase-2.md)
   - Use this exact format: `| 1 | [Title](phase-1.md) | Focus | Risk | Status |`
   - Do NOT use prefixes like "feature-name-phase-1.md", just "phase-N.md"
4. Include realistic risk assessment based on the issues
5. Define measurable success metrics
6. List any dependencies between phases

Output the complete MASTER_PLAN.md content only, no additional commentary.
"""

# =============================================================================
# Phase Plan Prompt
# =============================================================================

PHASE_PLAN_PROMPT = """## Master Plan Context

{master_plan_summary}

## Phase {phase_num} Focus

This phase should focus on: {phase_focus}

## Related Issues

{related_issues}

## Template to Follow

{phase_template}

## Instructions

Generate phase-{phase_num}.md following the template structure exactly.

Requirements:
1. Break down the phase focus into specific, checkable tasks
2. Include concrete validation commands in the Gates section
3. Specify files to create/modify with their purposes
4. Define rollback procedures
5. Include notes output path: notes/NOTES_{{feature}}_phase_{phase_num}.md

For Python projects, use these gates:
- ruff: `uv run ruff check .` (0 errors)
- pyright: `uv run pyright src/` (0 errors)
- tests: `uv run pytest tests/ -v` (all pass)

Output the complete phase-{phase_num}.md content only, no additional commentary.
"""

# =============================================================================
# Issue Summary Template
# =============================================================================

ISSUE_SUMMARY_TEMPLATE = """### Issue #{number}: {title}

**Labels:** {labels}
**State:** {state}

{body}

---
"""

# =============================================================================
# Q&A Context Template
# =============================================================================

QA_CONTEXT_TEMPLATE = """### {question}

**Answer:** {answer}

"""

# =============================================================================
# Helper Functions
# =============================================================================


def format_issue_for_prompt(
    number: int,
    title: str,
    body: str,
    labels: list[str],
    state: str,
) -> str:
    """Format a single issue for inclusion in a prompt.

    Args:
        number: Issue number
        title: Issue title
        body: Issue body text
        labels: List of label names
        state: Issue state (OPEN/CLOSED)

    Returns:
        Formatted issue string.
    """
    labels_str = ", ".join(labels) if labels else "none"
    return ISSUE_SUMMARY_TEMPLATE.format(
        number=number,
        title=title,
        labels=labels_str,
        state=state,
        body=body or "(no description)",
    )


def format_qa_for_prompt(answers: dict[str, str]) -> str:
    """Format Q&A answers for inclusion in a prompt.

    Args:
        answers: Dictionary mapping questions to answers.

    Returns:
        Formatted Q&A context string.
    """
    if not answers:
        return "(No additional context provided)"

    parts = []
    for question, answer in answers.items():
        parts.append(
            QA_CONTEXT_TEMPLATE.format(
                question=question,
                answer=answer,
            )
        )
    return "".join(parts)


def build_master_plan_prompt(
    formatted_issues: str,
    qa_answers: str,
    master_template: str,
) -> str:
    """Build the complete prompt for master plan generation.

    Args:
        formatted_issues: Pre-formatted issue summaries
        qa_answers: Pre-formatted Q&A context
        master_template: Master plan template content

    Returns:
        Complete prompt string.
    """
    return MASTER_PLAN_PROMPT.format(
        formatted_issues=formatted_issues,
        qa_answers=qa_answers,
        master_template=master_template,
    )


def build_phase_plan_prompt(
    master_plan_summary: str,
    phase_num: int,
    phase_focus: str,
    related_issues: str,
    phase_template: str,
) -> str:
    """Build the complete prompt for phase plan generation.

    Args:
        master_plan_summary: Brief summary of master plan context
        phase_num: Phase number (1-indexed)
        phase_focus: What this phase should accomplish
        related_issues: Formatted issues relevant to this phase
        phase_template: Phase plan template content

    Returns:
        Complete prompt string.
    """
    return PHASE_PLAN_PROMPT.format(
        master_plan_summary=master_plan_summary,
        phase_num=phase_num,
        phase_focus=phase_focus,
        related_issues=related_issues,
        phase_template=phase_template,
    )
