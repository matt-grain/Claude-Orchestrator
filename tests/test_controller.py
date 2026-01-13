"""Unit tests for OrchestrationController business logic.

This tests the full controller implementation added in PR #2.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from debussy.ui.base import UIState, UserAction
from debussy.ui.controller import OrchestrationController
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


class TestOrchestrationLifecycle:
    """Test orchestration lifecycle methods."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app that captures posted messages."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_start_initializes_context(self, controller: OrchestrationController) -> None:
        """start() should initialize all context fields."""
        controller.start("test-plan", 5)

        assert controller.context.plan_name == "test-plan"
        assert controller.context.total_phases == 5
        assert controller.context.state == UIState.RUNNING
        assert controller.context.start_time > 0

    def test_start_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """start() should emit OrchestrationStarted message."""
        controller.start("test-plan", 5)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, OrchestrationStarted)
        assert msg.plan_name == "test-plan"
        assert msg.total_phases == 5

    def test_stop_is_no_op(self, controller: OrchestrationController) -> None:
        """stop() should be a no-op (doesn't raise or change state)."""
        controller.context.state = UIState.RUNNING
        controller.stop()
        # State should not change
        assert controller.context.state == UIState.RUNNING

    def test_set_phase_updates_context(self, controller: OrchestrationController) -> None:
        """set_phase() should update all phase-related context."""
        mock_phase = Mock()
        mock_phase.id = "phase-1"
        mock_phase.title = "Setup Phase"
        controller.context.total_phases = 3

        controller.set_phase(mock_phase, 1)

        assert controller.context.current_phase == "phase-1"
        assert controller.context.phase_title == "Setup Phase"
        assert controller.context.phase_index == 1
        assert controller.context.start_time > 0

    def test_set_phase_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """set_phase() should emit PhaseChanged message."""
        mock_phase = Mock()
        mock_phase.id = "phase-2"
        mock_phase.title = "Build Phase"
        controller.context.total_phases = 4

        controller.set_phase(mock_phase, 2)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, PhaseChanged)
        assert msg.phase_id == "phase-2"
        assert msg.phase_title == "Build Phase"
        assert msg.phase_index == 2
        assert msg.total_phases == 4

    def test_set_state_updates_context(self, controller: OrchestrationController) -> None:
        """set_state() should update the UI state."""
        controller.set_state(UIState.PAUSED)

        assert controller.context.state == UIState.PAUSED

    def test_set_state_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """set_state() should emit StateChanged message."""
        controller.set_state(UIState.WAITING_INPUT)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, StateChanged)
        assert msg.state == UIState.WAITING_INPUT

    def test_complete_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """complete() should emit OrchestrationCompleted message."""
        controller.complete("run-123", True, "All done!")

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, OrchestrationCompleted)
        assert msg.run_id == "run-123"
        assert msg.success is True
        assert msg.message == "All done!"

    def test_complete_with_failure(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """complete() should handle failure case."""
        controller.complete("run-456", False, "Phase 2 failed")

        msg = mock_app.posted_messages[0]
        assert msg.success is False
        assert msg.message == "Phase 2 failed"


class TestTokenStatistics:
    """Test token tracking and accumulation."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_update_token_stats_session_tracking(self, controller: OrchestrationController) -> None:
        """update_token_stats() should update session stats."""
        controller.update_token_stats(
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0,  # No cost means intermediate update
            context_tokens=150,
            context_window=200_000,
        )

        assert controller.context.session_input_tokens == 100
        assert controller.context.session_output_tokens == 50
        assert controller.context.current_context_tokens == 150
        assert controller.context.context_window == 200_000

    def test_update_token_stats_no_accumulation_without_cost(
        self, controller: OrchestrationController
    ) -> None:
        """Intermediate updates (cost=0) should not accumulate totals."""
        controller.update_token_stats(100, 50, 0.0, 100, 200_000)

        assert controller.context.total_input_tokens == 0
        assert controller.context.total_output_tokens == 0
        assert controller.context.total_cost_usd == 0.0

    def test_update_token_stats_accumulation_with_cost(
        self, controller: OrchestrationController
    ) -> None:
        """Final updates (cost>0) should accumulate to totals."""
        controller.update_token_stats(100, 50, 0.05, 100, 200_000)

        assert controller.context.total_input_tokens == 100
        assert controller.context.total_output_tokens == 50
        assert controller.context.total_cost_usd == 0.05

    def test_update_token_stats_multiple_accumulation(
        self, controller: OrchestrationController
    ) -> None:
        """Multiple final updates should accumulate correctly."""
        # First final update
        controller.update_token_stats(100, 50, 0.05, 100, 200_000)
        # Second final update
        controller.update_token_stats(200, 100, 0.10, 200, 200_000)

        assert controller.context.total_input_tokens == 300
        assert controller.context.total_output_tokens == 150
        assert controller.context.total_cost_usd == pytest.approx(0.15)

    def test_update_token_stats_context_percentage(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """Context percentage should be calculated correctly."""
        controller.update_token_stats(1000, 500, 0.0, 50_000, 200_000)

        msg = mock_app.posted_messages[0]
        assert isinstance(msg, TokenStatsUpdated)
        assert msg.context_pct == 25  # 50_000 / 200_000 * 100

    def test_update_token_stats_context_percentage_zero_context(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """Context percentage should be 0 when context_tokens is 0."""
        controller.update_token_stats(100, 50, 0.0, 0, 200_000)

        msg = mock_app.posted_messages[0]
        assert msg.context_pct == 0

    def test_update_token_stats_context_percentage_zero_window(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """Context percentage should be 0 when context_window is 0."""
        controller.update_token_stats(100, 50, 0.0, 100, 0)

        msg = mock_app.posted_messages[0]
        assert msg.context_pct == 0

    def test_update_token_stats_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """update_token_stats() should emit TokenStatsUpdated message."""
        controller.update_token_stats(1000, 500, 0.05, 1500, 200_000)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, TokenStatsUpdated)
        # session_input_tokens is input + output combined
        assert msg.session_input_tokens == 1500
        assert msg.session_output_tokens == 500
        assert msg.total_cost_usd == 0.05


class TestUserActions:
    """Test user action queue management."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_queue_action_adds_to_queue(self, controller: OrchestrationController) -> None:
        """queue_action() should add action to the queue."""
        controller.queue_action(UserAction.PAUSE)

        assert len(controller._action_queue) == 1
        assert controller._action_queue[0] == UserAction.PAUSE

    def test_queue_action_fifo_order(self, controller: OrchestrationController) -> None:
        """Action queue should be FIFO."""
        controller.queue_action(UserAction.PAUSE)
        controller.queue_action(UserAction.SKIP)
        controller.queue_action(UserAction.RESUME)

        assert controller.get_pending_action() == UserAction.PAUSE
        assert controller.get_pending_action() == UserAction.SKIP
        assert controller.get_pending_action() == UserAction.RESUME

    def test_queue_action_emits_feedback_pause(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """queue_action(PAUSE) should emit feedback message."""
        controller.queue_action(UserAction.PAUSE)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, HUDMessageSet)
        assert "Pause" in msg.message

    def test_queue_action_emits_feedback_resume(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """queue_action(RESUME) should emit feedback message."""
        controller.queue_action(UserAction.RESUME)

        msg = mock_app.posted_messages[0]
        assert "Resume" in msg.message

    def test_queue_action_emits_feedback_skip(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """queue_action(SKIP) should emit feedback message."""
        controller.queue_action(UserAction.SKIP)

        msg = mock_app.posted_messages[0]
        assert "Skip" in msg.message

    def test_queue_action_emits_feedback_quit(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """queue_action(QUIT) should emit feedback message."""
        controller.queue_action(UserAction.QUIT)

        msg = mock_app.posted_messages[0]
        assert "Quit" in msg.message

    def test_queue_action_no_feedback_for_status(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """queue_action(STATUS) should not emit feedback."""
        controller.queue_action(UserAction.STATUS)

        assert len(mock_app.posted_messages) == 0

    def test_get_pending_action_returns_none_when_empty(
        self, controller: OrchestrationController
    ) -> None:
        """get_pending_action() should return NONE when queue is empty."""
        action = controller.get_pending_action()

        assert action == UserAction.NONE

    def test_get_pending_action_updates_last_action(
        self, controller: OrchestrationController
    ) -> None:
        """get_pending_action() should update context.last_action."""
        controller.queue_action(UserAction.PAUSE)

        controller.get_pending_action()

        assert controller.context.last_action == UserAction.PAUSE

    def test_get_pending_action_removes_from_queue(
        self, controller: OrchestrationController
    ) -> None:
        """get_pending_action() should remove action from queue."""
        controller.queue_action(UserAction.PAUSE)

        controller.get_pending_action()

        assert len(controller._action_queue) == 0


class TestVerboseToggle:
    """Test verbose mode toggling."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_toggle_verbose_flips_state(self, controller: OrchestrationController) -> None:
        """toggle_verbose() should flip the verbose state."""
        assert controller.context.verbose is True  # Default

        result = controller.toggle_verbose()

        assert result is False
        assert controller.context.verbose is False

    def test_toggle_verbose_flips_back(self, controller: OrchestrationController) -> None:
        """toggle_verbose() called twice should restore state."""
        controller.toggle_verbose()
        controller.toggle_verbose()

        assert controller.context.verbose is True

    def test_toggle_verbose_emits_verbose_toggled(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """toggle_verbose() should emit VerboseToggled message."""
        controller.toggle_verbose()

        verbose_msgs = [m for m in mock_app.posted_messages if isinstance(m, VerboseToggled)]
        assert len(verbose_msgs) == 1
        assert verbose_msgs[0].is_verbose is False

    def test_toggle_verbose_emits_hud_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """toggle_verbose() should emit HUD feedback message."""
        controller.toggle_verbose()

        hud_msgs = [m for m in mock_app.posted_messages if isinstance(m, HUDMessageSet)]
        assert len(hud_msgs) == 1
        assert "Verbose: OFF" in hud_msgs[0].message

    def test_toggle_verbose_on_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """toggle_verbose() should show ON when turning verbose on."""
        controller.context.verbose = False

        controller.toggle_verbose()

        hud_msgs = [m for m in mock_app.posted_messages if isinstance(m, HUDMessageSet)]
        assert "Verbose: ON" in hud_msgs[0].message


class TestLogging:
    """Test logging methods."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_log_message_emits_non_raw(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """log_message() should emit LogMessage with raw=False."""
        controller.log_message("test message")

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, LogMessage)
        assert msg.message == "test message"
        assert msg.raw is False

    def test_log_message_raw_emits_raw(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """log_message_raw() should emit LogMessage with raw=True."""
        controller.log_message_raw("important message")

        msg = mock_app.posted_messages[0]
        assert msg.message == "important message"
        assert msg.raw is True


class TestStatus:
    """Test status-related methods."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock Textual app."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app: MagicMock) -> OrchestrationController:
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_show_status_popup_emits_header(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """show_status_popup() should emit header message."""
        controller.show_status_popup({"Key": "Value"})

        messages = [m.message for m in mock_app.posted_messages if isinstance(m, LogMessage)]
        assert any("Current Status" in m for m in messages)

    def test_show_status_popup_emits_details(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """show_status_popup() should emit all detail lines."""
        controller.show_status_popup({"Phase": "Setup", "Progress": "50%"})

        messages = [m.message for m in mock_app.posted_messages if isinstance(m, LogMessage)]
        assert any("Phase: Setup" in m for m in messages)
        assert any("Progress: 50%" in m for m in messages)

    def test_show_status_popup_all_raw(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """show_status_popup() messages should all be raw."""
        controller.show_status_popup({"Key": "Value"})

        log_msgs = [m for m in mock_app.posted_messages if isinstance(m, LogMessage)]
        assert all(m.raw is True for m in log_msgs)

    def test_confirm_returns_true(self, controller: OrchestrationController) -> None:
        """confirm() should always return True (auto-confirm)."""
        result = controller.confirm("Proceed?")

        assert result is True

    def test_confirm_emits_message(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """confirm() should emit confirmation message."""
        controller.confirm("Delete all files?")

        msg = mock_app.posted_messages[0]
        assert isinstance(msg, LogMessage)
        assert "Delete all files?" in msg.message
        assert "auto-confirmed" in msg.message
        assert msg.raw is True
