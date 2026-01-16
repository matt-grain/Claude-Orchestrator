"""Tests for GitHub issue synchronization.

Tests cover:
- GitHubClient: API wrapper, auth, rate limiting, retries
- LabelManager: Label lifecycle, atomic state transitions
- GitHubSyncCoordinator: Phase lifecycle hooks, issue parsing
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from debussy.config import GitHubLabelConfig, GitHubSyncConfig
from debussy.sync.github_client import (
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from debussy.sync.github_sync import GitHubSyncCoordinator
from debussy.sync.label_manager import LabelManager, LabelState

# =============================================================================
# GitHubClient Tests
# =============================================================================


class TestGitHubClientAuth:
    """Test GitHub client authentication."""

    def test_init_with_token_param(self) -> None:
        """Test initialization with explicit token."""
        client = GitHubClient("owner/repo", token="test-token")
        assert client._token == "test-token"
        assert client.repo == "owner/repo"

    def test_init_with_env_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with GITHUB_TOKEN env var."""
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        client = GitHubClient("owner/repo")
        assert client._token == "env-token"

    def test_init_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing token raises GitHubAuthError."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(GitHubAuthError, match="No GitHub token provided"):
            GitHubClient("owner/repo")

    def test_dry_run_mode(self) -> None:
        """Test dry run mode flag."""
        client = GitHubClient("owner/repo", token="test", dry_run=True)
        assert client.dry_run is True


class TestGitHubClientContext:
    """Test GitHub client context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self) -> None:
        """Test async context manager creates and closes client."""
        client = GitHubClient("owner/repo", token="test")

        assert client._client is None

        async with client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

        assert client._client is None

    def test_client_property_outside_context_raises(self) -> None:
        """Test accessing client outside context raises RuntimeError."""
        client = GitHubClient("owner/repo", token="test")
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            _ = client.client


class TestGitHubClientRequests:
    """Test GitHub client HTTP requests."""

    @pytest.mark.asyncio
    async def test_get_issue(self) -> None:
        """Test fetching a single issue."""
        mock_response = {
            "number": 42,
            "title": "Test Issue",
            "state": "open",
            "labels": [{"name": "bug"}],
            "milestone": {"number": 1, "title": "v1.0"},
            "html_url": "https://github.com/owner/repo/issues/42",
        }

        with patch.object(GitHubClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = GitHubClient("owner/repo", token="test")
            async with client:
                issue = await client.get_issue(42)

            assert issue.number == 42
            assert issue.title == "Test Issue"
            assert issue.state == "open"
            assert issue.labels == ["bug"]
            assert issue.milestone_number == 1
            assert issue.milestone_title == "v1.0"

    @pytest.mark.asyncio
    async def test_update_labels(self) -> None:
        """Test updating issue labels."""
        mock_response = {
            "labels": [{"name": "new-label"}],
        }

        with patch.object(GitHubClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = GitHubClient("owner/repo", token="test")
            async with client:
                labels = await client.update_labels(42, ["new-label"])

            assert labels == ["new-label"]
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_labels_dry_run(self) -> None:
        """Test that dry run mode logs but doesn't execute."""
        client = GitHubClient("owner/repo", token="test", dry_run=True)
        async with client:
            labels = await client.update_labels(42, ["new-label"])

        assert labels == ["new-label"]

    @pytest.mark.asyncio
    async def test_close_issue(self) -> None:
        """Test closing an issue with comment."""
        with patch.object(GitHubClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: {"id": 1})

            client = GitHubClient("owner/repo", token="test")
            async with client:
                result = await client.close_issue(42, comment="Done!")

            assert result is True
            # Should have been called twice: comment + close
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_close_issue_dry_run(self) -> None:
        """Test dry run doesn't close issue."""
        client = GitHubClient("owner/repo", token="test", dry_run=True)
        async with client:
            result = await client.close_issue(42, comment="Done!")

        assert result is True


