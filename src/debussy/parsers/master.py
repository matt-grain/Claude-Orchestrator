"""Parser for master plan files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from debussy.core.models import MasterPlan, Phase, PhaseStatus


def parse_master_plan(master_path: Path) -> MasterPlan:
    """Parse a master plan markdown file.

    Expected format:
    ```markdown
    # Feature Name - Master Plan

    **GitHub Issues:** #10, #11
    **GitHub Repo:** owner/repo

    ## Phases

    | Phase | Title | Focus | Risk | Status |
    |-------|-------|-------|------|--------|
    | 1 | [Unit of Work](feature-phase1.md) | ... | Low | Pending |
    | 2 | [State Model](feature-phase2.md) | ... | Low | Pending |
    ```
    """
    content = master_path.read_text(encoding="utf-8")

    # Extract name from first H1
    name_match = re.search(r"^#\s+(.+?)(?:\s*-\s*Master Plan)?$", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else master_path.stem

    # Find the phases table
    phases = _parse_phases_table(content, master_path.parent)

    # Extract GitHub sync metadata
    github_issues = _parse_github_issues(content)
    github_repo = _parse_github_repo(content)

    return MasterPlan(
        name=name,
        path=master_path,
        phases=phases,
        github_issues=github_issues,
        github_repo=github_repo,
        created_at=datetime.now(),
    )


def _parse_phases_table(content: str, base_dir: Path) -> list[Phase]:
    """Parse the phases table from markdown content."""
    phases: list[Phase] = []

    # Find table with Phase column
    # Match table rows: | 1 | [Title](path.md) | Focus | Risk | Status |
    # Phase IDs can be integers (1, 2, 3) or decimals (3.1, 3.2)
    table_pattern = re.compile(
        r"^\|\s*(\d+(?:\.\d+)?)\s*\|"  # Phase number (int or decimal)
        r"\s*\[([^\]]+)\]\(([^)]+)\)\s*\|"  # [Title](path.md)
        r"\s*[^|]*\|"  # Focus (skip)
        r"\s*[^|]*\|"  # Risk (skip)
        r"\s*(\w+)\s*\|",  # Status
        re.MULTILINE,
    )

    for match in table_pattern.finditer(content):
        phase_num = match.group(1)
        title = match.group(2).strip()
        rel_path = match.group(3).strip()
        status_str = match.group(4).strip().lower()

        # Convert status string to enum
        status = _parse_status(status_str)

        # Resolve path relative to master plan
        phase_path = base_dir / rel_path

        phases.append(
            Phase(
                id=phase_num,
                title=title,
                path=phase_path,
                status=status,
            )
        )

    return phases


def _parse_status(status_str: str) -> PhaseStatus:
    """Convert status string to PhaseStatus enum."""
    status_map = {
        "pending": PhaseStatus.PENDING,
        "in progress": PhaseStatus.RUNNING,
        "in_progress": PhaseStatus.RUNNING,
        "running": PhaseStatus.RUNNING,
        "validating": PhaseStatus.VALIDATING,
        "complete": PhaseStatus.COMPLETED,
        "completed": PhaseStatus.COMPLETED,
        "done": PhaseStatus.COMPLETED,
        "failed": PhaseStatus.FAILED,
        "blocked": PhaseStatus.BLOCKED,
        "awaiting": PhaseStatus.AWAITING_HUMAN,
        "awaiting_human": PhaseStatus.AWAITING_HUMAN,
    }
    return status_map.get(status_str.lower(), PhaseStatus.PENDING)


def _parse_github_issues(content: str) -> str | None:
    """Extract GitHub issues from master plan content.

    Supports formats:
    - **GitHub Issues:** #10, #11
    - **github_issues:** [10, 11]
    - GitHub Issues: #10

    Args:
        content: Master plan markdown content.

    Returns:
        Raw issues string if found, None otherwise.
    """
    # Match various formats for GitHub issues
    patterns = [
        r"\*\*(?:GitHub\s*Issues?|github_issues)\*\*:\s*(.+?)(?:\n|$)",  # **GitHub Issues:** ...
        r"(?:GitHub\s*Issues?|github_issues):\s*(.+?)(?:\n|$)",  # GitHub Issues: ...
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _parse_github_repo(content: str) -> str | None:
    """Extract GitHub repo from master plan content.

    Supports formats:
    - **GitHub Repo:** owner/repo
    - **github_repo:** owner/repo
    - GitHub Repo: owner/repo

    Args:
        content: Master plan markdown content.

    Returns:
        Repository string (owner/repo) if found, None otherwise.
    """
    # Match various formats for GitHub repo
    patterns = [
        r"\*\*(?:GitHub\s*Repo|github_repo)\*\*:\s*([^\s\n]+)",  # **GitHub Repo:** ...
        r"(?:GitHub\s*Repo|github_repo):\s*([^\s\n]+)",  # GitHub Repo: ...
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            repo = match.group(1).strip()
            # Validate it looks like owner/repo
            if "/" in repo:
                return repo

    return None
