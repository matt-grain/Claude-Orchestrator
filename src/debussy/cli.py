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
from rich.text import Text

from debussy.config import get_orchestrator_dir
from debussy.core.models import CompletionSignal, PhaseStatus, RunStatus
from debussy.core.orchestrator import run_orchestration
from debussy.core.state import StateManager
from debussy.parsers.master import parse_master_plan
from debussy.ui.controller import OrchestrationController
from debussy.utils.docker import get_docker_command, wsl_path

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
    if config.auto_commit and not allow_dirty:
        from debussy.core.orchestrator import Orchestrator

        # Create a temporary orchestrator just to check the directory
        temp_orchestrator = Orchestrator(master_plan, config, project_root=Path.cwd())
        is_clean, file_count = temp_orchestrator.check_clean_working_directory()
        if not is_clean:
            console.print()
            console.print("[bold yellow]⚠️  DIRTY WORKING DIRECTORY[/bold yellow]")
            console.print()
            console.print(f"Found {file_count} uncommitted file(s) in working directory.")
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


@app.command("plan-init")
def plan_init(
    feature: Annotated[str, typer.Argument(help="Feature name for the plan")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory (default: ./plans/{feature}/)"),
    ] = None,
    phases: Annotated[
        int,
        typer.Option("--phases", "-p", help="Number of phases to generate"),
    ] = 3,
    template: Annotated[
        str,
        typer.Option("--template", "-t", help="Template type: generic, backend, frontend"),
    ] = "generic",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing files"),
    ] = False,
) -> None:
    """Initialize a new plan from templates.

    Creates a master plan and phase files from templates.

    Example:
        debussy plan-init user-auth --phases 3
        debussy plan-init api-refactor --output plans/api/ --template backend
    """
    from debussy.core.auditor import PlanAuditor
    from debussy.templates import TEMPLATES_DIR
    from debussy.templates.scaffolder import PlanScaffolder

    # Determine output directory
    if output is None:
        feature_slug = feature.lower().replace(" ", "-").replace("_", "-")
        output = Path("plans") / feature_slug

    # Check if directory exists
    if output.exists() and not force:
        console.print(f"[red]Error:[/red] Directory already exists: {output}")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    console.print(f"\n[bold]Creating plan:[/bold] {feature}\n")

    # Validate template type
    if template not in ["generic", "backend", "frontend"]:
        console.print(f"[red]Error:[/red] Invalid template type: {template}")
        console.print("Valid options: generic, backend, frontend")
        raise typer.Exit(1)

    # Validate phases count
    if phases < 1:
        console.print(f"[red]Error:[/red] Number of phases must be at least 1, got {phases}")
        raise typer.Exit(1)

    # Create scaffolder and generate files
    try:
        scaffolder = PlanScaffolder(TEMPLATES_DIR)
        created_files = scaffolder.scaffold(
            feature_name=feature,
            output_dir=output,
            num_phases=phases,
            template_type=template,
        )

        # Display created files
        for file_path in created_files:
            relative = file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path
            console.print(f"  [green]✓[/green] Created: {relative}")

        console.print()

        # Run audit on generated files
        master_plan = output / "MASTER_PLAN.md"
        console.print("[bold]Running audit...[/bold]")
        auditor = PlanAuditor()
        audit_result = auditor.audit(master_plan)

        if audit_result.passed:
            console.print("[green]✓ Plan passes audit[/green]\n")
        else:
            console.print("[yellow]⚠ Plan has validation issues:[/yellow]")
            for issue in audit_result.issues:
                console.print(f"  - {issue.message}")
            console.print()

        # Success message with next steps
        console.print("[bold green]Success![/bold green]\n")
        console.print("[bold]Next steps:[/bold]")
        # Use relative path if possible, otherwise use absolute
        display_path = master_plan.relative_to(Path.cwd()) if master_plan.is_relative_to(Path.cwd()) else master_plan
        console.print(f"1. Edit {display_path} to fill in overview and goals")
        console.print("2. Edit each phase file to add specific tasks")
        console.print(f"3. Run: [cyan]debussy run {display_path}[/cyan]\n")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Templates not found. Please check your installation.")
        raise typer.Exit(1) from e
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def convert(
    source: Annotated[
        Path,
        typer.Argument(
            help="Path to freeform plan markdown file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for structured plan"),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Ask clarifying questions"),
    ] = False,
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Claude model to use"),
    ] = "haiku",
    max_retries: Annotated[
        int,
        typer.Option("--max-retries", help="Max conversion attempts"),
    ] = 3,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout for Claude calls in seconds"),
    ] = 120,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing output directory"),
    ] = False,
) -> None:
    """Convert a freeform plan to Debussy format.

    Uses Claude to transform an unstructured plan markdown file into
    Debussy's structured format with master plan and phase files.

    The converted output is validated with audit. If audit fails,
    the conversion retries with feedback up to --max-retries times.

    Example:
        debussy convert my-plan.md --output plans/my-feature/
        debussy convert messy-plan.md --interactive
    """
    from debussy.converters import PlanConverter
    from debussy.core.auditor import PlanAuditor
    from debussy.templates import TEMPLATES_DIR

    # Determine output directory
    if output is None:
        # Default to same directory as source, with structured- prefix
        output = source.parent / f"structured-{source.stem}"

    # Check if output exists
    if output.exists() and not force:
        console.print(f"[red]Error:[/red] Output directory already exists: {output}")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    console.print(f"\n[bold]Converting:[/bold] {source.name}\n")

    # Create converter
    auditor = PlanAuditor()
    converter = PlanConverter(
        auditor=auditor,
        templates_dir=TEMPLATES_DIR,
        max_iterations=max_retries,
        model=model,
        timeout=timeout,
    )

    # Run conversion with progress display
    console.print("Analyzing plan structure...")

    result = converter.convert(
        source_plan=source,
        output_dir=output,
        interactive=interactive,
    )

    # Display results
    if result.files_created:
        console.print()
        for file_path in result.files_created:
            # Try to get relative path
            try:
                rel_path = Path(file_path).relative_to(Path.cwd())
            except ValueError:
                rel_path = Path(file_path)
            console.print(f"  [green]✓[/green] Created: {rel_path}")
        console.print()

    # Display audit result
    if result.audit_passed:
        console.print("[green]✓ Audit passed![/green]")
    else:
        console.print(f"[red]✗ Audit failed[/red] ({result.audit_errors} errors, {result.audit_warnings} warnings)")

    # Display warnings
    for warning in result.warnings:
        console.print(f"[yellow]⚠ {warning}[/yellow]")

    if result.success:
        console.print(f"\n[bold green]Conversion complete![/bold green] (attempt {result.iterations}/{max_retries})\n")

        # Run quality check if we have source directory
        from debussy.converters.quality import ConversionQualityEvaluator

        evaluator = ConversionQualityEvaluator(
            source_dir=source.parent,
            output_dir=output,
        )
        quality = evaluator.evaluate(audit_result=None)

        # Check for critical quality issues
        quality_issues = []
        if quality.agents_lost:
            quality_issues.append(f"Lost subagents: {', '.join(sorted(quality.agents_lost))}")
        if quality.tech_lost and len(quality.tech_lost) > 2:
            quality_issues.append(f"Lost tech keywords: {', '.join(sorted(quality.tech_lost))}")
        if quality.preprocessed_jaccard < 0.25:
            quality_issues.append(f"Low content similarity: {quality.preprocessed_jaccard:.0%}")

        if quality_issues and model == "haiku":
            console.print("[yellow]⚠ Quality issues detected:[/yellow]")
            for issue in quality_issues:
                console.print(f"  • {issue}")
            console.print()

            # Offer upgrade to sonnet (skip in non-interactive/CI environments)
            try:
                should_upgrade = typer.confirm(
                    "Retry with Sonnet model for better quality? (more expensive, slower)",
                    default=False,
                )
            except (typer.Abort, EOFError):
                # Non-interactive environment (CI, tests) - skip upgrade prompt
                should_upgrade = False
                console.print("[dim]Tip: Use --model sonnet for complex plans, or split into smaller files[/dim]\n")

            if should_upgrade:
                console.print("\n[cyan]Retrying with Sonnet (this may take a few minutes)...[/cyan]\n")
                # Sonnet needs more time for complex plans
                sonnet_timeout = max(timeout, 600)  # At least 10 minutes for sonnet
                converter_sonnet = PlanConverter(
                    auditor=auditor,
                    templates_dir=TEMPLATES_DIR,
                    max_iterations=max_retries,
                    model="sonnet",
                    timeout=sonnet_timeout,
                )
                result = converter_sonnet.convert(
                    source_plan=source,
                    output_dir=output,
                    interactive=interactive,
                )
                if result.success:
                    console.print("[green]✓ Sonnet conversion complete![/green]\n")
                else:
                    console.print("[red]✗ Sonnet conversion also failed[/red]")
                    console.print("[dim]Consider splitting your plan into smaller parts[/dim]\n")
                    raise typer.Exit(1)
            elif should_upgrade is False:
                # User explicitly declined (not caught by exception)
                pass  # Already printed tip above or will print below

        console.print("[bold]Next steps:[/bold]")
        master_plan = output / "MASTER_PLAN.md"
        try:
            display_path = master_plan.relative_to(Path.cwd())
        except ValueError:
            display_path = master_plan
        console.print("1. Review generated files for accuracy")
        console.print(f"2. Run: [cyan]debussy run {display_path}[/cyan]\n")
    else:
        console.print(f"\n[bold red]Conversion failed[/bold red] after {result.iterations} attempts")
        console.print("[dim]Try editing the source plan to be more structured, or use --max-retries[/dim]\n")
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


