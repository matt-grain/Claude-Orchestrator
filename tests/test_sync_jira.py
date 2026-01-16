"""Tests for Jira issue synchronization.

Tests cover:
- JiraClient: API wrapper, auth, rate limiting, retries
- JiraSynchronizer: Phase lifecycle hooks, issue parsing
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from debussy.config import JiraConfig, JiraTransitionConfig
from debussy.sync.jira_client import (
    JiraAuthError,
    JiraClient,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraTransitionError,
)
from debussy.sync.jira_sync import JIRA_ISSUE_PATTERN, JiraSynchronizer

# =============================================================================
# JiraClient Tests
# =============================================================================


class TestJiraClientAuth:
    """Test Jira client authentication."""

    def test_init_with_token_param(self) -> None:
        """Test initialization with explicit token and email."""
        client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test-token")
        assert client._token == "test-token"
        assert client._email == "test@example.com"
        assert client.base_url == "https://test.atlassian.net"

    def test_init_normalizes_trailing_slash(self) -> None:
        """Test that trailing slash is normalized."""
        client = JiraClient("https://test.atlassian.net/", email="test@example.com", token="test-token")
        assert client.base_url == "https://test.atlassian.net"

    def test_init_with_env_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with JIRA_API_TOKEN and JIRA_EMAIL env vars."""
        monkeypatch.setenv("JIRA_API_TOKEN", "env-token")
        monkeypatch.setenv("JIRA_EMAIL", "env@example.com")
        client = JiraClient("https://test.atlassian.net")
        assert client._token == "env-token"
        assert client._email == "env@example.com"

    def test_init_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing token raises JiraAuthError."""
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
        with pytest.raises(JiraAuthError, match="No Jira API token provided"):
            JiraClient("https://test.atlassian.net")

    def test_init_missing_email_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing email raises JiraAuthError."""
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.delenv("JIRA_EMAIL", raising=False)
        with pytest.raises(JiraAuthError, match="No Jira email provided"):
            JiraClient("https://test.atlassian.net")

    def test_dry_run_mode(self) -> None:
        """Test dry run mode flag."""
        client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test", dry_run=True)
        assert client.dry_run is True


class TestJiraClientContext:
    """Test Jira client context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self) -> None:
        """Test async context manager creates and closes client."""
        client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")

        assert client._client is None

        async with client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

        assert client._client is None

    def test_client_property_outside_context_raises(self) -> None:
        """Test accessing client outside context raises RuntimeError."""
        client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            _ = client.client


class TestJiraClientRequests:
    """Test Jira client HTTP requests."""

    @pytest.mark.asyncio
    async def test_get_issue(self) -> None:
        """Test fetching a single issue."""
        mock_response = {
            "key": "PROJ-123",
            "fields": {
                "summary": "Test Issue",
                "status": {"name": "To Do"},
                "project": {"key": "PROJ"},
            },
        }

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                issue = await client.get_issue("PROJ-123")

            assert issue.key == "PROJ-123"
            assert issue.summary == "Test Issue"
            assert issue.status == "To Do"
            assert issue.project_key == "PROJ"
            assert "browse/PROJ-123" in issue.url

    @pytest.mark.asyncio
    async def test_get_transitions(self) -> None:
        """Test fetching available transitions."""
        mock_response = {
            "transitions": [
                {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Done", "to": {"name": "Done"}},
            ]
        }

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                transitions = await client.get_transitions("PROJ-123")

            assert len(transitions) == 2
            assert transitions[0].id == "11"
            assert transitions[0].name == "In Progress"
            assert transitions[1].name == "Done"

    @pytest.mark.asyncio
    async def test_get_transitions_caching(self) -> None:
        """Test that transitions are cached."""
        mock_response = {
            "transitions": [
                {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
            ]
        }

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                # First call
                await client.get_transitions("PROJ-123")
                # Second call should use cache
                await client.get_transitions("PROJ-123")

            # Should only make one request
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_get_transitions_bypass_cache(self) -> None:
        """Test that cache can be bypassed."""
        mock_response = {
            "transitions": [
                {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
            ]
        }

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                await client.get_transitions("PROJ-123")
                await client.get_transitions("PROJ-123", use_cache=False)

            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_find_transition_by_name(self) -> None:
        """Test finding transition by name (case-insensitive)."""
        mock_response = {
            "transitions": [
                {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Done", "to": {"name": "Done"}},
            ]
        }

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                # Case insensitive match
                transition = await client.find_transition_by_name("PROJ-123", "in progress")

            assert transition is not None
            assert transition.id == "11"

    @pytest.mark.asyncio
    async def test_find_transition_by_name_not_found(self) -> None:
        """Test finding non-existent transition returns None."""
        mock_response = {"transitions": [{"id": "11", "name": "Done", "to": {"name": "Done"}}]}

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_response)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                transition = await client.find_transition_by_name("PROJ-123", "nonexistent")

            assert transition is None

    @pytest.mark.asyncio
    async def test_perform_transition(self) -> None:
        """Test performing a transition."""
        mock_transitions = {"transitions": [{"id": "11", "name": "In Progress", "to": {"name": "In Progress"}}]}

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_transitions)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                result = await client.perform_transition("PROJ-123", "In Progress")

            assert result is True
            # Should have made 2 calls: get transitions + perform transition
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_perform_transition_not_available(self) -> None:
        """Test that unavailable transition raises JiraTransitionError."""
        mock_transitions = {"transitions": [{"id": "11", "name": "Done", "to": {"name": "Done"}}]}

        with patch.object(JiraClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = MagicMock(json=lambda: mock_transitions)

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                with pytest.raises(JiraTransitionError, match="not available"):
                    await client.perform_transition("PROJ-123", "In Progress")

    @pytest.mark.asyncio
    async def test_perform_transition_dry_run(self) -> None:
        """Test that dry run mode logs but doesn't execute."""
        client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test", dry_run=True)
        async with client:
            result = await client.perform_transition("PROJ-123", "In Progress")

        assert result is True


