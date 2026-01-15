"""Docker-related utilities."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


def get_docker_command() -> list[str]:
    """Get the docker command prefix, using WSL on Windows if needed.

    Returns:
        Command list suitable for subprocess calls.
        On Windows without native Docker, returns ["wsl", "docker"].
    """
    if shutil.which("docker"):
        return ["docker"]
    # On Windows, try docker through WSL
    if platform.system() == "Windows" and shutil.which("wsl"):
        return ["wsl", "docker"]
    return ["docker"]  # Will fail, but gives clear error


def is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is running."""
    docker_cmd = get_docker_command()
    # If using WSL, we don't need which() check
    if docker_cmd[0] != "wsl" and not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            [*docker_cmd, "info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def normalize_path_for_docker(path: Path, use_wsl: bool = False) -> str:
    """Convert Windows path to Docker-compatible format.

    Args:
        path: Path to convert
        use_wsl: If True, use /mnt/c format (WSL). If False, use /c format (Docker Desktop).

    Returns:
        Path string suitable for Docker volume mounts.

    Examples:
        - Windows + use_wsl=False: C:\\Projects\\foo -> /c/Projects/foo
        - Windows + use_wsl=True:  C:\\Projects\\foo -> /mnt/c/Projects/foo
        - Unix: /home/user/foo -> /home/user/foo (unchanged)
    """
    if platform.system() == "Windows":
        path_str = str(path.resolve())
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            if use_wsl:
                return f"/mnt/{drive}{rest}"
            return f"/{drive}{rest}"
    return str(path)


# Convenience alias for WSL path conversion
def wsl_path(path: Path) -> str:
    """Convert path to WSL format (/mnt/c/...).

    Convenience wrapper for normalize_path_for_docker(path, use_wsl=True).
    """
    return normalize_path_for_docker(path, use_wsl=True)
