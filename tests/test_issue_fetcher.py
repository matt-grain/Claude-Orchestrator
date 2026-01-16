"""Unit tests for GitHub issue fetcher module."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from debussy.planners.github_fetcher import (
    GHAuthError,
    GHNotFoundError,
    GHRateLimitError,
    GHResult,
    _parse_gh_json,
    _run_gh_command,
    check_gh_available,
    fetch_issue_detail,
    fetch_issues_by_label,
    fetch_issues_by_labels,
    fetch_issues_by_milestone,
)
from debussy.planners.models import (
    GitHubIssue,
    IssueLabel,
    IssueMilestone,
    IssueSet,
)

# =============================================================================
# Model Tests
# =============================================================================


class TestGitHubIssue:
    """Tests for GitHubIssue dataclass."""

    def test_issue_creation_minimal(self) -> None:
        """Test creating an issue with minimal required fields."""
        issue = GitHubIssue(number=1, title="Test issue", body="Description")

        assert issue.number == 1
        assert issue.title == "Test issue"
        assert issue.body == "Description"
        assert issue.state == "OPEN"
        assert issue.labels == []
        assert issue.assignees == []
        assert issue.url == ""

    def test_issue_creation_full(self) -> None:
        """Test creating an issue with all fields."""
        milestone = IssueMilestone(title="v1.0", description="First release")
        labels = [IssueLabel(name="bug", description="Bug reports")]

        issue = GitHubIssue(
            number=42,
            title="Full issue",
            body="Full description",
            labels=labels,
            state="CLOSED",
            milestone=milestone,
            assignees=["alice", "bob"],
            url="https://github.com/owner/repo/issues/42",
        )

        assert issue.number == 42
        assert issue.state == "CLOSED"
        assert len(issue.labels) == 1
        assert issue.milestone is not None
        assert issue.milestone.title == "v1.0"
        assert issue.assignees == ["alice", "bob"]

    def test_issue_is_open_property(self) -> None:
        """Test the is_open property."""
        open_issue = GitHubIssue(number=1, title="Open", body="", state="OPEN")
        closed_issue = GitHubIssue(number=2, title="Closed", body="", state="CLOSED")
        lowercase_open = GitHubIssue(number=3, title="Open", body="", state="open")

        assert open_issue.is_open is True
        assert closed_issue.is_open is False
        assert lowercase_open.is_open is True

    def test_issue_is_closed_property(self) -> None:
        """Test the is_closed property."""
        open_issue = GitHubIssue(number=1, title="Open", body="", state="OPEN")
        closed_issue = GitHubIssue(number=2, title="Closed", body="", state="CLOSED")

        assert open_issue.is_closed is False
        assert closed_issue.is_closed is True

    def test_issue_label_names_property(self) -> None:
        """Test the label_names property."""
        labels = [
            IssueLabel(name="bug"),
            IssueLabel(name="enhancement"),
            IssueLabel(name="help wanted"),
        ]
        issue = GitHubIssue(number=1, title="Test", body="", labels=labels)

        assert issue.label_names == ["bug", "enhancement", "help wanted"]

    def test_issue_label_names_empty(self) -> None:
        """Test label_names with no labels."""
        issue = GitHubIssue(number=1, title="Test", body="")
        assert issue.label_names == []


class TestIssueSet:
    """Tests for IssueSet dataclass."""

    def test_issue_set_creation_empty(self) -> None:
        """Test creating an empty issue set."""
        issue_set = IssueSet()

        assert len(issue_set) == 0
        assert issue_set.source == ""
        assert issue_set.filter_used == ""

    def test_issue_set_with_issues(self) -> None:
        """Test creating an issue set with multiple issues."""
        issues = [
            GitHubIssue(number=1, title="Issue 1", body=""),
            GitHubIssue(number=2, title="Issue 2", body=""),
            GitHubIssue(number=3, title="Issue 3", body=""),
        ]

        issue_set = IssueSet(
            issues=issues,
            source="owner/repo",
            filter_used="milestone:v1.0",
        )

        assert len(issue_set) == 3
        assert issue_set.source == "owner/repo"
        assert issue_set.filter_used == "milestone:v1.0"

    def test_issue_set_iteration(self) -> None:
        """Test iterating over an issue set."""
        issues = [
            GitHubIssue(number=1, title="Issue 1", body=""),
            GitHubIssue(number=2, title="Issue 2", body=""),
        ]

        issue_set = IssueSet(issues=issues)
        numbers = [issue.number for issue in issue_set]

        assert numbers == [1, 2]

    def test_issue_set_open_closed_properties(self) -> None:
        """Test filtering open and closed issues."""
        issues = [
            GitHubIssue(number=1, title="Open 1", body="", state="OPEN"),
            GitHubIssue(number=2, title="Closed 1", body="", state="CLOSED"),
            GitHubIssue(number=3, title="Open 2", body="", state="OPEN"),
        ]

        issue_set = IssueSet(issues=issues)

        assert len(issue_set.open_issues) == 2
        assert len(issue_set.closed_issues) == 1
        assert all(i.is_open for i in issue_set.open_issues)
        assert all(i.is_closed for i in issue_set.closed_issues)


class TestIssueLabel:
    """Tests for IssueLabel dataclass."""

    def test_label_creation(self) -> None:
        """Test creating a label."""
        label = IssueLabel(name="bug", description="Bug reports")

        assert label.name == "bug"
        assert label.description == "Bug reports"

    def test_label_without_description(self) -> None:
        """Test creating a label without description."""
        label = IssueLabel(name="enhancement")

        assert label.name == "enhancement"
        assert label.description is None


class TestIssueMilestone:
    """Tests for IssueMilestone dataclass."""

    def test_milestone_creation(self) -> None:
        """Test creating a milestone."""
        due = datetime(2024, 12, 31)
        milestone = IssueMilestone(
            title="v1.0",
            description="First release",
            due_on=due,
        )

        assert milestone.title == "v1.0"
        assert milestone.description == "First release"
        assert milestone.due_on == due

    def test_milestone_without_due_date(self) -> None:
        """Test creating a milestone without due date."""
        milestone = IssueMilestone(title="Backlog")

        assert milestone.title == "Backlog"
        assert milestone.due_on is None


# =============================================================================
# Parsing Tests
# =============================================================================


class TestParseGHJson:
    """Tests for _parse_gh_json function."""

    def test_parse_empty_json(self) -> None:
        """Test parsing empty JSON array."""
        result = _parse_gh_json("[]", source="test/repo")

        assert len(result) == 0
        assert result.source == "test/repo"

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        result = _parse_gh_json("", source="test/repo")

        assert len(result) == 0

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON returns empty set."""
        result = _parse_gh_json("not valid json")

        assert len(result) == 0

    def test_parse_single_issue(self) -> None:
        """Test parsing a single issue."""
        json_data = json.dumps(
            [
                {
                    "number": 4,
                    "title": "Test Issue",
                    "body": "Issue body content",
                    "labels": [{"name": "bug", "description": "Bug reports"}],
                    "state": "OPEN",
                    "milestone": {"title": "v1.0", "description": "First release"},
                    "assignees": [{"login": "alice"}],
                    "url": "https://github.com/owner/repo/issues/4",
                }
            ]
        )

        result = _parse_gh_json(json_data, source="owner/repo", filter_used="all")

        assert len(result) == 1
        issue = result.issues[0]
        assert issue.number == 4
        assert issue.title == "Test Issue"
        assert issue.body == "Issue body content"
        assert len(issue.labels) == 1
        assert issue.labels[0].name == "bug"
        assert issue.state == "OPEN"
        assert issue.milestone is not None
        assert issue.milestone.title == "v1.0"
        assert issue.assignees == ["alice"]
        assert issue.url == "https://github.com/owner/repo/issues/4"

    def test_parse_multiple_issues(self) -> None:
        """Test parsing multiple issues."""
        json_data = json.dumps(
            [
                {"number": 1, "title": "First", "body": "", "labels": [], "state": "OPEN", "milestone": None, "assignees": [], "url": ""},
                {"number": 2, "title": "Second", "body": "", "labels": [], "state": "CLOSED", "milestone": None, "assignees": [], "url": ""},
                {"number": 3, "title": "Third", "body": "", "labels": [], "state": "OPEN", "milestone": None, "assignees": [], "url": ""},
            ]
        )

        result = _parse_gh_json(json_data)

        assert len(result) == 3
        assert result.issues[0].number == 1
        assert result.issues[1].number == 2
        assert result.issues[2].number == 3

    def test_parse_issue_with_null_body(self) -> None:
        """Test parsing issue where body is null."""
        json_data = json.dumps([{"number": 1, "title": "No body", "body": None, "labels": [], "state": "OPEN", "milestone": None, "assignees": [], "url": ""}])

        result = _parse_gh_json(json_data)

        assert len(result) == 1
        assert result.issues[0].body == ""

    def test_parse_milestone_with_due_date(self) -> None:
        """Test parsing milestone with ISO format due date."""
        json_data = json.dumps(
            [
                {
                    "number": 1,
                    "title": "Test",
                    "body": "",
                    "labels": [],
                    "state": "OPEN",
                    "milestone": {
                        "title": "v1.0",
                        "description": None,
                        "dueOn": "2024-12-31T00:00:00Z",
                    },
                    "assignees": [],
                    "url": "",
                }
            ]
        )

        result = _parse_gh_json(json_data)

        assert result.issues[0].milestone is not None
        assert result.issues[0].milestone.due_on is not None

    def test_parse_large_issue_count_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that fetching >20 issues logs a warning."""
        issues = [{"number": i, "title": f"Issue {i}", "body": "", "labels": [], "state": "OPEN", "milestone": None, "assignees": [], "url": ""} for i in range(25)]
        json_data = json.dumps(issues)

        _parse_gh_json(json_data)

        assert "Fetched 25 issues" in caplog.text
        assert ">20" in caplog.text


# =============================================================================
# Check GH Available Tests
# =============================================================================


class TestCheckGHAvailable:
    """Tests for check_gh_available function."""

    def test_gh_available_when_installed(self) -> None:
        """Test that check_gh_available returns True when gh is found."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            assert check_gh_available() is True

    def test_gh_not_available(self) -> None:
        """Test that check_gh_available returns False when gh is not found."""
        with patch("shutil.which", return_value=None):
            assert check_gh_available() is False