def _install_resource(
    subpackage: str,
    filename: str,
    dst: Path,
    force: bool,
    file_type: str,
) -> None:
    """Install a resource file from the package to destination."""
    from debussy.resources.loader import copy_resource_to

    if dst.exists() and not force:
        console.print(f"[yellow]{file_type} exists (skipped): {dst.name}[/yellow]")
        return

    copy_resource_to(subpackage, filename, dst)
    console.print(f"[green]Installed {file_type}: {dst.name}[/green]")


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

    # Install agent and skill files from package resources
    _install_resource("agents", "debussy.md", agents_dir / "debussy.md", force, "agent")
    _install_resource("skills", "debussy.md", skills_dir / "debussy.md", force, "skill")

    # Install command files
    for cmd_name in ["debussy-done", "debussy-progress", "debussy-status"]:
        _install_resource("commands", f"{cmd_name}.md", commands_dir / f"{cmd_name}.md", force, f"command: /{cmd_name}")

    # Install LTM commands via ltm setup if requested
    if with_ltm:
        import subprocess

        result = subprocess.run(
            ["uv", "run", "ltm", "setup", str(target)],
            capture_output=True,
            text=True,
            cwd=target,
            check=False,  # Handle errors ourselves
        )
        if result.returncode == 0:
            console.print("[green]LTM commands installed via ltm setup[/green]")
        else:
            console.print(f"[yellow]LTM setup warning: {result.stderr.strip()}[/yellow]")

    # Always create config (with learnings enabled if --with-ltm)
    from debussy.config import Config

    debussy_dir = target / ".debussy"
    debussy_dir.mkdir(exist_ok=True)
    config_path = debussy_dir / "config.yaml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        console.print("[dim]Use --force to overwrite.[/dim]")
    else:
        config = Config(learnings=with_ltm)
        config.save(config_path)
        learnings_note = " with learnings enabled" if with_ltm else ""
        console.print(f"[green]Created {config_path}{learnings_note}[/green]")

    console.print("\n[bold]Setup complete![/bold]")
    if with_ltm:
        console.print("Debussy agent has access to orchestration + memory commands.")
    else:
        console.print("Debussy agent has access to orchestration commands.")
        console.print("[dim]Tip: Use --with-ltm to enable cross-phase memory.[/dim]")


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

    docker_cmd = get_docker_command()
    # If using WSL, convert paths
    if docker_cmd[0] == "wsl":
        dockerfile_path = wsl_path(dockerfile)
        context_path = wsl_path(docker_dir)
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
        _is_sandbox_image_available,
    )
    from debussy.utils.docker import is_docker_available

    console.print("[bold]Sandbox Status[/bold]\n")

    # Check Docker
    if is_docker_available():
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


