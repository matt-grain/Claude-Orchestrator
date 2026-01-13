"""Orchestration state controller for the TUI.

This controller owns all orchestration state and business logic.
The TUI subscribes to messages and renders accordingly.

Responsibilities:
- UIContext singleton ownership
- Action queue management
- Token usage accumulation
- State machine transitions
- Emitting UI update messages
"""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from textual.app import App
from textual.message import Message

from debussy.ui.base import UIContext, UIState, UserAction
from debussy.ui.messages import (
    HUDMessageSet,
    LogMessage,
    OrchestrationCompleted,
    OrchestrationStarted,
    PhaseChanged,
    StateChanged,
    TokenStatsUpdated,
    VerboseToggled,
)

if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestrationController:
    """Manages orchestration state and emits UI messages.

    This controller owns all orchestration state and business logic.
    The TUI subscribes to messages and renders accordingly.
    """

    def __init__(self, app: App) -> None:
        """Initialize the controller.

        Args:
            app: The Textual app to post messages to
        """
        self._app = app
        self.context = UIContext()
        self._action_queue: deque[UserAction] = deque()

    def _post(self, message: Message) -> None:
        """Post a message to the TUI.

        Args:
            message: The message to post
        """
        self._app.post_message(message)

    # =========================================================================
    # Orchestration Lifecycle
    # =========================================================================

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize orchestration state.

        Called by the orchestrator when starting a run.

        Args:
            plan_name: Name of the plan being executed
            total_phases: Total number of phases in the plan
        """
        self.context.plan_name = plan_name
        self.context.total_phases = total_phases
        self.context.start_time = time.time()
        self.context.state = UIState.RUNNING
        self._post(OrchestrationStarted(plan_name, total_phases))

    def stop(self) -> None:
        """Stop the orchestration (no-op, app controls lifecycle)."""
        pass

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed.

        Args:
            phase: The phase model
            index: 1-based index of the phase
        """
        self.context.current_phase = phase.id
        self.context.phase_title = phase.title
        self.context.phase_index = index
        self.context.start_time = time.time()
        self._post(
            PhaseChanged(
                phase_id=phase.id,
                phase_title=phase.title,
                phase_index=index,
                total_phases=self.context.total_phases,
            )
        )

    def set_state(self, state: UIState) -> None:
        """Update the UI state.

        Args:
            state: New state (RUNNING, PAUSED, etc.)
        """
        self.context.state = state
        self._post(StateChanged(state))

    def complete(self, run_id: str, success: bool, message: str) -> None:
        """Signal orchestration completion.

        Args:
            run_id: The run ID
            success: Whether orchestration succeeded
            message: Completion message
        """
        self._post(OrchestrationCompleted(run_id, success, message))

    # =========================================================================
    # Token Statistics
    # =========================================================================

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics.

        Per-turn updates show cumulative stats within current session.
        Final result (with cost > 0) adds session totals to run totals.

        Args:
            input_tokens: Input tokens this session
            output_tokens: Output tokens this session
            cost_usd: Cost in USD (>0 only on final result)
            context_tokens: Current context window usage
            context_window: Maximum context window size
        """
        # Update current session stats
        self.context.session_input_tokens = input_tokens
        self.context.session_output_tokens = output_tokens
        self.context.current_context_tokens = context_tokens
        self.context.context_window = context_window

        # Final result has cost - add session totals to run totals
        if cost_usd > 0:
            self.context.total_input_tokens += input_tokens
            self.context.total_output_tokens += output_tokens
            self.context.total_cost_usd += cost_usd

        # Calculate context percentage
        context_pct = 0
        if context_window > 0 and context_tokens > 0:
            context_pct = int((context_tokens / context_window) * 100)

        session_total = input_tokens + output_tokens
        self._post(
            TokenStatsUpdated(
                session_input_tokens=session_total,
                session_output_tokens=output_tokens,
                total_cost_usd=self.context.total_cost_usd,
                context_pct=context_pct,
            )
        )

    # =========================================================================
    # User Actions
    # =========================================================================

    def queue_action(self, action: UserAction) -> None:
        """Queue a user action for processing by the orchestrator.

        Args:
            action: The action requested by the user
        """
        self._action_queue.append(action)

        # Emit appropriate feedback message
        feedback_map = {
            UserAction.PAUSE: "Pause requested (after current operation)",
            UserAction.RESUME: "Resume requested",
            UserAction.SKIP: "Skip requested (after current operation)",
            UserAction.QUIT: "Quit requested",
        }
        if action in feedback_map:
            self._post(HUDMessageSet(feedback_map[action]))

    def get_pending_action(self) -> UserAction:
        """Get and remove the next pending user action.

        Called by the orchestrator to check for user input.

        Returns:
            The next action, or UserAction.NONE if queue is empty
        """
        if self._action_queue:
            action = self._action_queue.popleft()
            self.context.last_action = action
            return action
        return UserAction.NONE

    # =========================================================================
    # Verbose Toggle
    # =========================================================================

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging mode.

        Returns:
            New verbose state
        """
        self.context.verbose = not self.context.verbose
        self._post(VerboseToggled(self.context.verbose))
        state_str = "ON" if self.context.verbose else "OFF"
        self._post(HUDMessageSet(f"Verbose: {state_str}"))
        return self.context.verbose

    # =========================================================================
    # Logging
    # =========================================================================

    def log_message(self, message: str) -> None:
        """Log a message (respects verbose setting).

        Args:
            message: Message to log
        """
        self._post(LogMessage(message, raw=False))

    def log_message_raw(self, message: str) -> None:
        """Log a message (ignores verbose setting).

        Args:
            message: Message to log
        """
        self._post(LogMessage(message, raw=True))

    # =========================================================================
    # Status
    # =========================================================================

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show status details in the log.

        Args:
            details: Key-value pairs to display
        """
        self._post(LogMessage("", raw=True))
        self._post(LogMessage("[bold]Current Status[/bold]", raw=True))
        for key, value in details.items():
            self._post(LogMessage(f"  {key}: {value}", raw=True))
        self._post(LogMessage("", raw=True))

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation (auto-confirms in TUI mode).

        Args:
            message: Confirmation message

        Returns:
            Always True (TUI auto-confirms)
        """
        self._post(LogMessage(f"[yellow]{message}[/yellow] (auto-confirmed)", raw=True))
        return True
