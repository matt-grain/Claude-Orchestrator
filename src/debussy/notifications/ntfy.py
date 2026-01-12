"""ntfy.sh notification provider."""

from __future__ import annotations

import logging

import httpx

from debussy.notifications.base import NotificationLevel, Notifier

logger = logging.getLogger(__name__)

# ntfy priority levels (1=min, 5=max)
# https://docs.ntfy.sh/publish/#message-priority
PRIORITY_MAP: dict[NotificationLevel, int] = {
    "info": 3,  # default
    "success": 3,  # default
    "warning": 4,  # high
    "error": 5,  # max/urgent
    "alert": 5,  # max/urgent
}

# ntfy tags (emojis) for different levels
# https://docs.ntfy.sh/publish/#tags-emojis
TAGS_MAP: dict[NotificationLevel, list[str]] = {
    "info": ["information_source"],
    "success": ["white_check_mark"],
    "warning": ["warning"],
    "error": ["x"],
    "alert": ["rotating_light"],
}


class NtfyNotifier(Notifier):
    """Send notifications via ntfy.sh or self-hosted ntfy server.

    ntfy is a simple HTTP-based pub-sub notification service.
    Notifications can be received on phone (Android/iOS) or desktop.

    See: https://ntfy.sh/
    """

    def __init__(
        self,
        server: str = "https://ntfy.sh",
        topic: str = "claude-debussy",
        timeout: float = 10.0,
    ) -> None:
        """Initialize ntfy notifier.

        Args:
            server: ntfy server URL (default: https://ntfy.sh)
            topic: Topic to publish to (like a channel name)
            timeout: HTTP request timeout in seconds
        """
        self.server = server.rstrip("/")
        self.topic = topic
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = "info",
    ) -> None:
        """Send notification via ntfy.

        Args:
            title: Notification title
            message: Notification body
            level: Severity level (affects priority and tags)
        """
        url = f"{self.server}/{self.topic}"
        priority = PRIORITY_MAP.get(level, 3)
        tags = TAGS_MAP.get(level, [])

        headers = {
            "Title": title,
            "Priority": str(priority),
            "Tags": ",".join(tags),
        }

        try:
            response = self.client.post(url, content=message, headers=headers)
            response.raise_for_status()
            logger.debug(f"ntfy notification sent: {title}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"ntfy notification failed (HTTP {e.response.status_code}): {e}")
        except httpx.RequestError as e:
            logger.warning(f"ntfy notification failed (network error): {e}")
        except Exception as e:
            logger.warning(f"ntfy notification failed: {e}")

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
