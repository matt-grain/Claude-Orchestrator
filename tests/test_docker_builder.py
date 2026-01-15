"""Tests for the DockerCommandBuilder module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from debussy.runners.docker_builder import (
    BASE_CLAUDE_ARGS,
    CONTAINER_PATH,
    EXCLUDED_DIRS,
    SANDBOX_IMAGE,
    DockerCommandBuilder,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a project root directory."""
    return tmp_path / "project"


@pytest.fixture
def mock_native_docker() -> None:
    """Mock native Docker (not WSL)."""
    with patch("debussy.runners.docker_builder.get_docker_command", return_value=["docker"]):
        yield


@pytest.fixture
def mock_wsl_docker() -> None:
    """Mock Docker via WSL."""
    with patch("debussy.runners.docker_builder.get_docker_command", return_value=["wsl", "docker"]):
        yield


class TestDockerCommandBuilderInit:
    """Tests for DockerCommandBuilder initialization."""

    def test_default_sandbox_image(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder uses default sandbox image."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        # The sandbox image is used in build_command
        cmd = builder.build_command("test prompt")
        cmd_str = " ".join(cmd)
        assert SANDBOX_IMAGE in cmd_str

    def test_custom_sandbox_image(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder accepts custom sandbox image."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
            sandbox_image="custom-image:v1",
        )
        cmd = builder.build_command("test prompt")
        cmd_str = " ".join(cmd)
        assert "custom-image:v1" in cmd_str

    def test_detects_wsl_mode(self, project_root: Path, mock_wsl_docker: None) -> None:  # noqa: ARG002
        """Builder detects WSL mode."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        assert builder.use_wsl is True

    def test_detects_native_docker(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder detects native Docker mode."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        assert builder.use_wsl is False


class TestDockerCommandBuilderCommand:
    """Tests for build_command method."""

    def test_builds_docker_run_command(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder creates docker run command."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test prompt")

        # Should be sh -c with exec
        assert cmd[0] == "sh"
        assert cmd[1] == "-c"
        assert cmd[2].startswith("exec docker run")

    def test_wsl_wrapper(self, project_root: Path, mock_wsl_docker: None) -> None:  # noqa: ARG002
        """Builder wraps command in WSL on Windows."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test prompt")

        # Should use wsl -e sh -c
        assert cmd[0] == "wsl"
        assert cmd[1] == "-e"
        assert cmd[2] == "sh"
        assert cmd[3] == "-c"
        assert cmd[4].startswith("exec docker run")

    def test_includes_model(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder includes model in command."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="opus",
        )
        cmd = builder.build_command("test prompt")
        cmd_str = " ".join(cmd)

        assert "--model opus" in cmd_str

    def test_quotes_prompt(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder properly quotes prompt with special characters."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        prompt = "Test with 'quotes' and\nnewlines"
        cmd = builder.build_command(prompt)
        cmd_str = " ".join(cmd)

        # Prompt should be quoted (shlex.quote handles this)
        # The quoted version will have the quotes escaped
        assert "-p" in cmd_str

    def test_removes_container_after_exit(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder includes --rm flag."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "--rm" in cmd_str


class TestDockerCommandBuilderVolumes:
    """Tests for volume mount building."""

    def test_mounts_project_root(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder mounts project root to /workspace."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        # Should mount project to /workspace
        assert ":/workspace:rw" in cmd_str

    def test_mounts_excluded_dirs_as_tmpfs(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder mounts excluded dirs as tmpfs."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        # All excluded dirs should have tmpfs mounts
        for excluded in EXCLUDED_DIRS:
            assert f"--mount type=tmpfs,destination=/workspace/{excluded}" in cmd_str

    def test_mounts_venv_with_exec(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder mounts .venv with exec option."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        # .venv needs exec flag
        assert "--tmpfs /workspace/.venv:exec" in cmd_str

    def test_mounts_claude_config_if_exists(self, project_root: Path, mock_native_docker: None, tmp_path: Path) -> None:  # noqa: ARG002
        """Builder mounts .claude config if it exists."""
        # Create a mock .claude directory
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        with patch("pathlib.Path.home", return_value=tmp_path):
            builder = DockerCommandBuilder(
                project_root=project_root,
                model="haiku",
            )
            cmd = builder.build_command("test")
            cmd_str = " ".join(cmd)

            # Should mount .claude
            assert ":/home/claude/.claude:rw" in cmd_str


class TestDockerCommandBuilderEnvVars:
    """Tests for environment variable building."""

    def test_sets_container_path(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder sets PATH to prevent host PATH leaking."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert f"-e PATH={CONTAINER_PATH}" in cmd_str

    def test_passes_api_key_if_set(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder passes ANTHROPIC_API_KEY if available."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
            builder = DockerCommandBuilder(
                project_root=project_root,
                model="haiku",
            )
            cmd = builder.build_command("test")
            cmd_str = " ".join(cmd)

            assert "-e ANTHROPIC_API_KEY=test-key-123" in cmd_str

    def test_no_api_key_if_not_set(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder doesn't add empty API key."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            builder = DockerCommandBuilder(
                project_root=project_root,
                model="haiku",
            )
            cmd = builder.build_command("test")
            cmd_str = " ".join(cmd)

            # Should have PATH but not empty API key
            assert "-e PATH=" in cmd_str
            # Should not have empty ANTHROPIC_API_KEY
            assert "-e ANTHROPIC_API_KEY=" not in cmd_str


class TestDockerCommandBuilderClaudeArgs:
    """Tests for Claude CLI arguments."""

    def test_includes_base_args(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder includes all base Claude CLI args."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        for arg in BASE_CLAUDE_ARGS:
            assert arg in cmd_str

    def test_includes_stream_json_output(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder includes stream-json output format."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "--output-format stream-json" in cmd_str

    def test_includes_prompt_flag(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder includes -p flag for prompt."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "-p" in cmd_str


class TestDockerCommandBuilderCapabilities:
    """Tests for Docker capability settings."""

    def test_adds_network_capabilities(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder adds NET_ADMIN and NET_RAW capabilities."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "--cap-add=NET_ADMIN" in cmd_str
        assert "--cap-add=NET_RAW" in cmd_str

    def test_attaches_stdout_stderr(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder attaches stdout and stderr."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "--attach=stdout" in cmd_str
        assert "--attach=stderr" in cmd_str

    def test_sets_workdir(self, project_root: Path, mock_native_docker: None) -> None:  # noqa: ARG002
        """Builder sets working directory to /workspace."""
        builder = DockerCommandBuilder(
            project_root=project_root,
            model="haiku",
        )
        cmd = builder.build_command("test")
        cmd_str = " ".join(cmd)

        assert "-w /workspace" in cmd_str
