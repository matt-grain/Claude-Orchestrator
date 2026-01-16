"""Configuration management for the debussy."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class NotificationConfig(BaseModel):
    """Notification settings."""

    enabled: bool = True
    provider: Literal["desktop", "ntfy", "none"] = "desktop"
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: str = "claude-debussy"


class GitHubLabelConfig(BaseModel):
    """Label configuration for GitHub sync."""

    in_progress: str = Field(default="debussy:in-progress", description="Label for running phases")
    completed: str = Field(default="debussy:completed", description="Label for completed phases")
    failed: str = Field(default="debussy:failed", description="Label for failed phases")
    color_in_progress: str = Field(default="1D76DB", description="Hex color for in-progress label (blue)")
    color_completed: str = Field(default="0E8A16", description="Hex color for completed label (green)")
    color_failed: str = Field(default="D93F0B", description="Hex color for failed label (red)")


class GitHubSyncConfig(BaseModel):
    """GitHub issue sync settings."""

    enabled: bool = Field(default=False, description="Enable GitHub issue synchronization")
    auto_close: bool = Field(default=False, description="Auto-close issues when plan completes")
    labels: GitHubLabelConfig = Field(default_factory=GitHubLabelConfig)
    create_labels_if_missing: bool = Field(default=True, description="Create labels if they don't exist")
    dry_run: bool = Field(default=False, description="Log operations without executing")


class Config(BaseModel):
    """Debussy configuration.

    Auto-commit settings:
        auto_commit: Whether to commit at phase boundaries (default: True)
        commit_on_failure: Whether to commit even if phase fails (default: False)
        commit_message_template: Template for commit messages using {phase_id}, {phase_name}, {status}
    """

    timeout: int = Field(default=1800, description="Phase timeout in seconds (default: 30 min)")
    max_retries: int = Field(default=2, description="Max retry attempts per phase")
    model: str = Field(default="opus", description="Claude model to use (haiku, sonnet, opus)")
    output: Literal["terminal", "file", "both"] = Field(default="terminal", description="Output mode: terminal, file, or both")
    interactive: bool = Field(default=True, description="Interactive mode with dashboard UI")
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    github: GitHubSyncConfig = Field(default_factory=GitHubSyncConfig)
    strict_compliance: bool = Field(default=True, description="Fail on any compliance issue")
    learnings: bool = Field(
        default=False,
        description="Enable LTM learnings - workers save insights via /remember",
    )
    sandbox_mode: Literal["none", "devcontainer"] = Field(
        default="none",
        description="Sandboxing mode: none (direct execution) or devcontainer (Docker isolation)",
    )
    auto_commit: bool = Field(
        default=True,
        description="Commit at phase boundaries for clean checkpoints",
    )
    commit_on_failure: bool = Field(
        default=False,
        description="Commit even if phase fails (default: only commit successful phases)",
    )
    commit_message_template: str = Field(
        default="Debussy: Phase {phase_id} - {phase_name} {status}",
        description="Template for commit messages; supports {phase_id}, {phase_name}, {status}",
    )
    context_threshold: float = Field(
        default=80.0,
        description="Percentage of context window to trigger restart (0-100). Set to 100 to disable.",
    )
    tool_call_threshold: int = Field(
        default=100,
        description="Fallback: restart after this many tool calls if token threshold not reached.",
    )
    max_restarts: int = Field(
        default=3,
        description="Maximum restart attempts per phase before failing. Set to 0 to disable restarts.",
    )
    plan_generation_model: str = Field(
        default="sonnet",
        description="Claude model for plan-from-issues generation (haiku, sonnet, opus)",
    )
    plan_generation_timeout: int = Field(
        default=300,
        description="Timeout for plan generation Claude calls in seconds (default: 5 min)",
    )

    @classmethod
    def load(cls, config_path: Path | None = None) -> Config:
        """Load configuration from file or use defaults."""
        if config_path is None:
            # Look for config in .debussy/config.yaml
            config_path = Path(".debussy/config.yaml")

        if config_path.exists():
            with config_path.open() as f:
                data = yaml.safe_load(f) or {}
            return cls.model_validate(data)

        return cls()

    def save(self, config_path: Path) -> None:
        """Save configuration to file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


def get_orchestrator_dir(project_root: Path | None = None) -> Path:
    """Get the .debussy directory, creating if needed."""
    if project_root is None:
        project_root = Path.cwd()
    orchestrator_dir = project_root / ".debussy"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    return orchestrator_dir
