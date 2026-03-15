"""Plan commands: plan-from-issues and plan-init."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register plan-related commands on the given Typer app."""

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
        questions_only: Annotated[
            bool,
            typer.Option("--questions-only", help="Output questions as JSON and exit (for Claude Code integration)"),
        ] = False,
        answers_file: Annotated[
            Path | None,
            typer.Option("--answers-file", help="Path to JSON file with pre-collected answers"),
        ] = None,
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
        force: Annotated[
            bool,
            typer.Option("--force", "-f", help="Bypass completion check confirmation"),
        ] = False,
    ) -> None:
        """Generate Debussy plans from GitHub issues.

        Fetches issues, analyzes them for gaps, conducts optional Q&A,
        generates structured plans, and validates with audit.

        If any issues were part of a previously completed feature,
        you will be prompted to confirm before regenerating.
        Use --force to bypass this check.

        Two-pass mode for Claude Code integration:
            1. Run with --questions-only to get questions as JSON
            2. Run with --answers-file to inject pre-collected answers

        Examples:
            debussy plan-from-issues --milestone "v2.0"
            debussy plan-from-issues --label feature --label auth
            debussy plan-from-issues --source gh --skip-qa
            debussy plan-from-issues --milestone "v1.0" --force  # bypass completion check
            debussy plan-from-issues --milestone "v2.0" --questions-only  # output questions JSON
            debussy plan-from-issues --milestone "v2.0" --answers-file answers.json  # use pre-collected answers
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
            questions_only=questions_only,
            answers_file=answers_file,
            max_retries=max_retries,
            model=model,
            timeout=timeout,
            verbose=verbose,
            console=console,
            force=force,
        )

        if not result.success and not questions_only:
            raise typer.Exit(1)

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
