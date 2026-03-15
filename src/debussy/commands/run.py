"""Run command and all its private helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from debussy.config import get_orchestrator_dir
from debussy.core.models import PhaseStatus
from debussy.core.orchestrator import run_orchestration
from debussy.core.state import StateManager
from debussy.parsers.master import parse_master_plan
from debussy.ui.controller import OrchestrationController

console = Console()

BANNER = r"""

██████╗ ███████╗██████╗ ██╗   ██╗███████╗███████╗██╗   ██╗
██╔══██╗██╔════╝██╔══██╗██║   ██║██╔════╝██╔════╝╚██╗ ██╔╝
██║  ██║█████╗  ██████╔╝██║   ██║███████╗███████╗ ╚████╔╝
██║  ██║██╔══╝  ██╔══██╗██║   ██║╚════██║╚════██║  ╚██╔╝
██████╔╝███████╗██████╔╝╚██████╔╝███████║███████║   ██║
╚═════╝ ╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚══════╝   ╚═╝
"""


def _display_banner(
    plan_name: str,
    phases: list,
    model: str,
    output: str,
    max_retries: int,
    timeout: int,
    interactive: bool = True,
) -> None:
    """Display the startup banner with plan info."""
    # ASCII art
    console.print(Text(BANNER, style="bold cyan"))

    # Info line
    info_left = f"[bold]Plan:[/bold] {plan_name}"
    info_right = f"[bold]Model:[/bold] {model}"
    console.print(f"  {info_left:<40} {info_right}")

    info_left = f"[bold]Phases:[/bold] {len(phases)}"
    info_right = f"[bold]Retries:[/bold] {max_retries}"
    console.print(f"  {info_left:<40} {info_right}")

    info_left = f"[bold]Output:[/bold] {output}"
    info_right = f"[bold]Timeout:[/bold] {timeout // 60}min"
    console.print(f"  {info_left:<40} {info_right}")

    mode_str = "[green]Interactive[/green]" if interactive else "[yellow]YOLO[/yellow]"
    console.print(f"  [bold]Mode:[/bold] {mode_str}")

    # Phase table
    console.print()
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Phase", style="cyan", width=6)
    table.add_column("Title", width=25)
    table.add_column("Status", width=10)
    table.add_column("Dependencies", width=20)

    for phase in phases:
        deps = ", ".join(phase.depends_on) if phase.depends_on else "-"
        status_style = "dim" if phase.status == PhaseStatus.PENDING else "yellow"
        table.add_row(
            phase.id,
            phase.title[:24] + "..." if len(phase.title) > 24 else phase.title,
            f"[{status_style}]{phase.status.value}[/{status_style}]",
            deps,
        )

    console.print(table)
    console.print()
    console.print("[dim]─" * 60 + "[/dim]")
    console.print()


def _get_resumable_run_info(
    master_plan: Path,
) -> tuple[str, set[str]] | None:
    """Get info about a resumable run if one exists.

    Args:
        master_plan: Path to the master plan file

    Returns:
        Tuple of (run_id, completed_phase_ids) or None if no resumable run
    """
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")
    existing = state.find_resumable_run(master_plan)

    if not existing:
        return None

    completed = state.get_completed_phases(existing.id)
    if not completed:
        return None

    return (existing.id, completed)


def _check_resumable_run_noninteractive(
    master_plan: Path,
    resume_run: bool,
) -> set[str] | None:
    """Check for a resumable run and return phases to skip (non-interactive mode).

    Args:
        master_plan: Path to the master plan file
        resume_run: Whether --resume flag was passed

    Returns:
        Set of phase IDs to skip, or None if starting fresh
    """
    if not resume_run:
        return None

    info = _get_resumable_run_info(master_plan)
    if not info:
        return None

    run_id, completed = info
    console.print(f"[cyan]Resuming run {run_id}: skipping {len(completed)} completed phase(s)[/cyan]")
    return completed


def _run_with_tui(
    master_plan_path: Path,
    start_phase: str | None = None,
    skip_phases: set[str] | None = None,
    resumable_run: tuple[str, set[str]] | None = None,
    config: object = None,
) -> None:
    """Run orchestration with Textual TUI.

    The TUI is the main driver and runs orchestration as a worker task.

    Args:
        master_plan_path: Path to the master plan file
        start_phase: Optional phase ID to start from
        skip_phases: Optional set of phase IDs to skip (from --resume flag)
        resumable_run: Optional (run_id, completed_phases) for interactive resume dialog
        config: Optional config overrides
    """
    from debussy.config import Config
    from debussy.core.orchestrator import Orchestrator
    from debussy.ui.tui import DebussyTUI

    if config is None:
        config = Config.load()

    # Create orchestrator (but don't run yet)
    orchestrator = Orchestrator(
        master_plan_path,
        config=config,  # type: ignore[arg-type]
        project_root=Path.cwd(),
    )

    # Create the TUI app with controller and resumable run info
    tui = DebussyTUI(resumable_run=resumable_run)
    controller = OrchestrationController(tui)
    tui.set_controller(controller)

    # Pre-set skip_phases if provided (from --resume flag)
    if skip_phases:
        tui._skip_phases = skip_phases

    # Define the orchestration coroutine that will run as a worker
    async def run_orchestration_task() -> str:
        """Run orchestration and return run_id."""
        # Wire up the TUI as the UI for the orchestrator
        # Use type: ignore since DebussyTUI implements the same interface
        orchestrator.ui = tui  # type: ignore[assignment]  # DebussyTUI implements OrchestratorUI interface
        if orchestrator.config.interactive:
            orchestrator.claude._output_callback = tui.log_message

        # Use skip_phases from TUI (may be set by resume dialog or --resume flag)
        return await orchestrator.run(start_phase=start_phase, skip_phases=tui._skip_phases)

    # Pass the coroutine factory to the TUI and run
    tui._orchestration_coro = run_orchestration_task
    tui.run()


def _dry_run(master_plan: Path) -> None:
    """Perform a dry run - parse and validate without executing."""
    console.print("[bold]Dry Run - Parsing and Validating[/bold]\n")

    try:
        plan = parse_master_plan(master_plan)
        console.print("[green]Master plan parsed successfully[/green]")
        console.print(f"  Name: {plan.name}")
        console.print(f"  Phases: {len(plan.phases)}")

        # Parse each phase
        console.print("\n[bold]Phases:[/bold]")
        table = Table()
        table.add_column("ID")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Dependencies")
        table.add_column("Gates")
        table.add_column("Required Agents")

        from debussy.parsers.phase import parse_phase

        for phase in plan.phases:
            deps = ", ".join(phase.depends_on) if phase.depends_on else "-"
            gates_count = 0
            agents = "-"

            if phase.path.exists():
                detailed = parse_phase(phase.path, phase.id)
                gates_count = len(detailed.gates)
                agents = ", ".join(detailed.required_agents) if detailed.required_agents else "-"

            table.add_row(
                phase.id,
                phase.title,
                phase.status.value,
                deps,
                str(gates_count),
                agents,
            )

        console.print(table)
        console.print("\n[green]Validation passed[/green]")

    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1) from e


def register(app: typer.Typer) -> None:
    """Register the run and resume commands on the given Typer app."""

    @app.command()
    def run(
        master_plan: Annotated[
            Path,
            typer.Argument(
                help="Path to the master plan markdown file",
                exists=True,
                file_okay=True,
                dir_okay=False,
                resolve_path=True,
            ),
        ],
        phase: Annotated[
            str | None,
            typer.Option("--phase", "-p", help="Start from specific phase ID"),
        ] = None,
        resume_run: Annotated[
            bool,
            typer.Option("--resume", "-r", help="Resume previous run, skip completed phases"),
        ] = False,
        restart: Annotated[
            bool,
            typer.Option("--restart", help="Start fresh, ignore previous progress"),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", "-n", help="Parse and validate only, don't execute"),
        ] = False,
        skip_audit: Annotated[
            bool,
            typer.Option("--skip-audit", help="Skip pre-flight audit check"),
        ] = False,
        model: Annotated[
            str,
            typer.Option("--model", "-m", help="Claude model: haiku, sonnet, opus"),
        ] = "opus",
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="Output mode: terminal, file, both"),
        ] = "terminal",
        no_interactive: Annotated[
            bool,
            typer.Option(
                "--no-interactive",
                "--yolo",
                help="YOLO mode: disable interactive dashboard (for CI/automation)",
            ),
        ] = False,
        learnings: Annotated[
            bool,
            typer.Option(
                "--learnings",
                "-L",
                help="Enable LTM learnings: workers save insights via /remember and recall via /recall",
            ),
        ] = False,
        sandbox: Annotated[
            bool | None,
            typer.Option(
                "--sandbox/--no-sandbox",
                help="Run Claude in Docker sandbox (requires Docker Desktop)",
            ),
        ] = None,
        accept_risks: Annotated[
            bool,
            typer.Option(
                "--accept-risks",
                help="Skip security warning when running without sandbox (for CI/scripts)",
            ),
        ] = False,
        auto_commit: Annotated[
            bool | None,
            typer.Option(
                "--auto-commit/--no-auto-commit",
                help="Commit changes at phase boundaries (default: True)",
            ),
        ] = None,
        allow_dirty: Annotated[
            bool,
            typer.Option(
                "--allow-dirty",
                help="Allow starting with uncommitted changes in working directory",
            ),
        ] = False,
        context_threshold: Annotated[
            float | None,
            typer.Option(
                "--context-threshold",
                help="Context usage percentage (0-100) to trigger restart. Set to 100 to disable. Default: 80",
            ),
        ] = None,
        max_restarts: Annotated[
            int | None,
            typer.Option(
                "--max-restarts",
                help="Maximum restart attempts per phase. Set to 0 to disable. Default: 3",
            ),
        ] = None,
        tool_call_threshold: Annotated[
            int | None,
            typer.Option(
                "--tool-call-threshold",
                help="Fallback: restart after N tool calls. Default: 100",
            ),
        ] = None,
        auto_close_issues: Annotated[
            bool,
            typer.Option(
                "--auto-close",
                help="Auto-close linked GitHub issues when plan completes",
            ),
        ] = False,
        dry_run_sync: Annotated[
            bool,
            typer.Option(
                "--dry-run-sync",
                help="Preview GitHub sync operations without executing",
            ),
        ] = False,
    ) -> None:
        """Start orchestrating a master plan."""
        if dry_run:
            _dry_run(master_plan)
            return

        # Pre-flight audit check (unless skipped)
        if not skip_audit:
            from debussy.core.auditor import PlanAuditor

            auditor = PlanAuditor()
            audit_result = auditor.audit(master_plan)

            if not audit_result.passed:
                console.print("[bold red]Plan failed audit. Fix issues before running.[/bold red]")
                console.print(f"  Errors: {audit_result.summary.errors}")
                console.print(f"  Warnings: {audit_result.summary.warnings}")
                console.print()
                console.print("[dim]Run 'debussy audit' for details or --skip-audit to bypass.[/dim]")
                console.print()
                raise typer.Exit(1)

        # Validate mutually exclusive flags
        if resume_run and restart:
            console.print("[red]Cannot use --resume and --restart together[/red]")
            raise typer.Exit(1)

        # Load config from file, then apply CLI overrides
        from debussy.config import Config

        config = Config.load()  # Load from .debussy/config.yaml if exists

        # Apply CLI overrides - only override if explicitly set via CLI flag
        # no_interactive flag: only override config if --no-interactive was passed
        if no_interactive:
            config.interactive = False

        # Model and output: apply CLI overrides to config
        # Note: Since defaults match config.py defaults, only non-default values indicate explicit CLI usage
        config.model = model
        config.output = output  # type: ignore[assignment]
        # In non-interactive mode, force file output (logs are essential for CI/automation)
        if not config.interactive and config.output == "terminal":
            config.output = "file"  # type: ignore[assignment]
        # Only override learnings if explicitly set via CLI flag
        if learnings:
            config.learnings = learnings
        # CLI flag overrides config file for sandbox mode
        if sandbox is not None:
            config.sandbox_mode = "devcontainer" if sandbox else "none"
        # CLI flag overrides config for auto-commit
        if auto_commit is not None:
            config.auto_commit = auto_commit
        # CLI flags override config for context restart settings
        if context_threshold is not None:
            config.context_threshold = context_threshold
        if max_restarts is not None:
            config.max_restarts = max_restarts
        if tool_call_threshold is not None:
            config.tool_call_threshold = tool_call_threshold
        # CLI flags override config for GitHub sync
        if auto_close_issues:
            config.github.auto_close = True
        if dry_run_sync:
            config.github.dry_run = True

        # Security warning for non-sandboxed mode
        if config.sandbox_mode == "none" and not accept_risks:
            if not config.interactive:
                # Non-interactive mode: require --accept-risks flag
                console.print("[bold red]SECURITY WARNING[/bold red]")
                console.print("Running without sandbox gives Claude FULL ACCESS to your system.")
                console.print("Use --sandbox to enable Docker isolation, or --accept-risks to proceed.")
                raise typer.Exit(1)
            else:
                # Interactive mode: show confirmation prompt
                console.print()
                console.print("[bold red]⚠️  SECURITY WARNING[/bold red]")
                console.print()
                console.print("Running without sandbox gives Claude [bold]FULL ACCESS[/bold] to your system:")
                console.print("  • Read/write any file")
                console.print("  • Execute any command")
                console.print("  • Access network resources")
                console.print()
                console.print("[dim]Use --sandbox to run Claude in Docker isolation instead.[/dim]")
                console.print()
                confirm = typer.confirm("Do you want to proceed without sandbox?", default=False)
                if not confirm:
                    console.print("[yellow]Aborted. Use --sandbox for safer execution.[/yellow]")
                    raise typer.Exit(0)

        # Check for dirty working directory (if auto-commit enabled and not --allow-dirty)
        # Note: Untracked files are ignored - only tracked changes trigger the warning
        if config.auto_commit and not allow_dirty:
            from debussy.utils.git import check_working_directory

            is_clean, file_count, modified_files = check_working_directory(Path.cwd())
            if not is_clean:
                console.print()
                console.print("[bold yellow]⚠️  UNCOMMITTED CHANGES[/bold yellow]")
                console.print()
                console.print(f"Found {file_count} modified tracked file(s):")
                for file_path in modified_files:
                    console.print(f"  [dim]•[/dim] {file_path}")
                if file_count > len(modified_files):
                    console.print(f"  [dim]... and {file_count - len(modified_files)} more[/dim]")
                console.print()
                console.print("Auto-commit is enabled, which may commit these changes.")
                console.print()
                console.print("[bold]Options:[/bold]")
                console.print("  1. Commit or stash your changes first")
                console.print("  2. Use --allow-dirty to proceed anyway")
                console.print("  3. Use --no-auto-commit to disable auto-commit")
                console.print()
                if not config.interactive:
                    raise typer.Exit(1)
                confirm = typer.confirm("Proceed with uncommitted changes?", default=False)
                if not confirm:
                    console.print("[yellow]Aborted. Please commit or stash your changes.[/yellow]")
                    raise typer.Exit(0)

        # Parse plan and display banner (skip for TUI - it has its own header)
        plan = parse_master_plan(master_plan)

        try:
            if config.interactive:
                # For TUI mode: get resumable info and let TUI handle the prompt
                resumable_run = None if restart else _get_resumable_run_info(master_plan)
                # If --resume flag, auto-skip without dialog
                skip_phases = None
                if resume_run and resumable_run:
                    skip_phases = resumable_run[1]
                    resumable_run = None  # Don't show dialog if auto-resuming
                _run_with_tui(
                    master_plan,
                    start_phase=phase,
                    skip_phases=skip_phases,
                    resumable_run=resumable_run,
                    config=config,
                )
            else:
                # Non-interactive (YOLO) mode
                _display_banner(
                    plan_name=plan.name,
                    phases=plan.phases,
                    model=config.model,
                    output=config.output,
                    max_retries=config.max_retries,
                    timeout=config.timeout,
                    interactive=config.interactive,
                )
                if phase:
                    console.print(f"[yellow]Starting from phase: {phase}[/yellow]\n")

                # Check for resumable run (--resume flag required in non-interactive)
                skip_phases = None if restart else _check_resumable_run_noninteractive(master_plan, resume_run)
                run_id = run_orchestration(master_plan, start_phase=phase, skip_phases=skip_phases, config=config)
                console.print(f"\nOrchestration completed. Run ID: {run_id}")
                if config.output in ("file", "both"):
                    console.print("[dim]Logs saved to: .debussy/logs/[/dim]")
        except Exception as e:
            console.print(f"\n[bold red]Orchestration failed: {e}[/bold red]")
            raise typer.Exit(1) from e

    @app.command()
    def resume() -> None:
        """Resume a paused orchestration run."""
        orchestrator_dir = get_orchestrator_dir()
        state = StateManager(orchestrator_dir / "state.db")

        current_run = state.get_current_run()
        if current_run is None:
            console.print("[yellow]No paused orchestration run found[/yellow]")
            return

        from debussy.core.models import RunStatus

        if current_run.status != RunStatus.PAUSED:
            msg = f"Run {current_run.id} is not paused (status: {current_run.status.value})"
            console.print(f"[yellow]{msg}[/yellow]")
            return

        console.print(f"[blue]Resuming run {current_run.id}[/blue]")

        # Resume from current phase
        try:
            run_orchestration(
                current_run.master_plan_path,
                start_phase=current_run.current_phase,
            )
        except Exception as e:
            console.print(f"[red]Resume failed: {e}[/red]")
            raise typer.Exit(1) from e
