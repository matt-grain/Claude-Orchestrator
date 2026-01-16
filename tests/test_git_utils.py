"""Tests for git utility functions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from debussy.utils.git import (
    GitStatusResult,
    check_working_directory,
    get_git_status,
    parse_git_status_output,
)


class TestParseGitStatusOutput:
    """Tests for parse_git_status_output function."""

    def test_empty_output_returns_clean(self) -> None:
        """Empty output indicates clean working directory."""
        result = parse_git_status_output("")
        assert result.untracked == []
        assert result.modified == []
        assert result.is_clean is True
        assert result.has_tracked_changes is False

    def test_only_whitespace_returns_clean(self) -> None:
        """Whitespace-only output is clean."""
        result = parse_git_status_output("  \n\n  ")
        assert result.is_clean is True
        assert result.untracked == []
        assert result.modified == []

    def test_untracked_files_only(self) -> None:
        """Untracked files are categorized correctly."""
        output = """\
?? notes/test.md
?? temp.txt
?? scripts/debug.py
"""
        result = parse_git_status_output(output)
        assert result.untracked == ["notes/test.md", "temp.txt", "scripts/debug.py"]
        assert result.modified == []
        assert result.is_clean is True  # Untracked files don't make it "dirty"
        assert result.has_tracked_changes is False

    def test_modified_in_worktree(self) -> None:
        """Modified in worktree (unstaged) are tracked changes."""
        output = " M src/main.py\n M tests/test_foo.py"
        result = parse_git_status_output(output)
        assert result.untracked == []
        assert result.modified == ["src/main.py", "tests/test_foo.py"]
        assert result.is_clean is False
        assert result.has_tracked_changes is True

    def test_modified_in_index(self) -> None:
        """Modified in index (staged) are tracked changes."""
        output = "M  src/staged.py\nM  docs/README.md"
        result = parse_git_status_output(output)
        assert result.modified == ["src/staged.py", "docs/README.md"]
        assert result.is_clean is False

    def test_modified_in_both(self) -> None:
        """Modified in both index and worktree."""
        output = "MM src/both.py"
        result = parse_git_status_output(output)
        assert result.modified == ["src/both.py"]
        assert result.is_clean is False

    def test_added_files(self) -> None:
        """Added files (staged new files) are tracked changes."""
        output = "A  src/new_file.py\nA  tests/new_test.py"
        result = parse_git_status_output(output)
        assert result.modified == ["src/new_file.py", "tests/new_test.py"]
        assert result.is_clean is False

    def test_deleted_files(self) -> None:
        """Deleted files are tracked changes."""
        output = "D  old_file.py\n D deleted_unstaged.py"
        result = parse_git_status_output(output)
        assert result.modified == ["old_file.py", "deleted_unstaged.py"]
        assert result.is_clean is False

    def test_renamed_file(self) -> None:
        """Renamed files show the new path."""
        output = "R  old_name.py -> new_name.py"
        result = parse_git_status_output(output)
        assert result.modified == ["new_name.py"]
        assert result.is_clean is False

    def test_copied_file(self) -> None:
        """Copied files show the new path."""
        output = "C  original.py -> copy.py"
        result = parse_git_status_output(output)
        assert result.modified == ["copy.py"]
        assert result.is_clean is False

    def test_added_and_modified(self) -> None:
        """Added then modified files."""
        output = "AM src/new_then_changed.py"
        result = parse_git_status_output(output)
        assert result.modified == ["src/new_then_changed.py"]
        assert result.is_clean is False

    def test_mixed_state(self) -> None:
        """Mix of untracked, modified, and staged files."""
        output = """\
?? notes/temp.md
?? scratch.txt
 M src/module.py
