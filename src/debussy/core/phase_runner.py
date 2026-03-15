"""Phase execution logic: internal execution loop and compliance-driven retry."""
# pyright: reportAttributeAccessIssue=false
# Mixin class — attributes are defined in Orchestrator which inherits this mixin.

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from debussy.core.models import ExecutionResult, Phase, PhaseStatus, RemediationStrategy

if TYPE_CHECKING:
    from debussy.core.models import ComplianceIssue

logger = logging.getLogger(__name__)


class PhaseRunnerMixin:
    """Mixin for phase execution logic.

    Implements the context-restart inner loop (_execute_phase_internal) and the
    compliance-driven outer retry loop (_execute_phase_with_compliance).
    Mixed into Orchestrator — all methods have access to full self state.
    """

    async def _execute_phase_internal(
        self,
        run_id: str,
        phase: Phase,
        prompt: str | None,
        is_remediation: bool,
    ) -> ExecutionResult:
        """Execute a phase with automatic restart on context limit.

        Implements the smart restart loop that monitors context usage and
        restarts the phase when limits are approached. Uses checkpoint
        context to help Claude continue from where it left off.

        Args:
            run_id: The current run ID
            phase: The phase to execute
            prompt: Custom prompt (for remediation) or None
            is_remediation: Whether this is a remediation attempt

        Returns:
            ExecutionResult from the phase execution
        """
        from debussy.runners.context_estimator import ContextEstimator

        restart_count = 0
        max_restarts = self.config.max_restarts
        effective_prompt = prompt
        restart_context: str | None = None

        # Skip restart logic if disabled (threshold >= 100 or max_restarts == 0)
        # Also skip for remediation runs (they have their own retry logic)
        restart_enabled = self.config.context_threshold < 100.0 and max_restarts > 0 and not is_remediation

        while True:
            # Setup context estimator for this attempt
            if restart_enabled:
                estimator = ContextEstimator(
                    threshold_percent=int(self.config.context_threshold),
                    tool_call_threshold=self.config.tool_call_threshold,
                )

                # Create restart callback that requests graceful stop
                def on_context_limit() -> None:
                    logger.warning("Context limit reached, requesting graceful stop")
                    self.ui.log_raw("[yellow]Context limit approaching - preparing to restart[/yellow]")
                    self.claude.request_stop()

                self.claude.set_context_estimator(estimator)
                self.claude.set_restart_callback(on_context_limit)
            else:
                self.claude.set_context_estimator(None)  # type: ignore[arg-type]
                self.claude.set_restart_callback(None)  # type: ignore[arg-type]

            # Build prompt with optional restart context
            final_prompt = effective_prompt
            if restart_context:
                # Prepend restart context to the prompt
                if effective_prompt:
                    final_prompt = f"{restart_context}\n\n---\n\n{effective_prompt}"
                else:
                    # Build phase prompt and prepend context
                    original_prompt = self.claude._build_phase_prompt(phase, with_ltm=self.config.learnings)
                    final_prompt = f"{restart_context}\n\n---\n\n{original_prompt}"
                logger.info(f"Injecting restart context (attempt {restart_count + 1})")

            # Execute the phase
            result = await self.claude.execute_phase(phase, final_prompt, run_id=run_id)

            # Check if this was a context limit restart
            if result.session_log.startswith("CONTEXT_LIMIT_RESTART") and restart_enabled:
                if restart_count >= max_restarts:
                    # Max restarts exceeded - fail the phase
                    logger.error(f"Max restarts ({max_restarts}) exceeded for phase {phase.id}")
                    self.ui.log_raw(f"[red]Phase {phase.id} failed: max restarts ({max_restarts}) exceeded[/red]")
                    self.notifier.error(
                        f"Phase {phase.id} Failed",
                        f"Max restarts ({max_restarts}) exceeded - phase may be too complex",
                    )
                    # Return a failure result
                    return ExecutionResult(
                        success=False,
                        session_log=f"Max restarts ({max_restarts}) exceeded",
                        exit_code=-3,
                        duration_seconds=0,
                        pid=result.pid,
                    )

                # Prepare for restart
                restart_count += 1
                logger.warning(f"Restarting phase {phase.id} (attempt {restart_count}/{max_restarts})")
                self.ui.log_raw(f"[yellow]Restarting phase (attempt {restart_count}/{max_restarts})...[/yellow]")

                # Auto-commit before restart
                self._auto_commit_phase(phase, success=False)

                # Prepare restart context from checkpoint
                restart_context = self.checkpoint_manager.prepare_restart()

                self.notifier.warning(
                    f"Phase {phase.id} Restarting",
                    f"Context limit reached, attempt {restart_count}/{max_restarts}",
                )

                continue  # Restart the loop

            # Normal completion (success or failure)
            return result

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
        phase_start_time = time.time()

        # Start checkpoint for this phase
        self.checkpoint_manager.start_phase(phase.id, phase.title)

        # GitHub sync: phase start
        if self._github_sync:
            try:
                results = await self._github_sync.on_phase_start(phase)
                for r in results:
                    if r.success:
                        self.ui.log_raw(f"[dim]GitHub: {r.message}[/dim]")
            except Exception as e:
                logger.warning(f"GitHub sync phase start failed: {e}")

        # Jira sync: phase start
        if self._jira_sync:
            try:
                results = await self._jira_sync.on_phase_start(phase)
                for r in results:
                    if r.success:
                        self.ui.log_raw(f"[dim]Jira: {r.message}[/dim]")
            except Exception as e:
                logger.warning(f"Jira sync phase start failed: {e}")

        for attempt in range(1, max_attempts + 1):
            # Create execution record
            self.state.create_phase_execution(run_id, phase.id, attempt)
            self.state.update_phase_status(run_id, phase.id, PhaseStatus.RUNNING)

            # Log phase start
            self._event_logger.log_phase_start(phase.id, phase.title, attempt)

            self.notifier.info(
                f"Phase {phase.id}: {phase.title}",
                f"Attempt {attempt}/{max_attempts}",
            )

            # Build prompt (normal or remediation)
            prompt = self.claude.build_remediation_prompt(phase, previous_issues, with_ltm=self.config.learnings) if is_remediation else None

            # Spawn Claude worker (with restart logic for non-remediation runs)
            result = await self._execute_phase_internal(run_id, phase, prompt, is_remediation)

            if not result.success:
                self.state.update_phase_status(
                    run_id,
                    phase.id,
                    PhaseStatus.FAILED,
                    error_message=result.session_log[:500],
                )
                # Log phase failure
                duration = time.time() - phase_start_time
                self._event_logger.log_phase_stop(phase.id, PhaseStatus.FAILED, duration)
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
                phase.status = PhaseStatus.COMPLETED  # Update in-memory status for dependency checks
                # Log phase completion
                duration = time.time() - phase_start_time
                self._event_logger.log_phase_stop(phase.id, PhaseStatus.COMPLETED, duration)
                self.notifier.success(
                    f"Phase {phase.id} Completed",
                    "All compliance checks passed",
                )
                # GitHub sync: phase complete
                await self._github_sync_phase_complete(phase)
                # Jira sync: phase complete
                await self._jira_sync_phase_complete(phase)
                # Save learnings to LTM if enabled
                if self.config.learnings:
                    self._save_learnings_to_ltm(phase)
                # Auto-commit at phase boundary
                self._auto_commit_phase(phase, success=True)
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
                    # Log phase completion (with warnings)
                    duration = time.time() - phase_start_time
                    self._event_logger.log_phase_stop(phase.id, PhaseStatus.COMPLETED, duration)
                    # GitHub sync: phase complete (even with warnings)
                    await self._github_sync_phase_complete(phase)
                    # Jira sync: phase complete (even with warnings)
                    await self._jira_sync_phase_complete(phase)
                    # Save learnings to LTM if enabled (even with warnings)
                    if self.config.learnings:
                        self._save_learnings_to_ltm(phase)
                    # Auto-commit at phase boundary (success with warnings)
                    self._auto_commit_phase(phase, success=True)
                    return True

                case RemediationStrategy.TARGETED_FIX | RemediationStrategy.FULL_RETRY:
                    is_remediation = True
                    # Log phase rejection with compliance issues
                    self._event_logger.log_phase_rejection(
                        phase.id,
                        "compliance failed",
                        [i.details for i in compliance.issues],
                    )
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
                    # Log phase rejection requiring human intervention
                    duration = time.time() - phase_start_time
                    self._event_logger.log_phase_stop(phase.id, PhaseStatus.AWAITING_HUMAN, duration)
                    self._event_logger.log_phase_rejection(
                        phase.id,
                        "human intervention required",
                        [i.details for i in compliance.issues],
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
        # Log phase failure after max attempts
        duration = time.time() - phase_start_time
        self._event_logger.log_phase_stop(phase.id, PhaseStatus.FAILED, duration)
        self._event_logger.log_phase_rejection(
            phase.id,
            f"max attempts ({max_attempts}) reached",
            [i.details for i in previous_issues] if previous_issues else None,
        )
        self.notifier.error(
            f"Phase {phase.id} Failed",
            f"Max attempts ({max_attempts}) reached",
        )
        # GitHub sync: phase failed
        await self._github_sync_phase_failed(phase)
        # Auto-commit at phase boundary (failure - respects commit_on_failure setting)
        self._auto_commit_phase(phase, success=False)
        return False
