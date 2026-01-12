"""Base notification interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

NotificationLevel = Literal["info", "success", "warning", "error", "alert"]


class Notifier(ABC):
    """Abstract base class for notification providers."""

    @abstractmethod
    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Send a notification.

        Args:
            title: Notification title
            message: Notification body
            level: Severity level
        """

    def info(self, title: str, message: str) -> None:
        """Send an info notification."""
        self.notify(title, message, "info")

    def success(self, title: str, message: str) -> None:
        """Send a success notification."""
        self.notify(title, message, "success")

    def warning(self, title: str, message: str) -> None:
        """Send a warning notification."""
        self.notify(title, message, "warning")

    def error(self, title: str, message: str) -> None:
        """Send an error notification."""
        self.notify(title, message, "error")

    def alert(self, title: str, message: str) -> None:
        """Send an alert notification (highest priority)."""
        self.notify(title, message, "alert")


class ConsoleNotifier(Notifier):
    """Simple console-based notifier using Rich."""

    def __init__(self) -> None:
        from rich.console import Console

        self.console = Console()

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Print notification to console with appropriate styling."""
        styles = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "alert": "bold red",
        }
        icons = {
            "info": "i",
            "success": "+",
            "warning": "!",
            "error": "x",
            "alert": "!!!",
        }

        style = styles.get(level, "blue")
        icon = icons.get(level, "i")

        self.console.print(f"[{style}][{icon}] {title}[/{style}]")
        if message:
            self.console.print(f"    {message}")


class NullNotifier(Notifier):
    """No-op notifier for testing or when notifications are disabled."""

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Do nothing."""
