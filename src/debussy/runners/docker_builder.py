"""Docker command building for sandboxed Claude execution."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from debussy.utils.docker import get_docker_command, normalize_path_for_docker

# Default sandbox image
SANDBOX_IMAGE = "debussy-sandbox:latest"

# Base Claude CLI arguments for stream-json output
BASE_CLAUDE_ARGS = [
    "--print",
    "--verbose",
    "--output-format",
    "stream-json",
    "--dangerously-skip-permissions",
]

# Directories to exclude from container (use tmpfs overlay)
EXCLUDED_DIRS = [
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]

# Container PATH to prevent host PATH from leaking
CONTAINER_PATH = "/home/claude/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


class DockerCommandBuilder:
    """Builds Docker run commands for sandboxed Claude execution.

    Handles:
    - Volume mounts for project and Claude config
    - Windows path normalization
    - WSL wrapper for Windows without native Docker
    - Environment variable passthrough
    - Shadow mounts for host-specific directories
    """

    def __init__(
        self,
        project_root: Path,
        model: str,
        sandbox_image: str = SANDBOX_IMAGE,
    ) -> None:
        """Initialize the builder.

        Args:
            project_root: Root directory of the project to mount
            model: Claude model name (e.g., "opus", "sonnet", "haiku")
            sandbox_image: Docker image name for sandbox
        """
        self._project_root = project_root
        self._model = model
        self._sandbox_image = sandbox_image
        docker_cmd = get_docker_command()
        self._use_wsl = docker_cmd[0] == "wsl"

    @property
    def use_wsl(self) -> bool:
        """Check if WSL wrapper is needed for Docker."""
        return self._use_wsl

    def build_command(self, prompt: str) -> list[str]:
        """Build the complete Docker run command.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Command list for subprocess execution.
        """
        volumes = self._build_volume_mounts()
        env_vars = self._build_env_vars()
        claude_args = self._build_claude_args(prompt)

        # Build the full docker command as a shell string
        # This prevents Git Bash from mangling paths when passed through WSL
        docker_args = [
            "docker run",
            "--rm",  # Remove container after exit
            "--attach=stdout",
            "--attach=stderr",
            *volumes,
            "-w /workspace",
            *env_vars,
            "--cap-add=NET_ADMIN",
            "--cap-add=NET_RAW",
            self._sandbox_image,
            *claude_args,
        ]
        docker_command_str = " ".join(docker_args)

        if self._use_wsl:
            # Wrap in 'wsl -e sh -c' to avoid Git Bash path mangling
            # Use 'exec' to replace shell with docker so we properly wait for it
            return ["wsl", "-e", "sh", "-c", f"exec {docker_command_str}"]
        else:
            # Direct docker execution (non-Windows or native Docker)
            return ["sh", "-c", f"exec {docker_command_str}"]

    def _build_volume_mounts(self) -> list[str]:
        """Build volume mount arguments.

        Returns:
            List of Docker volume mount arguments.
        """
        project_path = normalize_path_for_docker(self._project_root, use_wsl=self._use_wsl)
        volumes = ["-v", f"{project_path}:/workspace:rw"]

        # Exclude host-specific directories by mounting empty tmpfs over them
        # This prevents Windows .venv, __pycache__, .git from breaking Linux container
        for excluded in EXCLUDED_DIRS:
            volumes.append(f"--mount type=tmpfs,destination=/workspace/{excluded}")

        # .venv needs exec flag for shared object loading (pydantic-core, tiktoken, etc.)
        # Must use --tmpfs syntax (not --mount) to enable exec option
        volumes.extend(["--tmpfs", "/workspace/.venv:exec"])

        # Mount Claude credentials for OAuth authentication
        # Note: mounted as rw because Claude writes to debug/, stats-cache.json, etc.
        claude_config_dir = Path.home() / ".claude"
        if claude_config_dir.exists():
            claude_config_path = normalize_path_for_docker(claude_config_dir, use_wsl=self._use_wsl)
            volumes.append(f"-v {claude_config_path}:/home/claude/.claude:rw")

        return volumes

    def _build_env_vars(self) -> list[str]:
        """Build environment variable arguments.

        Returns:
            List of Docker environment variable arguments.
        """
        # CRITICAL: Set PATH explicitly to prevent host PATH from overriding container
        env_vars = [f"-e PATH={CONTAINER_PATH}"]

        # Pass through API key if available
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            env_vars.append(f"-e ANTHROPIC_API_KEY={api_key}")

        return env_vars

    def _build_claude_args(self, prompt: str) -> list[str]:
        """Build the Claude CLI arguments.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            List of Claude CLI arguments.
        """
        # CRITICAL: The prompt must be shell-quoted as it contains spaces, newlines, etc.
        quoted_prompt = shlex.quote(prompt)
        return [
            *BASE_CLAUDE_ARGS,
            "--model",
            self._model,
            "-p",
            quoted_prompt,
        ]