@app.command("plan-from-issues")
def plan_from_issues(
    source: Annotated[
        str,
        typer.Option("--source", "-s", help="Issue source: gh (GitHub), jira (future)"),
    ] = "gh",
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help="Repository in 'owner/repo' format (default: current repo)"),
    ] = None,
    milestone: Annotated[
        str | None,
        typer.Option("--milestone", "-m", help="Filter by GitHub milestone"),
    ] = None,
    label: Annotated[
        list[str] | None,
        typer.Option("--label", "-l", help="Filter by label (repeatable)"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Output directory (default: plans/<feature>)"),
    ] = None,
    skip_qa: Annotated[
        bool,
        typer.Option("--skip-qa", help="Skip interactive Q&A phase"),
    ] = False,
    max_retries: Annotated[
        int,
        typer.Option("--max-retries", help="Maximum audit retry attempts"),
    ] = 3,
    model: Annotated[
        str,
        typer.Option("--model", help="Claude model to use (default: sonnet)"),
    ] = "sonnet",
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout for Claude calls in seconds (default: 300)"),
    ] = 300,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
) -> None:
    """Generate Debussy plans from GitHub issues.

    Fetches issues, analyzes them for gaps, conducts optional Q&A,
    generates structured plans, and validates with audit.

    Examples:
        debussy plan-from-issues --milestone "v2.0"
        debussy plan-from-issues --label feature --label auth
        debussy plan-from-issues --source gh --skip-qa
    """
    from debussy.planners.command import plan_from_issues as do_plan_from_issues

    # Validate source
    if source not in ("gh", "jira"):
        console.print(f"[red]Error:[/red] Invalid source '{source}'. Use 'gh' or 'jira'.")
        raise typer.Exit(1)

    # Run the command
    result = do_plan_from_issues(
        source=source,  # type: ignore[arg-type]
        repo=repo,
        milestone=milestone,
        labels=label,
        output_dir=output_dir,
        skip_qa=skip_qa,
        max_retries=max_retries,
        model=model,
        timeout=timeout,
        verbose=verbose,
        console=console,
    )

    if not result.success:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
