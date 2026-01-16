"""Plan builder for generating Debussy plans from analyzed GitHub issues.

This module provides the PlanBuilder class that generates structured
implementation plans using Claude as the underlying generator.
"""

from __future__ import annotations

import importlib.resources
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from debussy.planners.analyzer import AnalysisReport
    from debussy.planners.models import IssueSet


class PlanBuilder:
    """Generates Debussy-compliant plans from analyzed GitHub issues.

    Uses Claude as the underlying generator with structured prompts that
    include issue content, user answers, and template requirements.
    """

    def __init__(
        self,
        issues: IssueSet,
        analysis: AnalysisReport,
        model: str = "haiku",
        timeout: int = 120,
    ) -> None:
        """Initialize the plan builder.

        Args:
            issues: The set of GitHub issues to generate a plan from.
            analysis: The analysis report with gap detection results.
            model: Claude model to use (haiku recommended for cost).
            timeout: Timeout for Claude CLI calls in seconds.
        """
        self.issues = issues
        self.analysis = analysis
        self.model = model
        self.timeout = timeout
        self._answers: dict[str, str] = {}
        self._master_template: str | None = None
        self._phase_template: str | None = None

    def set_answers(self, answers: dict[str, str]) -> None:
        """Store Q&A responses from the user.

        Args:
            answers: Dictionary mapping questions to user answers.
        """
        self._answers = answers

    def _load_templates(self) -> tuple[str, str]:
        """Load master and phase templates from package resources.

        Templates are loaded from docs/templates/plans/ directory.

        Returns:
            Tuple of (master_template, phase_template) content strings.

        Raises:
            FileNotFoundError: If templates cannot be found.
        """
        if self._master_template is not None and self._phase_template is not None:
            return self._master_template, self._phase_template

        # Try loading from package resources first (for installed package)
        try:
            # Use importlib.resources for package data
            templates_path = Path(__file__).parent.parent.parent.parent / "docs" / "templates" / "plans"

            master_path = templates_path / "MASTER_TEMPLATE.md"
            phase_path = templates_path / "PHASE_GENERIC.md"

            if master_path.exists() and phase_path.exists():
                self._master_template = master_path.read_text(encoding="utf-8")
                self._phase_template = phase_path.read_text(encoding="utf-8")
                return self._master_template, self._phase_template

        except Exception:
            pass

        # Fallback to importlib.resources
        try:
            with importlib.resources.files("debussy").joinpath("resources/templates/MASTER_TEMPLATE.md").open() as f:
                self._master_template = f.read()
            with importlib.resources.files("debussy").joinpath("resources/templates/PHASE_GENERIC.md").open() as f:
                self._phase_template = f.read()
            return self._master_template, self._phase_template
        except Exception:
            pass

        msg = "Could not load plan templates. Ensure templates exist in docs/templates/plans/"
        raise FileNotFoundError(msg)

    def _build_master_prompt(self) -> str:
        """Build the prompt for master plan generation.

        Combines issues, answers, and template into a complete prompt.

        Returns:
            Complete prompt string for Claude.
        """
        from debussy.planners.prompts import (
            SYSTEM_PROMPT,
            build_master_plan_prompt,
            format_issue_for_prompt,
            format_qa_for_prompt,
        )

        # Format all issues
        formatted_issues = ""
        for issue in self.issues.issues:
            formatted_issues += format_issue_for_prompt(
                number=issue.number,
                title=issue.title,
                body=issue.body,
                labels=issue.label_names,
                state=issue.state,
            )

        # Format Q&A answers
        qa_context = format_qa_for_prompt(self._answers)

        # Load templates
        master_template, _ = self._load_templates()

        # Build the user prompt
        user_prompt = build_master_plan_prompt(
            formatted_issues=formatted_issues,
            qa_answers=qa_context,
            master_template=master_template,
        )

        return f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    def _build_phase_prompt(self, phase_num: int, phase_focus: str) -> str:
        """Build the prompt for a single phase plan generation.

        Args:
            phase_num: Phase number (1-indexed).
            phase_focus: Brief description of what this phase should accomplish.

        Returns:
            Complete prompt string for Claude.
        """
        from debussy.planners.prompts import (
            SYSTEM_PROMPT,
            build_phase_plan_prompt,
            format_issue_for_prompt,
        )

        # Format relevant issues (for now, include all)
        related_issues = ""
        for issue in self.issues.issues:
            related_issues += format_issue_for_prompt(
                number=issue.number,
                title=issue.title,
                body=issue.body,
                labels=issue.label_names,
                state=issue.state,
            )

        # Load templates
        _, phase_template = self._load_templates()

        # Build a brief master plan summary
        master_summary = f"Feature plan with {len(self.issues)} source issues, {self._estimate_phase_count()} phases total."

        # Build the user prompt
        user_prompt = build_phase_plan_prompt(
            master_plan_summary=master_summary,
            phase_num=phase_num,
            phase_focus=phase_focus,
            related_issues=related_issues,
            phase_template=phase_template,
        )

        return f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    def _run_claude(self, prompt: str) -> str:
        """Run Claude CLI with the given prompt.

        Uses stdin to pass the prompt to avoid command-line length limits.

        Args:
            prompt: Prompt to send to Claude.

        Returns:
            Claude's output text.

        Raises:
            subprocess.TimeoutExpired: If Claude times out.
            FileNotFoundError: If Claude CLI is not installed.
        """
        result = subprocess.run(
            [
                "claude",
                "--print",
                "-p",
                "-",
                "--model",
                self.model,
                "--system-prompt",
                "You are a plan generation assistant. Output only the requested markdown content. No additional commentary.",
                "--no-session-persistence",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        return result.stdout

    def generate_master_plan(self) -> str:
        """Generate the master plan document using Claude.

        Returns:
            Generated master plan markdown content.

        Raises:
            subprocess.TimeoutExpired: If Claude times out.
            FileNotFoundError: If Claude CLI is not installed.
        """
        prompt = self._build_master_prompt()
        return self._run_claude(prompt)

    def generate_phase_plan(self, phase_num: int, phase_focus: str = "") -> str:
        """Generate a single phase plan document using Claude.

        Args:
            phase_num: Phase number (1-indexed).
            phase_focus: Optional description of phase focus.

        Returns:
            Generated phase plan markdown content.

        Raises:
            subprocess.TimeoutExpired: If Claude times out.
            FileNotFoundError: If Claude CLI is not installed.
        """
        if not phase_focus:
            phase_focus = f"Phase {phase_num} implementation"

        prompt = self._build_phase_prompt(phase_num, phase_focus)
        return self._run_claude(prompt)

    def generate_all(self) -> dict[str, str]:
        """Generate all plan files (master + phases).

        Returns:
            Dictionary mapping filenames to content.
            Keys include "MASTER_PLAN.md" and "phase-N.md" files.

        Raises:
            subprocess.TimeoutExpired: If Claude times out.
            FileNotFoundError: If Claude CLI is not installed.
        """
        files: dict[str, str] = {}

        # Generate master plan first
        master_content = self.generate_master_plan()
        files["MASTER_PLAN.md"] = master_content

        # Extract phase focuses from master plan if possible
        phase_focuses = self._extract_phase_focuses(master_content)

        # Generate each phase - use actual phase count from MASTER_PLAN, not estimate
        # This ensures we generate files for all phases referenced in the plan
        phase_count = len(phase_focuses) if phase_focuses else self._estimate_phase_count()
        for i in range(1, phase_count + 1):
            focus = phase_focuses.get(i, f"Phase {i} implementation")
            phase_content = self.generate_phase_plan(i, focus)
            files[f"phase-{i}.md"] = phase_content

        return files

    def _estimate_phase_count(self) -> int:
        """Estimate appropriate number of phases based on issue complexity.

        Heuristic:
        - 1-2 issues: 2-3 phases (small feature)
        - 3-5 issues: 3-4 phases (medium feature)
        - 6+ issues: 4-5 phases (large feature)

        Returns:
            Estimated number of phases.
        """
        issue_count = len(self.issues.issues)

        if issue_count <= 2:
            # Small feature: 2-3 phases
            return 3 if self.analysis.critical_gaps > 0 else 2
        elif issue_count <= 5:
            # Medium feature: 3-4 phases
            return 4 if self.analysis.critical_gaps > 2 else 3
        else:
            # Large feature: 4-5 phases
            return 5 if self.analysis.critical_gaps > 3 else 4

    def _extract_phase_focuses(self, master_content: str) -> dict[int, str]:
        """Extract phase focuses from a generated master plan.

        Parses the phases table to extract focus descriptions.

        Args:
            master_content: Generated master plan content.

        Returns:
            Dictionary mapping phase numbers to focus descriptions.
        """
        focuses: dict[int, str] = {}

        # Look for phase table rows like:
        # | 1 | [Title](phase-1.md) | Focus description | Risk | Status |
        pattern = r"\|\s*(\d+)\s*\|[^|]+\|([^|]+)\|"

        for match in re.finditer(pattern, master_content):
            phase_num = int(match.group(1))
            focus = match.group(2).strip()
            focuses[phase_num] = focus

        return focuses
