"""CLI interface for the orchestrator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from orchestrator.config import get_orchestrator_dir
from orchestrator.core.models import CompletionSignal, PhaseStatus, RunStatus
from orchestrator.core.orchestrator import run_orchestration
from orchestrator.core.state import StateManager
from orchestrator.parsers.master import parse_master_plan

app = typer.Typer(
    name="orchestrate",
    help="Orchestrate multi-phase Claude CLI sessions with compliance verification.",
    no_args_is_help=True,
)
console = Console()


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
) -> None:
    """Start orchestrating a master plan."""
    if dry_run:
        _dry_run(master_plan)
        return

    console.print("[bold blue]Starting orchestration[/bold blue]")
    console.print(f"  Master plan: {master_plan}")
    console.print(f"  Model: {model}")
    if phase:
        console.print(f"  Starting from phase: {phase}")

    # Create config with model override
    from orchestrator.config import Config

    config = Config(model=model)

    try:
        run_id = run_orchestration(master_plan, start_phase=phase, config=config)
        console.print(f"\n[green]Orchestration completed. Run ID: {run_id}[/green]")
    except Exception as e:
        console.print(f"\n[red]Orchestration failed: {e}[/red]")
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

        from orchestrator.parsers.phase import parse_phase

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
