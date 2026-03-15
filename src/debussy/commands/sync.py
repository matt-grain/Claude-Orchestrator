"""Sync command: reconcile state drift between Debussy and issue trackers."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from debussy.config import get_orchestrator_dir
from debussy.core.state import StateManager

if TYPE_CHECKING:
    from debussy.core.models import RunState

console = Console()


def _detect_github_repo() -> str | None:
    """Detect GitHub repo from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Parse owner/repo from URL
        if "github.com" in url:
            # Handle both SSH (git@github.com:owner/repo.git) and HTTPS formats
            parts = url.split(":")[-1].replace(".git", "") if url.startswith("git@") else "/".join(url.split("/")[-2:]).replace(".git", "")
            return parts
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


async def _display_issue_status(
    run_state: RunState,
    state: StateManager,
    refresh: bool,
    output_format: str,
) -> None:
    """Display linked issue status from external trackers."""
    from debussy.config import Config
    from debussy.parsers.master import parse_master_plan
    from debussy.sync.drift_detector import DriftDetector
    from debussy.sync.status_fetcher import IssueStatusFetcher

    # Load config for API credentials
    config = Config.load()

    # Parse master plan for issue metadata
    plan = parse_master_plan(run_state.master_plan_path)

    # Extract GitHub and Jira issues
    github_issues: list[str] = []
    jira_issues: list[str] = []

    if plan.github_issues:
        if isinstance(plan.github_issues, list):
            github_issues = [str(n) for n in plan.github_issues]
        else:
            from debussy.sync.github_sync import GitHubSyncCoordinator

            coord = GitHubSyncCoordinator(repo="dummy/repo", config=None)  # type: ignore[arg-type]
            github_issues = [str(n) for n in coord.parse_github_issues(plan.github_issues)]

    if plan.jira_issues:
        if isinstance(plan.jira_issues, list):
            jira_issues = plan.jira_issues
        else:
            from debussy.sync.jira_sync import JIRA_ISSUE_PATTERN

            jira_issues = JIRA_ISSUE_PATTERN.findall(plan.jira_issues)

    if not github_issues and not jira_issues:
        console.print("\n[yellow]No linked issues found in plan.[/yellow]")
        return

    # Create fetcher and get status
    repo = plan.github_repo or _detect_github_repo()
    jira_url = config.jira.url if config.jira.url else None

    async with IssueStatusFetcher(
        github_repo=repo,
        jira_url=jira_url,
    ) as fetcher:
        # Fetch status
        all_statuses = await fetcher.fetch_all(
            github_issues=github_issues if github_issues else None,
            jira_issues=jira_issues if jira_issues else None,
            use_cache=not refresh,
        )

        # Detect drift
        detector = DriftDetector(state, fetcher)
        drift_reports = await detector.detect_drift(
            run_state.id,
            run_state.master_plan_path,
            use_cache=not refresh,
        )

        # Build drift lookup
        drift_lookup = {d.issue_id: d for d in drift_reports}

        if output_format == "json":
            # JSON output
            output_data = {
                "issues": [
                    {
                        "id": issue_id,
                        "platform": status.platform,
                        "state": status.state,
                        "labels": status.labels,
                        "milestone": status.milestone,
                        "drift": drift_lookup.get(status.id, drift_lookup.get(issue_id)),
                    }
                    for issue_id, status in all_statuses.items()
                ],
                "drift_count": len(drift_reports),
            }
            print(json.dumps(output_data, indent=2, default=str))
            return

        # Text output
        console.print("\n[bold]Linked Issues[/bold]")

        # Show cache freshness if not refreshed
        if not refresh:
            freshness = fetcher.cache.freshness_seconds
            if freshness:
                avg_age = sum(freshness.values()) / len(freshness)
                console.print(f"[dim]Cached {avg_age:.0f}s ago, use --refresh to update[/dim]")

        # Issue table
        issue_table = Table()
        issue_table.add_column("Issue")
        issue_table.add_column("Platform")
        issue_table.add_column("State")
        issue_table.add_column("Drift")

        for issue_id, status in all_statuses.items():
            platform_tag = "GH" if status.platform == "github" else "JIRA"
            state_color = "green" if status.state in ("closed", "Done") else "blue" if status.state == "open" else "yellow"

            # Check for drift
            drift = drift_lookup.get(status.id) or drift_lookup.get(issue_id.split("-", 1)[-1] if "-" in issue_id else issue_id)
            drift_str = f"[red]{drift.drift_type.value}[/red]" if drift else "[green]✓[/green]"

            issue_table.add_row(
                issue_id,
                platform_tag,
                f"[{state_color}]{status.state}[/{state_color}]",
                drift_str,
            )

        console.print(issue_table)

        # Drift warning
        if drift_reports:
            console.print(f"\n[yellow]⚠ {len(drift_reports)} issue(s) have state drift[/yellow]")
            console.print("[dim]Use 'debussy sync' to reconcile state[/dim]")