class TestJiraClientErrorHandling:
    """Test Jira client error handling."""

    @pytest.mark.asyncio
    async def test_auth_error_401(self) -> None:
        """Test 401 response raises JiraAuthError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="bad-token")
            async with client:
                with pytest.raises(JiraAuthError, match="authentication failed"):
                    await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_auth_error_403(self) -> None:
        """Test 403 response raises JiraAuthError."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                with pytest.raises(JiraAuthError, match="access forbidden"):
                    await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_not_found_404(self) -> None:
        """Test 404 response raises JiraNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                with pytest.raises(JiraNotFoundError, match="not found"):
                    await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_rate_limit_429(self) -> None:
        """Test rate limit response raises JiraRateLimitError after retries."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = JiraClient("https://test.atlassian.net", email="test@example.com", token="test")
            async with client:
                with pytest.raises(JiraRateLimitError, match="rate limit"):
                    await client._request("GET", "/test")


# =============================================================================
# JiraSynchronizer Tests
# =============================================================================


class TestJiraIssuePattern:
    """Test Jira issue key pattern matching."""

    def test_matches_standard_key(self) -> None:
        """Test matching standard PROJECT-123 format."""
        match = JIRA_ISSUE_PATTERN.search("PROJ-123")
        assert match is not None
        assert match.group(1) == "PROJ-123"

    def test_matches_multiple_keys(self) -> None:
        """Test finding multiple keys in string."""
        matches = JIRA_ISSUE_PATTERN.findall("PROJ-123, DEV-456, TEST-789")
        assert matches == ["PROJ-123", "DEV-456", "TEST-789"]

    def test_no_match_for_lowercase(self) -> None:
        """Test lowercase project keys don't match."""
        match = JIRA_ISSUE_PATTERN.search("proj-123")
        assert match is None

    def test_no_match_for_missing_number(self) -> None:
        """Test keys without numbers don't match."""
        match = JIRA_ISSUE_PATTERN.search("PROJ-")
        assert match is None


