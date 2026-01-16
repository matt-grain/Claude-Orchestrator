"""Command handler for the plan-from-issues CLI command.

This module implements the main pipeline for generating Debussy-compliant
plans from GitHub issues:
1. FETCH - Retrieve issues from GitHub
2. ANALYZE - Detect gaps in issue specifications
3. Q&A - Ask user for missing information (optional)
4. GENERATE - Create plan files using Claude
5. AUDIT - Validate plans and retry if needed
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rich.console import Console

if TYPE_CHECKING:
    from debussy.core.audit import AuditResult
    from debussy.planners.analyzer import AnalysisReport
    from debussy.planners.models import IssueSet

logger = logging.getLogger(__name__)

IssueSource = Literal["gh", "jira"]


@dataclass
class PlanFromIssuesResult:
    """Result of the plan-from-issues command."""

    success: bool = False
    files_created: list[str] = field(default_factory=list)
    audit_passed: bool = False
    audit_attempts: int = 0
    issues_fetched: int = 0
    gaps_found: int = 0
    questions_asked: int = 0
    error_message: str | None = None


def plan_from_issues(
    source: IssueSource,
    repo: str | None = None,
    milestone: str | None = None,
    labels: list[str] | None = None,
    output_dir: Path | None = None,
    skip_qa: bool = False,
    max_retries: int = 3,
    model: str = "haiku",
    timeout: int = 120,
    verbose: bool = False,
    console: Console | None = None,
) -> PlanFromIssuesResult:
    """Generate plans from GitHub issues.

    Main entry point for the plan-from-issues command.

    Args:
        source: Issue source ('gh' for GitHub, 'jira' reserved for future).
        repo: Repository in format 'owner/repo'. If None, uses current repo.
        milestone: Filter by milestone name.
        labels: Filter by label names.
        output_dir: Directory to write plan files. Defaults to plans/<feature>.
        skip_qa: Skip interactive Q&A phase.
        max_retries: Maximum audit retry attempts.
        model: Claude model to use.
        timeout: Timeout for Claude calls in seconds.
        verbose: Enable verbose output.
        console: Rich console for output.

    Returns:
        PlanFromIssuesResult with success status and created files.
    """
    if console is None:
        console = Console()

    result = PlanFromIssuesResult()

    # Validate source
    if source == "jira":
        result.error_message = "Jira source is not yet implemented"
        console.print("[red]Error:[/red] Jira source is not yet implemented")
        return result

    # Get repository name if not provided
    if repo is None:
        repo = _get_current_repo()
        if repo is None:
            result.error_message = "Could not detect repository. Use --repo flag."
            console.print("[red]Error:[/red] Could not detect repository. Use --repo flag.")
            return result

    # Phase 1: FETCH
    console.print("[bold]Phase 1: Fetching issues...[/bold]")
    try:
        issues = _fetch_phase(repo, milestone, labels, console, verbose)
        result.issues_fetched = len(issues.issues)

        if not issues.issues:
            result.error_message = "No issues found matching the filter criteria"
            console.print("[yellow]Warning:[/yellow] No issues found matching the filter criteria")
            return result

        console.print(f"  [green]✓[/green] Fetched {len(issues.issues)} issues")
    except Exception as e:
        result.error_message = f"Fetch failed: {e}"
        console.print(f"[red]Error:[/red] Fetch failed: {e}")
        return result

    # Phase 2: ANALYZE
    console.print("[bold]Phase 2: Analyzing issues...[/bold]")
    analysis = _analyze_phase(issues, console, verbose)
    result.gaps_found = analysis.total_gaps
    console.print(f"  [green]✓[/green] Found {analysis.critical_gaps} critical gaps, {analysis.total_gaps - analysis.critical_gaps} warnings")

    # Phase 3: Q&A (optional)
    answers: dict[str, str] = {}
    if not skip_qa and analysis.questions_needed:
        console.print("[bold]Phase 3: Interactive Q&A...[/bold]")
        answers = _qa_phase(analysis, console, verbose)
        result.questions_asked = len(answers)
        console.print(f"  [green]✓[/green] Collected {len(answers)} answers")
    elif skip_qa:
        console.print("[bold]Phase 3: Q&A skipped (--skip-qa)[/bold]")
    else:
        console.print("[bold]Phase 3: No questions needed[/bold]")

    # Determine output directory
    if output_dir is None:
        # Generate from milestone or first issue
        if milestone:
            feature_name = milestone.lower().replace(" ", "-")
        elif labels:
            feature_name = "-".join(labels[:2]).lower().replace(" ", "-")
        else:
            feature_name = f"feature-{issues.issues[0].number}"
        output_dir = Path("plans") / feature_name

    # Phase 4: GENERATE
    console.print(f"[bold]Phase 4: Generating plans to {output_dir}...[/bold]")
    files = _generate_phase(issues, analysis, answers, output_dir, model, timeout, console, verbose)
    result.files_created = files
    console.print(f"  [green]✓[/green] Generated {len(files)} files")

    # Phase 5: AUDIT with retry loop
    console.print("[bold]Phase 5: Running audit...[/bold]")
    audit_passed, audit_attempts = _audit_loop(output_dir, max_retries, console, verbose)
    result.audit_passed = audit_passed
    result.audit_attempts = audit_attempts

    if audit_passed:
        console.print(f"  [green]✓[/green] Audit PASSED (attempt {audit_attempts}/{max_retries})")
        result.success = True
    else:
        console.print(f"  [red]✗[/red] Audit FAILED after {audit_attempts} attempts")
        result.error_message = f"Audit failed after {audit_attempts} attempts"

    # Summary
    _print_summary(result, output_dir, console)

    return result


def _get_current_repo() -> str | None:
    """Get the current repository from git remote.

    Returns:
        Repository in 'owner/repo' format, or None if not detected.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        url = result.stdout.strip()

        # Handle SSH URLs: git@github.com:owner/repo.git
        if url.startswith("git@"):
            parts = url.split(":")
            if len(parts) == 2:
                repo_path = parts[1].removesuffix(".git")
                return repo_path

        # Handle HTTPS URLs: https://github.com/owner/repo.git
        if "github.com" in url:
            parts = url.rstrip(".git").split("/")
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"

        return None
    except Exception:
        return None


