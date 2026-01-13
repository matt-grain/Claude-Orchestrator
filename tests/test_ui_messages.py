"""Unit tests for UI message types and controller skeleton.

This tests the foundation added in PR #1 of the UI/Logic separation refactor.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from debussy.ui.base import UIState, UserAction
from debussy.ui.controller import OrchestrationController
from debussy.ui.messages import (
    HUDMessageSet,
    LogMessage,
    OrchestrationCompleted,
    OrchestrationStarted,
    PhaseChanged,
    ShutdownRequested,
    StateChanged,
    StatusDetailsRequested,
    TokenStatsUpdated,
    UserActionRequested,
    VerboseToggled,
)


class TestControllerToTUIMessages:
    """Test message types flowing from controller to TUI."""

    def test_orchestration_started(self) -> None:
        """OrchestrationStarted should store plan info."""
        msg = OrchestrationStarted("my-plan", 5)

        assert msg.plan_name == "my-plan"
        assert msg.total_phases == 5

    def test_phase_changed(self) -> None:
        """PhaseChanged should store all phase info."""
        msg = PhaseChanged(
            phase_id="p1",
            phase_title="Setup Phase",
            phase_index=1,
            total_phases=3,
        )

        assert msg.phase_id == "p1"
        assert msg.phase_title == "Setup Phase"
        assert msg.phase_index == 1
        assert msg.total_phases == 3

    def test_state_changed(self) -> None:
        """StateChanged should store the new state."""
        msg = StateChanged(UIState.PAUSED)

        assert msg.state == UIState.PAUSED

    def test_token_stats_updated(self) -> None:
        """TokenStatsUpdated should store all token info."""
        msg = TokenStatsUpdated(
            session_input_tokens=1000,
            session_output_tokens=500,
            total_cost_usd=0.05,
            context_pct=25,
        )

        assert msg.session_input_tokens == 1000
        assert msg.session_output_tokens == 500
        assert msg.total_cost_usd == 0.05
        assert msg.context_pct == 25

    def test_log_message_default(self) -> None:
        """LogMessage should default to non-raw."""
        msg = LogMessage("test message")

        assert msg.message == "test message"
        assert msg.raw is False

    def test_log_message_raw(self) -> None:
        """LogMessage with raw=True bypasses verbose check."""
        msg = LogMessage("important", raw=True)

        assert msg.message == "important"
        assert msg.raw is True

    def test_hud_message_set_default(self) -> None:
        """HUDMessageSet should default to 3 second clear."""
        msg = HUDMessageSet("status")

        assert msg.message == "status"
        assert msg.clear_after == 3.0

    def test_hud_message_set_no_clear(self) -> None:
        """HUDMessageSet with clear_after=0 persists."""
        msg = HUDMessageSet("persistent", clear_after=0)

        assert msg.message == "persistent"
        assert msg.clear_after == 0

    def test_verbose_toggled(self) -> None:
        """VerboseToggled should store the new state."""
        msg = VerboseToggled(is_verbose=False)

        assert msg.is_verbose is False

    def test_orchestration_completed_success(self) -> None:
        """OrchestrationCompleted should store completion info."""
        msg = OrchestrationCompleted(
            run_id="run-123",
            success=True,
            message="All phases completed successfully",
        )

        assert msg.run_id == "run-123"
        assert msg.success is True
        assert msg.message == "All phases completed successfully"

    def test_orchestration_completed_failure(self) -> None:
        """OrchestrationCompleted can represent failure."""
        msg = OrchestrationCompleted(
            run_id="run-456",
            success=False,
            message="Phase 2 failed quality gates",
        )

        assert msg.success is False


class TestTUIToControllerMessages:
    """Test message types flowing from TUI to controller."""

    def test_user_action_requested(self) -> None:
        """UserActionRequested should store the action."""
        msg = UserActionRequested(UserAction.PAUSE)

        assert msg.action == UserAction.PAUSE

    def test_shutdown_requested(self) -> None:
        """ShutdownRequested is a simple marker message."""
        msg = ShutdownRequested()

        # Just verify it instantiates (no data)
        assert isinstance(msg, ShutdownRequested)

    def test_status_details_requested(self) -> None:
        """StatusDetailsRequested is a simple marker message."""
        msg = StatusDetailsRequested()

        assert isinstance(msg, StatusDetailsRequested)


class TestOrchestrationControllerSkeleton:
    """Test the controller skeleton structure."""

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

    def test_controller_has_context(self, controller: OrchestrationController) -> None:
        """Controller should own a UIContext instance."""
        assert controller.context is not None
        assert controller.context.state == UIState.IDLE

    def test_controller_has_action_queue(self, controller: OrchestrationController) -> None:
        """Controller should have an action queue."""
        assert hasattr(controller, "_action_queue")

    def test_post_sends_to_app(
        self, controller: OrchestrationController, mock_app: MagicMock
    ) -> None:
        """_post() should forward messages to the app."""
        msg = HUDMessageSet("test")
        controller._post(msg)

        assert len(mock_app.posted_messages) == 1
        assert mock_app.posted_messages[0] is msg

    def test_skeleton_methods_raise_not_implemented(
        self, controller: OrchestrationController
    ) -> None:
        """Skeleton methods should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            controller.start("plan", 5)

        with pytest.raises(NotImplementedError):
            from unittest.mock import Mock

            mock_phase = Mock()
            controller.set_phase(mock_phase, 1)

        with pytest.raises(NotImplementedError):
            controller.update_token_stats(100, 50, 0.05, 100)

        with pytest.raises(NotImplementedError):
            controller.queue_action(UserAction.PAUSE)

        with pytest.raises(NotImplementedError):
            controller.get_pending_action()

        with pytest.raises(NotImplementedError):
            controller.toggle_verbose()

    def test_stop_is_no_op(self, controller: OrchestrationController) -> None:
        """stop() should be a no-op (doesn't raise)."""
        # Should not raise
        controller.stop()
