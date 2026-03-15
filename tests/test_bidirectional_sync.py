"""Integration tests for bidirectional sync CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from debussy.cli import app
from debussy.core.models import PhaseStatus, RunStatus

runner = CliRunner()


@pytest.fixture
def mock_run_state() -> MagicMock:
    """Create a mock run state."""
    run_state = MagicMock()
    run_state.id = "test-run"
    run_state.status = RunStatus.RUNNING
    run_state.master_plan_path = Path("test/MASTER_PLAN.md")
    run_state.started_at = MagicMock()
    run_state.started_at.strftime.return_value = "2024-01-15 10:00:00"
    run_state.completed_at = None
    run_state.current_phase = "1"
    run_state.phase_executions = []
    return run_state


@pytest.fixture
def mock_master_plan() -> MagicMock:
    """Create a mock master plan."""
    plan = MagicMock()
    plan.name = "Test Plan"
    plan.phases = [MagicMock(id="1", status=PhaseStatus.RUNNING)]
    plan.github_issues = [10, 11]
    plan.jira_issues = None
    plan.github_repo = "owner/repo"
    return plan


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_no_run_found(self) -> None:
        """Test status when no run exists."""
        with patch("debussy.cli.StateManager") as mock_sm:
            mock_sm.return_value.get_current_run.return_value = None

            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "No orchestration run found" in result.stdout

    def test_status_shows_run_info(self, mock_run_state: MagicMock) -> None:
        """Test status shows basic run information."""
        with patch("debussy.cli.StateManager") as mock_sm:
            mock_sm.return_value.get_current_run.return_value = mock_run_state

            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "test-run" in result.stdout
            assert "running" in result.stdout.lower()

    def test_status_with_issues_flag_no_issues(
        self,
        mock_run_state: MagicMock,
        mock_master_plan: MagicMock,
    ) -> None:
        """Test status --issues when plan has no linked issues."""
        mock_master_plan.github_issues = None
        mock_master_plan.jira_issues = None

        with (
            patch("debussy.cli.StateManager") as mock_sm,
            patch("debussy.commands.sync._display_issue_status"),
            patch("debussy.parsers.master.parse_master_plan") as mock_parse,
            patch("debussy.config.Config") as mock_config,
        ):
            mock_sm.return_value.get_current_run.return_value = mock_run_state
            mock_parse.return_value = mock_master_plan
            mock_config.load.return_value = MagicMock(jira=MagicMock(url=None))

            result = runner.invoke(app, ["status", "--issues"])

            # The async function should have been called
            assert result.exit_code == 0


class TestSyncCommand:
    """Tests for the sync command."""

    def test_sync_no_run_found(self) -> None:
        """Test sync when no run exists."""
        with patch("debussy.commands.sync.StateManager") as mock_sm:
            mock_sm.return_value.get_current_run.return_value = None

            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "No orchestration run found" in result.stdout

    def test_sync_invalid_direction(self, mock_run_state: MagicMock) -> None:
        """Test sync with invalid direction."""
        with patch("debussy.commands.sync.StateManager") as mock_sm:
            mock_sm.return_value.get_current_run.return_value = mock_run_state

            result = runner.invoke(app, ["sync", "--direction", "invalid"])

            assert result.exit_code == 1
            assert "Invalid direction" in result.stdout

    def test_sync_no_issues(
        self,
        mock_run_state: MagicMock,
        mock_master_plan: MagicMock,
    ) -> None:
        """Test sync when no issues linked."""
        mock_master_plan.github_issues = None
        mock_master_plan.jira_issues = None

        with (
            patch("debussy.commands.sync.StateManager") as mock_sm,
            patch("debussy.commands.sync._sync_issues"),
            patch("debussy.parsers.master.parse_master_plan") as mock_parse,
            patch("debussy.config.Config") as mock_config,
        ):
            mock_sm.return_value.get_current_run.return_value = mock_run_state
            mock_parse.return_value = mock_master_plan
            mock_config.load.return_value = MagicMock(jira=MagicMock(url=None))

            result = runner.invoke(app, ["sync"])

            # The async function should have been called
            assert result.exit_code == 0


class TestDriftModels:
    """Tests for drift-related models."""

    def test_drift_type_values(self) -> None:
        """Test DriftType enum values."""
        from debussy.core.models import DriftType

        assert DriftType.LABEL_MISMATCH.value == "label_mismatch"
        assert DriftType.STATUS_MISMATCH.value == "status_mismatch"
        assert DriftType.CLOSED_EXTERNALLY.value == "closed_externally"
        assert DriftType.REOPENED_EXTERNALLY.value == "reopened_externally"

    def test_sync_direction_values(self) -> None:
        """Test SyncDirection enum values."""
        from debussy.core.models import SyncDirection

        assert SyncDirection.FROM_TRACKER.value == "from-tracker"
        assert SyncDirection.TO_TRACKER.value == "to-tracker"

    def test_issue_status_model(self) -> None:
        """Test IssueStatus model creation."""
        from debussy.core.models import IssueStatus

        status = IssueStatus(
            id="10",
            platform="github",
            state="open",
            labels=["bug", "feature"],
            milestone="v1.0",
        )

        assert status.id == "10"
        assert status.platform == "github"
        assert status.state == "open"
        assert "bug" in status.labels

    def test_drift_report_model(self) -> None:
        """Test DriftReport model creation."""
        from debussy.core.models import DriftReport, DriftType

        report = DriftReport(
            issue_id="10",
            platform="github",
            expected_state="closed",
            actual_state="open",
            drift_type=DriftType.REOPENED_EXTERNALLY,
        )

        assert report.issue_id == "10"
        assert report.drift_type == DriftType.REOPENED_EXTERNALLY

    def test_reconciliation_action_model(self) -> None:
        """Test ReconciliationAction model creation."""
        from debussy.core.models import ReconciliationAction

        action = ReconciliationAction(
            issue_id="10",
            platform="github",
            action="update_phase_status",
            description="Mark phase completed",
            from_value="open",
            to_value="completed",
        )

        assert action.issue_id == "10"
        assert action.action == "update_phase_status"

    def test_reconciliation_plan_model(self) -> None:
        """Test ReconciliationPlan model creation."""
        from debussy.core.models import ReconciliationPlan, SyncDirection

        plan = ReconciliationPlan(
            direction=SyncDirection.FROM_TRACKER,
            actions=[],
            total_drift_count=0,
        )

        assert plan.direction == SyncDirection.FROM_TRACKER
        assert plan.total_drift_count == 0


class TestCacheIntegration:
    """Tests for cache behavior in status fetching."""

    @pytest.mark.asyncio
    async def test_cache_reduces_api_calls(self) -> None:
        """Test that caching reduces repeated API calls."""
        from unittest.mock import AsyncMock, patch

        from debussy.core.models import IssueStatus
        from debussy.sync.status_fetcher import IssueStatusFetcher

        with patch("debussy.sync.status_fetcher.GitHubClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            fetcher = IssueStatusFetcher(
                github_repo="owner/repo",
                github_token="test-token",
            )

            # Pre-populate cache
            for i in range(10):
                fetcher._cache.set(
                    IssueStatus(
                        id=str(i),
                        platform="github",
                        state="open",
                    )
                )

            async with fetcher:
                # All should come from cache
                result = await fetcher.fetch_github_status(
                    [str(i) for i in range(10)],
                    use_cache=True,
                )

            assert len(result) == 10
            # Verify no API calls were made
            mock_instance.get_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_freshness_reporting(self) -> None:
        """Test cache freshness tracking."""
        from debussy.core.models import IssueStatus
        from debussy.sync.status_fetcher import IssueStatusFetcher

        fetcher = IssueStatusFetcher()
        fetcher._cache.set(IssueStatus(id="10", platform="github", state="open"))

        freshness = fetcher.cache.freshness_seconds

        assert "github:10" in freshness
        assert freshness["github:10"] < 1  # Should be very fresh