def _fetch_phase(
    repo: str,
    milestone: str | None,
    labels: list[str] | None,
    console: Console,
    verbose: bool,
) -> IssueSet:
    """Execute the fetch phase.

    Args:
        repo: Repository in format 'owner/repo'.
        milestone: Filter by milestone name.
        labels: Filter by label names.
        console: Rich console for output.
        verbose: Enable verbose output.

    Returns:
        IssueSet containing fetched issues.
    """
    from debussy.planners.github_fetcher import (
        fetch_issues_by_labels,
        fetch_issues_by_milestone,
    )

    if verbose:
        console.print(f"  [dim]Fetching from {repo}...[/dim]")

    # Run async fetch in sync context
    if milestone:
        issues = asyncio.run(fetch_issues_by_milestone(repo, milestone))
    elif labels:
        issues = asyncio.run(fetch_issues_by_labels(repo, labels))
    else:
        # Fetch all open issues
        issues = asyncio.run(fetch_issues_by_labels(repo, []))

    return issues


def _analyze_phase(
    issues: IssueSet,
    console: Console,
    verbose: bool,
) -> AnalysisReport:
    """Execute the analysis phase.

    Args:
        issues: Set of issues to analyze.
        console: Rich console for output.
        verbose: Enable verbose output.

    Returns:
        AnalysisReport with gap detection results.
    """
    from debussy.planners.analyzer import IssueAnalyzer

    analyzer = IssueAnalyzer()
    report = analyzer.analyze_issue_set(issues)

    if verbose:
        for iq in report.issues:
            console.print(f"  [dim]Issue #{iq.issue_number}: score={iq.score}, gaps={len(iq.gaps)}[/dim]")

    return report


def _qa_phase(
    analysis: AnalysisReport,
    console: Console,
    verbose: bool,  # noqa: ARG001
) -> dict[str, str]:
    """Execute the Q&A phase interactively.

    Args:
        analysis: Analysis report with questions.
        console: Rich console for output.
        verbose: Enable verbose output (reserved for future use).

    Returns:
        Dictionary mapping questions to user answers.
    """
    from debussy.planners.qa_handler import QAHandler

    # Collect all gaps for batching
    all_gaps: list = []
    for iq in analysis.issues:
        all_gaps.extend(iq.gaps)

    handler = QAHandler(analysis.questions_needed, gaps=all_gaps)

    # Interactive Q&A
    console.print()
    handler.ask_questions_interactive()
    console.print()

    return handler.get_answers_by_question()


def _generate_phase(
    issues: IssueSet,
    analysis: AnalysisReport,
    answers: dict[str, str],
    output_dir: Path,
    model: str,
    timeout: int,
    console: Console,
    verbose: bool,
) -> list[str]:
    """Execute the generation phase.

    Args:
        issues: Set of issues to generate plans from.
        analysis: Analysis report with gap detection results.
        answers: Q&A answers from user.
        output_dir: Directory to write plan files.
        model: Claude model to use.
        timeout: Timeout for Claude calls.
        console: Rich console for output.
        verbose: Enable verbose output.

    Returns:
        List of created file paths.
    """
    from debussy.planners.plan_builder import PlanBuilder

    builder = PlanBuilder(issues, analysis, model=model, timeout=timeout)
    builder.set_answers(answers)

    if verbose:
        console.print(f"  [dim]Using model: {model}, timeout: {timeout}s[/dim]")

    # Generate all files
    files = builder.generate_all()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write files
    created: list[str] = []
    for filename, content in files.items():
        file_path = output_dir / filename
        file_path.write_text(content, encoding="utf-8")
        created.append(str(file_path))

        if verbose:
            console.print(f"  [dim]Created: {file_path}[/dim]")

    return created


