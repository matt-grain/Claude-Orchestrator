"""CLI interface for the debussy."""

from __future__ import annotations

import json
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Parse and validate only, don't execute"),
    ] = False,
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Claude model: haiku, sonnet, opus"),
    ] = "sonnet",
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
) -> None:
    """Start orchestrating a master plan."""
    if dry_run:
        _dry_run(master_plan)
        return

    # Create config with overrides
    from debussy.config import Config

    interactive = not no_interactive
    config = Config(model=model, output=output, interactive=interactive)  # type: ignore[arg-type]

    # Parse plan and display banner
    plan = parse_master_plan(master_plan)
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

    try:
        run_id = run_orchestration(master_plan, start_phase=phase, config=config)
        console.print(f"\n[bold green]Orchestration completed. Run ID: {run_id}[/bold green]")
        if output in ("file", "both"):
            console.print("[dim]Logs saved to: .debussy/logs/[/dim]")
    except Exception as e:
        console.print(f"\n[bold red]Orchestration failed: {e}[/bold red]")
        raise typer.Exit(1) from e


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


if __name__ == "__main__":
    app()
