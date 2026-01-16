"""Jira REST API v3 client for issue synchronization.

This module provides an async HTTP client for Jira API operations
including issue fetching, transition discovery, and workflow transitions.
Uses JIRA_API_TOKEN environment variable for authentication.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Jira API constants
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


class JiraClientError(Exception):
    """Base exception for Jira client errors."""


class JiraAuthError(JiraClientError):
    """Authentication with Jira failed."""


class JiraRateLimitError(JiraClientError):
    """Jira API rate limit exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after  # Seconds to wait before retry


class JiraNotFoundError(JiraClientError):
    """Requested resource not found."""


class JiraTransitionError(JiraClientError):
    """Transition failed or is not available."""


@dataclass
class JiraIssue:
    """Represents a Jira issue."""

    key: str  # e.g., "PROJ-123"
    summary: str
    status: str  # Current status name
    project_key: str
    url: str = ""


@dataclass
class JiraTransition:
    """Represents an available Jira workflow transition."""

    id: str  # Transition ID (used for API calls)
    name: str  # Transition name (user-facing)
    to_status: str  # Target status name after transition


@dataclass
class TransitionCache:
    """Cache for available transitions per issue."""

    transitions: dict[str, list[JiraTransition]] = field(default_factory=dict)

    def get(self, issue_key: str) -> list[JiraTransition] | None:
        """Get cached transitions for an issue."""
        return self.transitions.get(issue_key)

    def set(self, issue_key: str, transitions: list[JiraTransition]) -> None:
        """Cache transitions for an issue."""
        self.transitions[issue_key] = transitions

    def clear(self) -> None:
        """Clear all cached transitions."""
        self.transitions.clear()


