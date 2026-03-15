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
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from debussy.config import get_orchestrator_dir
from debussy.core.models import CompletionSignal, PhaseStatus, RunStatus
from debussy.core.state import StateManager

__version__ = "0.1.1"

app = typer.Typer(
    name="debussy",
    help="Orchestrate multi-phase Claude CLI sessions with compliance verification.",
    no_args_is_help=True,
)
console = Console()

# ---------------------------------------------------------------------------
# Register command modules
# ---------------------------------------------------------------------------

from debussy.commands import convert, init_cmd, plan, run, sandbox, sync  # noqa: E402

run.register(app)
plan.register(app)
convert.register(app)
init_cmd.register(app)
sandbox.register(app)
sync.register(app)


# ---------------------------------------------------------------------------
# audit command
# ---------------------------------------------------------------------------


def _display_issue(issue: object, verbose: int) -> None:
    """Display an audit issue with optional verbose details.

    Args:
        issue: The AuditIssue to display.
        verbose: Verbosity level (0=basic, 1=with suggestions, 2=full).
    """
    from debussy.core.audit import AuditIssue, AuditSeverity

    if not isinstance(issue, AuditIssue):
        return

    # Icon based on severity
    icon_map = {
        AuditSeverity.ERROR: "[red]✗[/red]",
        AuditSeverity.WARNING: "[yellow]⚠[/yellow]",
        AuditSeverity.INFO: "[cyan]i[/cyan]",
    }
    icon = icon_map.get(issue.severity, " ")

    # Basic message
    location = f" ({issue.location})" if issue.location else ""
    console.print(f"  {icon} {issue.message}{location}")

    # Verbose level 1+: show suggestions
    if verbose >= 1 and issue.suggestion:
        # Handle multi-line suggestions with proper indentation
        suggestion_lines = issue.suggestion.split("\n")
        console.print(f"      [dim]Suggestion:[/dim] {suggestion_lines[0]}")
        for line in suggestion_lines[1:]:
            console.print(f"                  {line}")


def _display_audit_structure(plan_path: Path) -> None:
    """Display parsed plan structure for verbose output.

    Args:
        plan_path: Path to the master plan file.
    """
    from debussy.parsers.master import parse_master_plan
    from debussy.parsers.phase import parse_phase

    try:
        master = parse_master_plan(plan_path)
    except Exception:
        return  # Structure display is best-effort

    console.print("[bold]Parsed Structure:[/bold]")
    console.print(f"  Master Plan: {master.name}")
    console.print()

    for phase in master.phases:
        console.print(f"  [cyan]Phase {phase.id}:[/cyan] {phase.title}")
        console.print(f"    Status: {phase.status.value}")
        console.print(f"    Path: {phase.path}")

        if phase.depends_on:
            console.print(f"    Depends on: {', '.join(phase.depends_on)}")

        # Try to parse phase file for more details
        if phase.path.exists():
            try:
                detailed = parse_phase(phase.path, phase.id)
                if detailed.gates:
                    console.print("    Gates:")
                    for gate in detailed.gates:
                        blocking = "" if gate.blocking else " [non-blocking]"
                        console.print(f"      - {gate.name}: `{gate.command}`{blocking}")
                if detailed.notes_output:
                    console.print(f"    Notes output: {detailed.notes_output}")
            except Exception:
                pass  # Skip details if parsing fails

        console.print()


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
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Increase output verbosity (-v for details, -vv for structure)"),
    ] = 0,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text, json"),
    ] = "text",
) -> None:
    """Validate plan structure before running."""
    from debussy.core.auditor import PlanAuditor

    auditor = PlanAuditor()
    result = auditor.audit(plan_path)

    # JSON output mode
    if output_format == "json":
        output = {
            "passed": result.passed,
            "summary": {
                "master_plan": result.summary.master_plan,
                "phases_found": result.summary.phases_found,
                "phases_valid": result.summary.phases_valid,
                "gates_total": result.summary.gates_total,
                "errors": result.summary.errors,
                "warnings": result.summary.warnings,
            },
            "issues": [
                {
                    "severity": issue.severity.value,
                    "code": issue.code,
                    "message": issue.message,
                    "location": issue.location,
                    "suggestion": issue.suggestion,
                }
                for issue in result.issues
            ],
        }
        # Use print directly to avoid Rich markup processing
        print(json.dumps(output, indent=2))
        if not result.passed:
            raise typer.Exit(1)
        if strict and result.summary.warnings > 0:
            raise typer.Exit(1)
        return

    # Text output mode
    console.print(f"\n[bold]Auditing:[/bold] {plan_path.name}\n")

    # Display summary
    console.print(f"[bold]{result.summary.master_plan}[/bold]")
    console.print(f"  Phases found: {result.summary.phases_found}")
    console.print(f"  Phases valid: {result.summary.phases_valid}")
    console.print(f"  Total gates: {result.summary.gates_total}")
    console.print()

    # Verbose level 2: show parsed structure
    if verbose >= 2:
        _display_audit_structure(plan_path)

    # Display issues grouped by severity
    from debussy.core.audit import AuditSeverity

    errors = [i for i in result.issues if i.severity == AuditSeverity.ERROR]
    warnings = [i for i in result.issues if i.severity == AuditSeverity.WARNING]
    infos = [i for i in result.issues if i.severity == AuditSeverity.INFO]

    if errors:
        console.print("[bold red]Errors:[/bold red]")
        for issue in errors:
            _display_issue(issue, verbose)
        console.print()

    if warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for issue in warnings:
            _display_issue(issue, verbose)
        console.print()

    if infos:
        console.print("[bold cyan]Info:[/bold cyan]")
        for issue in infos:
            _display_issue(issue, verbose)
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


# ---------------------------------------------------------------------------
# done command
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# progress command
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------


@app.command()
def status(
    run_id: Annotated[
        str | None,
        typer.Option("--run", "-r", help="Specific run ID to check"),
    ] = None,
    issues: Annotated[
        bool,
        typer.Option("--issues", "-i", help="Show linked issue status from GitHub/Jira"),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option("--refresh", help="Force refresh issue status (bypass cache)"),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text, json"),
    ] = "text",
) -> None:
    """Show current orchestration status."""
    import asyncio

    orchestrator_dir = get_orchestrator_dir()
    state_mgr = StateManager(orchestrator_dir / "state.db")

    run_state = state_mgr.get_run(run_id) if run_id else state_mgr.get_current_run()

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

    # Issue status display
    if issues:
        from debussy.commands.sync import _display_issue_status

        asyncio.run(_display_issue_status(run_state, state_mgr, refresh, output_format))


# ---------------------------------------------------------------------------
# history command
# ---------------------------------------------------------------------------


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

    for run_entry in runs:
        color = status_colors.get(run_entry.status, "white")
        duration = ""
        if run_entry.completed_at:
            delta = run_entry.completed_at - run_entry.started_at
            duration = f"{delta.total_seconds():.0f}s"

        table.add_row(
            run_entry.id,
            run_entry.master_plan_path.name,
            f"[{color}]{run_entry.status.value}[/{color}]",
            run_entry.started_at.strftime("%Y-%m-%d %H:%M"),
            duration,
        )

    console.print(table)


if __name__ == "__main__":
    app()