# =============================================================================
# Async Command Runner Tests
# =============================================================================


class TestRunGHCommand:
    """Tests for _run_gh_command function."""

    @pytest.mark.asyncio
    async def test_gh_not_found_raises_error(self) -> None:
        """Test that GHNotFoundError is raised when gh is not installed."""
        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=False), pytest.raises(GHNotFoundError):
            await _run_gh_command(["issue", "list"])

    @pytest.mark.asyncio
    async def test_auth_error_raises_ghautherror(self) -> None:
        """Test that GHAuthError is raised on auth failures."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"authentication required: not logged in")
        mock_process.returncode = 1

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process), pytest.raises(GHAuthError):
            await _run_gh_command(["issue", "list"])

    @pytest.mark.asyncio
    async def test_rate_limit_error_raises_ghratelimiterror(self) -> None:
        """Test that GHRateLimitError is raised on rate limit."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"API rate limit exceeded")
        mock_process.returncode = 1

        with (
            patch("debussy.planners.github_fetcher.check_gh_available", return_value=True),
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            pytest.raises(GHRateLimitError),
        ):
            await _run_gh_command(["issue", "list"])

    @pytest.mark.asyncio
    async def test_successful_command(self) -> None:
        """Test successful command execution."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'[{"number": 1}]', b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await _run_gh_command(["issue", "list"])

            assert result.success is True
            assert result.stdout == '[{"number": 1}]'
            assert result.stderr == ""


# =============================================================================
# Fetcher Function Tests
# =============================================================================


class TestFetchIssuesByMilestone:
    """Tests for fetch_issues_by_milestone function."""

    @pytest.mark.asyncio
    async def test_fetch_by_milestone_success(self) -> None:
        """Test fetching issues by milestone."""
        mock_json = json.dumps([{"number": 1, "title": "Issue 1", "body": "", "labels": [], "state": "OPEN", "milestone": {"title": "v1.0"}, "assignees": [], "url": ""}])

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (mock_json.encode(), b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await fetch_issues_by_milestone("owner/repo", "v1.0")

            assert len(result) == 1
            assert result.source == "owner/repo"
            assert "milestone:v1.0" in result.filter_used

    @pytest.mark.asyncio
    async def test_fetch_by_milestone_with_state(self) -> None:
        """Test fetching issues by milestone with state filter."""
        mock_json = json.dumps([])

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (mock_json.encode(), b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await fetch_issues_by_milestone("owner/repo", "v1.0", state="closed")

            # Check that --state closed was passed
            call_args = mock_exec.call_args[0]
            assert "--state" in call_args
            state_idx = call_args.index("--state")
            assert call_args[state_idx + 1] == "closed"


class TestFetchIssuesByLabel:
    """Tests for fetch_issues_by_label function."""

    @pytest.mark.asyncio
    async def test_fetch_by_label_success(self) -> None:
        """Test fetching issues by label."""
        mock_json = json.dumps([{"number": 1, "title": "Bug", "body": "", "labels": [{"name": "bug"}], "state": "OPEN", "milestone": None, "assignees": [], "url": ""}])

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (mock_json.encode(), b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await fetch_issues_by_label("owner/repo", "bug")

            assert len(result) == 1
            assert "label:bug" in result.filter_used


class TestFetchIssuesByLabels:
    """Tests for fetch_issues_by_labels function."""

    @pytest.mark.asyncio
    async def test_fetch_by_multiple_labels(self) -> None:
        """Test fetching issues with multiple labels (AND logic)."""
        mock_json = json.dumps([{"number": 1, "title": "Important bug", "body": "", "labels": [{"name": "bug"}, {"name": "priority"}], "state": "OPEN", "milestone": None, "assignees": [], "url": ""}])

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (mock_json.encode(), b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await fetch_issues_by_labels("owner/repo", ["bug", "priority"])

            assert len(result) == 1
            assert "labels:bug,priority" in result.filter_used

            # Verify multiple --label flags were passed
            call_args = mock_exec.call_args[0]
            label_count = call_args.count("--label")
            assert label_count == 2

    @pytest.mark.asyncio
    async def test_fetch_by_empty_labels(self) -> None:
        """Test fetching with empty labels list returns empty set."""
        result = await fetch_issues_by_labels("owner/repo", [])

        assert len(result) == 0
        assert "labels:[]" in result.filter_used


class TestFetchIssueDetail:
    """Tests for fetch_issue_detail function."""

    @pytest.mark.asyncio
    async def test_fetch_single_issue(self) -> None:
        """Test fetching details of a single issue."""
        mock_json = json.dumps(
            {
                "number": 42,
                "title": "Specific Issue",
                "body": "Detailed description",
                "labels": [{"name": "feature"}],
                "state": "OPEN",
                "milestone": {"title": "v2.0"},
                "assignees": [{"login": "dev"}],
                "url": "https://github.com/owner/repo/issues/42",
            }
        )

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (mock_json.encode(), b"")
        mock_process.returncode = 0

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            issue = await fetch_issue_detail("owner/repo", 42)

            assert issue is not None
            assert issue.number == 42
            assert issue.title == "Specific Issue"
            assert issue.body == "Detailed description"
            assert len(issue.labels) == 1
            assert issue.labels[0].name == "feature"

    @pytest.mark.asyncio
    async def test_fetch_nonexistent_issue(self) -> None:
        """Test fetching a non-existent issue returns None."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"issue not found")
        mock_process.returncode = 1

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            issue = await fetch_issue_detail("owner/repo", 99999)

            assert issue is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error conditions and edge cases."""

    @pytest.mark.asyncio
    async def test_gh_command_failure_returns_empty_set(self) -> None:
        """Test that command failures return empty issue sets."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"some error")
        mock_process.returncode = 1

        with patch("debussy.planners.github_fetcher.check_gh_available", return_value=True), patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # Milestone fetch should return empty set on non-auth errors
            result = await fetch_issues_by_milestone("owner/repo", "v1.0")
            assert len(result) == 0

    def test_gh_result_success_property(self) -> None:
        """Test GHResult success property."""
        success = GHResult(stdout="output", stderr="", returncode=0)
        failure = GHResult(stdout="", stderr="error", returncode=1)

        assert success.success is True
        assert failure.success is False
