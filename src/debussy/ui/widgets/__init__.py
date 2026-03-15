"""Widget modules for the Debussy TUI."""

from __future__ import annotations

from debussy.ui.widgets.dialogs import QuitConfirmScreen, ResumeConfirmScreen
from debussy.ui.widgets.phase_panel import HUDHeader
from debussy.ui.widgets.status_bar import HotkeyBar

__all__ = [
    "HUDHeader",
    "HotkeyBar",
    "QuitConfirmScreen",
    "ResumeConfirmScreen",
]
