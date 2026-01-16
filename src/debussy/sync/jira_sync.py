"""Jira issue synchronization coordinator.

This module coordinates Jira issue workflow transitions during Debussy
orchestration, hooking into phase lifecycle events to transition issues
through configured workflow states.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from debussy.sync.jira_client import (
    JiraClient,
    JiraClientError,
    JiraTransitionError,
)

if TYPE_CHECKING:
    from debussy.config import JiraConfig
    from debussy.core.models import Phase

logger = logging.getLogger(__name__)

# Regex pattern to extract Jira issue keys (PROJECT-NUMBER format)
JIRA_ISSUE_PATTERN = re.compile(r"([A-Z][A-Z0-9_]+-\d+)")


@dataclass
class JiraSyncResult:
    """Result of a Jira sync operation."""

    success: bool
    message: str
    issue_key: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    error: str | None = None


@dataclass
class JiraSyncStats:
    """Statistics for Jira sync operations."""

    issues_transitioned: int = 0
    issues_skipped: int = 0
    issues_failed: int = 0
    transitions_cached: int = 0


class JiraSynchronizer:
    """Coordinates Jira issue sync during orchestration.

    Handles:
    - Parsing jira_issues from plan metadata
    - Transitioning issues on phase start/complete/fail
    - Caching available transitions to minimize API calls
    - Graceful error handling (sync failures never block phases)
    """

    def __init__(
        self,
        config: JiraConfig,
        email: str | None = None,
        token: str | None = None,
    ) -> None:
        """Initialize the sync coordinator.

        Args:
            config: Jira sync configuration.
            email: Jira user email (or uses JIRA_EMAIL env var).
            token: Jira API token (or uses JIRA_API_TOKEN env var).
        """
        self.config = config
        self._email = email
        self._token = token
        self._client: JiraClient | None = None
        self._linked_issues: list[str] = []
        self._stats = JiraSyncStats()

    async def __aenter__(self) -> JiraSynchronizer:
        """Enter async context manager."""
        self._client = JiraClient(
            base_url=self.config.url,
            email=self._email,
            token=self._token,
            dry_run=self.config.dry_run,
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    @property
    def client(self) -> JiraClient:
        """Get the Jira client."""
        if self._client is None:
            raise RuntimeError("JiraSynchronizer must be used as async context manager")
        return self._client

    @property
    def stats(self) -> JiraSyncStats:
        """Get sync statistics."""
        return self._stats

    # =========================================================================
    # Plan Metadata Parsing
    # =========================================================================

    def parse_jira_issues(self, metadata: list[str] | str | None) -> list[str]:
        """Parse jira_issues from plan metadata.

        Supports formats:
        - List: ["PROJ-123", "PROJ-124"]
        - String with keys: "PROJ-123, PROJ-124"
        - String with mixed content: "See PROJ-123 and PROJ-124"

        Args:
            metadata: The jira_issues value from plan metadata.

        Returns:
            List of Jira issue keys.
        """
        if metadata is None:
            return []

        if isinstance(metadata, list):
            # Validate each key matches PROJECT-NUMBER pattern
            valid_keys = []
            for key in metadata:
                if isinstance(key, str) and JIRA_ISSUE_PATTERN.match(key):
                    valid_keys.append(key.upper())
            return valid_keys

        # metadata is a string - extract all issue keys
        matches = JIRA_ISSUE_PATTERN.findall(metadata)
        return [m.upper() for m in matches]

    async def initialize_from_plan(self, jira_issues: list[str] | str | None) -> list[str]:
        """Initialize sync from plan metadata.

        Parses issue references and validates they exist.

        Args:
            jira_issues: The jira_issues value from plan metadata.

        Returns:
            List of valid issue keys.
        """
        self._linked_issues = self.parse_jira_issues(jira_issues)

        if not self._linked_issues:
            logger.info("No Jira issues linked to this plan")
            return []

        # Validate issues exist
        valid_issues = []
        for issue_key in self._linked_issues:
            try:
                issue = await self.client.get_issue(issue_key)
                valid_issues.append(issue_key)
                logger.debug(f"Validated Jira issue {issue_key}: {issue.summary} ({issue.status})")
            except JiraClientError as e:
                logger.warning(f"Jira issue {issue_key} not accessible: {e}")

        self._linked_issues = valid_issues
        logger.info(f"Initialized Jira sync with {len(valid_issues)} issue(s)")
        return valid_issues

    # =========================================================================
    # Phase Lifecycle Hooks
    # =========================================================================

    async def on_phase_start(self, phase: Phase) -> list[JiraSyncResult]:
        """Handle phase start event.

        Transitions linked issues to the configured 'on_phase_start' state.

        Args:
            phase: The phase that started.

        Returns:
            List of sync results.
        """
        transition_name = self.config.transitions.on_phase_start
        if not transition_name:
            logger.debug("No on_phase_start transition configured, skipping")
            return []

        return await self._transition_all_issues(
            transition_name=transition_name,
            event_description=f"phase {phase.id} start",
        )

    async def on_phase_complete(self, phase: Phase) -> list[JiraSyncResult]:
        """Handle phase completion event.

        Transitions linked issues to the configured 'on_phase_complete' state.

        Args:
            phase: The phase that completed.

        Returns:
            List of sync results.
        """
        transition_name = self.config.transitions.on_phase_complete
        if not transition_name:
            logger.debug("No on_phase_complete transition configured, skipping")
            return []

        return await self._transition_all_issues(
            transition_name=transition_name,
            event_description=f"phase {phase.id} complete",
        )

    async def on_plan_complete(self) -> list[JiraSyncResult]:
        """Handle plan completion event.

        Transitions linked issues to the configured 'on_plan_complete' state.

        Returns:
            List of sync results.
        """
        transition_name = self.config.transitions.on_plan_complete
        if not transition_name:
            logger.debug("No on_plan_complete transition configured, skipping")
            return []

        return await self._transition_all_issues(
            transition_name=transition_name,
            event_description="plan complete",
        )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _transition_all_issues(
        self,
        transition_name: str,
        event_description: str,
    ) -> list[JiraSyncResult]:
        """Transition all linked issues using the specified transition.

        Args:
            transition_name: The transition name to execute.
            event_description: Description for logging (e.g., "phase 1 start").

        Returns:
            List of sync results.
        """
        results: list[JiraSyncResult] = []

        for issue_key in self._linked_issues:
            result = await self._transition_issue(issue_key, transition_name, event_description)
            results.append(result)

            # Update stats
            if result.success:
                if "would transition" in result.message.lower() or "transitioned" in result.message.lower():
                    self._stats.issues_transitioned += 1
                else:
                    self._stats.issues_skipped += 1
            else:
                self._stats.issues_failed += 1

        return results

    async def _transition_issue(
        self,
        issue_key: str,
        transition_name: str,
        event_description: str,
    ) -> JiraSyncResult:
        """Transition a single issue.

        Args:
            issue_key: The Jira issue key.
            transition_name: The transition name to execute.
            event_description: Description for logging.

        Returns:
            Sync result.
        """
        try:
            # Get current issue status
            issue = await self.client.get_issue(issue_key)
            from_status = issue.status

            # Try to perform the transition
            await self.client.perform_transition(issue_key, transition_name)

            # Get new status (for dry run, we show the transition name)
            to_status = transition_name if self.config.dry_run else None
            if not self.config.dry_run:
                updated_issue = await self.client.get_issue(issue_key)
                to_status = updated_issue.status

            message = (
                f"[DRY RUN] Would transition {issue_key} via '{transition_name}' ({event_description})"
                if self.config.dry_run
                else f"Transitioned {issue_key} via '{transition_name}' ({event_description})"
            )

            logger.info(f"Jira sync: {message}")
            return JiraSyncResult(
                success=True,
                message=message,
                issue_key=issue_key,
                from_status=from_status,
                to_status=to_status,
            )

        except JiraTransitionError as e:
            # Transition not available - log warning but don't fail
            message = f"Transition '{transition_name}' not available for {issue_key}: {e}"
            logger.warning(f"Jira sync: {message}")
            return JiraSyncResult(
                success=False,
                message=message,
                issue_key=issue_key,
                error=str(e),
            )

        except JiraClientError as e:
            # Other API error - log warning but don't fail
            message = f"Failed to transition {issue_key}: {e}"
            logger.warning(f"Jira sync: {message}")
            return JiraSyncResult(
                success=False,
                message=message,
                issue_key=issue_key,
                error=str(e),
            )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @property
    def linked_issues(self) -> list[str]:
        """Get list of linked issue keys."""
        return self._linked_issues.copy()

    def clear_cache(self) -> None:
        """Clear the transition cache."""
        if self._client:
            self._client.clear_cache()
