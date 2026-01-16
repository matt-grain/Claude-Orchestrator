"""Git-related utilities for parsing status and checking working directory state."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitStatusResult:
    """Result of parsing git status output.

    Attributes:
        untracked: List of untracked file paths (new files not in git)
        modified: List of modified tracked file paths (staged or unstaged changes)
        is_clean: True if no tracked changes exist (untracked files are ignored)
        has_tracked_changes: True if there are any staged or unstaged changes
    """

    untracked: list[str]
    modified: list[str]

    @property
    def is_clean(self) -> bool:
        """Check if working directory is clean (no tracked changes)."""
        return len(self.modified) == 0

    @property
    def has_tracked_changes(self) -> bool:
        """Check if there are any tracked changes (modified/staged/deleted)."""
        return len(self.modified) > 0


def parse_git_status_output(output: str) -> GitStatusResult:
    """Parse git status --porcelain output into structured result.

    The porcelain format uses a two-character prefix XY where:
    - X = status of the index (staging area)
    - Y = status of the work tree

    Key prefixes:
    - '??' = untracked file
    - 'M ' = modified in index (staged)
    - ' M' = modified in work tree (unstaged)
    - 'MM' = modified in both
    - 'A ' = added to index
    - 'D ' = deleted from index
    - ' D' = deleted from work tree
    - 'R ' = renamed in index
    - 'C ' = copied in index
    - 'AM' = added and modified

    Args:
        output: Raw output from `git status --porcelain`

    Returns:
        GitStatusResult with categorized file lists
    """
    untracked: list[str] = []
    modified: list[str] = []

    for line in output.splitlines():
        if not line or len(line) < 3:
            continue

        # Extract the two-character status prefix
        prefix = line[:2]
        # File path starts at position 3 (after "XY ")
        file_path = line[3:]

        # Handle renamed/copied files which have "old -> new" format
        if " -> " in file_path:
            file_path = file_path.split(" -> ", 1)[1]

        if prefix == "??":
            # Untracked file
            untracked.append(file_path)
        else:
            # Any other prefix indicates a tracked change
            # This includes: M, A, D, R, C, and combinations like MM, AM, etc.
            modified.append(file_path)

    return GitStatusResult(untracked=untracked, modified=modified)


def get_git_status(project_root: Path | None = None) -> GitStatusResult | None:
    """Get the current git status for a project.

    Args:
        project_root: Directory to check. Defaults to current directory.

    Returns:
        GitStatusResult if successful, None if git command fails
        (e.g., not a git repo, git not installed)
    """
    cwd = project_root or Path.cwd()

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            # Git command failed (not a repo, etc.)
            return None

        return parse_git_status_output(result.stdout)

    except FileNotFoundError:
        # Git not installed
        return None
    except subprocess.TimeoutExpired:
        # Timeout - treat as failure
        return None


def check_working_directory(project_root: Path | None = None) -> tuple[bool, int, list[str]]:
    """Check if the working directory has tracked changes.

    This is a higher-level function that returns information suitable
    for CLI dirty check warnings. Untracked files are ignored.

    Args:
        project_root: Directory to check. Defaults to current directory.

    Returns:
        Tuple of:
        - is_clean: True if no tracked changes
        - tracked_count: Number of modified/staged/deleted tracked files
        - modified_files: List of modified file paths (up to first 10)
    """
    status = get_git_status(project_root)

    if status is None:
        # Git unavailable or not a repo - consider clean
        return (True, 0, [])

    # Return only tracked changes, ignore untracked
    modified_files = status.modified[:10]  # Limit to first 10 for display
    return (status.is_clean, len(status.modified), modified_files)
