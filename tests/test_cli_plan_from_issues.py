"""Unit tests for the plan-from-issues CLI command and command module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from debussy.planners.command import (
    PlanFromIssuesResult,
    _analyze_phase,
    _audit_loop,
    _fetch_phase,
    _generate_phase,
    _get_audit_errors,
    _get_current_repo,
    plan_from_issues,
)
from debussy.planners.models import GitHubIssue, IssueSet

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_console() -> Console:
    """Create a mock console for testing."""
    return Console(force_terminal=False, quiet=True)


@pytest.fixture
def sample_issue() -> GitHubIssue:
    """Create a sample GitHub issue for testing."""
    return GitHubIssue(
        number=1,
        title="Add user authentication",
        body="""## Problem

We need user authentication.

## Acceptance Criteria

- [ ] Users can log in
- [ ] Users can log out

## Testing

- Unit tests with pytest
""",
    )


@pytest.fixture
def sample_issue_set(sample_issue: GitHubIssue) -> IssueSet:
    """Create a sample issue set for testing."""
    return IssueSet(
        issues=[sample_issue],
        source="test/repo",
        filter_used="milestone:v1.0",
    )


@pytest.fixture
def mock_audit_result_pass() -> MagicMock:
    """Create a mock passing audit result."""
    result = MagicMock()
    result.passed = True
    result.issues = []
    result.summary = MagicMock()
    result.summary.errors = 0
    result.summary.warnings = 0
    return result


@pytest.fixture
def mock_audit_result_fail() -> MagicMock:
    """Create a mock failing audit result."""
    from debussy.core.audit import AuditIssue, AuditSeverity

    result = MagicMock()
    result.passed = False
    result.issues = [
        AuditIssue(
            severity=AuditSeverity.ERROR,
            code="MISSING_GATES",
            message="Phase 1 has no gates defined",
            location="phase-1.md",
            suggestion="Add gates",
        ),
    ]
    result.summary = MagicMock()
    result.summary.errors = 1
    result.summary.warnings = 0
    return result


# =============================================================================
# Test PlanFromIssuesResult Dataclass
# =============================================================================


class TestPlanFromIssuesResult:
    """Test the PlanFromIssuesResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = PlanFromIssuesResult()
        assert result.success is False
        assert result.files_created == []
        assert result.audit_passed is False
        assert result.audit_attempts == 0
        assert result.issues_fetched == 0
        assert result.gaps_found == 0
        assert result.questions_asked == 0
        assert result.error_message is None

    def test_custom_values(self) -> None:
        """Test custom values can be set."""
        result = PlanFromIssuesResult(
            success=True,
            files_created=["MASTER_PLAN.md", "phase-1.md"],
            audit_passed=True,
            audit_attempts=2,
            issues_fetched=5,
            gaps_found=3,
            questions_asked=2,
        )
        assert result.success is True
        assert len(result.files_created) == 2
        assert result.audit_attempts == 2


# =============================================================================
# Test _get_current_repo
# =============================================================================


class TestGetCurrentRepo:
    """Test the _get_current_repo function."""

    def test_returns_none_on_failure(self) -> None:
        """Test that function returns None when git command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = _get_current_repo()
            assert result is None

    def test_parses_ssh_url(self) -> None:
        """Test parsing of SSH git URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="git@github.com:owner/repo.git\n",
            )
            result = _get_current_repo()
            assert result == "owner/repo"

    def test_parses_https_url(self) -> None:
        """Test parsing of HTTPS git URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo.git\n",
            )
            result = _get_current_repo()
            assert result == "owner/repo"

    def test_handles_timeout(self) -> None:
        """Test that timeout exception is handled."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("timeout")
            result = _get_current_repo()
            assert result is None


# =============================================================================
# Test _fetch_phase
# =============================================================================


