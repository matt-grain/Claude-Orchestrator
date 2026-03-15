"""Sandbox commands: sandbox-build and sandbox-status."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from debussy.utils.docker import get_docker_command, wsl_path

console = Console()


def _get_docker_dir() -> Path:
    """Get the docker directory, checking package data first, then repo root."""
    # First try: inside package directory (installed package or src layout)
    pkg_docker = Path(__file__).parent.parent / "docker"
    if pkg_docker.exists():
        return pkg_docker

    # Second try: repo root (development mode / editable install)
    repo_docker = Path(__file__).parent.parent.parent.parent / "docker"
    if repo_docker.exists():
        return repo_docker

    # Nothing found - return package path for error message
    return pkg_docker


def register(app: typer.Typer) -> None:
    """Register sandbox commands on the given Typer app."""

    @app.command("sandbox-build")
    def sandbox_build(
        no_cache: Annotated[
            bool,
            typer.Option("--no-cache", help="Build without using Docker cache"),
        ] = False,
    ) -> None:
        """Build the debussy-sandbox Docker image."""
        import subprocess

        # Find the Dockerfile
        docker_dir = _get_docker_dir()
        dockerfile = docker_dir / "Dockerfile.sandbox"

        if not dockerfile.exists():
            console.print(f"[red]Dockerfile not found: {dockerfile}[/red]")
            console.print("Please ensure the docker/ directory is present.")
            console.print(f"  Checked: {docker_dir}")
            raise typer.Exit(1)

        console.print("[bold]Building debussy-sandbox image...[/bold]")
        console.print(f"  Dockerfile: {dockerfile}")
        if no_cache:
            console.print("  [dim]--no-cache: rebuilding all layers[/dim]")
        console.print()

        docker_cmd = get_docker_command()
        # If using WSL, convert paths
        if docker_cmd[0] == "wsl":
            dockerfile_path = wsl_path(dockerfile)
            context_path = wsl_path(docker_dir)
        else:
            dockerfile_path = str(dockerfile)
            context_path = str(docker_dir)

        build_args = [
            *docker_cmd,
            "build",
            "-t",
            "debussy-sandbox:latest",
            "-f",
            dockerfile_path,
        ]
        if no_cache:
            build_args.append("--no-cache")
        build_args.append(context_path)

        result = subprocess.run(build_args, check=False)

        if result.returncode == 0:
            console.print("\n[green]Image built successfully![/green]")
            console.print("Run with: debussy run --sandbox <master_plan>")
        else:
            console.print("\n[red]Build failed[/red]")
            raise typer.Exit(1)

    @app.command("sandbox-status")
    def sandbox_status() -> None:
        """Check Docker and sandbox image availability."""
        from debussy.runners.claude import (
            SANDBOX_IMAGE,
            _is_sandbox_image_available,
        )
        from debussy.utils.docker import is_docker_available

        console.print("[bold]Sandbox Status[/bold]\n")

        # Check Docker
        if is_docker_available():
            console.print("[green]Docker:[/green] Available")
        else:
            console.print("[red]Docker:[/red] Not available")
            console.print("  Install Docker Desktop from https://docker.com/products/docker-desktop")
            return

        # Check sandbox image
        if _is_sandbox_image_available():
            console.print(f"[green]Image:[/green] {SANDBOX_IMAGE} found")
            console.print("\n[green]Ready to run with --sandbox![/green]")
        else:
            console.print(f"[yellow]Image:[/yellow] {SANDBOX_IMAGE} not found")
            console.print("  Build with: debussy sandbox-build")
