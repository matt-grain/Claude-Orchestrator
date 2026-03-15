"""Hotkey bar widget showing available actions and status message."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class HotkeyBar(Static):
    """Hotkey bar showing available actions and status message."""

    verbose = reactive(True)
    auto_scroll = reactive(False)
    message = reactive("")  # Transient status message

    def render(self) -> Text:
        """Render the hotkey bar."""
        bar = Text()
        bar.append("[", style="dim")
        bar.append("s", style="bold yellow")
        bar.append("]tatus  ", style="dim")
        bar.append("[", style="dim")
        bar.append("p", style="bold yellow")
        bar.append("]ause  ", style="dim")
        bar.append("[", style="dim")
        bar.append("v", style="bold yellow")
        bar.append("]erbose ", style="dim")

        # Show current verbose state
        v_state = "on" if self.verbose else "off"
        bar.append(f"({v_state})  ", style="dim italic")

        bar.append("[", style="dim")
        bar.append("a", style="bold yellow")
        bar.append("]utoscroll ", style="dim")

        # Show current auto-scroll state
        a_state = "on" if self.auto_scroll else "off"
        bar.append(f"({a_state})  ", style="dim italic")

        bar.append("s[", style="dim")
        bar.append("k", style="bold yellow")
        bar.append("]ip  ", style="dim")
        bar.append("[", style="dim")
        bar.append("q", style="bold yellow")
        bar.append("]uit", style="dim")

        # Show status message if any
        if self.message:
            bar.append("  │  ", style="dim")
            bar.append(self.message, style="italic yellow")

        return bar
