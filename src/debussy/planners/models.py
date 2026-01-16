"""Data models for GitHub issue representation.

These models represent the structure of GitHub issues as fetched
via the gh CLI tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IssueLabel:
    """A label attached to a GitHub issue."""

    name: str
    description: str | None = None


@dataclass
class IssueMilestone:
    """A milestone associated with a GitHub issue."""

    title: str
    description: str | None = None
    due_on: datetime | None = None


@dataclass
class GitHubIssue:
    """A GitHub issue with its metadata.

    Represents an issue as returned by `gh issue list --json`.
    """

    number: int
    title: str
    body: str
    labels: list[IssueLabel] = field(default_factory=list)
    state: str = "OPEN"
    milestone: IssueMilestone | None = None
    assignees: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def is_open(self) -> bool:
        """Check if the issue is open."""
        return self.state.upper() == "OPEN"

    @property
    def is_closed(self) -> bool:
        """Check if the issue is closed."""
        return self.state.upper() == "CLOSED"

    @property
    def label_names(self) -> list[str]:
        """Get a list of label names for this issue."""
        return [label.name for label in self.labels]


@dataclass
class IssueSet:
    """A collection of GitHub issues with metadata about the fetch.

    Stores the issues along with information about how and when
    they were fetched.
    """

    issues: list[GitHubIssue] = field(default_factory=list)
    source: str = ""
    filter_used: str = ""
    fetched_at: datetime = field(default_factory=datetime.now)

    def __len__(self) -> int:
        """Return the number of issues in the set."""
        return len(self.issues)

    def __iter__(self):
        """Iterate over the issues."""
        return iter(self.issues)

    @property
    def open_issues(self) -> list[GitHubIssue]:
        """Get all open issues in the set."""
        return [issue for issue in self.issues if issue.is_open]

    @property
    def closed_issues(self) -> list[GitHubIssue]:
        """Get all closed issues in the set."""
        return [issue for issue in self.issues if issue.is_closed]