def _audit_loop(
    output_dir: Path,
    max_retries: int,
    console: Console,
    verbose: bool,
) -> tuple[bool, int]:
    """Execute the audit loop with retries.

    Args:
        output_dir: Directory containing plan files.
        max_retries: Maximum retry attempts.
        console: Rich console for output.
        verbose: Enable verbose output.

    Returns:
        Tuple of (passed, attempts).
    """
    master_plan_path = output_dir / "MASTER_PLAN.md"

    for attempt in range(1, max_retries + 1):
        if verbose:
            console.print(f"  [dim]Audit attempt {attempt}/{max_retries}...[/dim]")

        # Run audit
        audit_result = _run_audit(master_plan_path)

        if audit_result.passed:
            return True, attempt

        # Get audit errors for feedback
        errors = _get_audit_errors(audit_result)

        if verbose:
            console.print(f"  [dim]Audit found {len(errors)} issues[/dim]")
            for err in errors[:3]:
                console.print(f"    [dim]- {err}[/dim]")

        # Don't retry on last attempt
        if attempt == max_retries:
            break

        # Regenerate with error feedback
        console.print(f"  [yellow]Attempt {attempt} failed, regenerating...[/yellow]")
        _regenerate_with_errors(output_dir, errors, console, verbose)

    return False, max_retries


def _run_audit(plan_path: Path) -> AuditResult:
    """Run the compliance audit on a plan.

    Args:
        plan_path: Path to master plan file.

    Returns:
        AuditResult from the auditor.
    """
    from debussy.core.auditor import PlanAuditor

    auditor = PlanAuditor()
    return auditor.audit(plan_path)


def _get_audit_errors(result: AuditResult) -> list[str]:
    """Extract error messages from audit result.

    Args:
        result: AuditResult to extract from.

    Returns:
        List of error message strings.
    """
    from debussy.core.audit import AuditSeverity

    errors: list[str] = []
    for issue in result.issues:
        if issue.severity == AuditSeverity.ERROR:
            errors.append(f"[{issue.code}] {issue.message}")
        elif issue.severity == AuditSeverity.WARNING:
            errors.append(f"[WARNING] {issue.message}")
    return errors


def _regenerate_with_errors(
    output_dir: Path,  # noqa: ARG001
    errors: list[str],
    console: Console,
    verbose: bool,
) -> None:
    """Regenerate plans with audit error feedback.

    Injects errors into the prompt and regenerates using the converter pattern.

    Args:
        output_dir: Directory containing plan files (reserved for future use).
        errors: List of audit error messages.
        console: Rich console for output.
        verbose: Enable verbose output.
    """
    # For now, this is a placeholder - the retry logic will need to
    # read existing plans, inject error context, and regenerate.
    # Full implementation would follow the pattern from plan_converter.py
    if verbose:
        console.print("  [dim]Regeneration with errors not yet implemented[/dim]")
        for error in errors[:3]:
            console.print(f"    [dim]Error: {error}[/dim]")


def _print_summary(
    result: PlanFromIssuesResult,
    output_dir: Path,
    console: Console,
) -> None:
    """Print final summary of the operation.

    Args:
        result: The operation result.
        output_dir: Directory where files were written.
        console: Rich console for output.
    """
    console.print()
    console.print("[bold]═══════════════════════════════════════════════[/bold]")
    console.print()

    if result.success:
        console.print("[bold green]✓ Plan generation complete![/bold green]")
    else:
        console.print("[bold red]✗ Plan generation failed[/bold red]")
        if result.error_message:
            console.print(f"  [red]Error: {result.error_message}[/red]")

    console.print()
    console.print(f"  Issues fetched: {result.issues_fetched}")
    console.print(f"  Gaps detected: {result.gaps_found}")
    console.print(f"  Questions answered: {result.questions_asked}")
    console.print(f"  Files created: {len(result.files_created)}")
    console.print(f"  Audit attempts: {result.audit_attempts}")
    console.print()

    if result.files_created:
        console.print(f"Plans written to: {output_dir}/")
        for file_path in result.files_created:
            console.print(f"  - {Path(file_path).name}")
    console.print()