class TestJiraSynchronizer:
    """Test JiraSynchronizer functionality."""

    @pytest.fixture
    def sync_config(self) -> JiraConfig:
        """Create default sync config."""
        return JiraConfig(
            enabled=True,
            url="https://test.atlassian.net",
            transitions=JiraTransitionConfig(
                on_phase_start="In Development",
                on_phase_complete="Code Review",
                on_plan_complete="Done",
            ),
            dry_run=False,
        )

    def test_parse_jira_issues_list(self, sync_config: JiraConfig) -> None:
        """Test parsing issue keys from list."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        issues = sync.parse_jira_issues(["PROJ-123", "PROJ-124"])
        assert issues == ["PROJ-123", "PROJ-124"]

    def test_parse_jira_issues_string(self, sync_config: JiraConfig) -> None:
        """Test parsing issue keys from string."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        issues = sync.parse_jira_issues("PROJ-123, PROJ-124")
        assert issues == ["PROJ-123", "PROJ-124"]

    def test_parse_jira_issues_mixed_text(self, sync_config: JiraConfig) -> None:
        """Test parsing keys from string with other text."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        issues = sync.parse_jira_issues("See PROJ-123 and also DEV-456 for details")
        assert "PROJ-123" in issues
        assert "DEV-456" in issues

    def test_parse_jira_issues_normalizes_case(self, sync_config: JiraConfig) -> None:
        """Test that keys are normalized to uppercase."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        # Input already uppercase, should stay uppercase
        issues = sync.parse_jira_issues(["PROJ-123"])
        assert issues == ["PROJ-123"]

    def test_parse_jira_issues_none(self, sync_config: JiraConfig) -> None:
        """Test parsing None returns empty list."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        issues = sync.parse_jira_issues(None)
        assert issues == []

    def test_parse_jira_issues_invalid_keys_filtered(self, sync_config: JiraConfig) -> None:
        """Test invalid keys are filtered out."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        issues = sync.parse_jira_issues(["PROJ-123", "invalid", "123", ""])
        assert issues == ["PROJ-123"]

    @pytest.mark.asyncio
    async def test_on_phase_start_no_transition_configured(self, sync_config: JiraConfig) -> None:
        """Test phase start skips when no transition configured."""
        sync_config.transitions.on_phase_start = None
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123"]

        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await sync.on_phase_start(mock_phase)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_on_phase_start_transitions_issues(self, sync_config: JiraConfig) -> None:
        """Test phase start transitions all linked issues."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123", "PROJ-124"]

        # Mock client
        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", status="To Do"))
        mock_client.perform_transition = AsyncMock(return_value=True)
        sync._client = mock_client

        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await sync.on_phase_start(mock_phase)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_client.perform_transition.call_count == 2

    @pytest.mark.asyncio
    async def test_on_phase_complete_transitions_issues(self, sync_config: JiraConfig) -> None:
        """Test phase complete transitions all linked issues."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123"]

        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", status="In Development"))
        mock_client.perform_transition = AsyncMock(return_value=True)
        sync._client = mock_client

        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await sync.on_phase_complete(mock_phase)

        assert len(results) == 1
        assert results[0].success

    @pytest.mark.asyncio
    async def test_on_plan_complete_transitions_issues(self, sync_config: JiraConfig) -> None:
        """Test plan complete transitions all linked issues."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123"]

        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", status="Code Review"))
        mock_client.perform_transition = AsyncMock(return_value=True)
        sync._client = mock_client

        results = await sync.on_plan_complete()

        assert len(results) == 1
        assert results[0].success

    @pytest.mark.asyncio
    async def test_transition_error_returns_failure_result(self, sync_config: JiraConfig) -> None:
        """Test that transition errors return failure result, not raise."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123"]

        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", status="To Do"))
        mock_client.perform_transition = AsyncMock(side_effect=JiraTransitionError("Transition not available"))
        sync._client = mock_client

        mock_phase = MagicMock()
        mock_phase.id = "1"

        results = await sync.on_phase_start(mock_phase)

        assert len(results) == 1
        assert not results[0].success
        assert results[0].error is not None
        assert "not available" in results[0].error

    @pytest.mark.asyncio
    async def test_stats_tracking(self, sync_config: JiraConfig) -> None:
        """Test statistics are updated during sync."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")
        sync._linked_issues = ["PROJ-123", "PROJ-124"]

        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", status="To Do"))
        # First succeeds, second fails
        mock_client.perform_transition = AsyncMock(side_effect=[True, JiraTransitionError("Failed")])
        sync._client = mock_client

        mock_phase = MagicMock()
        mock_phase.id = "1"

        await sync.on_phase_start(mock_phase)

        assert sync.stats.issues_transitioned == 1
        assert sync.stats.issues_failed == 1


class TestJiraSynchronizerInitialization:
    """Test JiraSynchronizer initialization from plan."""

    @pytest.fixture
    def sync_config(self) -> JiraConfig:
        """Create default sync config."""
        return JiraConfig(
            enabled=True,
            url="https://test.atlassian.net",
            transitions=JiraTransitionConfig(),
            dry_run=False,
        )

    @pytest.mark.asyncio
    async def test_initialize_from_plan_validates_issues(self, sync_config: JiraConfig) -> None:
        """Test initialization validates issues exist."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")

        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", summary="Test", status="To Do"))
        sync._client = mock_client

        valid = await sync.initialize_from_plan("PROJ-123, PROJ-124")

        # Should have tried to fetch both
        assert mock_client.get_issue.call_count == 2
        # Both should be valid
        assert len(valid) == 2

    @pytest.mark.asyncio
    async def test_initialize_from_plan_filters_invalid(self, sync_config: JiraConfig) -> None:
        """Test initialization filters out inaccessible issues."""
        from debussy.sync.jira_client import JiraClientError

        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")

        mock_client = MagicMock()
        # First issue exists, second doesn't
        mock_client.get_issue = AsyncMock(
            side_effect=[
                MagicMock(key="PROJ-123", summary="Test", status="To Do"),
                JiraClientError("Not found"),
            ]
        )
        sync._client = mock_client

        valid = await sync.initialize_from_plan(["PROJ-123", "PROJ-124"])

        assert valid == ["PROJ-123"]
        assert sync.linked_issues == ["PROJ-123"]

    @pytest.mark.asyncio
    async def test_initialize_from_plan_empty(self, sync_config: JiraConfig) -> None:
        """Test initialization with no issues."""
        sync = JiraSynchronizer(sync_config, email="test@example.com", token="test")

        mock_client = MagicMock()
        sync._client = mock_client

        valid = await sync.initialize_from_plan(None)

        assert valid == []
        mock_client.get_issue.assert_not_called()