class JiraClient:
    """Async Jira REST API v3 client for issue synchronization.

    Uses JIRA_API_TOKEN environment variable for authentication.
    The token should be an API token created in Atlassian account settings.
    Implements rate limit detection and retry logic with exponential backoff.
    """

    def __init__(
        self,
        base_url: str,
        email: str | None = None,
        token: str | None = None,
        dry_run: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the Jira client.

        Args:
            base_url: Jira instance URL (e.g., https://company.atlassian.net).
            email: User email for authentication. If None, reads from JIRA_EMAIL env var.
            token: API token. If None, reads from JIRA_API_TOKEN env var.
            dry_run: If True, log operations without executing.
            timeout: Request timeout in seconds.

        Raises:
            JiraAuthError: If no token/email is provided or found in environment.
        """
        # Normalize base URL (remove trailing slash)
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.timeout = timeout

        # Get credentials from params or environment
        self._email = email or os.getenv("JIRA_EMAIL")
        self._token = token or os.getenv("JIRA_API_TOKEN")

        if not self._token:
            raise JiraAuthError("No Jira API token provided. Set JIRA_API_TOKEN environment variable or pass token parameter.")
        if not self._email:
            raise JiraAuthError("No Jira email provided. Set JIRA_EMAIL environment variable or pass email parameter.")

        # Build Basic Auth header (email:token base64 encoded) - never log!
        credentials = f"{self._email}:{self._token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded}",
        }

        self._client: httpx.AsyncClient | None = None
        self._transition_cache = TransitionCache()

    async def __aenter__(self) -> JiraClient:
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, ensuring it's initialized."""
        if self._client is None:
            raise RuntimeError("JiraClient must be used as async context manager")
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint (e.g., "/rest/api/3/issue/PROJ-123").
            **kwargs: Additional arguments passed to httpx request.

        Returns:
            httpx.Response object.

        Raises:
            JiraAuthError: If authentication fails.
            JiraRateLimitError: If rate limit is exceeded after retries.
            JiraNotFoundError: If resource is not found.
            JiraClientError: For other API errors.
        """
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.request(method, endpoint, **kwargs)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    if attempt < MAX_RETRIES - 1:
                        wait_time = min(retry_after, 60)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                        await asyncio.sleep(wait_time)
                        continue
                    raise JiraRateLimitError(
                        f"Jira API rate limit exceeded. Retry after {retry_after}s",
                        retry_after=retry_after,
                    )

                # Handle auth errors (401, 403)
                if response.status_code == 401:
                    raise JiraAuthError("Jira authentication failed. Check your email and API token.")
                if response.status_code == 403:
                    raise JiraAuthError("Jira access forbidden. Check token permissions.")

                # Handle not found (404)
                if response.status_code == 404:
                    raise JiraNotFoundError(f"Resource not found: {endpoint}")

                # Handle other errors
                if response.status_code >= 400:
                    error_body = response.text
                    logger.error(f"Jira API error {response.status_code}: {error_body}")
                    raise JiraClientError(f"Jira API error {response.status_code}: {error_body[:200]}")

                return response

            except httpx.TimeoutException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = backoff * (2**attempt)
                    logger.warning(f"Request timeout, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise JiraClientError(f"Request timeout after {MAX_RETRIES} attempts") from e

            except httpx.HTTPError as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = backoff * (2**attempt)
                    logger.warning(f"HTTP error: {e}, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise JiraClientError(f"HTTP error after {MAX_RETRIES} attempts: {e}") from e

        # Should not reach here, but just in case
        raise JiraClientError("Max retries exceeded")

    # =========================================================================
    # Issue Operations
    # =========================================================================

    async def get_issue(self, issue_key: str) -> JiraIssue:
        """Get a single issue by key.

        Args:
            issue_key: The issue key (e.g., "PROJ-123").

        Returns:
            JiraIssue object.
        """
        endpoint = f"/rest/api/3/issue/{issue_key}"
        response = await self._request("GET", endpoint, params={"fields": "summary,status,project"})
        data = response.json()

        fields = data.get("fields", {})
        status = fields.get("status", {})
        project = fields.get("project", {})

        return JiraIssue(
            key=data["key"],
            summary=fields.get("summary", ""),
            status=status.get("name", ""),
            project_key=project.get("key", ""),
            url=f"{self.base_url}/browse/{data['key']}",
        )

    # =========================================================================
    # Transition Operations
    # =========================================================================

    async def get_transitions(self, issue_key: str, use_cache: bool = True) -> list[JiraTransition]:
        """Get available transitions for an issue.

        Args:
            issue_key: The issue key (e.g., "PROJ-123").
            use_cache: Whether to use cached transitions if available.

        Returns:
            List of available JiraTransition objects.
        """
        # Check cache first
        if use_cache:
            cached = self._transition_cache.get(issue_key)
            if cached is not None:
                return cached

        endpoint = f"/rest/api/3/issue/{issue_key}/transitions"
        response = await self._request("GET", endpoint)
        data = response.json()

        transitions = []
        for t in data.get("transitions", []):
            to_status = t.get("to", {})
            transitions.append(
                JiraTransition(
                    id=t["id"],
                    name=t["name"],
                    to_status=to_status.get("name", ""),
                )
            )

        # Cache the result
        self._transition_cache.set(issue_key, transitions)

        return transitions

    async def find_transition_by_name(self, issue_key: str, transition_name: str) -> JiraTransition | None:
        """Find a transition by name for an issue.

        Args:
            issue_key: The issue key (e.g., "PROJ-123").
            transition_name: The transition name to find (case-insensitive).

        Returns:
            JiraTransition if found, None otherwise.
        """
        transitions = await self.get_transitions(issue_key)
        transition_name_lower = transition_name.lower()

        for t in transitions:
            if t.name.lower() == transition_name_lower:
                return t

        return None

    async def perform_transition(
        self,
        issue_key: str,
        transition_name: str,
    ) -> bool:
        """Perform a workflow transition on an issue.

        Args:
            issue_key: The issue key (e.g., "PROJ-123").
            transition_name: The transition name to perform.

        Returns:
            True if transition succeeded.

        Raises:
            JiraTransitionError: If transition is not available or fails.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would transition {issue_key} via '{transition_name}'")
            return True

        # Find the transition ID
        transition = await self.find_transition_by_name(issue_key, transition_name)
        if transition is None:
            available = await self.get_transitions(issue_key)
            available_names = [t.name for t in available]
            raise JiraTransitionError(f"Transition '{transition_name}' not available for {issue_key}. Available transitions: {available_names}")

        # Perform the transition
        endpoint = f"/rest/api/3/issue/{issue_key}/transitions"
        await self._request(
            "POST",
            endpoint,
            json={"transition": {"id": transition.id}},
        )

        # Invalidate cache for this issue (status changed)
        self._transition_cache.transitions.pop(issue_key, None)

        logger.info(f"Transitioned {issue_key} via '{transition_name}' -> {transition.to_status}")
        return True

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear_cache(self) -> None:
        """Clear the transition cache."""
        self._transition_cache.clear()
