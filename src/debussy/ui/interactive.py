"""Interactive UI for orchestration with live dashboard."""

from __future__ import annotations

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from debussy.core.models import Phase


class UIState(str, Enum):
    """Current state of the UI."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_INPUT = "waiting_input"


class UserAction(str, Enum):
    """Actions that can be triggered by user input."""

    NONE = "none"
    STATUS = "status"
    PAUSE = "pause"
    RESUME = "resume"
    TOGGLE_VERBOSE = "verbose"
    SKIP = "skip"
    QUIT = "quit"


@dataclass
class UIContext:
    """Current context for the UI display."""

    plan_name: str = ""
    current_phase: str = ""
    phase_title: str = ""
    total_phases: int = 0
    phase_index: int = 0
    state: UIState = UIState.IDLE
    start_time: float = field(default_factory=time.time)
    verbose: bool = True
    last_action: UserAction = UserAction.NONE


class InteractiveUI:
    """Interactive dashboard UI for orchestration.

    Provides:
    - Sticky header with phase info and elapsed time
    - Hotkey bar for available actions
    - Scrolling log panel for Claude output
    - Keyboard input handling
    """

    MAX_LOG_LINES = 100

    def __init__(self, console: Console | None = None) -> None:
        """Initialize interactive UI.

        Args:
            console: Rich console to use (creates new one if not provided)
        """
        self.console = console or Console()
        self.context = UIContext()
        self.log_lines: deque[str] = deque(maxlen=self.MAX_LOG_LINES)
        self._live: Live | None = None
        self._keyboard_thread: threading.Thread | None = None
        self._stop_keyboard = threading.Event()
        self._action_queue: deque[UserAction] = deque()
        self._lock = threading.Lock()

    def start(self, plan_name: str, total_phases: int) -> None:
        """Start the interactive UI.

        Args:
            plan_name: Name of the master plan
            total_phases: Total number of phases
        """
        self.context.plan_name = plan_name
        self.context.total_phases = total_phases
        self.context.start_time = time.time()
        self.context.state = UIState.RUNNING

        # Start keyboard listener
        self._stop_keyboard.clear()
        self._keyboard_thread = threading.Thread(
            target=self._keyboard_listener,
            daemon=True,
        )
        self._keyboard_thread.start()

        # Start live display
        self._live = Live(
            self._build_layout(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the interactive UI."""
        self._stop_keyboard.set()

        if self._live is not None:
            self._live.stop()
            self._live = None

        if self._keyboard_thread is not None:
            self._keyboard_thread.join(timeout=0.5)
            self._keyboard_thread = None

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed.

        Args:
            phase: The phase being executed
            index: 1-based index of the phase
        """
        with self._lock:
            self.context.current_phase = phase.id
            self.context.phase_title = phase.title
            self.context.phase_index = index
        self._refresh()

    def set_state(self, state: UIState) -> None:
        """Update the UI state.

        Args:
            state: New state
        """
        with self._lock:
            self.context.state = state
        self._refresh()

    def log(self, message: str) -> None:
        """Add a log message to the display.

        Args:
            message: Message to display
        """
        if not self.context.verbose:
            return

        with self._lock:
            self.log_lines.append(message)
        self._refresh()

    def log_raw(self, message: str) -> None:
        """Add a raw log message (ignores verbose setting).

        Args:
            message: Message to display
        """
        with self._lock:
            self.log_lines.append(message)
        self._refresh()

    def get_pending_action(self) -> UserAction:
        """Get the next pending user action.

        Returns:
            The next action, or UserAction.NONE if no action pending
        """
        with self._lock:
            if self._action_queue:
                action = self._action_queue.popleft()
                self.context.last_action = action
                return action
            return UserAction.NONE

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging.

        Returns:
            New verbose state
        """
        with self._lock:
            self.context.verbose = not self.context.verbose
            state_str = "ON" if self.context.verbose else "OFF"
            self.log_lines.append(f"[dim]Verbose logging: {state_str}[/dim]")
        self._refresh()
        return self.context.verbose

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show a detailed status popup.

        Args:
            details: Dictionary of status details to display
        """
        lines = ["[bold]Current Status[/bold]", ""]
        for key, value in details.items():
            lines.append(f"  {key}: {value}")

        with self._lock:
            self.log_lines.append("")
            for line in lines:
                self.log_lines.append(line)
            self.log_lines.append("")
        self._refresh()

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation.

        Args:
            message: Confirmation message

        Returns:
            True if confirmed, False otherwise
        """
        # Temporarily stop live display for input
        if self._live:
            self._live.stop()

        try:
            self.console.print(f"\n[yellow]{message}[/yellow]")
            response = self.console.input("[bold]Continue? (y/n): [/bold]").lower()
            return response in ("y", "yes")
        finally:
            # Restart live display
            if self._live:
                self._live.start()

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self._live is not None:
            self._live.update(self._build_layout())

    def _build_layout(self) -> Panel:
        """Build the dashboard layout.

        Returns:
            Panel containing the full layout
        """
        # Build header
        header = self._build_header()

        # Build hotkey bar
        hotkeys = self._build_hotkey_bar()

        # Build log panel
        log_content = self._build_log_content()

        # Combine into layout
        content = Group(header, hotkeys, Text(), log_content)

        return Panel(
            content,
            title="[bold blue]Debussy[/bold blue]",
            border_style="blue",
        )

    def _build_header(self) -> Text:
        """Build the header line with phase info and status."""
        ctx = self.context
        elapsed = time.time() - ctx.start_time
        elapsed_str = self._format_duration(elapsed)

        # Status indicator
        status_colors = {
            UIState.IDLE: ("dim", "Idle"),
            UIState.RUNNING: ("green", "Running"),
            UIState.PAUSED: ("yellow", "Paused"),
            UIState.WAITING_INPUT: ("cyan", "Waiting"),
        }
        color, status_text = status_colors.get(ctx.state, ("white", "Unknown"))

        header = Text()
        header.append("Phase ", style="dim")
        header.append(f"{ctx.phase_index}/{ctx.total_phases}", style="bold")
        header.append(": ", style="dim")
        header.append(ctx.phase_title or "Starting...", style="bold cyan")
        header.append("  |  ", style="dim")
        header.append(f"● {status_text}", style=color)
        header.append("  |  ", style="dim")
        header.append(f"⏱ {elapsed_str}", style="dim")

        return header

    def _build_hotkey_bar(self) -> Text:
        """Build the hotkey bar."""
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
        v_state = "on" if self.context.verbose else "off"
        bar.append(f"({v_state})  ", style="dim italic")

        bar.append("[", style="dim")
        bar.append("k", style="bold yellow")
        bar.append("]skip  ", style="dim")
        bar.append("[", style="dim")
        bar.append("q", style="bold yellow")
        bar.append("]uit", style="dim")

        return bar

    def _build_log_content(self) -> Text:
        """Build the log content area."""
        content = Text()

        with self._lock:
            lines = list(self.log_lines)

        if not lines:
            content.append("Waiting for output...", style="dim italic")
        else:
            for line in lines[-20:]:  # Show last 20 lines
                content.append(line)
                content.append("\n")

        return content

    def _format_duration(self, seconds: float) -> str:
        """Format duration in HH:MM:SS format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _keyboard_listener(self) -> None:
        """Background thread for keyboard input handling."""
        import contextlib

        # Try platform-specific keyboard handling with fallbacks
        if sys.platform == "win32":
            # On Windows, try msvcrt first (works in CMD/PowerShell)
            # Git Bash/MINGW: msvcrt doesn't work, but termios also unavailable
            with contextlib.suppress(Exception):
                self._keyboard_listener_windows()
        else:
            # Unix/Linux/macOS: use termios
            self._keyboard_listener_unix()

    def _keyboard_listener_windows(self) -> None:
        """Windows-specific keyboard listener using msvcrt."""
        import msvcrt

        while not self._stop_keyboard.is_set():
            if msvcrt.kbhit():
                try:
                    key = msvcrt.getch().decode("utf-8").lower()
                    self._handle_key(key)
                except (UnicodeDecodeError, OSError):
                    pass
            time.sleep(0.05)

    def _keyboard_listener_unix(self) -> None:
        """Unix-specific keyboard listener using termios."""
        import select
        import termios  # type: ignore[import-not-found]
        import tty  # type: ignore[import-not-found]

        old_settings = termios.tcgetattr(sys.stdin)  # type: ignore[attr-defined]
        try:
            tty.setcbreak(sys.stdin.fileno())  # type: ignore[attr-defined]

            while not self._stop_keyboard.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()
                    self._handle_key(key)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)  # type: ignore[attr-defined]

    def _handle_key(self, key: str) -> None:
        """Handle a keypress.

        Args:
            key: The key that was pressed
        """
        action_map = {
            "s": UserAction.STATUS,
            "p": UserAction.PAUSE if self.context.state == UIState.RUNNING else UserAction.RESUME,
            "v": UserAction.TOGGLE_VERBOSE,
            "k": UserAction.SKIP,
            "q": UserAction.QUIT,
        }

        action = action_map.get(key)
        if action:
            with self._lock:
                self._action_queue.append(action)


class NonInteractiveUI:
    """Simple non-interactive UI for YOLO/CI mode.

    Just passes through log messages to console without the dashboard.
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize non-interactive UI."""
        self.console = console or Console()
        self.context = UIContext()
        self.context.verbose = True

    def start(self, plan_name: str, total_phases: int) -> None:
        """Start the UI (no-op for non-interactive)."""
        self.context.plan_name = plan_name
        self.context.total_phases = total_phases
        self.context.start_time = time.time()
        self.console.print(f"[bold]Starting orchestration:[/bold] {plan_name}")
        self.console.print(f"[dim]Total phases: {total_phases}[/dim]\n")

    def stop(self) -> None:
        """Stop the UI (no-op for non-interactive)."""
        elapsed = time.time() - self.context.start_time
        self.console.print(f"\n[dim]Completed in {elapsed:.1f}s[/dim]")

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update current phase."""
        self.context.current_phase = phase.id
        self.context.phase_title = phase.title
        self.context.phase_index = index
        self.console.print(f"\n[bold cyan]Phase {index}: {phase.title}[/bold cyan]")

    def set_state(self, state: UIState) -> None:
        """Update state (no-op for non-interactive)."""
        self.context.state = state

    def log(self, message: str) -> None:
        """Log a message."""
        if self.context.verbose:
            self.console.print(message)

    def log_raw(self, message: str) -> None:
        """Log a raw message."""
        self.console.print(message)

    def get_pending_action(self) -> UserAction:
        """Get pending action (always NONE for non-interactive)."""
        return UserAction.NONE

    def toggle_verbose(self) -> bool:
        """Toggle verbose (no-op, always verbose in non-interactive)."""
        return True

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show status (print to console)."""
        self.console.print("\n[bold]Status:[/bold]")
        for key, value in details.items():
            self.console.print(f"  {key}: {value}")
        self.console.print()

    def confirm(self, message: str) -> bool:
        """Confirm action (auto-yes in non-interactive)."""
        self.console.print(f"[yellow]{message}[/yellow] (auto-confirmed in YOLO mode)")
        return True
