"""CLI interface for the debussy."""

from __future__ import annotations

# Force unbuffered output for Windows terminal compatibility
import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"
# Also force stdout/stderr to flush immediately
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[union-attr]

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from debussy.config import get_orchestrator_dir
from debussy.core.models import CompletionSignal, PhaseStatus, RunStatus
from debussy.core.orchestrator import run_orchestration
from debussy.core.state import StateManager
from debussy.parsers.master import parse_master_plan
from debussy.ui.controller import OrchestrationController

__version__ = "0.1.1"

app = typer.Typer(
    name="debussy",
    help="Orchestrate multi-phase Claude CLI sessions with compliance verification.",
    no_args_is_help=True,
)
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
    ] = "haiku",
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

    interactive = not no_interactive
    config = Config.load()  # Load from .debussy/config.yaml if exists
    # Apply CLI overrides (only model, output, interactive are typically overridden)
    config.model = model  # type: ignore[assignment]
    config.output = output  # type: ignore[assignment]
    config.interactive = interactive
    # Only override learnings if explicitly set via CLI flag
    if learnings:
        config.learnings = learnings
    # CLI flag overrides config file for sandbox mode
    if sandbox is not None:
        config.sandbox_mode = "devcontainer" if sandbox else "none"

    # Security warning for non-sandboxed mode
    if config.sandbox_mode == "none" and not accept_risks:
        if not interactive:
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

    # Parse plan and display banner (skip for TUI - it has its own header)
    plan = parse_master_plan(master_plan)

    try:
        if interactive:
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
                model=model,
                output=output,
                max_retries=config.max_retries,
                timeout=config.timeout,
                interactive=interactive,
            )
            if phase:
                console.print(f"[yellow]Starting from phase: {phase}[/yellow]\n")

            # Check for resumable run (--resume flag required in non-interactive)
            skip_phases = None if restart else _check_resumable_run_noninteractive(master_plan, resume_run)
            run_id = run_orchestration(master_plan, start_phase=phase, skip_phases=skip_phases, config=config)
            console.print(f"\nOrchestration completed. Run ID: {run_id}")
            if output in ("file", "both"):
                console.print("[dim]Logs saved to: .debussy/logs/[/dim]")
    except Exception as e:
        console.print(f"\n[bold red]Orchestration failed: {e}[/bold red]")
        raise typer.Exit(1) from e


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
        orchestrator.ui = tui  # type: ignore[assignment]
        if orchestrator.config.interactive:
            orchestrator.claude._output_callback = tui.log_message

        # Use skip_phases from TUI (may be set by resume dialog or --resume flag)
        return await orchestrator.run(start_phase=start_phase, skip_phases=tui._skip_phases)

    # Pass the coroutine factory to the TUI and run
    tui._orchestration_coro = run_orchestration_task
    tui.run()


