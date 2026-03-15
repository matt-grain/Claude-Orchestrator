"""Main orchestration logic."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from debussy.config import Config, get_orchestrator_dir
from debussy.core.checkpoint import CheckpointManager
from debussy.core.completion import CompletionMixin
from debussy.core.compliance import ComplianceChecker
from debussy.core.models import (
    MasterPlan,
    Phase,
    PhaseStatus,
    RunStatus,
)
from debussy.core.phase_runner import PhaseRunnerMixin
from debussy.core.retry_handler import RetryHandlerMixin
from debussy.core.state import StateManager
from debussy.logging import get_orchestrator_logger
from debussy.notifications.base import ConsoleNotifier, Notifier, NullNotifier
from debussy.notifications.desktop import CompositeNotifier, DesktopNotifier
from debussy.notifications.ntfy import NtfyNotifier
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase
from debussy.runners.claude import ClaudeRunner, TokenStats
from debussy.runners.gates import GateRunner
from debussy.ui import NonInteractiveUI, OrchestratorUI, TextualUI, UIState, UserAction

if TYPE_CHECKING:
    from debussy.sync.github_sync import GitHubSyncCoordinator
    from debussy.sync.jira_sync import JiraSynchronizer

logger = logging.getLogger(__name__)


class Orchestrator(PhaseRunnerMixin, RetryHandlerMixin, CompletionMixin):
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

        # Initialize orchestrator event logger
        self._event_logger = get_orchestrator_logger(self.project_root)

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
        import re

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

        # Log configuration and run initialization
        self._event_logger.log_config(
            model=self.config.model,
            sandbox_mode=self.config.sandbox_mode,
            learnings_enabled=self.config.learnings,
            auto_commit=self.config.auto_commit,
            interactive=self.config.interactive,
        )
        self._event_logger.log_run_init(
            run_id=run_id,
            plan_path=str(self.master_plan_path),
            total_phases=len(self.plan.phases),
        )

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
                    self._event_logger.log_phase_skip(phase.id, "already completed in previous run")
                    phase.status = PhaseStatus.COMPLETED  # For dependency checks
                    continue

                # Fallback: also skip if markdown status says COMPLETED
                # (for manually edited plans where user marked phases done)
                if phase.status == PhaseStatus.COMPLETED:
                    self.ui.log_raw(f"[dim]Skipping phase {phase.id}: marked completed in plan file[/dim]")
                    self._event_logger.log_phase_skip(phase.id, "marked completed in plan file")
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
                    self._event_logger.log_phase_skip(phase.id, "dependencies not met")
                    continue

                # Update UI for new phase
                self.ui.set_phase(phase, idx)
                self.ui.set_state(UIState.RUNNING)

                self.state.set_current_phase(run_id, phase.id)
                success = await self._execute_phase_with_compliance(run_id, phase)

                if not success:
                    self.state.update_run_status(run_id, RunStatus.FAILED)
                    completed_count = sum(1 for p in self.plan.phases if p.status == PhaseStatus.COMPLETED)
                    self._event_logger.log_run_complete(
                        run_id=run_id,
                        status="failed",
                        completed_phases=completed_count,
                        total_phases=len(self.plan.phases),
                    )
                    self.ui.stop()
                    return run_id

            self.state.update_run_status(run_id, RunStatus.COMPLETED)
            completed_count = sum(1 for p in self.plan.phases if p.status == PhaseStatus.COMPLETED)
            self._event_logger.log_run_complete(
                run_id=run_id,
                status="completed",
                completed_phases=completed_count,
                total_phases=len(self.plan.phases),
            )
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
        except asyncio.CancelledError:
            # CancelledError is BaseException, not Exception - must catch explicitly
            # This happens when TUI quits, crashes, or connection drops
            self.state.update_run_status(run_id, RunStatus.PAUSED)
            self.notifier.warning("Orchestration Cancelled", "Session terminated")
            self.ui.log_raw("[yellow]Orchestration cancelled[/yellow]")
            raise  # Re-raise so TUI can handle cleanup
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