class TestGitHubClientErrorHandling:
    """Test GitHub client error handling."""

    @pytest.mark.asyncio
    async def test_auth_error_401(self) -> None:
        """Test 401 response raises GitHubAuthError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = GitHubClient("owner/repo", token="bad-token")
            async with client:
                with pytest.raises(GitHubAuthError, match="authentication failed"):
                    await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_not_found_404(self) -> None:
        """Test 404 response raises GitHubNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = GitHubClient("owner/repo", token="test")
            async with client:
                with pytest.raises(GitHubNotFoundError, match="not found"):
                    await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_rate_limit_403(self) -> None:
        """Test rate limit response raises GitHubRateLimitError after retries."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1234567890",
        }

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = GitHubClient("owner/repo", token="test")
            async with client:
                with pytest.raises(GitHubRateLimitError, match="rate limit"):
                    await client._request("GET", "/test")


# =============================================================================
# LabelManager Tests
# =============================================================================


class TestLabelState:
    """Test LabelState dataclass."""

    def test_active_label_in_progress(self) -> None:
        """Test active_label returns in_progress when set."""
        config = GitHubLabelConfig()
        state = LabelState(in_progress=True)
        assert state.active_label(config) == config.in_progress

    def test_active_label_completed(self) -> None:
        """Test active_label returns completed when set."""
        config = GitHubLabelConfig()
        state = LabelState(completed=True)
        assert state.active_label(config) == config.completed

    def test_active_label_failed(self) -> None:
        """Test active_label returns failed when set."""
        config = GitHubLabelConfig()
        state = LabelState(failed=True)
        assert state.active_label(config) == config.failed

    def test_active_label_none(self) -> None:
        """Test active_label returns None when nothing set."""
        config = GitHubLabelConfig()
        state = LabelState()
        assert state.active_label(config) is None


class TestLabelManager:
    """Test LabelManager functionality."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock GitHub client."""
        client = MagicMock(spec=GitHubClient)
        client.get_issue = AsyncMock()
        client.update_labels = AsyncMock()
        client.ensure_label = AsyncMock()
        return client

    @pytest.fixture
    def label_config(self) -> GitHubLabelConfig:
        """Create default label config."""
        return GitHubLabelConfig()

    def test_get_debussy_labels(self, mock_client: MagicMock, label_config: GitHubLabelConfig) -> None:
        """Test getting list of Debussy labels."""
        manager = LabelManager(mock_client, label_config)
        labels = manager.get_debussy_labels()

        assert label_config.in_progress in labels
        assert label_config.completed in labels
        assert label_config.failed in labels

    def test_detect_state_in_progress(self, mock_client: MagicMock, label_config: GitHubLabelConfig) -> None:
        """Test detecting in_progress state from labels."""
        manager = LabelManager(mock_client, label_config)
        current_labels = [label_config.in_progress, "bug", "enhancement"]

        state = manager.detect_state(current_labels)

        assert state.in_progress is True
        assert state.completed is False
        assert state.failed is False

    def test_detect_state_no_debussy(self, mock_client: MagicMock, label_config: GitHubLabelConfig) -> None:
        """Test detecting no Debussy state."""
        manager = LabelManager(mock_client, label_config)
        current_labels = ["bug", "enhancement"]

        state = manager.detect_state(current_labels)

        assert state.in_progress is False
        assert state.completed is False
        assert state.failed is False

    @pytest.mark.asyncio
    async def test_set_in_progress(self, mock_client: MagicMock, label_config: GitHubLabelConfig) -> None:
        """Test setting in_progress state."""
        # Setup mock to return issue with existing labels
        mock_client.get_issue.return_value = MagicMock(labels=["bug", label_config.completed])
        mock_client.update_labels.return_value = ["bug", label_config.in_progress]

        manager = LabelManager(mock_client, label_config, create_if_missing=False)
        await manager.set_in_progress(42)

        # Should have removed completed and added in_progress
        mock_client.update_labels.assert_called_once()
        call_labels = mock_client.update_labels.call_args[0][1]
        assert label_config.completed not in call_labels
        assert label_config.in_progress in call_labels

    @pytest.mark.asyncio
    async def test_atomic_transition_removes_old_state(self, mock_client: MagicMock, label_config: GitHubLabelConfig) -> None:
        """Test that transitions atomically remove old state labels."""
        # Issue has both in_progress and failed (shouldn't happen, but test atomicity)
        mock_client.get_issue.return_value = MagicMock(labels=[label_config.in_progress, label_config.failed, "bug"])
        mock_client.update_labels.return_value = ["bug", label_config.completed]

        manager = LabelManager(mock_client, label_config, create_if_missing=False)
        await manager.set_completed(42)

        # Should have removed both in_progress and failed
        call_labels = mock_client.update_labels.call_args[0][1]
        assert label_config.in_progress not in call_labels
        assert label_config.failed not in call_labels
        assert label_config.completed in call_labels
        assert "bug" in call_labels  # Non-Debussy labels preserved