# =============================================================================
# Integration Tests (using mocks)
# =============================================================================


class TestJiraSyncIntegration:
    """Integration tests for the full Jira sync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_flow(self) -> None:
        """Test complete sync flow from init to completion."""
        config = JiraConfig(
            enabled=True,
            url="https://test.atlassian.net",
            transitions=JiraTransitionConfig(
                on_phase_start="In Development",
                on_phase_complete="Code Review",
                on_plan_complete="Done",
            ),
            dry_run=False,
        )

        sync = JiraSynchronizer(config, email="test@example.com", token="test")

        # Mock client
        mock_client = MagicMock()
        mock_client.get_issue = AsyncMock(return_value=MagicMock(key="PROJ-123", summary="Test", status="To Do"))
        mock_client.perform_transition = AsyncMock(return_value=True)
        sync._client = mock_client

        # Initialize
        valid = await sync.initialize_from_plan("PROJ-123")
        assert valid == ["PROJ-123"]

        # Phase start
        mock_phase = MagicMock(id="1")
        start_results = await sync.on_phase_start(mock_phase)
        assert len(start_results) == 1
        assert start_results[0].success

        # Phase complete
        complete_results = await sync.on_phase_complete(mock_phase)
        assert len(complete_results) == 1
        assert complete_results[0].success

        # Plan complete
        plan_results = await sync.on_plan_complete()
        assert len(plan_results) == 1
        assert plan_results[0].success

        # Verify all transitions were called
        assert mock_client.perform_transition.call_count == 3


# =============================================================================
# Config Tests
# =============================================================================


class TestJiraConfig:
    """Test Jira configuration."""

    def test_default_config(self) -> None:
        """Test default Jira config values."""
        config = JiraConfig()
        assert config.enabled is False
        assert config.url == ""
        assert config.dry_run is True  # Safe default

    def test_config_with_transitions(self) -> None:
        """Test config with transition mappings."""
        config = JiraConfig(
            enabled=True,
            url="https://test.atlassian.net",
            transitions=JiraTransitionConfig(
                on_phase_start="In Progress",
                on_phase_complete="In Review",
                on_plan_complete="Done",
            ),
        )
        assert config.transitions.on_phase_start == "In Progress"
        assert config.transitions.on_phase_complete == "In Review"
        assert config.transitions.on_plan_complete == "Done"
