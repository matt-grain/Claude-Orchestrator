"""Init command: initialize a target project for Debussy orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def _check_ltm_available() -> bool:
    """Check if LTM is installed."""
    try:
        import ltm  # noqa: F401

        return True
    except ImportError:
        return False


def _install_resource(
    subpackage: str,
    filename: str,
    dst: Path,
    force: bool,
    file_type: str,
) -> None:
    """Install a resource file from the package to destination."""
    from debussy.resources.loader import copy_resource_to

    if dst.exists() and not force:
        console.print(f"[yellow]{file_type} exists (skipped): {dst.name}[/yellow]")
        return

    copy_resource_to(subpackage, filename, dst)
    console.print(f"[green]Installed {file_type}: {dst.name}[/green]")


def register(app: typer.Typer) -> None:
    """Register the init command on the given Typer app."""

    @app.command()
    def init(
        target: Annotated[
            Path,
            typer.Argument(
                help="Path to the target project to initialize",
                exists=True,
                file_okay=False,
                dir_okay=True,
                resolve_path=True,
            ),
        ] = Path(),
        force: Annotated[
            bool,
            typer.Option("--force", "-f", help="Overwrite existing files"),
        ] = False,
        with_ltm: Annotated[
            bool,
            typer.Option("--with-ltm", help="Include LTM commands for memory support"),
        ] = False,
    ) -> None:
        """Initialize a target project for Debussy orchestration.

        Sets up .claude/agents/debussy.md, .claude/skills/debussy.md, and
        .claude/commands/debussy-*.md files for the spawned Claude agent.

        Use --with-ltm to also install LTM memory commands (/remember, /recall).
        """
        # Check LTM availability if requested
        if with_ltm and not _check_ltm_available():
            console.print("[yellow]LTM not installed.[/yellow]")
            console.print("Install with: pip install 'claude-debussy[ltm]'")
            console.print("Continuing without LTM support...")
            with_ltm = False

        # Create .claude directory structure
        claude_dir = target / ".claude"
        if not claude_dir.exists():
            claude_dir.mkdir()
            console.print(f"[green]Created {claude_dir}[/green]")

        agents_dir = claude_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        skills_dir = claude_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        commands_dir = claude_dir / "commands"
        commands_dir.mkdir(exist_ok=True)

        # Install agent and skill files from package resources
        _install_resource("agents", "debussy.md", agents_dir / "debussy.md", force, "agent")
        _install_resource("skills", "debussy.md", skills_dir / "debussy.md", force, "skill")

        # Install command files
        for cmd_name in ["debussy-done", "debussy-progress", "debussy-status"]:
            _install_resource("commands", f"{cmd_name}.md", commands_dir / f"{cmd_name}.md", force, f"command: /{cmd_name}")

        # Install LTM commands via ltm setup if requested
        if with_ltm:
            import subprocess

            result = subprocess.run(
                ["uv", "run", "ltm", "setup", str(target)],
                capture_output=True,
                text=True,
                cwd=target,
                check=False,  # Handle errors ourselves
            )
            if result.returncode == 0:
                console.print("[green]LTM commands installed via ltm setup[/green]")
            else:
                console.print(f"[yellow]LTM setup warning: {result.stderr.strip()}[/yellow]")

        # Always create config (with learnings enabled if --with-ltm)
        from debussy.config import Config

        debussy_dir = target / ".debussy"
        debussy_dir.mkdir(exist_ok=True)
        config_path = debussy_dir / "config.yaml"

        if config_path.exists() and not force:
            console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
            console.print("[dim]Use --force to overwrite.[/dim]")
        else:
            config = Config(learnings=with_ltm)
            config.save(config_path)
            learnings_note = " with learnings enabled" if with_ltm else ""
            console.print(f"[green]Created {config_path}{learnings_note}[/green]")

        console.print("\n[bold]Setup complete![/bold]")
        if with_ltm:
            console.print("Debussy agent has access to orchestration + memory commands.")
        else:
            console.print("Debussy agent has access to orchestration commands.")
            console.print("[dim]Tip: Use --with-ltm to enable cross-phase memory.[/dim]")