# =============================================================================
# GitHubSyncCoordinator Tests
# =============================================================================


class TestGitHubSyncCoordinator:
    """Test GitHubSyncCoordinator functionality."""

    @pytest.fixture
    def sync_config(self) -> GitHubSyncConfig:
        """Create default sync config."""
        return GitHubSyncConfig(enabled=True)

    def test_parse_github_issues_list(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing issue numbers from list."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues([10, 11, 12])
        assert issues == [10, 11, 12]

    def test_parse_github_issues_string_refs(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing issue numbers from string with refs."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues("#10, #11, #12")
        assert issues == [10, 11, 12]

    def test_parse_github_issues_gh_refs(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing gh# style refs."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues("gh#10, gh#11")
        assert issues == [10, 11]

    def test_parse_github_issues_urls(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing full GitHub URLs."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues("https://github.com/owner/repo/issues/10 and https://github.com/owner/repo/issues/11")
        assert issues == [10, 11]

    def test_parse_github_issues_mixed(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing mixed format refs."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues("#10, gh#11, https://github.com/owner/repo/issues/12")
        assert 10 in issues
        assert 11 in issues
        assert 12 in issues

    def test_parse_github_issues_none(self, sync_config: GitHubSyncConfig) -> None:
        """Test parsing None returns empty list."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        issues = coord.parse_github_issues(None)
        assert issues == []

    @pytest.mark.asyncio
    async def test_on_phase_start_updates_labels(self, sync_config: GitHubSyncConfig) -> None:
        """Test phase start sets in-progress label."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")

        # Mock the internal state
        coord._linked_issues = [10, 11]

        # Create mock label manager
        mock_label_manager = MagicMock()
        mock_label_manager.set_in_progress = AsyncMock(return_value=["debussy:in-progress"])
        coord._label_manager = mock_label_manager

        # Create mock phase
        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await coord.on_phase_start(mock_phase)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_label_manager.set_in_progress.call_count == 2

    @pytest.mark.asyncio
    async def test_on_phase_complete_updates_labels(self, sync_config: GitHubSyncConfig) -> None:
        """Test phase complete sets completed label."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        coord._linked_issues = [10]

        mock_label_manager = MagicMock()
        mock_label_manager.set_completed = AsyncMock(return_value=["debussy:completed"])
        coord._label_manager = mock_label_manager

        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await coord.on_phase_complete(mock_phase)

        assert len(results) == 1
        assert results[0].success
        mock_label_manager.set_completed.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_on_plan_complete_auto_close(self, sync_config: GitHubSyncConfig) -> None:
        """Test plan complete closes issues when auto_close enabled."""
        sync_config.auto_close = True
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        coord._linked_issues = [10]

        mock_client = MagicMock()
        mock_client.close_issue = AsyncMock(return_value=True)
        coord._client = mock_client

        results = await coord.on_plan_complete()

        assert len(results) == 1
        assert results[0].success
        mock_client.close_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_plan_complete_no_auto_close(self, sync_config: GitHubSyncConfig) -> None:
        """Test plan complete doesn't close issues when auto_close disabled."""
        sync_config.auto_close = False
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        coord._linked_issues = [10]

        mock_client = MagicMock()
        mock_client.close_issue = AsyncMock()
        coord._client = mock_client

        results = await coord.on_plan_complete()

        assert len(results) == 0
        mock_client.close_issue.assert_not_called()


class TestGitHubSyncMilestone:
    """Test milestone progress tracking."""

    @pytest.fixture
    def sync_config(self) -> GitHubSyncConfig:
        """Create default sync config."""
        return GitHubSyncConfig(enabled=True)

    @pytest.mark.asyncio
    async def test_update_milestone_progress(self, sync_config: GitHubSyncConfig) -> None:
        """Test milestone progress update."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        coord._milestone_number = 1

        mock_client = MagicMock()
        mock_client.get_milestone = AsyncMock(
            return_value=MagicMock(
                number=1,
                title="v1.0",
                description="Original description",
            )
        )
        mock_client.update_milestone_description = AsyncMock(
            return_value=MagicMock(
                number=1,
                title="v1.0",
                description="Updated",
            )
        )
        coord._client = mock_client

        result = await coord.update_milestone_progress(2, 4)

        assert result is not None
        assert result.success
        assert "50%" in result.message
        mock_client.update_milestone_description.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_milestone_progress_no_milestone(self, sync_config: GitHubSyncConfig) -> None:
        """Test milestone update skips when no milestone detected."""
        coord = GitHubSyncCoordinator("owner/repo", sync_config, token="test")
        coord._milestone_number = None

        result = await coord.update_milestone_progress(2, 4)

        assert result is None


# =============================================================================
# Integration Tests (using mocks)
# =============================================================================


class TestGitHubSyncIntegration:
    """Integration tests for the full sync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_flow(self) -> None:
        """Test complete sync flow from init to completion."""
        config = GitHubSyncConfig(enabled=True, auto_close=True)

        # Create coordinator
        coord = GitHubSyncCoordinator("owner/repo", config, token="test")

        # Mock client methods
        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(
            return_value=MagicMock(
                number=10,
                title="Test Issue",
                state="open",
                labels=[],
                milestone_number=1,
                milestone_title="v1.0",
            )
        )
        mock_client.update_labels = AsyncMock(return_value=["debussy:in-progress"])
        mock_client.close_issue = AsyncMock(return_value=True)
        mock_client.get_milestone = AsyncMock(
            return_value=MagicMock(
                number=1,
                title="v1.0",
                description="",
            )
        )
        mock_client.update_milestone_description = AsyncMock()
        mock_client.ensure_label = AsyncMock()

        coord._client = mock_client

        # Mock label manager
        mock_label_manager = MagicMock()
        mock_label_manager.set_in_progress = AsyncMock(return_value=["debussy:in-progress"])
        mock_label_manager.set_completed = AsyncMock(return_value=["debussy:completed"])
        mock_label_manager.ensure_labels_exist = AsyncMock()
        coord._label_manager = mock_label_manager

        # Initialize from plan
        valid_issues = await coord.initialize_from_plan("#10")
        assert valid_issues == [10]
        assert coord._milestone_number == 1

        # Phase start
        mock_phase = MagicMock(id="1")
        start_results = await coord.on_phase_start(mock_phase)
        assert len(start_results) == 1
        assert start_results[0].success

        # Phase complete
        complete_results = await coord.on_phase_complete(mock_phase)
        assert len(complete_results) == 1
        assert complete_results[0].success

        # Plan complete (auto-close)
        close_results = await coord.on_plan_complete()
        assert len(close_results) == 1
        mock_client.close_issue.assert_called_once()