async def _sync_issues(
    run_state: RunState,
    state: StateManager,
    direction: object,  # SyncDirection
    apply: bool,
    output_format: str,
) -> None:
    """Execute issue sync reconciliation."""
    from debussy.config import Config
    from debussy.core.models import SyncDirection
    from debussy.parsers.master import parse_master_plan
    from debussy.sync.drift_detector import DriftDetector, StateSynchronizer
    from debussy.sync.status_fetcher import IssueStatusFetcher

    # Load config
    config = Config.load()

    # Parse plan
    plan = parse_master_plan(run_state.master_plan_path)

    # Extract issues
    github_issues: list[str] = []
    jira_issues: list[str] = []

    if plan.github_issues:
        if isinstance(plan.github_issues, list):
            github_issues = [str(n) for n in plan.github_issues]
        else:
            from debussy.sync.github_sync import GitHubSyncCoordinator

            coord = GitHubSyncCoordinator(repo="dummy/repo", config=None)  # type: ignore[arg-type]
            github_issues = [str(n) for n in coord.parse_github_issues(plan.github_issues)]

    if plan.jira_issues:
        if isinstance(plan.jira_issues, list):
            jira_issues = plan.jira_issues
        else:
            from debussy.sync.jira_sync import JIRA_ISSUE_PATTERN

            jira_issues = JIRA_ISSUE_PATTERN.findall(plan.jira_issues)

    if not github_issues and not jira_issues:
        console.print("[yellow]No linked issues found in plan.[/yellow]")
        return

    # Get repo and config
    repo = plan.github_repo or _detect_github_repo()
    jira_url = config.jira.url if config.jira.url else None

    async with IssueStatusFetcher(
        github_repo=repo,
        jira_url=jira_url,
    ) as fetcher:
        # Detect drift (always fetch fresh for sync)
        detector = DriftDetector(state, fetcher)
        drift_reports = await detector.detect_drift(
            run_state.id,
            run_state.master_plan_path,
            use_cache=False,
        )

        if not drift_reports:
            console.print("[green]✓ No state drift detected. Debussy and trackers are in sync.[/green]")
            return

        # Create reconciliation plan
        sync_dir = direction if isinstance(direction, SyncDirection) else SyncDirection(direction)
        recon_plan = detector.create_reconciliation_plan(drift_reports, sync_dir)

        if output_format == "json":
            output_data = {
                "direction": sync_dir.value,
                "drift_count": recon_plan.total_drift_count,
                "actions": [
                    {
                        "issue_id": a.issue_id,
                        "platform": a.platform,
                        "action": a.action,
                        "description": a.description,
                        "from_value": a.from_value,
                        "to_value": a.to_value,
                    }
                    for a in recon_plan.actions
                ],
                "applied": apply,
            }
            print(json.dumps(output_data, indent=2))
        else:
            # Text output
            console.print(f"\n[bold]Reconciliation Plan[/bold] (direction: {sync_dir.value})")
            console.print(f"[yellow]{recon_plan.total_drift_count} drift(s) detected[/yellow]\n")

            for action in recon_plan.actions:
                console.print(f"  • {action.description}")
                console.print(f"    [dim]{action.from_value} → {action.to_value}[/dim]")

            console.print()

        if not apply:
            if output_format != "json":
                console.print("[dim]Dry-run mode. Use --apply to execute.[/dim]")
            return

        # Execute reconciliation
        if output_format != "json":
            console.print("[cyan]Applying reconciliation...[/cyan]")

        # Create synchronizer (would need GitHub/Jira clients for full implementation)
        synchronizer = StateSynchronizer(state)
        results = await synchronizer.apply_plan(recon_plan, run_state.id, dry_run=False)

        # Report results
        success_count = sum(1 for _, success, _ in results if success)
        fail_count = len(results) - success_count

        if output_format != "json":
            console.print(f"\n[green]✓ {success_count} action(s) completed[/green]")
            if fail_count > 0:
                console.print(f"[red]✗ {fail_count} action(s) failed[/red]")
                for action, success, error in results:
                    if not success:
                        console.print(f"  • {action.description}: {error}")


def register(app: typer.Typer) -> None:
    """Register the sync command on the given Typer app."""

    @app.command()
    def sync(
        run_id: Annotated[
            str | None,
            typer.Option("--run", "-r", help="Specific run ID to sync"),
        ] = None,
        apply: Annotated[
            bool,
            typer.Option("--apply", help="Execute reconciliation (default: dry-run)"),
        ] = False,
        direction: Annotated[
            str,
            typer.Option("--direction", "-d", help="Sync direction: from-tracker (default) or to-tracker"),
        ] = "from-tracker",
        output_format: Annotated[
            str,
            typer.Option("--format", "-f", help="Output format: text, json"),
        ] = "text",
    ) -> None:
        """Reconcile state drift between Debussy and issue trackers.

        By default, shows a reconciliation plan in dry-run mode.
        Use --apply to execute the reconciliation.

        Direction:
            from-tracker: Update Debussy state to match tracker (default, conservative)
            to-tracker: Push Debussy state to tracker (use when Debussy is correct)

        Examples:
            debussy sync                    # Show drift and reconciliation plan
            debussy sync --apply            # Execute reconciliation
            debussy sync --direction to-tracker --apply  # Force Debussy state to tracker
        """
        import asyncio

        orchestrator_dir = get_orchestrator_dir()
        state = StateManager(orchestrator_dir / "state.db")

        run_state = state.get_run(run_id) if run_id else state.get_current_run()

        if run_state is None:
            console.print("[yellow]No orchestration run found[/yellow]")
            return

        # Validate direction
        from debussy.core.models import SyncDirection

        try:
            sync_direction = SyncDirection(direction)
        except ValueError as e:
            console.print(f"[red]Invalid direction: {direction}[/red]")
            console.print("Use 'from-tracker' or 'to-tracker'")
            raise typer.Exit(1) from e

        asyncio.run(_sync_issues(run_state, state, sync_direction, apply, output_format))
