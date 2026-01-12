"""Unit tests for notification providers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from debussy.config import Config, NotificationConfig
from debussy.notifications.base import ConsoleNotifier, NullNotifier
from debussy.notifications.desktop import CompositeNotifier, DesktopNotifier


class TestNullNotifier:
    """Tests for NullNotifier."""

    def test_notify_does_nothing(self) -> None:
        """NullNotifier should not raise or produce output."""
        notifier = NullNotifier()
        # Should not raise
        notifier.notify("Title", "Message", "info")
        notifier.info("Title", "Message")
        notifier.success("Title", "Message")
        notifier.warning("Title", "Message")
        notifier.error("Title", "Message")
        notifier.alert("Title", "Message")


class TestConsoleNotifier:
    """Tests for ConsoleNotifier."""

    def test_notify_prints_to_console(self, capsys: pytest.CaptureFixture[str]) -> None:
        """ConsoleNotifier should print styled output."""
        notifier = ConsoleNotifier()
        notifier.notify("Test Title", "Test Message", "info")

        captured = capsys.readouterr()
        assert "Test Title" in captured.out
        assert "Test Message" in captured.out

    def test_all_levels_work(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All notification levels should work."""
        notifier = ConsoleNotifier()

        for level in ("info", "success", "warning", "error", "alert"):
            notifier.notify(f"{level} title", f"{level} message", level)  # type: ignore[arg-type]

        captured = capsys.readouterr()
        assert "info title" in captured.out
        assert "error title" in captured.out


class TestDesktopNotifier:
    """Tests for DesktopNotifier."""

    def test_init_checks_plyer_availability(self) -> None:
        """DesktopNotifier should check if plyer is available on init."""
        notifier = DesktopNotifier()
        # plyer should be available since we installed it
        assert notifier._plyer_available is True

    def test_init_with_custom_settings(self) -> None:
        """DesktopNotifier should accept custom app_name and timeout."""
        notifier = DesktopNotifier(app_name="TestApp", timeout=5)
        assert notifier.app_name == "TestApp"
        assert notifier.timeout == 5

    def test_notify_calls_plyer(self) -> None:
        """DesktopNotifier should call plyer.notification.notify."""
        notifier = DesktopNotifier(app_name="TestApp")

        with patch("plyer.notification.notify") as mock_notify:
            notifier.notify("Test Title", "Test Message", "info")

            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args.kwargs
            assert "[TestApp] Test Title" in call_kwargs["title"]
            assert call_kwargs["message"] == "Test Message"
            assert call_kwargs["app_name"] == "TestApp"

    def test_notify_with_error_level_sets_toast(self) -> None:
        """Error and alert levels should set toast=True."""
        notifier = DesktopNotifier()

        with patch("plyer.notification.notify") as mock_notify:
            notifier.notify("Error", "Something failed", "error")
            call_kwargs = mock_notify.call_args.kwargs
            assert call_kwargs["toast"] is True

            notifier.notify("Alert", "Critical issue", "alert")
            call_kwargs = mock_notify.call_args.kwargs
            assert call_kwargs["toast"] is True

    def test_notify_with_info_level_no_toast(self) -> None:
        """Info and success levels should not set toast."""
        notifier = DesktopNotifier()

        with patch("plyer.notification.notify") as mock_notify:
            notifier.notify("Info", "Just FYI", "info")
            call_kwargs = mock_notify.call_args.kwargs
            assert call_kwargs["toast"] is False

    def test_fallback_when_plyer_unavailable(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should fall back to logging when plyer is unavailable."""
        notifier = DesktopNotifier()
        notifier._plyer_available = False

        with caplog.at_level("INFO"):
            notifier.notify("Test", "Message", "info")

        assert "Test: Message" in caplog.text

    def test_fallback_on_plyer_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should fall back to logging when plyer raises an exception."""
        notifier = DesktopNotifier()

        with (
            patch(
                "plyer.notification.notify",
                side_effect=RuntimeError("Display not available"),
            ),
            caplog.at_level("WARNING"),
        ):
            notifier.notify("Test", "Message", "error")

        assert "Desktop notification failed" in caplog.text


class TestCompositeNotifier:
    """Tests for CompositeNotifier."""

    def test_notify_calls_all_notifiers(self) -> None:
        """CompositeNotifier should call all child notifiers."""
        mock1 = MagicMock()
        mock2 = MagicMock()

        notifier = CompositeNotifier([mock1, mock2])
        notifier.notify("Title", "Message", "info")

        mock1.notify.assert_called_once_with("Title", "Message", "info")
        mock2.notify.assert_called_once_with("Title", "Message", "info")

    def test_continues_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """CompositeNotifier should continue if one notifier fails."""
        mock1 = MagicMock()
        mock1.notify.side_effect = RuntimeError("Failed")
        mock2 = MagicMock()

        notifier = CompositeNotifier([mock1, mock2])

        with caplog.at_level("WARNING"):
            notifier.notify("Title", "Message", "info")

        # First failed but second should still be called
        mock2.notify.assert_called_once()
        assert "MagicMock failed" in caplog.text

    def test_convenience_methods(self) -> None:
        """Convenience methods should work with CompositeNotifier."""
        mock = MagicMock()
        notifier = CompositeNotifier([mock])

        notifier.info("Info", "msg")
        notifier.success("Success", "msg")
        notifier.warning("Warning", "msg")
        notifier.error("Error", "msg")
        notifier.alert("Alert", "msg")

        assert mock.notify.call_count == 5


class TestOrchestratorNotifierCreation:
    """Tests for Orchestrator._create_notifier method."""

    def test_disabled_returns_null_notifier(self, tmp_path: pytest.TempPathFactory) -> None:
        """When notifications disabled, should return NullNotifier."""
        from debussy.core.orchestrator import Orchestrator

        config = Config(notifications=NotificationConfig(enabled=False))

        # Create a minimal master plan file
        plan_file = tmp_path / "plan.md"  # type: ignore[operator]
        plan_file.write_text("# Test Plan\n\n| Phase | Title |\n|---|---|\n")

        orchestrator = Orchestrator(plan_file, config=config)
        assert isinstance(orchestrator.notifier, NullNotifier)

    def test_provider_none_returns_null_notifier(self, tmp_path: pytest.TempPathFactory) -> None:
        """When provider is 'none', should return NullNotifier."""
        from debussy.core.orchestrator import Orchestrator

        config = Config(notifications=NotificationConfig(enabled=True, provider="none"))

        plan_file = tmp_path / "plan.md"  # type: ignore[operator]
        plan_file.write_text("# Test Plan\n\n| Phase | Title |\n|---|---|\n")

        orchestrator = Orchestrator(plan_file, config=config)
        assert isinstance(orchestrator.notifier, NullNotifier)

    def test_provider_desktop_returns_composite(self, tmp_path: pytest.TempPathFactory) -> None:
        """When provider is 'desktop', should return CompositeNotifier."""
        from debussy.core.orchestrator import Orchestrator

        config = Config(notifications=NotificationConfig(enabled=True, provider="desktop"))

        plan_file = tmp_path / "plan.md"  # type: ignore[operator]
        plan_file.write_text("# Test Plan\n\n| Phase | Title |\n|---|---|\n")

        orchestrator = Orchestrator(plan_file, config=config)
        assert isinstance(orchestrator.notifier, CompositeNotifier)

        # Should have both desktop and console notifiers
        assert len(orchestrator.notifier.notifiers) == 2
        assert isinstance(orchestrator.notifier.notifiers[0], DesktopNotifier)
        assert isinstance(orchestrator.notifier.notifiers[1], ConsoleNotifier)
