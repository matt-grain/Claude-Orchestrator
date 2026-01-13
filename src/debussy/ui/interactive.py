"""Non-interactive UI for YOLO/CI mode."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console

from debussy.ui.base import UIContext, UIState, UserAction

if TYPE_CHECKING:
    from debussy.core.models import Phase


class NonInteractiveUI:
    """Simple non-interactive UI for YOLO/CI mode.

    Just passes through log messages to console without the dashboard.
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize non-interactive UI."""
        self.console = console or Console()
        self.context = UIContext()
        self.context.verbose = True

    def start(self, plan_name: str, total_phases: int) -> None:
        """Start the UI (no-op for non-interactive)."""
        self.context.plan_name = plan_name
        self.context.total_phases = total_phases
        self.context.start_time = time.time()
        self.console.print(f"[bold]Starting orchestration:[/bold] {plan_name}")
        self.console.print(f"[dim]Total phases: {total_phases}[/dim]\n")

    def stop(self) -> None:
        """Stop the UI (no-op for non-interactive)."""
        elapsed = time.time() - self.context.start_time
        self.console.print(f"\n[dim]Completed in {elapsed:.1f}s[/dim]")

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update current phase."""
        self.context.current_phase = phase.id
        self.context.phase_title = phase.title
        self.context.phase_index = index
        self.console.print(f"\n[bold cyan]Phase {index}: {phase.title}[/bold cyan]")

    def set_state(self, state: UIState) -> None:
        """Update state (no-op for non-interactive)."""
        self.context.state = state

    def log(self, message: str) -> None:
        """Log a message."""
        if self.context.verbose:
            self.console.print(message)

    # Alias for TUI compatibility
    log_message = log

    def log_raw(self, message: str) -> None:
        """Log a raw message."""
        self.console.print(message)

    def get_pending_action(self) -> UserAction:
        """Get pending action (always NONE for non-interactive)."""
        return UserAction.NONE

    def toggle_verbose(self) -> bool:
        """Toggle verbose (no-op, always verbose in non-interactive)."""
        return True

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show status (print to console)."""
        self.console.print("\n[bold]Status:[/bold]")
        for key, value in details.items():
            self.console.print(f"  {key}: {value}")
        self.console.print()

    def confirm(self, message: str) -> bool:
        """Confirm action (auto-yes in non-interactive)."""
        self.console.print(f"[yellow]{message}[/yellow] (auto-confirmed in YOLO mode)")
        return True

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics (no-op for non-interactive)."""
        # Track session stats
        self.context.session_input_tokens = input_tokens
        self.context.session_output_tokens = output_tokens
        self.context.current_context_tokens = context_tokens
        self.context.context_window = context_window
        # Accumulate on final result
        if cost_usd > 0:
            self.context.total_input_tokens += input_tokens
            self.context.total_output_tokens += output_tokens
            self.context.total_cost_usd += cost_usd

    def set_active_agent(self, _agent: str) -> None:
        """Update active agent (no-op for non-interactive)."""
        pass