class TestFetchPhase:
    """Test the _fetch_phase function."""

    def test_fetch_by_milestone(self, mock_console: Console, sample_issue_set: IssueSet) -> None:
        """Test fetching issues by milestone."""
        with patch("debussy.planners.command.asyncio.run") as mock_run:
            mock_run.return_value = sample_issue_set

            result = _fetch_phase(
                repo="owner/repo",
                milestone="v1.0",
                labels=None,
                console=mock_console,
                verbose=False,
            )

            assert len(result.issues) == 1
            mock_run.assert_called_once()

    def test_fetch_by_labels(self, mock_console: Console, sample_issue_set: IssueSet) -> None:
        """Test fetching issues by labels."""
        with patch("debussy.planners.command.asyncio.run") as mock_run:
            mock_run.return_value = sample_issue_set

            result = _fetch_phase(
                repo="owner/repo",
                milestone=None,
                labels=["feature", "auth"],
                console=mock_console,
                verbose=False,
            )

            assert len(result.issues) == 1


# =============================================================================
# Test _analyze_phase
# =============================================================================


class TestAnalyzePhase:
    """Test the _analyze_phase function."""

    def test_analyze_returns_report(self, mock_console: Console, sample_issue_set: IssueSet) -> None:
        """Test that analyze phase returns an analysis report."""
        report = _analyze_phase(sample_issue_set, mock_console, verbose=False)

        assert len(report.issues) == 1
        # Sample issue has good structure, so should have some score
        assert report.average_score > 0

    def test_analyze_empty_set(self, mock_console: Console) -> None:
        """Test analyzing an empty issue set."""
        empty_set = IssueSet(issues=[])
        report = _analyze_phase(empty_set, mock_console, verbose=False)

        assert len(report.issues) == 0
        assert report.total_gaps == 0


# =============================================================================
# Test _generate_phase
# =============================================================================


class TestGeneratePhase:
    """Test the _generate_phase function."""

    def test_generate_creates_files(
        self,
        mock_console: Console,
        sample_issue_set: IssueSet,
        tmp_path: Path,
    ) -> None:
        """Test that generate phase creates plan files."""
        from debussy.planners.analyzer import AnalysisReport

        mock_analysis = AnalysisReport(issues=[])

        with patch("debussy.planners.plan_builder.PlanBuilder") as mock_builder:
            mock_instance = MagicMock()
            mock_instance.generate_all.return_value = {
                "MASTER_PLAN.md": "# Master Plan",
                "phase-1.md": "# Phase 1",
            }
            mock_builder.return_value = mock_instance

            output_dir = tmp_path / "plans"
            files = _generate_phase(
                issues=sample_issue_set,
                analysis=mock_analysis,
                answers={},
                output_dir=output_dir,
                model="haiku",
                timeout=120,
                console=mock_console,
                verbose=False,
            )

            assert len(files) == 2
            assert (output_dir / "MASTER_PLAN.md").exists()
            assert (output_dir / "phase-1.md").exists()


# =============================================================================
# Test _audit_loop
# =============================================================================


