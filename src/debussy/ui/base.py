"""Base types and utilities for UI components."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol


class UIState(str, Enum):
    """Current state of the UI."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_INPUT = "waiting_input"


class UserAction(str, Enum):
    """Actions that can be triggered by user input."""

    NONE = "none"
    STATUS = "status"
    PAUSE = "pause"
    RESUME = "resume"
    TOGGLE_VERBOSE = "verbose"
    SKIP = "skip"
    QUIT = "quit"


if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestratorUI(Protocol):
    """Protocol defining the UI interface for orchestration.

    Implementations: TextualUI, NonInteractiveUI
    """

    @property
    def context(self) -> UIContext:
        """Return the UI context (single source of truth for state)."""
        ...

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize the UI for a new orchestration run."""
        ...

    def stop(self) -> None:
        """Stop the UI (cleanup)."""
        ...

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed."""
        ...

    def set_state(self, state: UIState) -> None:
        """Update the UI state (running, paused, etc.)."""
        ...

    def log(self, message: str) -> None:
        """Log a message (respects verbose setting)."""
        ...

    def log_raw(self, message: str) -> None:
        """Log a message (ignores verbose setting)."""
        ...

    def get_pending_action(self) -> UserAction:
        """Get the next pending user action."""
        ...

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging mode. Returns new state."""
        ...

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show detailed status information."""
        ...

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation. Returns True if confirmed."""
        ...

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics."""
        ...

    def set_active_agent(self, agent: str) -> None:
        """Update the active agent display."""
        ...

    def set_model(self, model: str) -> None:
        """Update the model name display."""
        ...


@dataclass
class UIContext:
    """Current context for the UI display."""

    plan_name: str = ""
    current_phase: str = ""
    phase_title: str = ""
    total_phases: int = 0
    phase_index: int = 0
    state: UIState = UIState.IDLE
    start_time: float = field(default_factory=time.time)
    verbose: bool = True
    last_action: UserAction = UserAction.NONE
    # Token usage tracking (cumulative across all phases)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    # Current session tracking (resets per phase)
    session_input_tokens: int = 0
    session_output_tokens: int = 0
    context_window: int = 200_000  # Default Claude context window
    current_context_tokens: int = 0  # Current session's context usage


# Status display configuration
STATUS_MAP: dict[UIState, tuple[str, str]] = {
    UIState.IDLE: ("Idle", "dim"),
    UIState.RUNNING: ("Running", "green"),
    UIState.PAUSED: ("Paused", "yellow"),
    UIState.WAITING_INPUT: ("Waiting", "cyan"),
}


def format_duration(seconds: float) -> str:
    """Format duration in HH:MM:SS format."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
