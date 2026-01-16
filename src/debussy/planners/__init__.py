"""Issue-to-plan pipeline for Debussy.

This module provides functionality to fetch GitHub issues and transform
them into structured implementation plans.
"""

from __future__ import annotations

from debussy.planners.github_fetcher import (
    GHAuthError,
    GHError,
    GHNotFoundError,
    GHRateLimitError,
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

__all__ = [
    "GHAuthError",
    "GHError",
    "GHNotFoundError",
    "GHRateLimitError",
    "GitHubIssue",
    "IssueLabel",
    "IssueMilestone",
    "IssueSet",
    "check_gh_available",
    "fetch_issue_detail",
    "fetch_issues_by_label",
    "fetch_issues_by_labels",
    "fetch_issues_by_milestone",
]
