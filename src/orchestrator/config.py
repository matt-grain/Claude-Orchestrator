"""Configuration management for the orchestrator."""

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
    ntfy_topic: str = "claude-orchestrator"


class Config(BaseModel):
    """Orchestrator configuration."""

    timeout: int = Field(default=1800, description="Phase timeout in seconds (default: 30 min)")
    max_retries: int = Field(default=2, description="Max retry attempts per phase")
    model: str = Field(default="sonnet", description="Claude model to use (haiku, sonnet, opus)")
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    strict_compliance: bool = Field(default=True, description="Fail on any compliance issue")

    @classmethod
    def load(cls, config_path: Path | None = None) -> Config:
        """Load configuration from file or use defaults."""
        if config_path is None:
            # Look for config in .orchestrator/config.yaml
            config_path = Path(".orchestrator/config.yaml")

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
    """Get the .orchestrator directory, creating if needed."""
    if project_root is None:
        project_root = Path.cwd()
    orchestrator_dir = project_root / ".orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)
    return orchestrator_dir