@app.command()
def audit(
    plan_path: Annotated[
        Path,
        typer.Argument(
            help="Path to master plan",
            exists=True,
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Fail on warnings too"),
    ] = False,
) -> None:
    """Validate plan structure before running."""
    from debussy.core.auditor import PlanAuditor

    console.print(f"\n[bold]Auditing:[/bold] {plan_path.name}\n")

    auditor = PlanAuditor()
    result = auditor.audit(plan_path)

    # Display summary
    console.print(f"[bold]{result.summary.master_plan}[/bold]")
    console.print(f"  Phases found: {result.summary.phases_found}")
    console.print(f"  Phases valid: {result.summary.phases_valid}")
    console.print(f"  Total gates: {result.summary.gates_total}")
    console.print()

    # Display issues grouped by severity
    from debussy.core.audit import AuditSeverity

    errors = [i for i in result.issues if i.severity == AuditSeverity.ERROR]
    warnings = [i for i in result.issues if i.severity == AuditSeverity.WARNING]
    infos = [i for i in result.issues if i.severity == AuditSeverity.INFO]

    if errors:
        console.print("[bold red]Errors:[/bold red]")
        for issue in errors:
            location = f" ({issue.location})" if issue.location else ""
            console.print(f"  [red]✗[/red] {issue.message}{location}")
        console.print()

    if warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for issue in warnings:
            location = f" ({issue.location})" if issue.location else ""
            console.print(f"  [yellow]⚠[/yellow] {issue.message}{location}")
        console.print()

    if infos:
        console.print("[bold cyan]Info:[/bold cyan]")
        for issue in infos:
            location = f" ({issue.location})" if issue.location else ""
            console.print(f"  [cyan]i[/cyan] {issue.message}{location}")
        console.print()

    # Summary
    err_count = result.summary.errors
    warn_count = result.summary.warnings
    console.print(f"[bold]Summary:[/bold] {err_count} error(s), {warn_count} warning(s)")

    if result.passed:
        console.print("[bold green]Result: PASS ✓[/bold green]\n")
    else:
        console.print("[bold red]Result: FAIL ✗[/bold red]")
        console.print("[dim]Run `debussy convert` to fix issues or edit manually.[/dim]\n")
        raise typer.Exit(1)

    # In strict mode, fail on warnings too
    if strict and result.summary.warnings > 0:
        console.print("[yellow]Strict mode: Failing due to warnings[/yellow]\n")
        raise typer.Exit(1)


@app.command()
def done(
    phase: Annotated[
        str,
        typer.Option("--phase", "-p", help="Phase ID that completed"),
    ],
    status: Annotated[
        str,
        typer.Option("--status", "-s", help="Completion status: completed, blocked, failed"),
    ] = "completed",
    reason: Annotated[
        str | None,
        typer.Option("--reason", "-r", help="Reason for blocked/failed status"),
    ] = None,
    report: Annotated[
        str | None,
        typer.Option("--report", help="JSON completion report"),
    ] = None,
) -> None:
    """Signal phase completion (called by Claude worker)."""
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")

    # Get current run
    current_run = state.get_current_run()
    if current_run is None:
        console.print("[red]No active orchestration run found[/red]")
        raise typer.Exit(1)

    # Parse report if provided
    report_dict = None
    if report:
        try:
            report_dict = json.loads(report)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON report: {e}[/red]")
            raise typer.Exit(1) from e

    # Record completion signal
    signal = CompletionSignal(
        phase_id=phase,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        report=report_dict,
        signaled_at=datetime.now(),
    )
    state.record_completion_signal(current_run.id, signal)

    console.print(f"[green]Completion signal recorded for phase {phase}[/green]")
    console.print(f"  Status: {status}")
    if reason:
        console.print(f"  Reason: {reason}")


@app.command()
def progress(
    phase: Annotated[
        str,
        typer.Option("--phase", "-p", help="Phase ID"),
    ],
    step: Annotated[
        str,
        typer.Option("--step", "-s", help="Step name (e.g., 'implementation:started')"),
    ],
) -> None:
    """Log progress during execution (for stuck detection)."""
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")

    current_run = state.get_current_run()
    if current_run is None:
        console.print("[red]No active orchestration run found[/red]")
        raise typer.Exit(1)

    state.log_progress(current_run.id, phase, step)
    console.print(f"[dim]Progress logged: {phase} - {step}[/dim]")


@app.command()
def status(
    run_id: Annotated[
        str | None,
        typer.Option("--run", "-r", help="Specific run ID to check"),
    ] = None,
) -> None:
    """Show current orchestration status."""
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")

    run_state = state.get_run(run_id) if run_id else state.get_current_run()

    if run_state is None:
        console.print("[yellow]No orchestration run found[/yellow]")
        return

    # Run info
    status_colors = {
        RunStatus.RUNNING: "blue",
        RunStatus.COMPLETED: "green",
        RunStatus.FAILED: "red",
        RunStatus.PAUSED: "yellow",
    }
    color = status_colors.get(run_state.status, "white")

    console.print(f"\n[bold]Run {run_state.id}[/bold]")
    console.print(f"  Status: [{color}]{run_state.status.value}[/{color}]")
    console.print(f"  Plan: {run_state.master_plan_path.name}")
    console.print(f"  Started: {run_state.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if run_state.completed_at:
        console.print(f"  Completed: {run_state.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if run_state.current_phase:
        console.print(f"  Current Phase: {run_state.current_phase}")

    # Phase executions table
    if run_state.phase_executions:
        console.print("\n[bold]Phase Executions[/bold]")
        table = Table()
        table.add_column("Phase")
        table.add_column("Attempt")
        table.add_column("Status")
        table.add_column("Duration")

        phase_colors = {
            PhaseStatus.PENDING: "dim",
            PhaseStatus.RUNNING: "blue",
            PhaseStatus.VALIDATING: "cyan",
            PhaseStatus.COMPLETED: "green",
            PhaseStatus.FAILED: "red",
            PhaseStatus.BLOCKED: "yellow",
            PhaseStatus.AWAITING_HUMAN: "magenta",
        }

        for exec in run_state.phase_executions:
            p_color = phase_colors.get(exec.status, "white")
            duration = ""
            if exec.started_at and exec.completed_at:
                delta = exec.completed_at - exec.started_at
                duration = f"{delta.total_seconds():.1f}s"

            table.add_row(
                exec.phase_id,
                str(exec.attempt),
                f"[{p_color}]{exec.status.value}[/{p_color}]",
                duration,
            )

        console.print(table)


@app.command()
def resume() -> None:
    """Resume a paused orchestration run."""
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")

    current_run = state.get_current_run()
    if current_run is None:
        console.print("[yellow]No paused orchestration run found[/yellow]")
        return

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


@app.command()
def history(
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Number of runs to show"),
    ] = 10,
) -> None:
    """List past orchestration runs."""
    orchestrator_dir = get_orchestrator_dir()
    state = StateManager(orchestrator_dir / "state.db")

    runs = state.list_runs(limit)
    if not runs:
        console.print("[yellow]No orchestration runs found[/yellow]")
        return

    table = Table(title="Orchestration History")
    table.add_column("Run ID")
    table.add_column("Plan")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Duration")

    status_colors = {
        RunStatus.RUNNING: "blue",
        RunStatus.COMPLETED: "green",
        RunStatus.FAILED: "red",
        RunStatus.PAUSED: "yellow",
    }

    for run in runs:
        color = status_colors.get(run.status, "white")
        duration = ""
        if run.completed_at:
            delta = run.completed_at - run.started_at
            duration = f"{delta.total_seconds():.0f}s"

        table.add_row(
            run.id,
            run.master_plan_path.name,
            f"[{color}]{run.status.value}[/{color}]",
            run.started_at.strftime("%Y-%m-%d %H:%M"),
            duration,
        )

    console.print(table)


def _check_ltm_available() -> bool:
    """Check if LTM is installed."""
    try:
        import ltm  # noqa: F401

        return True
    except ImportError:
        return False


def _copy_resource_file(
    src: Path,
    dst: Path,
    force: bool,
    file_type: str,
    inline_writer: Callable[[Path], None] | None = None,
) -> None:
    """Copy a resource file to destination, with fallback to inline writer."""
    import shutil

    if dst.exists() and not force:
        console.print(f"[yellow]{file_type} exists (skipped): {dst.name}[/yellow]")
        return

    if src.exists():
        shutil.copy(src, dst)
        console.print(f"[green]Installed {file_type}: {dst.name}[/green]")
    elif inline_writer:
        inline_writer(dst)
        console.print(f"[green]Created {file_type}: {dst.name}[/green]")


def _copy_command_files(
    resources_dir: Path,
    commands_dir: Path,
    command_names: list[str],
    force: bool,
    inline_writer: Callable[[Path, str], None],
    prefix: str = "",
) -> None:
    """Copy command files to target directory."""
    import shutil

    for cmd_name in command_names:
        cmd_src = resources_dir / "commands" / f"{cmd_name}.md"
        cmd_dst = commands_dir / f"{cmd_name}.md"

        if cmd_dst.exists() and not force:
            console.print(f"[yellow]Command exists (skipped): {cmd_name}[/yellow]")
            continue

        if cmd_src.exists():
            shutil.copy(cmd_src, cmd_dst)
            console.print(f"[green]Installed {prefix}command: /{cmd_name}[/green]")
        else:
            inline_writer(cmd_dst, cmd_name)
            console.print(f"[green]Created {prefix}command: /{cmd_name}[/green]")


@app.command()
def init(
    target: Annotated[
        Path,
        typer.Argument(
            help="Path to the target project to initialize",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path(),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing files"),
    ] = False,
    with_ltm: Annotated[
        bool,
        typer.Option("--with-ltm", help="Include LTM commands for memory support"),
    ] = False,
) -> None:
    """Initialize a target project for Debussy orchestration.

    Sets up .claude/agents/debussy.md, .claude/skills/debussy.md, and
    .claude/commands/debussy-*.md files for the spawned Claude agent.

    Use --with-ltm to also install LTM memory commands (/remember, /recall).
    """
    # Check LTM availability if requested
    if with_ltm and not _check_ltm_available():
        console.print("[yellow]LTM not installed.[/yellow]")
        console.print("Install with: pip install 'claude-debussy[ltm]'")
        console.print("Continuing without LTM support...")
        with_ltm = False

    # Create .claude directory structure
    claude_dir = target / ".claude"
    if not claude_dir.exists():
        claude_dir.mkdir()
        console.print(f"[green]Created {claude_dir}[/green]")

    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir(exist_ok=True)
    commands_dir = claude_dir / "commands"
    commands_dir.mkdir(exist_ok=True)

    resources_dir = Path(__file__).parent.parent.parent / "resources"

    # Copy agent, skill, and command files
    _copy_resource_file(
        resources_dir / "agents" / "debussy.md",
        agents_dir / "debussy.md",
        force,
        "agent",
        _write_agent_inline,
    )
    _copy_resource_file(
        resources_dir / "skills" / "debussy.md",
        skills_dir / "debussy.md",
        force,
        "skill",
        _write_skill_inline,
    )
    _copy_command_files(
        resources_dir,
        commands_dir,
        ["debussy-done", "debussy-progress", "debussy-status"],
        force,
        _write_command_inline,
    )

    # Copy LTM commands if requested
    if with_ltm:
        _copy_command_files(
            resources_dir,
            commands_dir,
            ["please-remember", "recall"],
            force,
            _write_ltm_command_inline,
            prefix="LTM ",
        )

    # Create config with learnings enabled if --with-ltm
    if with_ltm:
        from debussy.config import Config

        debussy_dir = target / ".debussy"
        debussy_dir.mkdir(exist_ok=True)
        config = Config(learnings=True)
        config_path = debussy_dir / "config.yaml"
        config.save(config_path)
        console.print(f"[green]Created {config_path} with learnings enabled[/green]")

    console.print("\n[bold]Setup complete![/bold]")
    if with_ltm:
        console.print("Debussy agent has access to orchestration + memory commands.")
    else:
        console.print("Debussy agent has access to orchestration commands.")
        console.print("[dim]Tip: Use --with-ltm to enable cross-phase memory.[/dim]")


def _write_agent_inline(path: Path) -> None:
    """Write the debussy agent file inline (fallback when resource not found)."""
    content = """# Debussy - Orchestration Worker Agent

You are Debussy, a focused orchestration worker agent.

## Identity

- **Name**: Debussy
- **Role**: Phase execution worker for the Debussy orchestrator
- **Personality**: Focused, methodical, task-oriented

## Your Mission

Execute implementation phases methodically:
1. Read and follow the phase plan file exactly
2. Invoke required agents via the Task tool
3. Run validation gates until they pass
4. Document your work in the notes output file
5. Signal completion with `/debussy-done`

## Important Rules

- Follow the Process Wrapper template exactly
- Use agents via Task tool - don't do their work yourself
- Run all gates before signaling completion
- Be thorough - the compliance checker will verify your work
"""
    path.write_text(content)


def _write_skill_inline(path: Path) -> None:
    """Write the debussy skill file inline (fallback when resource not found)."""
    content = """# Debussy Orchestrator Commands

This skill provides commands for interacting with the Debussy orchestrator.

## Commands

### Signal Phase Completion

```
/debussy-done <PHASE_ID> [STATUS] [REASON]
```

Examples:
```
/debussy-done 1
/debussy-done 2 completed
/debussy-done 3 blocked "Waiting for API credentials"
```

### Log Progress

```
/debussy-progress <PHASE_ID> <STEP_NAME>
```

### Check Status

```
/debussy-status
```

## Fallback

If the slash commands aren't available, use `uv run debussy` directly:

```bash
uv run debussy done --phase 1 --status completed
uv run debussy progress --phase 1 --step "tests:running"
uv run debussy status
```

## Important

Always call `/debussy-done` when finishing a phase. The orchestrator waits for this signal.
"""
    path.write_text(content)


def _write_command_inline(path: Path, command: str) -> None:
    """Write a debussy command file inline (fallback when resource not found)."""
    commands = {
        "debussy-done": """# Signal Phase Completion

Signal to the Debussy orchestrator that the current phase is complete.

## Usage

```
/debussy-done <PHASE_ID> [STATUS] [REASON]
```

## Arguments

- `PHASE_ID` (required): The phase ID (e.g., "1", "2", "setup")
- `STATUS` (optional): completed | blocked | failed (default: completed)
- `REASON` (optional): Explanation for blocked/failed status

## Implementation

```bash
uv run debussy done --phase $ARGUMENTS
```
""",
        "debussy-progress": """# Log Phase Progress

Signal to the Debussy orchestrator that you're making progress on a phase.

## Usage

```
/debussy-progress <PHASE_ID> <STEP_NAME>
```

## Implementation

```bash
uv run debussy progress --phase $ARGUMENTS
```
""",
        "debussy-status": """# Check Orchestration Status

View the current Debussy orchestration status.

## Usage

```
/debussy-status
```

## Implementation

```bash
uv run debussy status
```
""",
    }
    path.write_text(commands.get(command, ""))


def _write_ltm_command_inline(path: Path, command: str) -> None:
    """Write LTM command files inline (fallback when resource not found)."""
    commands = {
        "please-remember": """# Save to Long-Term Memory

Save important context for future phases.

## Usage

```
/remember "<memory content>"
```

## Examples

```
/remember "Phase 1: Used repository pattern for data access"
/remember "BLOCKER: Legacy auth code needed refactoring"
```

## Implementation

```bash
uv run ltm remember --region project "$ARGUMENTS"
```
""",
        "recall": """# Search Long-Term Memory

Recall memories from previous phases.

## Usage

```
/recall <search query>
```

## Examples

```
/recall auth
/recall "phase 1"
/recall blocker
```

## Implementation

```bash
uv run ltm recall "$ARGUMENTS"
```
""",
    }
    path.write_text(commands.get(command, ""))


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


# =============================================================================
# Sandbox Commands
# =============================================================================


def _get_docker_dir() -> Path:
    """Get the docker directory, checking package data first, then repo root."""
    # First try: inside package directory (installed package or src layout)
    pkg_docker = Path(__file__).parent / "docker"
    if pkg_docker.exists():
        return pkg_docker

    # Second try: repo root (development mode / editable install)
    repo_docker = Path(__file__).parent.parent.parent / "docker"
    if repo_docker.exists():
        return repo_docker

    # Nothing found - return package path for error message
    return pkg_docker


def _get_docker_command() -> list[str]:
    """Get the docker command prefix, using WSL on Windows if needed."""
    import platform
    import shutil

    if shutil.which("docker"):
        return ["docker"]
    # On Windows, try docker through WSL
    if platform.system() == "Windows" and shutil.which("wsl"):
        return ["wsl", "docker"]
    return ["docker"]  # Will fail, but gives clear error


def _wsl_path(path: Path) -> str:
    """Convert Windows path to WSL path format."""
    import platform

    if platform.system() != "Windows":
        return str(path)
    # C:\foo\bar -> /mnt/c/foo/bar
    path_str = str(path.resolve())
    if len(path_str) >= 2 and path_str[1] == ":":
        drive = path_str[0].lower()
        rest = path_str[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return str(path)


@app.command("sandbox-build")
def sandbox_build(
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Build without using Docker cache"),
    ] = False,
) -> None:
    """Build the debussy-sandbox Docker image."""
    import subprocess

    # Find the Dockerfile
    docker_dir = _get_docker_dir()
    dockerfile = docker_dir / "Dockerfile.sandbox"

    if not dockerfile.exists():
        console.print(f"[red]Dockerfile not found: {dockerfile}[/red]")
        console.print("Please ensure the docker/ directory is present.")
        console.print(f"  Checked: {docker_dir}")
        raise typer.Exit(1)

    console.print("[bold]Building debussy-sandbox image...[/bold]")
    console.print(f"  Dockerfile: {dockerfile}")
    if no_cache:
        console.print("  [dim]--no-cache: rebuilding all layers[/dim]")
    console.print()

    docker_cmd = _get_docker_command()
    # If using WSL, convert paths
    if docker_cmd[0] == "wsl":
        dockerfile_path = _wsl_path(dockerfile)
        context_path = _wsl_path(docker_dir)
    else:
        dockerfile_path = str(dockerfile)
        context_path = str(docker_dir)

    build_args = [
        *docker_cmd,
        "build",
        "-t",
        "debussy-sandbox:latest",
        "-f",
        dockerfile_path,
    ]
    if no_cache:
        build_args.append("--no-cache")
    build_args.append(context_path)

    result = subprocess.run(build_args, check=False)

    if result.returncode == 0:
        console.print("\n[green]Image built successfully![/green]")
        console.print("Run with: debussy run --sandbox <master_plan>")
    else:
        console.print("\n[red]Build failed[/red]")
        raise typer.Exit(1)


@app.command("sandbox-status")
def sandbox_status() -> None:
    """Check Docker and sandbox image availability."""
    from debussy.runners.claude import (
        SANDBOX_IMAGE,
        _is_docker_available,
        _is_sandbox_image_available,
    )

    console.print("[bold]Sandbox Status[/bold]\n")

    # Check Docker
    if _is_docker_available():
        console.print("[green]Docker:[/green] Available")
    else:
        console.print("[red]Docker:[/red] Not available")
        console.print("  Install Docker Desktop from https://docker.com/products/docker-desktop")
        return

    # Check sandbox image
    if _is_sandbox_image_available():
        console.print(f"[green]Image:[/green] {SANDBOX_IMAGE} found")
        console.print("\n[green]Ready to run with --sandbox![/green]")
    else:
        console.print(f"[yellow]Image:[/yellow] {SANDBOX_IMAGE} not found")
        console.print("  Build with: debussy sandbox-build")


if __name__ == "__main__":
    app()
