"""Desktop notification provider using plyer."""

from __future__ import annotations

import logging

from debussy.notifications.base import NotificationLevel, Notifier

logger = logging.getLogger(__name__)


class DesktopNotifier(Notifier):
    """Cross-platform desktop notifications using plyer.

    Works on:
    - Windows (via win10toast or Windows notifications)
    - Linux (via notify-send/libnotify)
    - macOS (via osascript/notification center)

    Falls back to console logging if plyer notifications fail.
    """

    def __init__(self, app_name: str = "Debussy", timeout: int = 10) -> None:
        """Initialize desktop notifier.

        Args:
            app_name: Application name shown in notifications
            timeout: Notification display duration in seconds
        """
        self.app_name = app_name
        self.timeout = timeout
        self._plyer_available = self._check_plyer()

    def _check_plyer(self) -> bool:
        """Check if plyer notifications are available."""
        try:
            from plyer import notification  # noqa: F401

            return True
        except ImportError:
            logger.warning("plyer not installed, desktop notifications disabled")
            return False
        except Exception as e:
            logger.warning(f"plyer initialization failed: {e}")
            return False

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body
            level: Severity level (affects icon/urgency on some platforms)
        """
        if not self._plyer_available:
            self._fallback_log(title, message, level)
            return

        try:
            from plyer import notification

            # Map levels to toast settings
            # Note: plyer's toast parameter only affects Windows behavior
            toast = level in ("error", "alert")

            notification.notify(  # type: ignore[misc]
                title=f"[{self.app_name}] {title}",
                message=message,
                app_name=self.app_name,
                timeout=self.timeout,
                toast=toast,
            )
        except Exception as e:
            logger.warning(f"Desktop notification failed: {e}")
            self._fallback_log(title, message, level)

    def _fallback_log(
        self,
        title: str,
        message: str,
        level: NotificationLevel,
    ) -> None:
        """Log notification when desktop notifications unavailable."""
        log_levels = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "alert": logging.CRITICAL,
        }
        log_level = log_levels.get(level, logging.INFO)
        logger.log(log_level, f"{title}: {message}")


class CompositeNotifier(Notifier):
    """Sends notifications to multiple providers simultaneously.

    Useful for sending both desktop and console notifications,
    or desktop and ntfy notifications.
    """

    def __init__(self, notifiers: list[Notifier]) -> None:
        """Initialize with list of notifiers.

        Args:
            notifiers: List of notification providers to use
        """
        self.notifiers = notifiers

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Send notification to all providers.

        Args:
            title: Notification title
            message: Notification body
            level: Severity level
        """
        for notifier in self.notifiers:
            try:
                notifier.notify(title, message, level)
            except Exception as e:
                logger.warning(f"Notifier {type(notifier).__name__} failed: {e}")
