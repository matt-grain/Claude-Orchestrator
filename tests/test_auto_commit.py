"""Tests for auto-commit functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from debussy.config import Config
from debussy.core.models import Phase, PhaseStatus


def _noop_init(_self: Any, *_args: Any, **_kwargs: Any) -> None:
    """No-op init for patching Orchestrator."""
    pass


class TestAutoCommitConfig:
    """Tests for auto-commit configuration fields."""

    def test_default_auto_commit_is_true(self) -> None:
        """Auto-commit is enabled by default."""
        config = Config()
        assert config.auto_commit is True

    def test_default_commit_on_failure_is_false(self) -> None:
        """Commit on failure is disabled by default."""
        config = Config()
        assert config.commit_on_failure is False

    def test_default_commit_message_template(self) -> None:
        """Default commit message template has expected format."""
        config = Config()
        assert "{phase_id}" in config.commit_message_template
        assert "{phase_name}" in config.commit_message_template
        assert "{status}" in config.commit_message_template

    def test_can_override_auto_commit(self) -> None:
        """Auto-commit can be set to False."""
        config = Config(auto_commit=False)
        assert config.auto_commit is False

    def test_can_override_commit_on_failure(self) -> None:
        """Commit on failure can be enabled."""
        config = Config(commit_on_failure=True)
        assert config.commit_on_failure is True

    def test_can_override_commit_message_template(self) -> None:
        """Commit message template can be customized."""
        custom_template = "Custom: {phase_id}"
        config = Config(commit_message_template=custom_template)
        assert config.commit_message_template == custom_template


class TestAutoCommitPhase:
    """Tests for _auto_commit_phase() method."""

    @pytest.fixture
    def mock_orchestrator(self) -> MagicMock:
        """Create a mock orchestrator with required attributes."""
        orchestrator = MagicMock()
        orchestrator.config = Config()
        orchestrator.project_root = Path("/test/project")
        orchestrator.ui = MagicMock()
        return orchestrator

    @pytest.fixture
    def test_phase(self) -> Phase:
        """Create a test phase."""
        return Phase(
            id="1",
            title="Test Phase",
            path=Path("/test/phase.md"),
            status=PhaseStatus.PENDING,
        )

    @patch("subprocess.run")
    def test_commits_on_successful_phase(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase commits changes on successful phase."""
        from debussy.core.orchestrator import Orchestrator

        # Mock git status showing changes
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="M src/file.py\n"),  # git status
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
        ]

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config()
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=True)

        # Should have called git add and commit
        assert mock_run.call_count == 3

    @patch("subprocess.run")
    def test_skips_commit_when_auto_commit_disabled(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase skips commit when config.auto_commit is False."""
        from debussy.core.orchestrator import Orchestrator

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config(auto_commit=False)
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=True)

        # Should not have called any git commands
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_skips_commit_on_failure_by_default(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase skips commit on failure when commit_on_failure is False."""
        from debussy.core.orchestrator import Orchestrator

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config(commit_on_failure=False)
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=False)

        # Should not have called any git commands
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_commits_on_failure_when_enabled(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase commits on failure when commit_on_failure is True."""
        from debussy.core.orchestrator import Orchestrator

        # Mock git status showing changes
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="M src/file.py\n"),  # git status
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
        ]

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config(commit_on_failure=True)
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=False)

        # Should have called git add and commit
        assert mock_run.call_count == 3

    @patch("subprocess.run")
    def test_skips_commit_when_no_changes(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase skips commit when no changes detected."""
        from debussy.core.orchestrator import Orchestrator

        # Mock git status showing no changes
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config()
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=True)

        # Should only have called git status (not add/commit)
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_commit_message_uses_template(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase formats commit message using template."""
        from debussy.core.orchestrator import Orchestrator

        # Mock git commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="M src/file.py\n"),  # git status
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
        ]

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config()
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=True)

        # Check commit message contains phase info
        commit_call = mock_run.call_args_list[2]
        commit_args = commit_call[0][0]
        assert "git" in commit_args
        assert "commit" in commit_args
        commit_message = commit_args[commit_args.index("-m") + 1]
        assert "1" in commit_message  # phase_id
        assert "Test Phase" in commit_message  # phase_name

    @patch("subprocess.run")
    def test_commit_message_includes_co_author(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase includes Co-Authored-By in commit message."""
        from debussy.core.orchestrator import Orchestrator

        # Mock git commands
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="M src/file.py\n"),  # git status
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
        ]

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config(model="sonnet")
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            orchestrator._auto_commit_phase(test_phase, success=True)

        # Check commit message contains Co-Authored-By
        commit_call = mock_run.call_args_list[2]
        commit_args = commit_call[0][0]
        commit_message = commit_args[commit_args.index("-m") + 1]
        assert "Co-Authored-By:" in commit_message
        assert "Claude" in commit_message

    @patch("subprocess.run")
    def test_handles_git_not_found(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase handles git not being installed."""
        from debussy.core.orchestrator import Orchestrator

        mock_run.side_effect = FileNotFoundError()

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config()
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            # Should not raise an exception
            orchestrator._auto_commit_phase(test_phase, success=True)

    @patch("subprocess.run")
    def test_handles_git_timeout(self, mock_run: MagicMock, test_phase: Phase) -> None:
        """_auto_commit_phase handles git command timeout."""
        import subprocess

        from debussy.core.orchestrator import Orchestrator

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.config = Config()
            orchestrator.project_root = Path("/test/project")
            orchestrator.ui = MagicMock()

            # Should not raise an exception
            orchestrator._auto_commit_phase(test_phase, success=True)


class TestCheckCleanWorkingDirectory:
    """Tests for check_clean_working_directory() method.

    Note: The method now returns (is_clean, count, modified_files) tuple
    and only counts tracked changes (untracked files are ignored).
    """

    @patch("subprocess.run")
    def test_returns_true_for_clean_directory(self, mock_run: MagicMock) -> None:
        """check_clean_working_directory returns (True, 0, []) for clean directory."""
        from debussy.core.orchestrator import Orchestrator

        mock_run.return_value = MagicMock(returncode=0, stdout="")

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.project_root = Path("/test/project")

            is_clean, count, files = orchestrator.check_clean_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("subprocess.run")
    def test_returns_false_for_dirty_directory(self, mock_run: MagicMock) -> None:
        """check_clean_working_directory returns (False, N, files) for dirty directory.

        Note: Untracked files (??) are no longer counted as dirty.
        Only tracked modifications (M, A, D, etc.) are counted.
        """
        from debussy.core.orchestrator import Orchestrator

        # Use proper porcelain format: "XY file"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" M file1.py\n M file2.py\n?? newfile.py\n",
        )

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.project_root = Path("/test/project")

            is_clean, count, files = orchestrator.check_clean_working_directory()

        assert is_clean is False
        # Only 2 modified files count, the untracked (??) file is ignored
        assert count == 2
        assert set(files) == {"file1.py", "file2.py"}

    @patch("subprocess.run")
    def test_returns_true_when_git_not_available(self, mock_run: MagicMock) -> None:
        """check_clean_working_directory returns (True, 0, []) when git not available."""
        from debussy.core.orchestrator import Orchestrator

        mock_run.side_effect = FileNotFoundError()

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.project_root = Path("/test/project")

            is_clean, count, files = orchestrator.check_clean_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("subprocess.run")
    def test_returns_true_on_timeout(self, mock_run: MagicMock) -> None:
        """check_clean_working_directory returns (True, 0, []) on timeout."""
        import subprocess

        from debussy.core.orchestrator import Orchestrator

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.project_root = Path("/test/project")

            is_clean, count, files = orchestrator.check_clean_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []

    @patch("subprocess.run")
    def test_returns_true_when_not_a_git_repo(self, mock_run: MagicMock) -> None:
        """check_clean_working_directory returns (True, 0, []) when not a git repo."""
        from debussy.core.orchestrator import Orchestrator

        mock_run.return_value = MagicMock(
            returncode=128,
            stderr="fatal: not a git repository",
        )

        with patch.object(Orchestrator, "__init__", _noop_init):
            orchestrator = Orchestrator.__new__(Orchestrator)
            orchestrator.project_root = Path("/test/project")

            is_clean, count, files = orchestrator.check_clean_working_directory()

        assert is_clean is True
        assert count == 0
        assert files == []


class TestCLIAutoCommitFlags:
    """Tests for CLI auto-commit flags."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_no_auto_commit_flag_exists(self) -> None:
        """--no-auto-commit flag is available on run command."""
        # Check the function signature has the parameter
        import inspect

        from debussy.cli import run

        sig = inspect.signature(run)
        assert "auto_commit" in sig.parameters

    def test_allow_dirty_flag_exists(self) -> None:
        """--allow-dirty flag is available on run command."""
        import inspect

        from debussy.cli import run

        sig = inspect.signature(run)
        assert "allow_dirty" in sig.parameters

    def test_no_auto_commit_disables_auto_commit(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--no-auto-commit flag sets config.auto_commit to False."""
        from debussy.cli import app

        # Create a mock master plan file with valid structure
        master_plan = tmp_path / "MASTER_PLAN.md"
        master_plan.write_text("""# Test Plan

## Phases

| Phase | Title | File |
|-------|-------|------|
| 1 | Setup | phase-1.md |
""")

        # Create phase file
        phase_file = tmp_path / "phase-1.md"
        phase_file.write_text("""# Phase 1: Setup

## Gates
- ruff: `uv run ruff check .`
""")

        # Run with --no-auto-commit and --dry-run
        result = runner.invoke(
            app,
            ["run", str(master_plan), "--no-auto-commit", "--dry-run"],
            catch_exceptions=False,
        )

        # Should use dry-run mode without error
        assert result.exit_code == 0


class TestAutoCommitMessageFormat:
    """Tests for commit message formatting."""

    def test_success_message_has_checkmark(self) -> None:
        """Successful phase commit message includes checkmark."""
        config = Config()
        message = config.commit_message_template.format(
            phase_id="1",
            phase_name="Test Phase",
            status="✓",
        )
        assert "✓" in message
        assert "1" in message
        assert "Test Phase" in message

    def test_failure_message_has_warning(self) -> None:
        """Failed phase commit message includes warning icon."""
        config = Config()
        message = config.commit_message_template.format(
            phase_id="2",
            phase_name="Build Phase",
            status="⚠️",
        )
        assert "⚠️" in message
        assert "2" in message
        assert "Build Phase" in message

    def test_custom_template_works(self) -> None:
        """Custom commit message template is properly formatted."""
        config = Config(commit_message_template="[{phase_id}] {phase_name}: {status}")
        message = config.commit_message_template.format(
            phase_id="3",
            phase_name="Deploy",
            status="✓",
        )
        assert message == "[3] Deploy: ✓"
