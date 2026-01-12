"""Compliance verification for phase executions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from debussy.core.models import (
    ComplianceIssue,
    ComplianceIssueType,
    ComplianceResult,
    GateResult,
    Phase,
    RemediationStrategy,
)

if TYPE_CHECKING:
    from debussy.runners.gates import GateRunner


# Required sections in notes files
REQUIRED_NOTES_SECTIONS = [
    "## Summary",
    "## Key Decisions",
    "## Files Modified",
]


class ComplianceChecker:
    """Verifies that phase executions comply with template requirements."""

    def __init__(self, gate_runner: GateRunner, project_root: Path | None = None) -> None:
        self.gate_runner = gate_runner
        self.project_root = project_root or Path.cwd()

    async def verify_completion(
        self,
        phase: Phase,
        session_log: str,
        completion_report: dict[str, object] | None,
    ) -> ComplianceResult:
        """Verify that a phase execution meets compliance requirements.

        Args:
            phase: The phase that was executed
            session_log: The full session log from Claude
            completion_report: The report submitted via `debussy done`

        Returns:
            ComplianceResult with pass/fail status and any issues found
        """
        issues: list[ComplianceIssue] = []
        verified_steps: list[str] = []
        report: dict[str, object] = completion_report or {}

        # 1. Re-run gates (NEVER trust Claude's claim)
        gate_results = await self._verify_gates(phase)
        for result in gate_results:
            if not result.passed:
                issues.append(
                    ComplianceIssue(
                        type=ComplianceIssueType.GATES_FAILED,
                        severity="critical",
                        details=f"Gate '{result.name}' failed",
                        evidence=result.output[:500] if result.output else None,
                    )
                )

        # 2. Check notes file exists and has required sections
        notes_issues = self._check_notes(phase)
        issues.extend(notes_issues)
        if not notes_issues:
            verified_steps.append("write_notes")

        # 3. Check required agents were invoked
        agents_used = report.get("agents_used", [])
        claimed_agents: list[str] = (
            [str(a) for a in agents_used] if isinstance(agents_used, list) else []
        )
        agent_issues = self._check_agent_invocations(
            session_log,
            phase.required_agents,
            claimed_agents,
        )
        issues.extend(agent_issues)
        if not agent_issues and phase.required_agents:
            verified_steps.append("invoke_required_agents")

        # 4. Check required steps were completed
        steps_completed = report.get("steps_completed", [])
        claimed_steps: list[str] = (
            [str(s) for s in steps_completed] if isinstance(steps_completed, list) else []
        )
        step_issues = self._check_required_steps(
            phase.required_steps,
            claimed_steps,
            session_log,
        )
        issues.extend(step_issues)

        # Determine remediation strategy
        remediation = self._determine_remediation(issues)

        return ComplianceResult(
            passed=len(issues) == 0,
            issues=issues,
            remediation=remediation,
            verified_steps=verified_steps,
            gate_results=gate_results,
        )

    async def _verify_gates(self, phase: Phase) -> list[GateResult]:
        """Re-run all gates to verify they pass."""
        return await self.gate_runner.run_gates(phase)

    def _check_notes(self, phase: Phase) -> list[ComplianceIssue]:
        """Check that notes file exists and has required sections."""
        issues: list[ComplianceIssue] = []

        if phase.notes_output is None:
            return issues  # No notes required

        notes_path = phase.notes_output
        if not notes_path.is_absolute():
            # Resolve relative to project root (where Claude runs)
            notes_path = self.project_root / notes_path

        if not notes_path.exists():
            issues.append(
                ComplianceIssue(
                    type=ComplianceIssueType.NOTES_MISSING,
                    severity="high",
                    details=f"Notes file not found: {notes_path}",
                )
            )
            return issues

        # Check for required sections
        content = notes_path.read_text(encoding="utf-8")
        missing_sections = []

        for section in REQUIRED_NOTES_SECTIONS:
            if section not in content:
                missing_sections.append(section)

        if missing_sections:
            issues.append(
                ComplianceIssue(
                    type=ComplianceIssueType.NOTES_INCOMPLETE,
                    severity="low",
                    details=f"Missing sections: {', '.join(missing_sections)}",
                )
            )

        return issues

    def _check_agent_invocations(
        self,
        session_log: str,
        required_agents: list[str],
        claimed_agents: list[str],
    ) -> list[ComplianceIssue]:
        """Check that required agents were invoked via Task tool."""
        issues: list[ComplianceIssue] = []

        for agent in required_agents:
            # Check if Task tool was called with this agent
            # Look for patterns like: subagent_type="agent-name" or subagent_type: agent-name
            patterns = [
                rf'subagent_type["\s:=]+{re.escape(agent)}',
                rf"Task.*{re.escape(agent)}",
                rf"launching.*{re.escape(agent)}",
            ]

            found_in_log = any(
                re.search(pattern, session_log, re.IGNORECASE | re.DOTALL) for pattern in patterns
            )
            claimed_used = agent in claimed_agents

            if not found_in_log and not claimed_used:
                issues.append(
                    ComplianceIssue(
                        type=ComplianceIssueType.AGENT_SKIPPED,
                        severity="critical",
                        details=f"Required agent '{agent}' was not invoked",
                    )
                )
            elif claimed_used and not found_in_log:
                # Claimed but no evidence - suspicious but not critical
                issues.append(
                    ComplianceIssue(
                        type=ComplianceIssueType.AGENT_SKIPPED,
                        severity="high",
                        details=f"Agent '{agent}' claimed in report but no evidence in session log",
                    )
                )

        return issues

    def _check_required_steps(
        self,
        required_steps: list[str],
        claimed_steps: list[str],
        session_log: str,
    ) -> list[ComplianceIssue]:
        """Check that required steps were completed."""
        issues: list[ComplianceIssue] = []

        # Map step names to log patterns
        step_patterns = {
            "read_previous_notes": [r"Read.*notes", r"previous.*notes"],
            "doc_sync_manager": [r"doc-sync-manager", r"sync.*ACTIVE"],
            "implementation": [r"implement", r"task.*\d+\.\d+"],
            "pre_validation": [r"ruff|pyright|bandit|pytest", r"validation"],
            "task_validator": [r"task-validator", r"validator"],
            "write_notes": [r"Write.*notes", r"NOTES_"],
        }

        for step in required_steps:
            claimed = step in claimed_steps

            # Check for evidence in session log
            patterns = step_patterns.get(step, [step])
            found_in_log = any(
                re.search(pattern, session_log, re.IGNORECASE) for pattern in patterns
            )

            if not claimed and not found_in_log:
                issues.append(
                    ComplianceIssue(
                        type=ComplianceIssueType.STEP_SKIPPED,
                        severity="high",
                        details=f"Required step '{step}' not completed",
                    )
                )

        return issues

    def _determine_remediation(
        self,
        issues: list[ComplianceIssue],
    ) -> RemediationStrategy | None:
        """Determine the remediation strategy based on issues."""
        if not issues:
            return None

        critical_count = sum(1 for i in issues if i.severity == "critical")
        high_count = sum(1 for i in issues if i.severity == "high")

        if critical_count >= 2:
            return RemediationStrategy.FULL_RETRY
        elif critical_count == 1 or high_count >= 2:
            return RemediationStrategy.TARGETED_FIX
        else:
            return RemediationStrategy.WARN_AND_ACCEPT
