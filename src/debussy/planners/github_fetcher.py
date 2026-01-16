"""GitHub issue fetcher using the gh CLI.

This module provides async functions to fetch GitHub issues using the
`gh` CLI tool. It supports filtering by milestone, label, and state.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from debussy.planners.models import (
    GitHubIssue,
    IssueLabel,
    IssueMilestone,
    IssueSet,
)

logger = logging.getLogger(__name__)

# Warning threshold for large issue counts
LARGE_ISSUE_THRESHOLD = 20

# Fields to request from gh CLI
GH_ISSUE_FIELDS = "number,title,body,labels,state,milestone,assignees,url"

IssueState = Literal["open", "closed", "all"]


class GHError(Exception):
    """Base exception for gh CLI errors."""


class GHNotFoundError(GHError):
    """The gh CLI tool is not installed or not found."""


class GHAuthError(GHError):
    """Authentication with GitHub failed."""


class GHRateLimitError(GHError):
    """GitHub API rate limit exceeded."""


@dataclass
class GHResult:
    """Result of a gh CLI command execution."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        """Check if the command succeeded."""
        return self.returncode == 0


def check_gh_available() -> bool:
    """Check if the gh CLI is installed and available.

    Returns:
        True if gh CLI is available, False otherwise.
    """
    return shutil.which("gh") is not None


async def _run_gh_command(args: list[str]) -> GHResult:
    """Run a gh CLI command asynchronously.

    Args:
        args: Arguments to pass to gh CLI (excluding 'gh' itself).

    Returns:
        GHResult with stdout, stderr, and return code.

    Raises:
        GHNotFoundError: If gh CLI is not installed.
        GHAuthError: If authentication fails.
        GHRateLimitError: If rate limit is exceeded.
    """
    if not check_gh_available():
        raise GHNotFoundError("gh CLI not found. Please install it from https://cli.github.com/")

    cmd = ["gh", *args]
    logger.debug(f"Running gh command: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    returncode = process.returncode or 0

    result = GHResult(stdout=stdout, stderr=stderr, returncode=returncode)

    # Check for specific error conditions
    if not result.success:
        if "authentication" in stderr.lower() or "not logged in" in stderr.lower():
            raise GHAuthError(f"GitHub authentication failed: {stderr}")
        if "rate limit" in stderr.lower() or "API rate limit" in stderr.lower():
            raise GHRateLimitError(f"GitHub rate limit exceeded: {stderr}")

    return result


def _parse_gh_json(json_str: str, source: str = "", filter_used: str = "") -> IssueSet:
    """Parse gh CLI JSON output into an IssueSet.

    Args:
        json_str: JSON string from gh CLI output.
        source: Description of the data source (e.g., repo name).
        filter_used: Description of the filter used.

    Returns:
        IssueSet containing parsed GitHubIssue objects.
    """
    if not json_str.strip():
        return IssueSet(
            issues=[],
            source=source,
            filter_used=filter_used,
            fetched_at=datetime.now(),
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse gh JSON output: {e}")
        return IssueSet(
            issues=[],
            source=source,
            filter_used=filter_used,
            fetched_at=datetime.now(),
        )

    issues: list[GitHubIssue] = []

    for item in data:
        # Parse labels
        labels = []
        for label_data in item.get("labels", []):
            labels.append(
                IssueLabel(
                    name=label_data.get("name", ""),
                    description=label_data.get("description"),
                )
            )

        # Parse milestone
        milestone = None
        milestone_data = item.get("milestone")
        if milestone_data:
            due_on = None
            due_on_str = milestone_data.get("dueOn")
            if due_on_str:
                with contextlib.suppress(ValueError):
                    due_on = datetime.fromisoformat(due_on_str.replace("Z", "+00:00"))
            milestone = IssueMilestone(
                title=milestone_data.get("title", ""),
                description=milestone_data.get("description"),
                due_on=due_on,
            )

        # Parse assignees
        assignees = [a.get("login", "") for a in item.get("assignees", [])]

        issue = GitHubIssue(
            number=item.get("number", 0),
            title=item.get("title", ""),
            body=item.get("body", "") or "",
            labels=labels,
            state=item.get("state", "OPEN"),
            milestone=milestone,
            assignees=assignees,
            url=item.get("url", ""),
        )
        issues.append(issue)

    issue_set = IssueSet(
        issues=issues,
        source=source,
        filter_used=filter_used,
        fetched_at=datetime.now(),
    )

    # Log warning if issue count exceeds threshold
    if len(issues) > LARGE_ISSUE_THRESHOLD:
        logger.warning(f"Fetched {len(issues)} issues (>{LARGE_ISSUE_THRESHOLD}). Consider using more specific filters.")

    return issue_set


async def fetch_issues_by_milestone(
    repo: str,
    milestone: str,
    state: IssueState = "open",
) -> IssueSet:
    """Fetch issues from a repository filtered by milestone.

    Args:
        repo: Repository in format 'owner/repo'.
        milestone: Milestone title to filter by.
        state: Issue state filter ('open', 'closed', or 'all').

    Returns:
        IssueSet containing the fetched issues.

    Raises:
        GHNotFoundError: If gh CLI is not installed.
        GHAuthError: If authentication fails.
        GHRateLimitError: If rate limit is exceeded.
    """
    args = [
        "issue",
        "list",
        "--repo",
        repo,
        "--milestone",
        milestone,
        "--state",
        state,
        "--json",
        GH_ISSUE_FIELDS,
    ]

    result = await _run_gh_command(args)

    if not result.success:
        logger.warning(f"gh command failed: {result.stderr}")
        return IssueSet(
            issues=[],
            source=repo,
            filter_used=f"milestone:{milestone} state:{state}",
            fetched_at=datetime.now(),
        )

    return _parse_gh_json(
        result.stdout,
        source=repo,
        filter_used=f"milestone:{milestone} state:{state}",
    )


async def fetch_issues_by_label(
    repo: str,
    label: str,
    state: IssueState = "open",
) -> IssueSet:
    """Fetch issues from a repository filtered by a single label.

    Args:
        repo: Repository in format 'owner/repo'.
        label: Label name to filter by.
        state: Issue state filter ('open', 'closed', or 'all').

    Returns:
        IssueSet containing the fetched issues.

    Raises:
        GHNotFoundError: If gh CLI is not installed.
        GHAuthError: If authentication fails.
        GHRateLimitError: If rate limit is exceeded.
    """
    args = [
        "issue",
        "list",
        "--repo",
        repo,
        "--label",
        label,
        "--state",
        state,
        "--json",
        GH_ISSUE_FIELDS,
    ]

    result = await _run_gh_command(args)

    if not result.success:
        logger.warning(f"gh command failed: {result.stderr}")
        return IssueSet(
            issues=[],
            source=repo,
            filter_used=f"label:{label} state:{state}",
            fetched_at=datetime.now(),
        )

    return _parse_gh_json(
        result.stdout,
        source=repo,
        filter_used=f"label:{label} state:{state}",
    )


async def fetch_issues_by_labels(
    repo: str,
    labels: list[str],
    state: IssueState = "open",
) -> IssueSet:
    """Fetch issues from a repository filtered by multiple labels (AND logic).

    Args:
        repo: Repository in format 'owner/repo'.
        labels: List of label names to filter by (all must match).
        state: Issue state filter ('open', 'closed', or 'all').

    Returns:
        IssueSet containing the fetched issues.

    Raises:
        GHNotFoundError: If gh CLI is not installed.
        GHAuthError: If authentication fails.
        GHRateLimitError: If rate limit is exceeded.
    """
    if not labels:
        return IssueSet(
            issues=[],
            source=repo,
            filter_used=f"labels:[] state:{state}",
            fetched_at=datetime.now(),
        )

    # gh CLI supports multiple --label flags for AND logic
    args = [
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
    ]

    for label in labels:
        args.extend(["--label", label])

    args.extend(["--json", GH_ISSUE_FIELDS])

    result = await _run_gh_command(args)

    filter_str = f"labels:{','.join(labels)} state:{state}"

    if not result.success:
        logger.warning(f"gh command failed: {result.stderr}")
        return IssueSet(
            issues=[],
            source=repo,
            filter_used=filter_str,
            fetched_at=datetime.now(),
        )

    return _parse_gh_json(result.stdout, source=repo, filter_used=filter_str)


async def fetch_issue_detail(repo: str, issue_number: int) -> GitHubIssue | None:
    """Fetch detailed information about a single issue.

    Args:
        repo: Repository in format 'owner/repo'.
        issue_number: The issue number to fetch.

    Returns:
        GitHubIssue with full details, or None if not found.

    Raises:
        GHNotFoundError: If gh CLI is not installed.
        GHAuthError: If authentication fails.
        GHRateLimitError: If rate limit is exceeded.
    """
    args = [
        "issue",
        "view",
        str(issue_number),
        "--repo",
        repo,
        "--json",
        GH_ISSUE_FIELDS,
    ]

    result = await _run_gh_command(args)

    if not result.success:
        logger.warning(f"Failed to fetch issue {issue_number}: {result.stderr}")
        return None

    # gh issue view returns a single object, not an array
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse issue detail JSON: {e}")
        return None

    # Wrap single item in list for parsing
    issue_set = _parse_gh_json(
        json.dumps([data]),
        source=repo,
        filter_used=f"issue:{issue_number}",
    )

    return issue_set.issues[0] if issue_set.issues else None
