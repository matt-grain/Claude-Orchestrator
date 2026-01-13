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

from collections import deque
from typing import TYPE_CHECKING

from textual.app import App
from textual.message import Message

from debussy.ui.base import UIContext, UIState, UserAction

if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestrationController:
    """Manages orchestration state and emits UI messages.

    This controller owns all orchestration state and business logic.
    The TUI subscribes to messages and renders accordingly.

    The full implementation will be added in PR #2.
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
    # Orchestration Lifecycle (Skeleton - PR #2 will implement)
    # =========================================================================

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize orchestration state.

        Args:
            plan_name: Name of the plan
            total_phases: Total number of phases
        """
        raise NotImplementedError("Will be implemented in PR #2")

    def stop(self) -> None:
        """Stop the orchestration."""
        pass

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed.

        Args:
            phase: The phase model
            index: 1-based index of the phase
        """
        raise NotImplementedError("Will be implemented in PR #2")

    def set_state(self, state: UIState) -> None:
        """Update the UI state.

        Args:
            state: New state
        """
        raise NotImplementedError("Will be implemented in PR #2")

    # =========================================================================
    # Token Statistics (Skeleton - PR #2 will implement)
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

        Args:
            input_tokens: Input tokens this session
            output_tokens: Output tokens this session
            cost_usd: Cost in USD
            context_tokens: Current context window usage
            context_window: Maximum context window size
        """
        raise NotImplementedError("Will be implemented in PR #2")

    # =========================================================================
    # User Actions (Skeleton - PR #2 will implement)
    # =========================================================================

    def queue_action(self, action: UserAction) -> None:
        """Queue a user action for processing.

        Args:
            action: The action to queue
        """
        raise NotImplementedError("Will be implemented in PR #2")

    def get_pending_action(self) -> UserAction:
        """Get and remove the next pending action.

        Returns:
            The next action, or UserAction.NONE if empty
        """
        raise NotImplementedError("Will be implemented in PR #2")

    # =========================================================================
    # Verbose Toggle (Skeleton - PR #2 will implement)
    # =========================================================================

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging mode.

        Returns:
            New verbose state
        """
        raise NotImplementedError("Will be implemented in PR #2")
