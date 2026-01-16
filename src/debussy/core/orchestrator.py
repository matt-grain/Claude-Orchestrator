"""Main orchestration logic."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from debussy.config import Config, get_orchestrator_dir
from debussy.core.checkpoint import CheckpointManager
from debussy.core.compliance import ComplianceChecker
from debussy.core.models import (
    ExecutionResult,
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
from debussy.parsers.learnings import extract_learnings
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase
from debussy.runners.claude import ClaudeRunner, TokenStats
from debussy.runners.context_estimator import ContextEstimator
from debussy.runners.gates import GateRunner
from debussy.ui import NonInteractiveUI, OrchestratorUI, TextualUI, UIState, UserAction

if TYPE_CHECKING:
    from debussy.core.models import ComplianceIssue
    from debussy.sync.github_sync import GitHubSyncCoordinator
    from debussy.sync.jira_sync import JiraSynchronizer

logger = logging.getLogger(__name__)


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
            with_ltm=self.config.learnings,
            sandbox_mode=self.config.sandbox_mode,
        )
        self.gates = GateRunner(self.project_root)
        self.checker = ComplianceChecker(self.gates, self.project_root, ltm_enabled=self.config.learnings)

        # Initialize notifier based on config
        if notifier is None:
            self.notifier = self._create_notifier()
        else:
            self.notifier = notifier

        # Initialize checkpoint manager for progress tracking
        self.checkpoint_manager = CheckpointManager(self.project_root)

        # Initialize UI based on config
        self.ui: OrchestratorUI = TextualUI() if self.config.interactive else NonInteractiveUI()

        # Connect UI to ClaudeRunner for log output routing
        self.claude.set_callbacks(
            output=self.ui.log,
            token_stats=self._on_token_stats if self.config.interactive else None,
            agent_change=self._on_agent_change if self.config.interactive else None,
            tool_use=self._on_tool_use,
        )

        # Parse master plan
        self.plan: MasterPlan | None = None

        # GitHub sync coordinator (initialized in load_plan if enabled)
        self._github_sync: GitHubSyncCoordinator | None = None

        # Jira sync coordinator (initialized in run if enabled)
        self._jira_sync: JiraSynchronizer | None = None

    def _on_token_stats(self, stats: TokenStats) -> None:
        """Handle token stats from Claude runner."""
        self.ui.update_token_stats(
            input_tokens=stats.input_tokens,
            output_tokens=stats.output_tokens,
            cost_usd=stats.cost_usd,
            context_tokens=stats.context_tokens,
            context_window=stats.context_window,
        )

    def _on_agent_change(self, agent: str) -> None:
        """Handle agent change from Claude runner."""
        self.ui.set_active_agent(agent)

    def _on_tool_use(self, tool_content: dict) -> None:
        """Handle tool use events from Claude runner.

        Detects /debussy-progress skill invocations and records progress
        to the checkpoint manager.

        Args:
            tool_content: The tool_use content block from Claude's stream
        """
        tool_name = tool_content.get("name", "")
        tool_input = tool_content.get("input", {})

        # Check for Skill tool with debussy-progress skill
        if tool_name == "Skill":
            skill_name = tool_input.get("skill", "")
            if skill_name == "debussy-progress":
                # Extract progress message from args
                args = tool_input.get("args", "")
                if args:
                    self.checkpoint_manager.record_progress(args)
                    logger.debug(f"Checkpoint: recorded progress from skill: {args}")

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

    async def _init_github_sync(self) -> None:
        """Initialize GitHub sync if enabled and plan has linked issues."""
        if not self.config.github.enabled:
            return

        if self.plan is None or not self.plan.github_issues:
            logger.debug("GitHub sync enabled but no issues linked in plan")
            return

        # Get repo from plan or detect from git remote
        repo = self.plan.github_repo
        if not repo:
            repo = self._detect_github_repo()

        if not repo:
            logger.warning("GitHub sync enabled but no repo specified/detected")
            return

        try:
            from debussy.sync.github_sync import GitHubSyncCoordinator

            self._github_sync = GitHubSyncCoordinator(
                repo=repo,
                config=self.config.github,
            )
            await self._github_sync.__aenter__()

            # Initialize from plan metadata
            valid_issues = await self._github_sync.initialize_from_plan(self.plan.github_issues)

            if valid_issues:
                self.ui.log_raw(f"[dim]GitHub sync: {len(valid_issues)} issue(s) linked[/dim]")
            else:
                logger.warning("No valid GitHub issues found from plan metadata")

        except Exception as e:
            logger.warning(f"Failed to initialize GitHub sync: {e}")
            self._github_sync = None

    def _detect_github_repo(self) -> str | None:
        """Detect GitHub repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return None

            url = result.stdout.strip()
            # Parse git@github.com:owner/repo.git or https://github.com/owner/repo.git
            import re

            match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
            if match:
                return f"{match.group(1)}/{match.group(2)}"

        except Exception:
            pass

        return None

    async def _cleanup_github_sync(self) -> None:
        """Clean up GitHub sync coordinator."""
        if self._github_sync:
            await self._github_sync.__aexit__(None, None, None)
            self._github_sync = None

    async def _init_jira_sync(self) -> None:
        """Initialize Jira sync if enabled and plan has linked issues."""
        if not self.config.jira.enabled:
            return

        if not self.config.jira.url:
            logger.warning("Jira sync enabled but no URL configured")
            return

        if self.plan is None or not self.plan.jira_issues:
            logger.debug("Jira sync enabled but no issues linked in plan")
            return

        try:
            from debussy.sync.jira_sync import JiraSynchronizer

            self._jira_sync = JiraSynchronizer(config=self.config.jira)
            await self._jira_sync.__aenter__()

            # Initialize from plan metadata
            valid_issues = await self._jira_sync.initialize_from_plan(self.plan.jira_issues)

            if valid_issues:
                self.ui.log_raw(f"[dim]Jira sync: {len(valid_issues)} issue(s) linked[/dim]")
            else:
                logger.warning("No valid Jira issues found from plan metadata")

        except Exception as e:
            logger.warning(f"Failed to initialize Jira sync: {e}")
            self._jira_sync = None

    async def _cleanup_jira_sync(self) -> None:
        """Clean up Jira sync coordinator."""
        if self._jira_sync:
            await self._jira_sync.__aexit__(None, None, None)
            self._jira_sync = None

    async def run(
        self,
        start_phase: str | None = None,
        skip_phases: set[str] | None = None,
    ) -> str:
        """Run the orchestration.

        Args:
            start_phase: Optional phase ID to start from
            skip_phases: Optional set of phase IDs to skip (already completed)

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

        # Start interactive UI
        self.ui.start(self.plan.name, len(self.plan.phases))

        # Set model name for HUD display
        self.ui.set_model(self.config.model)

        # Initialize GitHub sync if enabled
        await self._init_github_sync()

        # Initialize Jira sync if enabled
        await self._init_jira_sync()

        try:
            # Build effective skip_phases by checking state.db (source of truth)
            # This ensures we skip completed phases even without --resume flag
            effective_skip_phases = set(skip_phases) if skip_phases else set()

            # Check state.db for any completed phases from previous runs of this plan
            existing_run = self.state.find_resumable_run(self.master_plan_path)
            if existing_run:
                db_completed = self.state.get_completed_phases(existing_run.id)
                if db_completed:
                    # Merge with any explicitly passed skip_phases
                    newly_skipped = db_completed - effective_skip_phases
                    if newly_skipped:
                        self.ui.log_raw(f"[dim]Found {len(newly_skipped)} completed phase(s) in state.db[/dim]")
                    effective_skip_phases.update(db_completed)

            phases_to_run = self.plan.phases
            if start_phase:
                # Find starting phase and run from there
                start_idx = next(
                    (i for i, p in enumerate(phases_to_run) if p.id == start_phase),
                    0,
                )
                phases_to_run = phases_to_run[start_idx:]

            for idx, phase in enumerate(phases_to_run, 1):
                # Skip phases that were completed in a previous run (state.db is source of truth)
                if phase.id in effective_skip_phases:
                    self.ui.log_raw(f"[dim]Skipping completed phase {phase.id}: {phase.title}[/dim]")
                    phase.status = PhaseStatus.COMPLETED  # For dependency checks
                    continue

                # Fallback: also skip if markdown status says COMPLETED
                # (for manually edited plans where user marked phases done)
                if phase.status == PhaseStatus.COMPLETED:
                    self.ui.log_raw(f"[dim]Skipping phase {phase.id}: marked completed in plan file[/dim]")
                    continue
                # Check for user actions before each phase
                if await self._handle_user_action(run_id, phase):
                    continue  # Phase was skipped

                if not self._dependencies_met(phase):
                    self.notifier.warning(
                        f"Phase {phase.id} Skipped",
                        "Dependencies not met",
                    )
                    msg = f"[dim]Phase {phase.id} skipped: dependencies not met[/dim]"
                    self.ui.log_raw(msg)
                    continue

                # Update UI for new phase
                self.ui.set_phase(phase, idx)
                self.ui.set_state(UIState.RUNNING)

                self.state.set_current_phase(run_id, phase.id)
                success = await self._execute_phase_with_compliance(run_id, phase)

                if not success:
                    self.state.update_run_status(run_id, RunStatus.FAILED)
                    self.ui.stop()
                    return run_id

            self.state.update_run_status(run_id, RunStatus.COMPLETED)
            self.notifier.success(
                "Orchestration Completed",
                "All phases completed successfully",
            )

            # Record feature completion for re-run protection
            self._record_feature_completion()

            # GitHub sync: auto-close issues if enabled
            if self._github_sync:
                try:
                    await self._github_sync.on_plan_complete()
                except Exception as e:
                    logger.warning(f"GitHub sync plan complete failed: {e}")

            # Jira sync: transition issues on plan complete
            if self._jira_sync:
                try:
                    results = await self._jira_sync.on_plan_complete()
                    for r in results:
                        if r.success:
                            self.ui.log_raw(f"[dim]Jira: {r.message}[/dim]")
                except Exception as e:
                    logger.warning(f"Jira sync plan complete failed: {e}")

        except KeyboardInterrupt:
            self.state.update_run_status(run_id, RunStatus.PAUSED)
            self.notifier.warning("Orchestration Paused", "Interrupted by user")
            self.ui.log_raw("[yellow]Orchestration paused by user[/yellow]")
        except Exception as e:
            self.state.update_run_status(run_id, RunStatus.FAILED)
            self.notifier.error("Orchestration Failed", str(e))
            raise
        finally:
            # Cleanup GitHub sync
            await self._cleanup_github_sync()
            # Cleanup Jira sync
            await self._cleanup_jira_sync()
            self.ui.stop()

        return run_id

    async def _handle_user_action(self, run_id: str, phase: Phase) -> bool:
        """Handle pending user actions.

        Args:
            run_id: Current run ID
            phase: Phase about to execute

        Returns:
            True if the phase should be skipped
        """
        while True:
            action = self.ui.get_pending_action()

            if action == UserAction.NONE:
                return False

            if action == UserAction.STATUS:
                self._show_status_details(run_id, phase)
            elif action == UserAction.PAUSE:
                await self._handle_pause(run_id, phase)
            elif action == UserAction.TOGGLE_VERBOSE:
                self.ui.toggle_verbose()
            elif action == UserAction.SKIP:
                if self.ui.confirm(f"Skip phase {phase.id}?"):
                    self.ui.log_raw(f"[yellow]Skipping phase {phase.id}[/yellow]")
                    return True
            elif action == UserAction.QUIT and self.ui.confirm("Quit orchestration?"):
                self.state.update_run_status(run_id, RunStatus.PAUSED)
                raise KeyboardInterrupt

    async def _handle_pause(self, run_id: str, phase: Phase) -> None:
        """Handle pause action and wait for resume."""
        self.ui.set_state(UIState.PAUSED)
        self.ui.log_raw("[yellow]Paused. Press 'p' to resume.[/yellow]")
        self.state.update_run_status(run_id, RunStatus.PAUSED)

        while True:
            await asyncio.sleep(0.1)
            next_action = self.ui.get_pending_action()
            if next_action == UserAction.RESUME:
                self.ui.set_state(UIState.RUNNING)
                self.ui.log_raw("[green]Resumed.[/green]")
                self.state.update_run_status(run_id, RunStatus.RUNNING)
                return
            if next_action == UserAction.QUIT:
                self.state.update_run_status(run_id, RunStatus.PAUSED)
                raise KeyboardInterrupt
            if next_action == UserAction.STATUS:
                self._show_status_details(run_id, phase)

    def _show_status_details(self, run_id: str, phase: Phase) -> None:
        """Show detailed status information."""
        assert self.plan is not None

        # Calculate completed phases
        completed = sum(1 for p in self.plan.phases if p.status == PhaseStatus.COMPLETED)

        details = {
            "Run ID": run_id,
            "Plan": self.plan.name,
            "Current Phase": f"{phase.id}: {phase.title}",
            "Progress": f"{completed}/{len(self.plan.phases)} phases completed",
            "Gates": ", ".join(g.name for g in phase.gates) if phase.gates else "None",
        }
        self.ui.show_status_popup(details)

    def _record_feature_completion(self) -> None:
        """Record feature completion for re-run protection.

        Extracts linked issues from the plan metadata and stores them
        in the completed_features table for future detection.
        """
        if self.plan is None:
            return

        from debussy.core.models import IssueRef

        # Extract issues from plan metadata
        issues: list[IssueRef] = []

        # GitHub issues
        if self.plan.github_issues:
            if isinstance(self.plan.github_issues, list):
                for issue_num in self.plan.github_issues:
                    issues.append(IssueRef(type="github", id=str(issue_num)))
            elif isinstance(self.plan.github_issues, str):
                # Parse comma-separated format: "#10, #11" or "10, 11"
                import re

                for match in re.findall(r"#?(\d+)", self.plan.github_issues):
                    issues.append(IssueRef(type="github", id=match))

        # Jira issues
        if self.plan.jira_issues:
            if isinstance(self.plan.jira_issues, list):
                for issue_key in self.plan.jira_issues:
                    issues.append(IssueRef(type="jira", id=issue_key))
            elif isinstance(self.plan.jira_issues, str):
                # Parse comma-separated format: "PROJ-123, PROJ-124"
                import re

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
        # GitHub sync: phase failed
        await self._github_sync_phase_failed(phase)
        # Auto-commit at phase boundary (failure - respects commit_on_failure setting)
        self._auto_commit_phase(phase, success=False)
        return False

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
        if not phase.notes_output or not phase.notes_output.exists():
            return

        learnings = extract_learnings(phase.notes_output, phase.id)
        if not learnings:
            return

        import contextlib
        import subprocess

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

    def _auto_commit_phase(self, phase: Phase, success: bool) -> None:
        """Auto-commit changes at phase boundary.

        Args:
            phase: The phase that completed
            success: Whether the phase completed successfully
        """
        # Check if auto-commit is enabled
        if not self.config.auto_commit:
            logger.debug("Auto-commit disabled, skipping commit")
            return

        # Skip commit on failure unless commit_on_failure is enabled
        if not success and not self.config.commit_on_failure:
            logger.debug("Phase failed and commit_on_failure=False, skipping commit")
            return

        # Check for changes using git status
        has_changes = self._git_has_changes()
        if has_changes is None:
            return  # Git error occurred
        if not has_changes:
            logger.debug("No changes to commit, skipping")
            self.ui.log_raw("[dim]No changes to commit[/dim]")
            return

        # Format and execute commit
        self._execute_git_commit(phase, success)

    def _git_has_changes(self) -> bool | None:
        """Check if there are uncommitted changes.

        Returns:
            True if there are changes, False if clean, None on error.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(f"Git status failed: {result.stderr}")
                return None
            return bool(result.stdout.strip())
        except FileNotFoundError:
            logger.warning("Git not found, skipping auto-commit")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("Git status timed out, skipping auto-commit")
            return None

    def _execute_git_commit(self, phase: Phase, success: bool) -> None:
        """Execute git add and commit for a phase.

        Args:
            phase: The phase that completed
            success: Whether the phase completed successfully
        """
        # Format commit message using template
        status_icon = "✓" if success else "⚠️"
        message = self.config.commit_message_template.format(
            phase_id=phase.id,
            phase_name=phase.title,
            status=status_icon,
        )

        # Get model name for Co-Authored-By
        model_name = self.config.model.capitalize()
        co_author = f"Co-Authored-By: Claude {model_name} <noreply@anthropic.com>"

        full_message = f"{message}\n\n{co_author}"

        # Stage all changes and commit
        try:
            # Stage all changes
            add_result = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
                check=False,
            )
            if add_result.returncode != 0:
                logger.warning(f"Git add failed: {add_result.stderr}")
                return

            # Commit with message
            commit_result = subprocess.run(
                ["git", "commit", "-m", full_message],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
                check=False,
            )
            if commit_result.returncode != 0:
                # Check if it's just "nothing to commit"
                if "nothing to commit" in commit_result.stdout.lower():
                    logger.debug("Nothing to commit after staging")
                    return
                logger.warning(f"Git commit failed: {commit_result.stderr}")
                self.ui.log_raw(f"[yellow]Auto-commit failed: {commit_result.stderr.strip()}[/yellow]")
                return

            logger.info(f"Auto-commit successful: {message}")
            self.ui.log_raw(f"[green]Auto-commit: {message}[/green]")

        except FileNotFoundError:
            logger.warning("Git not found, skipping auto-commit")
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out during auto-commit")
            self.ui.log_raw("[yellow]Auto-commit timed out[/yellow]")

    def check_clean_working_directory(self) -> tuple[bool, int, list[str]]:
        """Check if the working directory has uncommitted tracked changes.

        Untracked files are ignored - only modified/staged/deleted tracked files
        are considered "dirty" for the purposes of auto-commit protection.

        Returns:
            Tuple of (is_clean, tracked_change_count, modified_files_sample)
            - is_clean: True if no tracked changes exist
            - tracked_change_count: Number of modified/staged/deleted files
            - modified_files_sample: Up to 10 modified file paths for display
        """
        from debussy.utils.git import check_working_directory

        return check_working_directory(self.project_root)

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
    skip_phases: set[str] | None = None,
    config: Config | None = None,
    project_root: Path | None = None,
) -> str:
    """Convenience function to run orchestration synchronously.

    Args:
        master_plan_path: Path to the master plan file
        start_phase: Optional phase ID to start from
        skip_phases: Optional set of phase IDs to skip (already completed)
        config: Optional configuration
        project_root: Optional project root (defaults to cwd)

    Returns:
        The run ID
    """
    orchestrator = Orchestrator(master_plan_path, config, project_root=project_root)
    orchestrator.load_plan()
    return asyncio.run(orchestrator.run(start_phase, skip_phases))
