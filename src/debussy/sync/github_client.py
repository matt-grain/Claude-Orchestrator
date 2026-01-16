"""GitHub API client using httpx for issue synchronization.

This module provides an async HTTP client for GitHub API operations
including issue updates, label management, and milestone tracking.
Uses GITHUB_TOKEN environment variable for authentication.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# GitHub API constants
GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""


class GitHubAuthError(GitHubClientError):
    """Authentication with GitHub failed."""


class GitHubRateLimitError(GitHubClientError):
    """GitHub API rate limit exceeded."""

    def __init__(self, message: str, reset_at: int | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at  # Unix timestamp when rate limit resets


class GitHubNotFoundError(GitHubClientError):
    """Requested resource not found."""


@dataclass
class GitHubIssue:
    """Represents a GitHub issue."""

    number: int
    title: str
    state: str  # "open" or "closed"
    labels: list[str]
    milestone_number: int | None = None
    milestone_title: str | None = None
    url: str = ""


@dataclass
class GitHubLabel:
    """Represents a GitHub label."""

    name: str
    color: str
    description: str = ""


@dataclass
class GitHubMilestone:
    """Represents a GitHub milestone."""

    number: int
    title: str
    description: str = ""
    open_issues: int = 0
    closed_issues: int = 0


class GitHubClient:
    """Async GitHub API client for issue synchronization.

    Uses GITHUB_TOKEN environment variable for authentication.
    Implements rate limit detection and retry logic with exponential backoff.
    """

    def __init__(
        self,
        repo: str,
        token: str | None = None,
        dry_run: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the GitHub client.

        Args:
            repo: Repository in 'owner/repo' format.
            token: GitHub token. If None, reads from GITHUB_TOKEN env var.
            dry_run: If True, log operations without executing.
            timeout: Request timeout in seconds.

        Raises:
            GitHubAuthError: If no token is provided or found in environment.
        """
        self.repo = repo
        self.dry_run = dry_run
        self.timeout = timeout

        # Get token from param or environment
        self._token = token or os.getenv("GITHUB_TOKEN")
        if not self._token:
            raise GitHubAuthError("No GitHub token provided. Set GITHUB_TOKEN environment variable or pass token parameter.")

        # Build headers - never log the token!
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> GitHubClient:
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=self._headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, ensuring it's initialized."""
        if self._client is None:
            raise RuntimeError("GitHubClient must be used as async context manager")
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.).
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues/1").
            **kwargs: Additional arguments passed to httpx request.

        Returns:
            httpx.Response object.

        Raises:
            GitHubAuthError: If authentication fails.
            GitHubRateLimitError: If rate limit is exceeded after retries.
            GitHubNotFoundError: If resource is not found.
            GitHubClientError: For other API errors.
        """
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.request(method, endpoint, **kwargs)

                # Handle rate limiting
                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        reset_at = int(response.headers.get("X-RateLimit-Reset", "0"))
                        if attempt < MAX_RETRIES - 1:
                            wait_time = min(backoff * (2**attempt), 60)
                            logger.warning(f"Rate limit hit, waiting {wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(wait_time)
                            continue
                        raise GitHubRateLimitError(
                            f"GitHub API rate limit exceeded. Resets at {reset_at}",
                            reset_at=reset_at,
                        )

                # Handle auth errors
                if response.status_code == 401:
                    raise GitHubAuthError("GitHub authentication failed. Check your token.")

                # Handle not found
                if response.status_code == 404:
                    raise GitHubNotFoundError(f"Resource not found: {endpoint}")

                # Handle other errors
                if response.status_code >= 400:
                    error_body = response.text
                    logger.error(f"GitHub API error {response.status_code}: {error_body}")
                    raise GitHubClientError(f"GitHub API error {response.status_code}: {error_body[:200]}")

                return response

            except httpx.TimeoutException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = backoff * (2**attempt)
                    logger.warning(f"Request timeout, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise GitHubClientError(f"Request timeout after {MAX_RETRIES} attempts") from e

            except httpx.HTTPError as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = backoff * (2**attempt)
                    logger.warning(f"HTTP error: {e}, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise GitHubClientError(f"HTTP error after {MAX_RETRIES} attempts: {e}") from e

        # Should not reach here, but just in case
        raise GitHubClientError("Max retries exceeded")

    # =========================================================================
    # Issue Operations
    # =========================================================================

    async def get_issue(self, issue_number: int) -> GitHubIssue:
        """Get a single issue by number.

        Args:
            issue_number: The issue number.

        Returns:
            GitHubIssue object.
        """
        endpoint = f"/repos/{self.repo}/issues/{issue_number}"
        response = await self._request("GET", endpoint)
        data = response.json()

        milestone = data.get("milestone")
        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            milestone_number=milestone["number"] if milestone else None,
            milestone_title=milestone["title"] if milestone else None,
            url=data.get("html_url", ""),
        )

    async def update_labels(
        self,
        issue_number: int,
        labels: list[str],
    ) -> list[str]:
        """Set labels on an issue (replaces existing labels).

        Args:
            issue_number: The issue number.
            labels: List of label names to set.

        Returns:
            List of label names after update.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would set labels on #{issue_number}: {labels}")
            return labels

        endpoint = f"/repos/{self.repo}/issues/{issue_number}"
        response = await self._request(
            "PATCH",
            endpoint,
            json={"labels": labels},
        )
        data = response.json()
        return [label["name"] for label in data.get("labels", [])]

    async def add_labels(
        self,
        issue_number: int,
        labels: list[str],
    ) -> list[str]:
        """Add labels to an issue (preserves existing labels).

        Args:
            issue_number: The issue number.
            labels: List of label names to add.

        Returns:
            List of all label names after update.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would add labels to #{issue_number}: {labels}")
            return labels

        endpoint = f"/repos/{self.repo}/issues/{issue_number}/labels"
        response = await self._request(
            "POST",
            endpoint,
            json={"labels": labels},
        )
        data = response.json()
        return [label["name"] for label in data]

    async def remove_label(
        self,
        issue_number: int,
        label: str,
    ) -> bool:
        """Remove a label from an issue.

        Args:
            issue_number: The issue number.
            label: Label name to remove.

        Returns:
            True if removed, False if label wasn't present.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would remove label '{label}' from #{issue_number}")
            return True

        endpoint = f"/repos/{self.repo}/issues/{issue_number}/labels/{label}"
        try:
            await self._request("DELETE", endpoint)
            return True
        except GitHubNotFoundError:
            # Label wasn't on the issue
            return False

    async def close_issue(
        self,
        issue_number: int,
        comment: str | None = None,
    ) -> bool:
        """Close an issue with optional comment.

        Args:
            issue_number: The issue number.
            comment: Optional comment to add before closing.

        Returns:
            True if closed successfully.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would close #{issue_number}" + (f" with comment: {comment}" if comment else ""))
            return True

        # Add comment first if provided
        if comment:
            await self.add_comment(issue_number, comment)

        # Close the issue
        endpoint = f"/repos/{self.repo}/issues/{issue_number}"
        await self._request(
            "PATCH",
            endpoint,
            json={"state": "closed"},
        )
        return True

    async def add_comment(
        self,
        issue_number: int,
        body: str,
    ) -> int:
        """Add a comment to an issue.

        Args:
            issue_number: The issue number.
            body: Comment body text.

        Returns:
            Comment ID.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would add comment to #{issue_number}: {body[:50]}...")
            return 0

        endpoint = f"/repos/{self.repo}/issues/{issue_number}/comments"
        response = await self._request(
            "POST",
            endpoint,
            json={"body": body},
        )
        return response.json()["id"]

    # =========================================================================
    # Label Operations
    # =========================================================================

    async def get_label(self, name: str) -> GitHubLabel | None:
        """Get a label by name.

        Args:
            name: Label name.

        Returns:
            GitHubLabel if found, None otherwise.
        """
        endpoint = f"/repos/{self.repo}/labels/{name}"
        try:
            response = await self._request("GET", endpoint)
            data = response.json()
            return GitHubLabel(
                name=data["name"],
                color=data["color"],
                description=data.get("description", ""),
            )
        except GitHubNotFoundError:
            return None

    async def create_label(
        self,
        name: str,
        color: str,
        description: str = "",
    ) -> GitHubLabel:
        """Create a new label.

        Args:
            name: Label name.
            color: Hex color (without #).
            description: Label description.

        Returns:
            Created GitHubLabel.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create label '{name}' with color {color}")
            return GitHubLabel(name=name, color=color, description=description)

        endpoint = f"/repos/{self.repo}/labels"
        response = await self._request(
            "POST",
            endpoint,
            json={
                "name": name,
                "color": color,
                "description": description,
            },
        )
        data = response.json()
        return GitHubLabel(
            name=data["name"],
            color=data["color"],
            description=data.get("description", ""),
        )

    async def update_label(
        self,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> GitHubLabel:
        """Update an existing label.

        Args:
            name: Label name.
            color: New hex color (without #).
            description: New description.

        Returns:
            Updated GitHubLabel.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update label '{name}'")
            return GitHubLabel(name=name, color=color or "", description=description or "")

        endpoint = f"/repos/{self.repo}/labels/{name}"
        update_data: dict[str, str] = {}
        if color is not None:
            update_data["color"] = color
        if description is not None:
            update_data["description"] = description

        response = await self._request("PATCH", endpoint, json=update_data)
        data = response.json()
        return GitHubLabel(
            name=data["name"],
            color=data["color"],
            description=data.get("description", ""),
        )

    async def ensure_label(
        self,
        name: str,
        color: str,
        description: str = "",
    ) -> GitHubLabel:
        """Ensure a label exists, creating if necessary.

        Args:
            name: Label name.
            color: Hex color (without #).
            description: Label description.

        Returns:
            GitHubLabel (existing or newly created).
        """
        existing = await self.get_label(name)
        if existing:
            return existing
        return await self.create_label(name, color, description)

    # =========================================================================
    # Milestone Operations
    # =========================================================================

    async def get_milestone(self, milestone_number: int) -> GitHubMilestone | None:
        """Get a milestone by number.

        Args:
            milestone_number: The milestone number.

        Returns:
            GitHubMilestone if found, None otherwise.
        """
        endpoint = f"/repos/{self.repo}/milestones/{milestone_number}"
        try:
            response = await self._request("GET", endpoint)
            data = response.json()
            return GitHubMilestone(
                number=data["number"],
                title=data["title"],
                description=data.get("description", ""),
                open_issues=data.get("open_issues", 0),
                closed_issues=data.get("closed_issues", 0),
            )
        except GitHubNotFoundError:
            return None

    async def update_milestone_description(
        self,
        milestone_number: int,
        description: str,
    ) -> GitHubMilestone:
        """Update a milestone's description.

        Args:
            milestone_number: The milestone number.
            description: New description text.

        Returns:
            Updated GitHubMilestone.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update milestone #{milestone_number} description")
            return GitHubMilestone(number=milestone_number, title="", description=description)

        endpoint = f"/repos/{self.repo}/milestones/{milestone_number}"
        response = await self._request(
            "PATCH",
            endpoint,
            json={"description": description},
        )
        data = response.json()
        return GitHubMilestone(
            number=data["number"],
            title=data["title"],
            description=data.get("description", ""),
            open_issues=data.get("open_issues", 0),
            closed_issues=data.get("closed_issues", 0),
        )
