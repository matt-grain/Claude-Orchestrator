"""GitHub issue synchronization coordinator.

This module coordinates GitHub issue updates during Debussy orchestration,
hooking into phase lifecycle events to update labels and milestones.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from debussy.sync.github_client import (
    GitHubClient,
    GitHubClientError,
)
from debussy.sync.label_manager import LabelManager

if TYPE_CHECKING:
    from debussy.config import GitHubSyncConfig
    from debussy.core.models import Phase

logger = logging.getLogger(__name__)

# Regex pattern to extract issue numbers from plan metadata
# Supports formats: #10, gh#10, github#10, or full URL
ISSUE_PATTERN = re.compile(
    r"(?:(?:gh|github)#?|#)(\d+)|"  # gh#10, github#10, #10
    r"github\.com/[^/]+/[^/]+/issues/(\d+)"  # Full URL
)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str
    issue_number: int | None = None
    labels_updated: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class MilestoneProgress:
    """Progress tracking for milestone updates."""

    milestone_number: int
    total_phases: int
    completed_phases: int

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_phases == 0:
            return 0.0
        return (self.completed_phases / self.total_phases) * 100


class GitHubSyncCoordinator:
    """Coordinates GitHub issue sync during orchestration.

    Handles:
    - Parsing github_issues from plan frontmatter
    - Syncing labels on phase start/complete/fail
    - Updating milestone progress
    - Auto-closing issues on plan completion
    """

    def __init__(
        self,
        repo: str,
        config: GitHubSyncConfig,
        token: str | None = None,
    ) -> None:
        """Initialize the sync coordinator.

        Args:
            repo: Repository in 'owner/repo' format.
            config: GitHub sync configuration.
            token: GitHub token (or uses GITHUB_TOKEN env var).
        """
        self.repo = repo
        self.config = config
        self._token = token
        self._client: GitHubClient | None = None
        self._label_manager: LabelManager | None = None
        self._linked_issues: list[int] = []
        self._milestone_number: int | None = None

    async def __aenter__(self) -> GitHubSyncCoordinator:
        """Enter async context manager."""
        self._client = GitHubClient(
            repo=self.repo,
            token=self._token,
            dry_run=self.config.dry_run,
        )
        await self._client.__aenter__()

        self._label_manager = LabelManager(
            client=self._client,
            config=self.config.labels,
            create_if_missing=self.config.create_labels_if_missing,
        )
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    @property
    def client(self) -> GitHubClient:
        """Get the GitHub client."""
        if self._client is None:
            raise RuntimeError("GitHubSyncCoordinator must be used as async context manager")
        return self._client

    @property
    def label_manager(self) -> LabelManager:
        """Get the label manager."""
        if self._label_manager is None:
            raise RuntimeError("GitHubSyncCoordinator must be used as async context manager")
        return self._label_manager

    # =========================================================================
    # Plan Metadata Parsing
    # =========================================================================

    def parse_github_issues(self, metadata: dict | str | list | None) -> list[int]:
        """Parse github_issues from plan frontmatter.

        Supports formats:
        - List: [10, 11, 12]
        - String with refs: "#10, #11"
        - String with URLs: "https://github.com/owner/repo/issues/10"

        Args:
            metadata: The github_issues value from plan frontmatter.

        Returns:
            List of issue numbers.
        """
        if metadata is None:
            return []

        if isinstance(metadata, list):
            # Direct list of numbers
            return [int(n) for n in metadata if isinstance(n, int | str)]

        if isinstance(metadata, str):
            # Parse string for issue references
            issues = []
            for match in ISSUE_PATTERN.finditer(metadata):
                # Match groups: (1) short form number, (2) URL number
                number = match.group(1) or match.group(2)
                if number:
                    issues.append(int(number))
            return issues

        return []

    async def initialize_from_plan(self, github_issues: dict | str | list | None) -> list[int]:
        """Initialize sync from plan metadata.

        Parses issue references, validates they exist, and detects milestone.

        Args:
            github_issues: The github_issues value from plan frontmatter.

        Returns:
            List of valid issue numbers.
        """
        self._linked_issues = self.parse_github_issues(github_issues)

        if not self._linked_issues:
            logger.info("No GitHub issues linked to this plan")
            return []

        # Validate issues exist and detect milestone
        valid_issues = []
        for issue_num in self._linked_issues:
            try:
                issue = await self.client.get_issue(issue_num)
                valid_issues.append(issue_num)

                # Use first issue's milestone as canonical
                if self._milestone_number is None and issue.milestone_number:
                    self._milestone_number = issue.milestone_number
                    logger.info(f"Detected milestone #{self._milestone_number} from issue #{issue_num}")
                elif issue.milestone_number and issue.milestone_number != self._milestone_number:
                    logger.warning(f"Issue #{issue_num} has different milestone (#{issue.milestone_number} vs #{self._milestone_number})")

            except GitHubClientError as e:
                logger.warning(f"Issue #{issue_num} not accessible: {e}")

        self._linked_issues = valid_issues
        logger.info(f"Initialized sync with {len(valid_issues)} GitHub issue(s)")
        return valid_issues

    # =========================================================================
    # Phase Lifecycle Hooks
    # =========================================================================

    async def on_phase_start(self, phase: Phase) -> list[SyncResult]:
        """Handle phase start event.

        Adds in-progress label to all linked issues.

        Args:
            phase: The phase that started.

        Returns:
            List of sync results.
        """
        results = []
        for issue_num in self._linked_issues:
            try:
                labels = await self.label_manager.set_in_progress(issue_num)
                results.append(
                    SyncResult(
                        success=True,
                        message=f"Set in-progress on #{issue_num}",
                        issue_number=issue_num,
                        labels_updated=labels,
                    )
                )
                logger.info(f"GitHub sync: #{issue_num} -> in-progress (phase {phase.id})")
            except GitHubClientError as e:
                results.append(
                    SyncResult(
                        success=False,
                        message=f"Failed to update #{issue_num}",
                        issue_number=issue_num,
                        error=str(e),
                    )
                )
                logger.warning(f"Failed to set in-progress on #{issue_num}: {e}")

        return results

    async def on_phase_complete(self, phase: Phase) -> list[SyncResult]:
        """Handle phase completion event.

        Sets completed label on all linked issues.

        Args:
            phase: The phase that completed.

        Returns:
            List of sync results.
        """
        results = []
        for issue_num in self._linked_issues:
            try:
                labels = await self.label_manager.set_completed(issue_num)
                results.append(
                    SyncResult(
                        success=True,
                        message=f"Set completed on #{issue_num}",
                        issue_number=issue_num,
                        labels_updated=labels,
                    )
                )
                logger.info(f"GitHub sync: #{issue_num} -> completed (phase {phase.id})")
            except GitHubClientError as e:
                results.append(
                    SyncResult(
                        success=False,
                        message=f"Failed to update #{issue_num}",
                        issue_number=issue_num,
                        error=str(e),
                    )
                )
                logger.warning(f"Failed to set completed on #{issue_num}: {e}")

        return results

    async def on_phase_failed(self, phase: Phase, error: str | None = None) -> list[SyncResult]:  # noqa: ARG002
        """Handle phase failure event.

        Sets failed label on all linked issues.

        Args:
            phase: The phase that failed.
            error: Optional error message.

        Returns:
            List of sync results.
        """
        results = []
        for issue_num in self._linked_issues:
            try:
                labels = await self.label_manager.set_failed(issue_num)
                results.append(
                    SyncResult(
                        success=True,
                        message=f"Set failed on #{issue_num}",
                        issue_number=issue_num,
                        labels_updated=labels,
                    )
                )
                logger.info(f"GitHub sync: #{issue_num} -> failed (phase {phase.id})")
            except GitHubClientError as e:
                results.append(
                    SyncResult(
                        success=False,
                        message=f"Failed to update #{issue_num}",
                        issue_number=issue_num,
                        error=str(e),
                    )
                )
                logger.warning(f"Failed to set failed on #{issue_num}: {e}")

        return results

    async def on_plan_complete(
        self,
        auto_close: bool | None = None,
    ) -> list[SyncResult]:
        """Handle plan completion event.

        Optionally closes linked issues with a completion comment.

        Args:
            auto_close: Whether to close issues. Uses config default if None.

        Returns:
            List of sync results.
        """
        should_close = auto_close if auto_close is not None else self.config.auto_close

        if not should_close:
            logger.debug("Auto-close disabled, skipping issue closure")
            return []

        results = []
        for issue_num in self._linked_issues:
            try:
                comment = "✅ **Debussy orchestration completed!**\n\nAll phases have been executed successfully. Closing this issue automatically."
                await self.client.close_issue(issue_num, comment=comment)
                results.append(
                    SyncResult(
                        success=True,
                        message=f"Closed #{issue_num}",
                        issue_number=issue_num,
                    )
                )
                logger.info(f"GitHub sync: Closed #{issue_num}")
            except GitHubClientError as e:
                results.append(
                    SyncResult(
                        success=False,
                        message=f"Failed to close #{issue_num}",
                        issue_number=issue_num,
                        error=str(e),
                    )
                )
                logger.warning(f"Failed to close #{issue_num}: {e}")

        return results

    # =========================================================================
    # Milestone Progress
    # =========================================================================

    async def update_milestone_progress(
        self,
        completed_phases: int,
        total_phases: int,
    ) -> SyncResult | None:
        """Update milestone progress based on phase completion.

        Updates the milestone description with progress percentage.

        Args:
            completed_phases: Number of completed phases.
            total_phases: Total number of phases.

        Returns:
            SyncResult if milestone was updated, None if no milestone.
        """
        if self._milestone_number is None:
            return None

        progress = MilestoneProgress(
            milestone_number=self._milestone_number,
            total_phases=total_phases,
            completed_phases=completed_phases,
        )

        try:
            # Get current milestone
            milestone = await self.client.get_milestone(self._milestone_number)
            if milestone is None:
                logger.warning(f"Milestone #{self._milestone_number} not found")
                return SyncResult(
                    success=False,
                    message=f"Milestone #{self._milestone_number} not found",
                    error="Milestone not found",
                )

            # Update description with progress
            progress_line = f"\n\n📊 **Debussy Progress:** {progress.percentage:.0f}% ({completed_phases}/{total_phases} phases)"

            # Check if we already have a progress line and update it
            current_desc = milestone.description or ""
            new_desc = (
                re.sub(r"\n\n📊 \*\*Debussy Progress:\*\* .*", progress_line, current_desc)
                if "**Debussy Progress:**" in current_desc
                else current_desc + progress_line
            )

            await self.client.update_milestone_description(
                self._milestone_number,
                new_desc,
            )

            return SyncResult(
                success=True,
                message=f"Updated milestone #{self._milestone_number} to {progress.percentage:.0f}%",
            )

        except GitHubClientError as e:
            logger.warning(f"Failed to update milestone progress: {e}")
            return SyncResult(
                success=False,
                message="Failed to update milestone",
                error=str(e),
            )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @property
    def linked_issues(self) -> list[int]:
        """Get list of linked issue numbers."""
        return self._linked_issues.copy()

    @property
    def milestone_number(self) -> int | None:
        """Get the detected milestone number."""
        return self._milestone_number