class TestAuditLoop:
    """Test the _audit_loop function."""

    def test_audit_passes_first_try(
        self,
        mock_console: Console,
        mock_audit_result_pass: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test audit loop passes on first attempt."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        (output_dir / "MASTER_PLAN.md").write_text("# Plan")

        with patch("debussy.planners.command._run_audit") as mock_run_audit:
            mock_run_audit.return_value = mock_audit_result_pass

            passed, attempts = _audit_loop(
                output_dir=output_dir,
                max_retries=3,
                console=mock_console,
                verbose=False,
            )

            assert passed is True
            assert attempts == 1

    def test_audit_fails_all_retries(
        self,
        mock_console: Console,
        mock_audit_result_fail: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test audit loop fails after all retries."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        (output_dir / "MASTER_PLAN.md").write_text("# Plan")

        with patch("debussy.planners.command._run_audit") as mock_run_audit, patch("debussy.planners.command._regenerate_with_errors"):
            mock_run_audit.return_value = mock_audit_result_fail

            passed, attempts = _audit_loop(
                output_dir=output_dir,
                max_retries=3,
                console=mock_console,
                verbose=False,
            )

            assert passed is False
            assert attempts == 3

    def test_audit_succeeds_on_retry(
        self,
        mock_console: Console,
        mock_audit_result_pass: MagicMock,
        mock_audit_result_fail: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test audit passes on second try after regeneration."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        (output_dir / "MASTER_PLAN.md").write_text("# Plan")

        with patch("debussy.planners.command._run_audit") as mock_run_audit, patch("debussy.planners.command._regenerate_with_errors"):
            # First call fails, second succeeds
            mock_run_audit.side_effect = [mock_audit_result_fail, mock_audit_result_pass]

            passed, attempts = _audit_loop(
                output_dir=output_dir,
                max_retries=3,
                console=mock_console,
                verbose=False,
            )

            assert passed is True
            assert attempts == 2


# =============================================================================
# Test _get_audit_errors
# =============================================================================


class TestGetAuditErrors:
    """Test the _get_audit_errors function."""

    def test_extracts_error_messages(self, mock_audit_result_fail: MagicMock) -> None:
        """Test that error messages are extracted correctly."""
        errors = _get_audit_errors(mock_audit_result_fail)

        assert len(errors) == 1
        assert "MISSING_GATES" in errors[0]
        assert "Phase 1" in errors[0]

    def test_empty_list_on_pass(self, mock_audit_result_pass: MagicMock) -> None:
        """Test that passing audit returns empty list."""
        errors = _get_audit_errors(mock_audit_result_pass)
        assert errors == []


# =============================================================================
# Test plan_from_issues Main Function
# =============================================================================


class TestPlanFromIssues:
    """Test the main plan_from_issues function."""

    def test_jira_source_not_implemented(self, mock_console: Console) -> None:
        """Test that jira source returns error."""
        result = plan_from_issues(
            source="jira",  # type: ignore
            console=mock_console,
        )

        assert result.success is False
        assert "jira" in result.error_message.lower()

    def test_no_repo_detected(self, mock_console: Console) -> None:
        """Test error when repo cannot be detected."""
        with patch("debussy.planners.command._get_current_repo") as mock_get_repo:
            mock_get_repo.return_value = None

            result = plan_from_issues(
                source="gh",
                repo=None,
                console=mock_console,
            )

            assert result.success is False
            assert "repository" in result.error_message.lower()

    def test_no_issues_found(self, mock_console: Console) -> None:
        """Test handling when no issues are found."""
        empty_set = IssueSet(issues=[])

        with patch("debussy.planners.command._fetch_phase") as mock_fetch:
            mock_fetch.return_value = empty_set

            result = plan_from_issues(
                source="gh",
                repo="owner/repo",
                milestone="v1.0",
                console=mock_console,
            )

            assert result.success is False
            assert "no issues" in result.error_message.lower()

    def test_skip_qa_flag(
        self,
        mock_console: Console,
        sample_issue_set: IssueSet,
        tmp_path: Path,
    ) -> None:
        """Test that --skip-qa skips the Q&A phase."""
        from debussy.planners.analyzer import AnalysisReport, IssueQuality

        mock_analysis = AnalysisReport(issues=[IssueQuality(issue_number=1, score=50, gaps=[])])

        with (
            patch("debussy.planners.command._fetch_phase") as mock_fetch,
            patch("debussy.planners.command._analyze_phase") as mock_analyze,
            patch("debussy.planners.command._generate_phase") as mock_generate,
            patch("debussy.planners.command._audit_loop") as mock_audit,
        ):
            mock_fetch.return_value = sample_issue_set
            mock_analyze.return_value = mock_analysis
            mock_generate.return_value = ["MASTER_PLAN.md"]
            mock_audit.return_value = (True, 1)

            result = plan_from_issues(
                source="gh",
                repo="owner/repo",
                milestone="v1.0",
                skip_qa=True,
                output_dir=tmp_path / "plans",
                console=mock_console,
            )

            assert result.success is True
            assert result.questions_asked == 0

    def test_full_pipeline_success(
        self,
        mock_console: Console,
        sample_issue_set: IssueSet,
        tmp_path: Path,
    ) -> None:
        """Test successful full pipeline execution."""
        from debussy.planners.analyzer import AnalysisReport, IssueQuality

        mock_analysis = AnalysisReport(issues=[IssueQuality(issue_number=1, score=80, gaps=[])])

        with (
            patch("debussy.planners.command._fetch_phase") as mock_fetch,
            patch("debussy.planners.command._analyze_phase") as mock_analyze,
            patch("debussy.planners.command._generate_phase") as mock_generate,
            patch("debussy.planners.command._audit_loop") as mock_audit,
        ):
            mock_fetch.return_value = sample_issue_set
            mock_analyze.return_value = mock_analysis
            mock_generate.return_value = ["MASTER_PLAN.md", "phase-1.md"]
            mock_audit.return_value = (True, 1)

            result = plan_from_issues(
                source="gh",
                repo="owner/repo",
                milestone="v1.0",
                skip_qa=True,
                output_dir=tmp_path / "plans",
                console=mock_console,
            )

            assert result.success is True
            assert result.issues_fetched == 1
            assert len(result.files_created) == 2
            assert result.audit_passed is True


# =============================================================================
# Test CLI Integration
# =============================================================================


class TestCLIIntegration:
    """Test CLI command integration."""

    def test_cli_help(self) -> None:
        """Test that CLI shows help for plan-from-issues command."""
        import re

        from typer.testing import CliRunner

        from debussy.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan-from-issues", "--help"])

        # Strip ANSI codes for reliable string matching
        output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)

        assert result.exit_code == 0
        assert "plan-from-issues" in output.lower() or "issues" in output.lower()
        assert "--source" in output
        assert "--milestone" in output
        assert "--label" in output

    def test_cli_invalid_source(self) -> None:
        """Test CLI rejects invalid source."""
        from typer.testing import CliRunner

        from debussy.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan-from-issues", "--source", "invalid"])

        assert result.exit_code == 1

    def test_cli_jira_not_implemented(self) -> None:
        """Test CLI shows error for jira source."""
        from typer.testing import CliRunner

        from debussy.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan-from-issues", "--source", "jira"])

        assert result.exit_code == 1
        assert "not" in result.output.lower() or "implement" in result.output.lower()


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_fetch_exception_handling(self, mock_console: Console) -> None:
        """Test handling of fetch phase exceptions."""
        with patch("debussy.planners.command._fetch_phase") as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            result = plan_from_issues(
                source="gh",
                repo="owner/repo",
                console=mock_console,
            )

            assert result.success is False
            assert "fetch" in result.error_message.lower()

    def test_output_dir_creation(
        self,
        mock_console: Console,
        sample_issue_set: IssueSet,
        tmp_path: Path,
    ) -> None:
        """Test that output directory is created if it doesn't exist."""
        from debussy.planners.analyzer import AnalysisReport

        mock_analysis = AnalysisReport(issues=[])

        with patch("debussy.planners.plan_builder.PlanBuilder") as mock_builder:
            mock_instance = MagicMock()
            mock_instance.generate_all.return_value = {"MASTER_PLAN.md": "# Plan"}
            mock_builder.return_value = mock_instance

            output_dir = tmp_path / "new" / "nested" / "path"
            assert not output_dir.exists()

            _generate_phase(
                issues=sample_issue_set,
                analysis=mock_analysis,
                answers={},
                output_dir=output_dir,
                model="haiku",
                timeout=120,
                console=mock_console,
                verbose=False,
            )

            assert output_dir.exists()

    def test_default_output_dir_from_milestone(
        self,
        mock_console: Console,
        sample_issue_set: IssueSet,
    ) -> None:
        """Test that output directory is derived from milestone."""
        from debussy.planners.analyzer import AnalysisReport, IssueQuality

        mock_analysis = AnalysisReport(issues=[IssueQuality(issue_number=1, score=80, gaps=[])])

        with (
            patch("debussy.planners.command._fetch_phase") as mock_fetch,
            patch("debussy.planners.command._analyze_phase") as mock_analyze,
            patch("debussy.planners.command._generate_phase") as mock_generate,
            patch("debussy.planners.command._audit_loop") as mock_audit,
        ):
            mock_fetch.return_value = sample_issue_set
            mock_analyze.return_value = mock_analysis
            mock_generate.return_value = []
            mock_audit.return_value = (True, 1)

            # Don't specify output_dir, milestone is "v2.0"
            plan_from_issues(
                source="gh",
                repo="owner/repo",
                milestone="v2.0",
                skip_qa=True,
                output_dir=None,  # Let it derive from milestone
                console=mock_console,
            )

            # Check that _generate_phase was called with derived path
            call_args = mock_generate.call_args
            assert call_args is not None
            # output_dir is the 4th positional argument (index 3)
            output_dir_arg = call_args[0][3]
            assert "v2.0" in str(output_dir_arg).lower()
