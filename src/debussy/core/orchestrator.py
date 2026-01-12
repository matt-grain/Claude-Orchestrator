"""Main orchestration logic."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from debussy.config import Config, get_orchestrator_dir
from debussy.core.compliance import ComplianceChecker
from debussy.core.models import (
    MasterPlan,
    Phase,
    PhaseStatus,
    RemediationStrategy,
    RunStatus,
)
from debussy.core.state import StateManager
from debussy.notifications.base import ConsoleNotifier, Notifier, NullNotifier
from debussy.notifications.desktop import CompositeNotifier, DesktopNotifier
from debussy.notifications.ntfy import NtfyNotifier
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase
from debussy.runners.claude import ClaudeRunner
from debussy.runners.gates import GateRunner

if TYPE_CHECKING:
    from debussy.core.models import ComplianceIssue


class Orchestrator:
    """Main orchestrator that coordinates phase execution."""

    def __init__(
        self,
        master_plan_path: Path,
        config: Config | None = None,
        notifier: Notifier | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.master_plan_path = master_plan_path.resolve()
        # Use explicit project_root or default to cwd (not plan's parent)
        # This ensures CLI commands find the same state.db
        self.project_root = (project_root or Path.cwd()).resolve()
        self.config = config or Config.load()

        # Initialize components
        orchestrator_dir = get_orchestrator_dir(self.project_root)
        self.state = StateManager(orchestrator_dir / "state.db")
        self.claude = ClaudeRunner(
            self.project_root,
            self.config.timeout,
            model=self.config.model,
            output_mode=self.config.output,
        )
        self.gates = GateRunner(self.project_root)
        self.checker = ComplianceChecker(self.gates, self.project_root)

        # Initialize notifier based on config
        if notifier is None:
            self.notifier = self._create_notifier()
        else:
            self.notifier = notifier

        # Parse master plan
        self.plan: MasterPlan | None = None

    def _create_notifier(self) -> Notifier:
        """Create notifier based on configuration."""
        if not self.config.notifications.enabled:
            return NullNotifier()

        provider = self.config.notifications.provider
        ntfy_config = self.config.notifications

        if provider == "none":
            return NullNotifier()
        elif provider == "desktop":
            # Use both desktop and console notifications
            return CompositeNotifier(
                [
                    DesktopNotifier(app_name="Debussy"),
                    ConsoleNotifier(),
                ]
            )
        elif provider == "ntfy":
            # Use ntfy + console notifications
            return CompositeNotifier(
                [
                    NtfyNotifier(
                        server=ntfy_config.ntfy_server,
                        topic=ntfy_config.ntfy_topic,
                    ),
                    ConsoleNotifier(),
                ]
            )
        else:
            # Default to console only
            return ConsoleNotifier()

    def load_plan(self) -> MasterPlan:
        """Load and parse the master plan."""
        self.plan = parse_master_plan(self.master_plan_path)

        # Enrich phases with detailed parsing
        for i, phase in enumerate(self.plan.phases):
            if phase.path.exists():
                detailed = parse_phase(phase.path, phase.id)
                # Merge detailed info into phase
                self.plan.phases[i] = Phase(
                    id=phase.id,
                    title=phase.title,
                    path=phase.path,
                    status=phase.status,
                    depends_on=detailed.depends_on or phase.depends_on,
                    gates=detailed.gates,
                    tasks=detailed.tasks,
                    required_agents=detailed.required_agents,
                    required_steps=detailed.required_steps,
                    notes_input=detailed.notes_input,
                    notes_output=detailed.notes_output,
                )

        return self.plan

    async def run(self, start_phase: str | None = None) -> str:
        """Run the orchestration.

        Args:
            start_phase: Optional phase ID to start from

        Returns:
            The run ID
        """
        if self.plan is None:
            self.load_plan()

        assert self.plan is not None

        run_id = self.state.create_run(self.plan)
        self.notifier.info(
            "Orchestration Started",
            f"Run ID: {run_id}, Plan: {self.plan.name}",
        )

        try:
            phases_to_run = self.plan.phases
            if start_phase:
                # Find starting phase and run from there
                start_idx = next(
                    (i for i, p in enumerate(phases_to_run) if p.id == start_phase),
                    0,
                )
                phases_to_run = phases_to_run[start_idx:]

            for phase in phases_to_run:
                if not self._dependencies_met(phase):
                    self.notifier.warning(
                        f"Phase {phase.id} Skipped",
                        "Dependencies not met",
                    )
                    continue

                self.state.set_current_phase(run_id, phase.id)
                success = await self._execute_phase_with_compliance(run_id, phase)

                if not success:
                    self.state.update_run_status(run_id, RunStatus.FAILED)
                    return run_id

            self.state.update_run_status(run_id, RunStatus.COMPLETED)
            self.notifier.success(
                "Orchestration Completed",
                "All phases completed successfully",
            )

        except Exception as e:
            self.state.update_run_status(run_id, RunStatus.FAILED)
            self.notifier.error("Orchestration Failed", str(e))
            raise

        return run_id

    async def _execute_phase_with_compliance(
        self,
        run_id: str,
        phase: Phase,
    ) -> bool:
        """Execute a phase with compliance checking and remediation.

        Returns:
            True if phase completed successfully
        """
        max_attempts = self.config.max_retries + 1
        is_remediation = False
        previous_issues: list[ComplianceIssue] = []

        for attempt in range(1, max_attempts + 1):
            # Create execution record
            self.state.create_phase_execution(run_id, phase.id, attempt)
            self.state.update_phase_status(run_id, phase.id, PhaseStatus.RUNNING)

            self.notifier.info(
                f"Phase {phase.id}: {phase.title}",
                f"Attempt {attempt}/{max_attempts}",
            )

            # Build prompt (normal or remediation)
            if is_remediation:
                prompt = self.claude.build_remediation_prompt(phase, previous_issues)
            else:
                prompt = None  # Use default prompt

            # Spawn Claude worker
            result = await self.claude.execute_phase(phase, prompt, run_id=run_id)

            if not result.success:
                self.state.update_phase_status(
                    run_id,
                    phase.id,
                    PhaseStatus.FAILED,
                    error_message=result.session_log[:500],
                )
                self.notifier.error(
                    f"Phase {phase.id} Execution Failed",
                    f"Exit code: {result.exit_code}",
                )
                return False

            # Get completion signal
            signal = self.state.get_completion_signal(run_id, phase.id)
            report = signal.report if signal else None

            # COMPLIANCE CHECK
            self.state.update_phase_status(run_id, phase.id, PhaseStatus.VALIDATING)
            compliance = await self.checker.verify_completion(
                phase,
                result.session_log,
                report,
            )

            # Record gate results
            exec_id = self.state.get_attempt_count(run_id, phase.id)
            for gate_result in compliance.gate_results:
                self.state.record_gate_result(exec_id, gate_result)

            if compliance.passed:
                self.state.update_phase_status(run_id, phase.id, PhaseStatus.COMPLETED)
                phase.status = (
                    PhaseStatus.COMPLETED
                )  # Update in-memory status for dependency checks
                self.notifier.success(
                    f"Phase {phase.id} Completed",
                    "All compliance checks passed",
                )
                return True

            # Handle non-compliance
            previous_issues = compliance.issues
            issues_summary = ", ".join(i.details for i in compliance.issues[:3])

            match compliance.remediation:
                case RemediationStrategy.WARN_AND_ACCEPT:
                    self.notifier.warning(
                        f"Phase {phase.id} Completed with Warnings",
                        issues_summary,
                    )
                    self.state.update_phase_status(run_id, phase.id, PhaseStatus.COMPLETED)
                    phase.status = PhaseStatus.COMPLETED  # Update in-memory status
                    return True

                case RemediationStrategy.TARGETED_FIX | RemediationStrategy.FULL_RETRY:
                    is_remediation = True
                    self.notifier.warning(
                        f"Phase {phase.id} Compliance Failed",
                        f"Attempt {attempt}/{max_attempts}: {issues_summary}",
                    )
                    # Continue loop with remediation

                case RemediationStrategy.HUMAN_REQUIRED:
                    self.state.update_phase_status(
                        run_id,
                        phase.id,
                        PhaseStatus.AWAITING_HUMAN,
                    )
                    self.notifier.alert(
                        f"Phase {phase.id} Needs Human Intervention",
                        issues_summary,
                    )
                    return False

                case _:
                    # Unknown remediation strategy
                    is_remediation = True

        # Max attempts reached
        self.state.update_phase_status(
            run_id,
            phase.id,
            PhaseStatus.FAILED,
            error_message=f"Failed after {max_attempts} attempts",
        )
        self.notifier.error(
            f"Phase {phase.id} Failed",
            f"Max attempts ({max_attempts}) reached",
        )
        return False

    def _dependencies_met(self, phase: Phase) -> bool:
        """Check if all dependencies are met for a phase."""
        if not phase.depends_on:
            return True

        assert self.plan is not None

        for dep_id in phase.depends_on:
            dep_phase = next(
                (p for p in self.plan.phases if p.id == dep_id),
                None,
            )
            if dep_phase is None:
                continue
            if dep_phase.status != PhaseStatus.COMPLETED:
                return False

        return True


def run_orchestration(
    master_plan_path: Path,
    start_phase: str | None = None,
    config: Config | None = None,
    project_root: Path | None = None,
) -> str:
    """Convenience function to run orchestration synchronously.

    Args:
        master_plan_path: Path to the master plan file
        start_phase: Optional phase ID to start from
        config: Optional configuration
        project_root: Optional project root (defaults to cwd)

    Returns:
        The run ID
    """
    orchestrator = Orchestrator(master_plan_path, config, project_root=project_root)
    orchestrator.load_plan()
    return asyncio.run(orchestrator.run(start_phase))
