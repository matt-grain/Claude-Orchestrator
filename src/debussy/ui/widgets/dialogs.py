"""Modal confirmation dialogs for the TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ResumeConfirmScreen(ModalScreen[bool]):
    """Modal confirmation screen for resuming a previous run."""

    CSS = """
    ResumeConfirmScreen {
        align: center middle;
    }

    #resume-dialog {
        width: 60;
        height: 14;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #resume-dialog Static {
        width: 100%;
        content-align: center middle;
    }

    #resume-title {
        text-style: bold;
        color: $primary;
    }

    #resume-info {
        color: $text-muted;
    }

    #resume-buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
    }

    #resume-buttons Button {
        margin: 0 2;
        min-width: 14;
        height: 3;
    }
    """

    def __init__(self, run_id: str, completed_count: int, **kwargs) -> None:
        """Initialize with run info."""
        super().__init__(**kwargs)
        self._run_id = run_id
        self._completed_count = completed_count

    def compose(self) -> ComposeResult:
        """Compose the resume confirmation dialog."""
        with Container(id="resume-dialog"):
            yield Static("Resume Previous Run?", id="resume-title")
            yield Static("")
            yield Static(
                f"Found incomplete run [bold]{self._run_id[:8]}[/bold]",
                id="resume-info",
            )
            yield Static(f"with {self._completed_count} completed phase(s).")
            yield Static("")
            with Horizontal(id="resume-buttons"):
                yield Button("Resume", variant="primary", id="resume-yes")
                yield Button("Start Fresh", variant="default", id="resume-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id == "resume-yes")


class QuitConfirmScreen(ModalScreen[bool]):
    """Modal confirmation screen for quitting."""

    CSS = """
    QuitConfirmScreen {
        align: center middle;
    }

    #quit-dialog {
        width: 50;
        height: 12;
        border: solid $error;
        background: $surface;
        padding: 1 2;
    }

    #quit-dialog Static {
        width: 100%;
        content-align: center middle;
    }

    #quit-title {
        text-style: bold;
        color: $error;
    }

    #quit-buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
    }

    #quit-buttons Button {
        margin: 0 2;
        min-width: 12;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the quit confirmation dialog."""
        with Container(id="quit-dialog"):
            yield Static("Quit Orchestration?", id="quit-title")
            yield Static("")
            yield Static("This will cancel all running Claude instances.")
            yield Static("")
            with Horizontal(id="quit-buttons"):
                yield Button("Quit", variant="error", id="quit-yes")
                yield Button("Cancel", variant="primary", id="quit-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id == "quit-yes")