M  staged.py
MM both_changed.py
A  new_feature.py
D  removed.py
"""
        result = parse_git_status_output(output)

        assert set(result.untracked) == {"notes/temp.md", "scratch.txt"}
        assert set(result.modified) == {
            "src/module.py",
            "staged.py",
            "both_changed.py",
            "new_feature.py",
            "removed.py",
        }
        assert result.is_clean is False
        assert result.has_tracked_changes is True

    def test_short_lines_ignored(self) -> None:
        """Lines too short to contain status are ignored."""
        output = "X\n\nAB"  # Line with < 3 chars
        result = parse_git_status_output(output)
        assert result.is_clean is True


class TestGitStatusResult:
    """Tests for GitStatusResult dataclass properties."""

    def test_is_clean_with_no_changes(self) -> None:
        """is_clean is True when no modified files."""
        result = GitStatusResult(untracked=[], modified=[])
        assert result.is_clean is True

    def test_is_clean_with_untracked_only(self) -> None:
        """is_clean is True even with untracked files."""
        result = GitStatusResult(untracked=["notes.md", "temp/"], modified=[])
        assert result.is_clean is True

    def test_is_clean_false_with_modified(self) -> None:
        """is_clean is False when modified files exist."""
        result = GitStatusResult(untracked=[], modified=["src/main.py"])
        assert result.is_clean is False

    def test_has_tracked_changes_false_when_empty(self) -> None:
        """has_tracked_changes is False when no modified files."""
        result = GitStatusResult(untracked=["foo.txt"], modified=[])
        assert result.has_tracked_changes is False

    def test_has_tracked_changes_true_when_modified(self) -> None:
        """has_tracked_changes is True when modified files exist."""
        result = GitStatusResult(untracked=[], modified=["bar.py"])
        assert result.has_tracked_changes is True


class TestGetGitStatus:
    """Tests for get_git_status function with mocked subprocess."""

    @patch("subprocess.run")
    def test_returns_parsed_result_on_success(self, mock_run: patch) -> None:
        """Successful git status returns parsed result."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="?? untracked.txt\n M modified.py\n",
            stderr="",
        )

        result = get_git_status()

        assert result is not None
        assert result.untracked == ["untracked.txt"]
        assert result.modified == ["modified.py"]
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_returns_none_on_non_zero_exit(self, mock_run: patch) -> None:
        """Non-zero exit code (not a git repo) returns None."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        result = get_git_status()
        assert result is None

    @patch("subprocess.run")
    def test_returns_none_on_file_not_found(self, mock_run: patch) -> None:
        """FileNotFoundError (git not installed) returns None."""
        mock_run.side_effect = FileNotFoundError("git not found")

        result = get_git_status()
        assert result is None

    @patch("subprocess.run")
    def test_returns_none_on_timeout(self, mock_run: patch) -> None:
        """Timeout returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)

        result = get_git_status()
        assert result is None

    @patch("subprocess.run")
    def test_uses_provided_project_root(self, mock_run: patch) -> None:
        """Uses specified project_root as cwd."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )

        project_path = Path("/custom/project")
        get_git_status(project_path)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == project_path


class TestCheckWorkingDirectory:
    """Tests for check_working_directory function."""

    @patch("debussy.utils.git.get_git_status")
    def test_returns_clean_when_git_unavailable(self, mock_get_status: patch) -> None:
        """Returns clean status when git is unavailable."""
        mock_get_status.return_value = None

        is_clean, count, files = check_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("debussy.utils.git.get_git_status")
    def test_returns_clean_when_no_changes(self, mock_get_status: patch) -> None:
        """Returns clean when no changes."""
        mock_get_status.return_value = GitStatusResult(untracked=[], modified=[])

        is_clean, count, files = check_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("debussy.utils.git.get_git_status")
    def test_returns_clean_when_only_untracked(self, mock_get_status: patch) -> None:
        """Returns clean when only untracked files exist."""
        mock_get_status.return_value = GitStatusResult(
            untracked=["notes/foo.md", "temp.txt"],
            modified=[],
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("debussy.utils.git.get_git_status")
    def test_returns_dirty_when_modified_files(self, mock_get_status: patch) -> None:
        """Returns dirty when modified files exist."""
        mock_get_status.return_value = GitStatusResult(
            untracked=["notes/temp.md"],
            modified=["src/main.py", "tests/test.py"],
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is False
        assert count == 2
        assert files == ["src/main.py", "tests/test.py"]

    @patch("debussy.utils.git.get_git_status")
    def test_limits_file_list_to_ten(self, mock_get_status: patch) -> None:
        """Limits returned file list to first 10 files."""
        many_files = [f"file{i}.py" for i in range(15)]
        mock_get_status.return_value = GitStatusResult(
            untracked=[],
            modified=many_files,
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is False
        assert count == 15  # Total count is accurate
        assert len(files) == 10  # But list is limited
        assert files == many_files[:10]

    @patch("debussy.utils.git.get_git_status")
    def test_passes_project_root_to_get_git_status(self, mock_get_status: patch) -> None:
        """Passes project_root parameter through."""
        mock_get_status.return_value = GitStatusResult(untracked=[], modified=[])
        project_path = Path("/my/project")

        check_working_directory(project_path)

        mock_get_status.assert_called_once_with(project_path)


class TestGitDirtyCheckIntegration:
    """Integration tests for the dirty check behavior."""

    @patch("subprocess.run")
    def test_full_flow_clean_repo(self, mock_run: patch) -> None:
        """Clean repository reports as clean."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("subprocess.run")
    def test_full_flow_untracked_only(self, mock_run: patch) -> None:
        """Only untracked files does not block."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="""\
?? notes/session.md
?? .debussy/
?? scratch.py
""",
            stderr="",
        )

        is_clean, count, files = check_working_directory()

        # Untracked files should NOT trigger dirty warning
        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("subprocess.run")
    def test_full_flow_modified_tracked(self, mock_run: patch) -> None:
        """Modified tracked files trigger dirty warning."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="""\
 M src/debussy/cli.py
M  tests/test_cli.py
?? notes/temp.md
""",
            stderr="",
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is False
        assert count == 2  # Only tracked changes count
        assert set(files) == {"src/debussy/cli.py", "tests/test_cli.py"}

    @patch("subprocess.run")
    def test_full_flow_mixed_state(self, mock_run: patch) -> None:
        """Mix of staged, modified, deleted, untracked."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="""\
?? notes/
?? .coverage
M  staged_file.py
 M unstaged_change.py
MM staged_and_changed.py
D  deleted_file.py
A  new_staged.py
R  old_name.py -> renamed.py
""",
            stderr="",
        )

        is_clean, count, files = check_working_directory()

        assert is_clean is False
        assert count == 6  # All tracked changes (excluding untracked)
        expected_files = {
            "staged_file.py",
            "unstaged_change.py",
            "staged_and_changed.py",
            "deleted_file.py",
            "new_staged.py",
            "renamed.py",  # Renamed shows new name
        }
        assert set(files) == expected_files
