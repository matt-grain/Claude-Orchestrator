"""Convert command: convert a freeform plan to Debussy format."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the convert command on the given Typer app."""

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
