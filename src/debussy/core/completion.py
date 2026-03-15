"""Phase completion side-effects: sync, learnings, and feature recording."""
# pyright: reportAttributeAccessIssue=false
# Mixin class — attributes are defined in Orchestrator which inherits this mixin.

from __future__ import annotations

import logging

from debussy.core.models import Phase, PhaseStatus

logger = logging.getLogger(__name__)


class CompletionMixin:
    """Mixin for post-phase completion side-effects.

    Handles GitHub/Jira sync updates, LTM learnings, and feature completion recording.
    Mixed into Orchestrator — all methods have access to full self state.
    """

    async def _github_sync_phase_complete(self, phase: Phase) -> None:
        """Update GitHub sync on phase completion."""
        if not self._github_sync:
            return

        try:
            results = await self._github_sync.on_phase_complete(phase)
            for r in results:
                if r.success:
                    self.ui.log_raw(f"[dim]GitHub: {r.message}[/dim]")

            # Update milestone progress
            assert self.plan is not None
            completed = sum(1 for p in self.plan.phases if p.status == PhaseStatus.COMPLETED)
            result = await self._github_sync.update_milestone_progress(completed, len(self.plan.phases))
            if result and result.success:
                self.ui.log_raw(f"[dim]GitHub: {result.message}[/dim]")

        except Exception as e:
            logger.warning(f"GitHub sync phase complete failed: {e}")

    async def _github_sync_phase_failed(self, phase: Phase) -> None:
        """Update GitHub sync on phase failure."""
        if not self._github_sync:
            return

        try:
            results = await self._github_sync.on_phase_failed(phase)
            for r in results:
                if r.success:
                    self.ui.log_raw(f"[dim]GitHub: {r.message}[/dim]")
        except Exception as e:
            logger.warning(f"GitHub sync phase failed: {e}")

    async def _jira_sync_phase_complete(self, phase: Phase) -> None:
        """Update Jira sync on phase completion."""
        if not self._jira_sync:
            return

        try:
            results = await self._jira_sync.on_phase_complete(phase)
            for r in results:
                if r.success:
                    self.ui.log_raw(f"[dim]Jira: {r.message}[/dim]")
        except Exception as e:
            logger.warning(f"Jira sync phase complete failed: {e}")

    def _save_learnings_to_ltm(self, phase: Phase) -> None:
        """Extract learnings from phase notes and save to LTM."""
        import contextlib
        import subprocess

        from debussy.parsers.learnings import extract_learnings

        if not phase.notes_output or not phase.notes_output.exists():
            return

        learnings = extract_learnings(phase.notes_output, phase.id)
        if not learnings:
            return

        for learning in learnings:
            with contextlib.suppress(subprocess.TimeoutExpired, FileNotFoundError):
                subprocess.run(
                    [
                        "uv",
                        "run",
                        "ltm",
                        "remember",
                        "--kind",
                        "learnings",
                        "--impact",
                        "medium",
                        f"[Phase {phase.id}] {learning.content}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=10,
                )

    def _record_feature_completion(self) -> None:
        """Record feature completion for re-run protection.

        Extracts linked issues from the plan metadata and stores them
        in the completed_features table for future detection.
        """
        import re

        from debussy.core.models import IssueRef

        if self.plan is None:
            return

        # Extract issues from plan metadata
        issues: list[IssueRef] = []

        # GitHub issues
        if self.plan.github_issues:
            if isinstance(self.plan.github_issues, list):
                for issue_num in self.plan.github_issues:
                    issues.append(IssueRef(type="github", id=str(issue_num)))
            elif isinstance(self.plan.github_issues, str):
                # Parse comma-separated format: "#10, #11" or "10, 11"
                for match in re.findall(r"#?(\d+)", self.plan.github_issues):
                    issues.append(IssueRef(type="github", id=match))

        # Jira issues
        if self.plan.jira_issues:
            if isinstance(self.plan.jira_issues, list):
                for issue_key in self.plan.jira_issues:
                    issues.append(IssueRef(type="jira", id=issue_key))
            elif isinstance(self.plan.jira_issues, str):
                # Parse comma-separated format: "PROJ-123, PROJ-124"
                for match in re.findall(r"([A-Z]+-\d+)", self.plan.jira_issues):
                    issues.append(IssueRef(type="jira", id=match))

        # Skip if no issues linked
        if not issues:
            logger.debug("No issues linked in plan - skipping completion recording")
            return

        # Extract feature name from plan
        feature_name = self.plan.name or self.master_plan_path.stem

        # Record completion
        try:
            feature_id = self.state.record_completion(
                name=feature_name,
                issues=issues,
                plan_path=self.master_plan_path,
            )
            logger.info(f"Recorded feature completion: {feature_name} (ID: {feature_id})")
            self.ui.log_raw(f"[dim]Feature recorded: {feature_name} ({len(issues)} issues)[/dim]")
        except Exception as e:
            logger.warning(f"Failed to record feature completion: {e}")
