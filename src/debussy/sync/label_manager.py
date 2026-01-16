"""Label lifecycle management for GitHub issue sync.

This module handles creation, update, and atomic state transitions
of Debussy labels on GitHub issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from debussy.config import GitHubLabelConfig
    from debussy.sync.github_client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class LabelState:
    """Represents the current Debussy label state on an issue."""

    in_progress: bool = False
    completed: bool = False
    failed: bool = False

    def active_label(self, config: GitHubLabelConfig) -> str | None:
        """Get the name of the active Debussy label, if any."""
        if self.in_progress:
            return config.in_progress
        if self.completed:
            return config.completed
        if self.failed:
            return config.failed
        return None


class LabelManager:
    """Manages Debussy label lifecycle on GitHub issues.

    Handles:
    - Label creation if missing
    - Atomic state transitions (remove old state, add new)
    - Detection of current label state
    """

    def __init__(
        self,
        client: GitHubClient,
        config: GitHubLabelConfig,
        create_if_missing: bool = True,
    ) -> None:
        """Initialize the label manager.

        Args:
            client: GitHubClient instance for API calls.
            config: Label configuration with names and colors.
            create_if_missing: Whether to create labels if they don't exist.
        """
        self.client = client
        self.config = config
        self.create_if_missing = create_if_missing
        self._labels_ensured = False

    async def ensure_labels_exist(self) -> None:
        """Ensure all Debussy labels exist in the repository.

        Creates labels if they don't exist and create_if_missing is True.
        """
        if self._labels_ensured or not self.create_if_missing:
            return

        label_configs = [
            (self.config.in_progress, self.config.color_in_progress, "Phase in progress"),
            (self.config.completed, self.config.color_completed, "Phase completed"),
            (self.config.failed, self.config.color_failed, "Phase failed"),
        ]

        for name, color, description in label_configs:
            try:
                await self.client.ensure_label(name, color, description)
                logger.debug(f"Ensured label exists: {name}")
            except Exception as e:
                logger.warning(f"Failed to ensure label '{name}': {e}")

        self._labels_ensured = True

    def get_debussy_labels(self) -> list[str]:
        """Get list of all Debussy label names."""
        return [
            self.config.in_progress,
            self.config.completed,
            self.config.failed,
        ]

    def detect_state(self, current_labels: list[str]) -> LabelState:
        """Detect the current Debussy label state from issue labels.

        Args:
            current_labels: List of label names currently on the issue.

        Returns:
            LabelState indicating which Debussy labels are present.
        """
        return LabelState(
            in_progress=self.config.in_progress in current_labels,
            completed=self.config.completed in current_labels,
            failed=self.config.failed in current_labels,
        )

    async def set_in_progress(self, issue_number: int) -> list[str]:
        """Set issue to in-progress state atomically.

        Removes any existing Debussy state labels and adds in-progress.

        Args:
            issue_number: The issue number.

        Returns:
            Updated list of labels on the issue.
        """
        return await self._transition_to_state(
            issue_number,
            target_label=self.config.in_progress,
        )

    async def set_completed(self, issue_number: int) -> list[str]:
        """Set issue to completed state atomically.

        Removes any existing Debussy state labels and adds completed.

        Args:
            issue_number: The issue number.

        Returns:
            Updated list of labels on the issue.
        """
        return await self._transition_to_state(
            issue_number,
            target_label=self.config.completed,
        )

    async def set_failed(self, issue_number: int) -> list[str]:
        """Set issue to failed state atomically.

        Removes any existing Debussy state labels and adds failed.

        Args:
            issue_number: The issue number.

        Returns:
            Updated list of labels on the issue.
        """
        return await self._transition_to_state(
            issue_number,
            target_label=self.config.failed,
        )

    async def clear_state(self, issue_number: int) -> list[str]:
        """Remove all Debussy state labels from an issue.

        Args:
            issue_number: The issue number.

        Returns:
            Updated list of labels on the issue.
        """
        return await self._transition_to_state(issue_number, target_label=None)

    async def _transition_to_state(
        self,
        issue_number: int,
        target_label: str | None,
    ) -> list[str]:
        """Atomically transition to a new label state.

        1. Get current issue labels
        2. Remove all existing Debussy state labels
        3. Add the target label (if not None)
        4. Update the issue in a single API call

        Args:
            issue_number: The issue number.
            target_label: The label to set, or None to clear all state.

        Returns:
            Updated list of labels on the issue.
        """
        # Ensure labels exist before transitioning
        await self.ensure_labels_exist()

        # Get current issue to see existing labels
        issue = await self.client.get_issue(issue_number)
        current_labels = issue.labels

        # Build new label list: remove all Debussy state labels
        debussy_labels = set(self.get_debussy_labels())
        new_labels = [label for label in current_labels if label not in debussy_labels]

        # Add target label if specified
        if target_label:
            new_labels.append(target_label)

        # Update issue with new labels
        return await self.client.update_labels(issue_number, new_labels)
