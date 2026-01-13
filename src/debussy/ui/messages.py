"""Message types for UI/Controller communication.

This module defines the message protocol between the OrchestrationController
and the DebussyTUI. Messages flow bidirectionally:

Controller -> TUI (Commands):
- OrchestrationStarted: Orchestration has begun
- PhaseChanged: Current phase has changed
- StateChanged: UI state transition (running, paused, etc.)
- TokenStatsUpdated: Token usage statistics updated
- LogMessage: Message to display in log panel
- HUDMessageSet: Transient message for hotkey bar
- VerboseToggled: Verbose mode state changed
- OrchestrationCompleted: Orchestration finished

TUI -> Controller (Events):
- UserActionRequested: User triggered an action via keyboard
- ShutdownRequested: User confirmed shutdown
- StatusDetailsRequested: User wants status popup
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message

if TYPE_CHECKING:
    from debussy.ui.base import UIState, UserAction


# =============================================================================
# Controller -> TUI Messages (Commands)
# =============================================================================


class OrchestrationStarted(Message):
    """Orchestration has started."""

    def __init__(self, plan_name: str, total_phases: int) -> None:
        """Initialize the message.

        Args:
            plan_name: Name of the plan being executed
            total_phases: Total number of phases in the plan
        """
        self.plan_name = plan_name
        self.total_phases = total_phases
        super().__init__()


class PhaseChanged(Message):
    """Current phase has changed."""

    def __init__(
        self,
        phase_id: str,
        phase_title: str,
        phase_index: int,
        total_phases: int,
    ) -> None:
        """Initialize the message.

        Args:
            phase_id: Unique identifier of the phase
            phase_title: Human-readable title of the phase
            phase_index: 1-based index of the phase
            total_phases: Total number of phases
        """
        self.phase_id = phase_id
        self.phase_title = phase_title
        self.phase_index = phase_index
        self.total_phases = total_phases
        super().__init__()


class StateChanged(Message):
    """UI state has changed (running, paused, etc.)."""

    def __init__(self, state: UIState) -> None:
        """Initialize the message.

        Args:
            state: New UI state
        """
        self.state = state
        super().__init__()


class TokenStatsUpdated(Message):
    """Token usage statistics have been updated."""

    def __init__(
        self,
        session_input_tokens: int,
        session_output_tokens: int,
        total_cost_usd: float,
        context_pct: int,
    ) -> None:
        """Initialize the message.

        Args:
            session_input_tokens: Input tokens for current session
            session_output_tokens: Output tokens for current session
            total_cost_usd: Cumulative cost across all sessions
            context_pct: Context window usage percentage (0-100)
        """
        self.session_input_tokens = session_input_tokens
        self.session_output_tokens = session_output_tokens
        self.total_cost_usd = total_cost_usd
        self.context_pct = context_pct
        super().__init__()


class LogMessage(Message):
    """Log message to display in the log panel."""

    def __init__(self, message: str, raw: bool = False) -> None:
        """Initialize the message.

        Args:
            message: Text to display
            raw: If True, bypasses verbose check (always displayed)
        """
        self.message = message
        self.raw = raw
        super().__init__()


class HUDMessageSet(Message):
    """Transient message to show in hotkey bar."""

    def __init__(self, message: str, clear_after: float = 3.0) -> None:
        """Initialize the message.

        Args:
            message: Text to display
            clear_after: Seconds before auto-clearing (0 = no auto-clear)
        """
        self.message = message
        self.clear_after = clear_after
        super().__init__()


class VerboseToggled(Message):
    """Verbose mode has been toggled."""

    def __init__(self, is_verbose: bool) -> None:
        """Initialize the message.

        Args:
            is_verbose: New verbose state
        """
        self.is_verbose = is_verbose
        super().__init__()


class OrchestrationCompleted(Message):
    """Orchestration has completed (success or failure)."""

    def __init__(self, run_id: str, success: bool, message: str) -> None:
        """Initialize the message.

        Args:
            run_id: Unique identifier for the orchestration run
            success: Whether orchestration completed successfully
            message: Completion message
        """
        self.run_id = run_id
        self.success = success
        self.message = message
        super().__init__()


# =============================================================================
# TUI -> Controller Messages (Events)
# =============================================================================


class UserActionRequested(Message):
    """User has requested an action via keyboard."""

    def __init__(self, action: UserAction) -> None:
        """Initialize the message.

        Args:
            action: The action requested by the user
        """
        self.action = action
        super().__init__()


class ShutdownRequested(Message):
    """User has requested shutdown (after confirmation)."""

    pass


class StatusDetailsRequested(Message):
    """User wants to see status details."""

    pass
