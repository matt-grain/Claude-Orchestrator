"""Textual-based TUI for orchestration with live dashboard.

Provides a proper terminal UI with:
- Fixed HUD header that updates in real-time (timer, status)
- Scrollable log panel for Claude output
- Keyboard bindings for control

The TUI runs as the main application and spawns orchestration as a worker.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, RichLog, Static
from textual.worker import Worker, WorkerState

from debussy.runners.claude import pid_registry
from debussy.ui.base import STATUS_MAP, UIContext, UIState, UserAction, format_duration
from debussy.ui.controller import OrchestrationController

# NOTE: These message imports are needed at RUNTIME for Textual's on_* message handlers.
# Textual's message dispatch system requires the actual types to be available.
from debussy.ui.messages import (  # noqa: TC001
    ActiveAgentChanged,
    HUDMessageSet,
    LogMessage,
    OrchestrationCompleted,
    OrchestrationStarted,
    PhaseChanged,
    StateChanged,
    TokenStatsUpdated,
    VerboseToggled,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from debussy.core.models import Phase


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


class HUDHeader(Static):
    """Fixed header widget showing phase info, status, timer, and token usage."""

    phase_info = reactive("Phase 0/0: Starting...")
    status = reactive("Running")
    status_style = reactive("green")
    elapsed = reactive("00:00:00")
    context_pct = reactive(0)
    total_tokens = reactive(0)
    cost_usd = reactive(0.0)
    active_agent = reactive("Debussy")  # Current agent (Debussy, Explore, etc.)

    def render(self) -> Text:
        """Render the HUD header."""
        text = Text()

        # Phase info
        text.append("Phase ", style="dim")
        text.append(self.phase_info, style="bold cyan")
        text.append("  |  ", style="dim")

        # Status indicator
        text.append(f"● {self.status}", style=self.status_style)
        text.append("  |  ", style="dim")

        # Active agent (highlighted when not Debussy)
        agent = self.active_agent
        if agent == "Debussy":
            text.append(f"🎹 {agent}", style="dim")
        else:
            text.append(f"🤖 {agent}", style="bold magenta")
        text.append("  |  ", style="dim")

        # Timer
        text.append(f"⏱ {self.elapsed}", style="dim")
        text.append("  |  ", style="dim")

        # Context window usage (color-coded)
        pct = self.context_pct
        if pct < 50:
            pct_style = "green"
        elif pct < 80:
            pct_style = "yellow"
        else:
            pct_style = "red bold"
        text.append(f"📊 {pct}%", style=pct_style)
        text.append("  |  ", style="dim")

        # Total tokens (formatted with K suffix)
        tokens_str = self._format_tokens(self.total_tokens)
        text.append(f"🔤 {tokens_str}", style="dim")
        text.append("  |  ", style="dim")

        # Cost
        text.append(f"💰 ${self.cost_usd:.2f}", style="dim")

        return text

    @staticmethod
    def _format_tokens(tokens: int) -> str:
        """Format token count with K/M suffix."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}M"
        if tokens >= 1_000:
            return f"{tokens / 1_000:.1f}K"
        return str(tokens)


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


class DebussyTUI(App):
    """Textual TUI for Debussy orchestration.

    This app is designed to be the main driver. It creates a TextualUI
    instance that provides the same interface as NonInteractiveUI, then
    runs orchestration as a background worker.
    """

    TITLE = "Debussy"

    CSS = """
    Screen {
        layout: vertical;
    }

    #hud-container {
        height: 4;
        border: solid $accent;
        padding: 0 1;
        background: $surface;
    }

    #hud-header {
        height: 1;
    }

    #hotkey-bar {
        height: 1;
    }

    #log-container {
        height: 1fr;
        border: solid $primary-background-darken-2;
    }

    RichLog {
        scrollbar-gutter: stable;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar = [
        Binding("s", "show_status", "Status", show=False),
        Binding("p", "toggle_pause", "Pause/Resume", show=False),
        Binding("v", "toggle_verbose", "Toggle Verbose", show=False),
        Binding("a", "toggle_autoscroll", "Toggle Auto-scroll", show=False),
        Binding("k", "skip_phase", "Skip Phase", show=False),
        Binding("q", "quit_orchestration", "Quit", show=False),
    ]

    def __init__(
        self,
        orchestration_coro: Callable[[], Coroutine[Any, Any, str]] | None = None,
        **kwargs,
    ) -> None:
        """Initialize the TUI.

        Args:
            orchestration_coro: Coroutine factory that runs the orchestration.
                               Should return the run_id when complete.
        """
        super().__init__(**kwargs)
        # Controller is required and owns all state (UIContext, action queue)
        # Set via set_controller() before app starts
        self._controller: OrchestrationController | None = None
        self._orchestration_coro = orchestration_coro
        self._worker: Worker[str] | None = None  # Properly typed
        self._run_id: str | None = None
        self._shutting_down: bool = False  # Prevent re-entrance during shutdown
        self._auto_scroll: bool = False  # Log panel auto-scroll state

    def set_controller(self, controller: OrchestrationController) -> None:
        """Inject the controller (set by TextualUI wrapper).

        The controller owns all orchestration state (UIContext, action queue).
        This must be called before the app starts.

        Args:
            controller: The orchestration controller instance
        """
        self._controller = controller

    @property
    def ui_context(self) -> UIContext:
        """Return the controller's UIContext (single source of truth).

        Raises:
            RuntimeError: If controller is not set
        """
        return self._require_controller().context

    def _require_controller(self) -> OrchestrationController:
        """Return the controller, raising if not set.

        Raises:
            RuntimeError: If controller is not set
        """
        if self._controller is None:
            msg = "Controller not set - call set_controller() before use"
            raise RuntimeError(msg)
        return self._controller

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        with Container(id="hud-container"):
            yield HUDHeader(id="hud-header")
            yield HotkeyBar(id="hotkey-bar")
        with VerticalScroll(id="log-container"):
            yield RichLog(id="log", highlight=True, markup=True, wrap=True, auto_scroll=False)

    def on_mount(self) -> None:
        """Start timer and orchestration when app mounts."""
        self.set_interval(1.0, self._update_timer)
        self.update_hud()

        # Start orchestration as a worker if provided
        if self._orchestration_coro:
            self._worker = self._start_orchestration()  # Capture worker for cancellation

    def on_unmount(self) -> None:
        """Cleanup when app unmounts (including crashes)."""
        logger.debug("TUI unmounting, running cleanup")
        self._cleanup_all_processes()

    def _cleanup_all_processes(self) -> None:
        """Cancel worker and kill any orphaned Claude processes.

        This is the primary cleanup method, called from multiple places:
        - on_unmount (normal exit, crashes)
        - _handle_quit_confirmation (user quit)
        """
        # Cancel the worker if running
        if self._worker and self._worker.is_running:
            logger.debug("Cancelling orchestration worker")
            self._worker.cancel()

        # Safety net: kill any registered PIDs that might have escaped
        active_pids = pid_registry.get_active_pids()
        if active_pids:
            logger.warning(f"Found {len(active_pids)} orphaned PIDs, killing: {active_pids}")
            killed = pid_registry.kill_all()
            if killed:
                logger.info(f"Killed orphaned PIDs: {killed}")

    def _verify_cleanup_complete(self) -> bool:
        """Verify all Claude processes are dead. Returns True if clean."""
        still_alive = pid_registry.verify_all_dead()
        if still_alive:
            logger.error(f"PIDs still alive after cleanup: {still_alive}")
            # Try one more time
            pid_registry.kill_all()
            still_alive = pid_registry.verify_all_dead()
            if still_alive:
                logger.critical(f"FAILED to kill PIDs: {still_alive}")
                return False
        return True

    @work(exclusive=True)
    async def _start_orchestration(self) -> str:
        """Run orchestration as a background worker."""
        if self._orchestration_coro:
            return await self._orchestration_coro()
        return ""

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            self._run_id = event.worker.result
            self.write_log("[green]Orchestration completed successfully[/green]")
            # Don't auto-exit - let user review logs
        elif event.state == WorkerState.ERROR:
            self.write_log(f"[red]Orchestration failed: {event.worker.error}[/red]")
        elif event.state == WorkerState.CANCELLED:
            self.write_log("[yellow]Orchestration cancelled[/yellow]")

    def _update_timer(self) -> None:
        """Update the elapsed time display."""
        elapsed = time.time() - self.ui_context.start_time
        header = self.query_one("#hud-header", HUDHeader)
        header.elapsed = format_duration(elapsed)

    def update_hud(self) -> None:
        """Update the HUD with current context."""
        header = self.query_one("#hud-header", HUDHeader)
        hotkey_bar = self.query_one("#hotkey-bar", HotkeyBar)

        # Update phase info
        ctx = self.ui_context
        title = ctx.phase_title or "Starting..."
        header.phase_info = f"{ctx.phase_index}/{ctx.total_phases}: {title}"

        # Update status
        status_text, status_style = STATUS_MAP.get(ctx.state, ("Unknown", "white"))
        header.status = status_text
        header.status_style = status_style

        # Update verbose state
        hotkey_bar.verbose = ctx.verbose

        # Update token stats - show session tokens (live) + run total cost
        session_tokens = ctx.session_input_tokens + ctx.session_output_tokens
        header.total_tokens = session_tokens
        header.cost_usd = ctx.total_cost_usd

        # Calculate context percentage from current session
        if ctx.context_window > 0 and ctx.current_context_tokens > 0:
            header.context_pct = int((ctx.current_context_tokens / ctx.context_window) * 100)
        else:
            header.context_pct = 0

    def write_log(self, message: str) -> None:
        """Add a message to the log panel."""
        log = self.query_one("#log", RichLog)
        # Style tool commands like [Read: file.py] or [ERROR: ...] in italic dim
        # Match pattern: [CapitalizedWord: ...] or indented [ERROR: ...]
        if re.match(r"^\s*\[[A-Z][a-zA-Z]*:", message):
            # Transform [Tool: content] to styled markup
            # Replace brackets to avoid Rich markup conflicts
            styled = re.sub(
                r"\[([A-Z][a-zA-Z]*):(.*?)\]",
                r"[italic dim]⟨\1:\2⟩[/italic dim]",
                message,
            )
            log.write(styled)
        else:
            log.write(message)

    def set_hud_message(self, message: str) -> None:
        """Set a transient message in the HUD hotkey bar."""
        hotkey_bar = self.query_one("#hotkey-bar", HotkeyBar)
        hotkey_bar.message = message

    def clear_hud_message(self) -> None:
        """Clear the HUD message after a delay."""
        self.set_hud_message("")

    def action_show_status(self) -> None:
        """Handle status action - show status summary in HUD."""
        ctx = self.ui_context
        elapsed = time.time() - ctx.start_time
        elapsed_str = format_duration(elapsed)

        # Show compact status in HUD message
        status_msg = f"{ctx.plan_name} | {ctx.state.value} | {elapsed_str}"
        self.set_hud_message(status_msg)
        # Clear message after 5 seconds
        self.set_timer(5.0, self.clear_hud_message)

    def action_toggle_pause(self) -> None:
        """Handle pause/resume action."""
        state = self.ui_context.state
        action = UserAction.PAUSE if state == UIState.RUNNING else UserAction.RESUME
        self._require_controller().queue_action(action)
        self.set_timer(3.0, self.clear_hud_message)

    def action_toggle_verbose(self) -> None:
        """Handle verbose toggle - apply immediately in TUI."""
        self._require_controller().toggle_verbose()
        self.set_timer(3.0, self.clear_hud_message)

    def action_toggle_autoscroll(self) -> None:
        """Handle auto-scroll toggle for the log panel."""
        self._auto_scroll = not self._auto_scroll
        log = self.query_one("#log", RichLog)
        log.auto_scroll = self._auto_scroll
        # Update hotkey bar display
        hotkey_bar = self.query_one("#hotkey-bar", HotkeyBar)
        hotkey_bar.auto_scroll = self._auto_scroll
        state_str = "ON" if self._auto_scroll else "OFF"
        self.set_hud_message(f"Auto-scroll: {state_str}")
        self.set_timer(3.0, self.clear_hud_message)

    def action_skip_phase(self) -> None:
        """Handle skip action."""
        self._require_controller().queue_action(UserAction.SKIP)
        self.set_timer(3.0, self.clear_hud_message)

    def action_quit_orchestration(self) -> None:
        """Handle quit action - show confirmation dialog."""
        self.push_screen(QuitConfirmScreen(), self._handle_quit_confirmation)

    # =========================================================================
    # Message Handlers (PR #4)
    # These handlers receive messages from OrchestrationController and update
    # the UI accordingly. This enables the message-driven architecture.
    # =========================================================================

    def on_orchestration_started(self, message: OrchestrationStarted) -> None:
        """Handle orchestration started message from controller.

        Updates the HUD to reflect the new orchestration run.
        Note: The welcome banner is written by start() method directly.
        """
        header = self.query_one("#hud-header", HUDHeader)
        header.phase_info = f"0/{message.total_phases}: Starting..."

    def on_phase_changed(self, message: PhaseChanged) -> None:
        """Handle phase change message from controller.

        Updates the HUD header with new phase information.
        """
        header = self.query_one("#hud-header", HUDHeader)
        header.phase_info = f"{message.phase_index}/{message.total_phases}: {message.phase_title}"

    def on_state_changed(self, message: StateChanged) -> None:
        """Handle state change message from controller.

        Updates the HUD status indicator with the new state.
        """
        header = self.query_one("#hud-header", HUDHeader)
        status_text, status_style = STATUS_MAP.get(message.state, ("Unknown", "white"))
        header.status = status_text
        header.status_style = status_style

    def on_token_stats_updated(self, message: TokenStatsUpdated) -> None:
        """Handle token stats update message from controller.

        Updates the HUD with current token usage and cost.
        """
        header = self.query_one("#hud-header", HUDHeader)
        header.total_tokens = message.session_input_tokens
        header.cost_usd = message.total_cost_usd
        header.context_pct = message.context_pct

    def on_log_message(self, message: LogMessage) -> None:
        """Handle log message from controller.

        Writes to the log panel, respecting verbose setting unless raw=True.
        """
        if message.raw or self.ui_context.verbose:
            self.write_log(message.message)

    def on_hud_message_set(self, message: HUDMessageSet) -> None:
        """Handle HUD message from controller.

        Shows a transient message in the hotkey bar with optional auto-clear.
        """
        self.set_hud_message(message.message)
        if message.clear_after > 0:
            self.set_timer(message.clear_after, self.clear_hud_message)

    def on_verbose_toggled(self, message: VerboseToggled) -> None:
        """Handle verbose toggle message from controller.

        Updates the hotkey bar to reflect the new verbose state.
        """
        hotkey_bar = self.query_one("#hotkey-bar", HotkeyBar)
        hotkey_bar.verbose = message.is_verbose

    def on_orchestration_completed(self, message: OrchestrationCompleted) -> None:
        """Handle orchestration completed message from controller.

        Logs completion status. The TUI continues running to let users review logs.
        """
        if message.success:
            self.write_log(f"[green]Orchestration completed: {message.message}[/green]")
        else:
            self.write_log(f"[red]Orchestration failed: {message.message}[/red]")

    def on_active_agent_changed(self, message: ActiveAgentChanged) -> None:
        """Handle active agent change message from controller.

        Updates the HUD header to show which agent is currently working.
        """
        header = self.query_one("#hud-header", HUDHeader)
        header.active_agent = message.agent

    def _handle_quit_confirmation(self, confirmed: bool | None) -> None:
        """Handle the result of quit confirmation dialog."""
        if not confirmed:
            self.set_hud_message("Quit cancelled")
            self.set_timer(2.0, self.clear_hud_message)
            return

        # Prevent re-entrance
        if self._shutting_down:
            return
        self._shutting_down = True

        # User confirmed quit
        self._require_controller().queue_action(UserAction.QUIT)
        self.write_log("")
        self.write_log("[yellow]Shutting down...[/yellow]")

        # Start graceful shutdown (waits for actual process termination)
        self._graceful_shutdown()

    @work(exclusive=True, group="shutdown")
    async def _graceful_shutdown(self) -> None:
        """Gracefully shutdown, waiting for subprocess cleanup."""
        # Cancel the worker (this will trigger CancelledError in Claude runner)
        if self._worker and self._worker.is_running:
            self._worker.cancel()
            self.call_later(
                self.write_log, "[dim]Waiting for Claude processes to terminate...[/dim]"
            )

            # Wait for worker to actually finish (with timeout)
            for _ in range(50):  # Max 5 seconds
                if not self._worker.is_running:
                    break
                await asyncio.sleep(0.1)

        # Cleanup any orphaned processes
        self._cleanup_all_processes()

        # Verify everything is dead
        if self._verify_cleanup_complete():
            self.call_later(
                self.write_log, "[green]All Claude instances terminated. Cleanup complete.[/green]"
            )
        else:
            self.call_later(
                self.write_log,
                "[red]WARNING: Some processes may still be running. Check manually.[/red]",
            )

        # Brief delay to show messages, then exit
        await asyncio.sleep(0.5)
        self.call_later(self.exit)

    # =========================================================================
    # UI interface - these methods match NonInteractiveUI for compatibility
    # =========================================================================

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize UI context (called by orchestrator).

        Note: Called from async worker context (same event loop as Textual),
        so direct method calls are safe - no call_later() needed.
        """
        self._require_controller().start(plan_name, total_phases)
        self.update_hud()
        self._write_welcome_banner(plan_name, total_phases)

    def _write_welcome_banner(self, plan_name: str, total_phases: int) -> None:
        """Write welcome banner to log panel."""
        banner = r"""[bold cyan]
██████╗ ███████╗██████╗ ██╗   ██╗███████╗███████╗██╗   ██╗
██╔══██╗██╔════╝██╔══██╗██║   ██║██╔════╝██╔════╝╚██╗ ██╔╝
██║  ██║█████╗  ██████╔╝██║   ██║███████╗███████╗ ╚████╔╝
██║  ██║██╔══╝  ██╔══██╗██║   ██║╚════██║╚════██║  ╚██╔╝
██████╔╝███████╗██████╔╝╚██████╔╝███████║███████║   ██║
╚═════╝ ╚══════╝╚═════╝  ╚═════╝ ╚══════╝╚══════╝   ╚═╝
[/bold cyan]"""
        self.write_log(banner)
        self.write_log(f"[bold]Plan:[/bold] {plan_name}")
        self.write_log(f"[bold]Phases:[/bold] {total_phases}")
        self.write_log("")

    def stop(self) -> None:
        """Stop the UI (no-op, app controls its own lifecycle)."""
        pass

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed."""
        self._require_controller().set_phase(phase, index)
        self.update_hud()

    def set_state(self, state: UIState) -> None:
        """Update the UI state."""
        self._require_controller().set_state(state)
        self.update_hud()

    def log_message(self, message: str) -> None:
        """Add a log message to the scrolling output."""
        if not self.ui_context.verbose:
            return
        self.write_log(message)

    def log_message_raw(self, message: str) -> None:
        """Add a raw log message (ignores verbose setting)."""
        self.write_log(message)

    # Alias for compatibility
    log_raw = log_message_raw

    def get_pending_action(self) -> UserAction:
        """Get the next pending user action."""
        return self._require_controller().get_pending_action()

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging."""
        result = self._require_controller().toggle_verbose()
        self.update_hud()
        return result

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics.

        Per-turn updates show cumulative stats within current session.
        Final result (with cost > 0) adds session totals to run totals.
        """
        self._require_controller().update_token_stats(
            input_tokens, output_tokens, cost_usd, context_tokens, context_window
        )
        self.update_hud()

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show a detailed status popup."""
        self.write_log("")
        self.write_log("[bold]Current Status[/bold]")
        for key, value in details.items():
            self.write_log(f"  {key}: {value}")
        self.write_log("")

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation (auto-confirms in TUI mode)."""
        self.write_log(f"[yellow]{message}[/yellow] (auto-confirmed)")
        return True

    def set_active_agent(self, agent: str) -> None:
        """Update the active agent display in the HUD."""
        header = self.query_one("#hud-header", HUDHeader)
        header.active_agent = agent


class TextualUI:
    """Wrapper that provides the UI interface backed by DebussyTUI.

    This class creates and manages a DebussyTUI app instance with an
    OrchestrationController for state management.

    The app must be run from the main thread using run_with_orchestration().
    """

    def __init__(self) -> None:
        """Initialize the Textual UI wrapper."""
        self._app: DebussyTUI | None = None
        self._controller: OrchestrationController | None = None

    @property
    def context(self) -> UIContext:
        """Return the controller's UIContext (single source of truth)."""
        if self._controller is None:
            raise RuntimeError("TextualUI.context accessed before app was created")
        return self._controller.context

    def create_app(
        self, orchestration_coro: Callable[[], Coroutine[Any, Any, str]] | None = None
    ) -> DebussyTUI:
        """Create and return the Textual app with controller.

        Creates the app, then creates an OrchestrationController and
        injects it into the app for state management.

        Args:
            orchestration_coro: Async function that runs the orchestration

        Returns:
            The DebussyTUI app instance
        """
        self._app = DebussyTUI(orchestration_coro=orchestration_coro)
        self._controller = OrchestrationController(self._app)
        self._app.set_controller(self._controller)
        return self._app

    def run_with_orchestration(
        self, orchestration_coro: Callable[[], Coroutine[Any, Any, str]]
    ) -> None:
        """Run the TUI with orchestration.

        This is the main entry point - it blocks until the app exits.

        Args:
            orchestration_coro: Async function that runs the orchestration
        """
        app = self.create_app(orchestration_coro)
        app.run()

    # Proxy methods for when app is running
    def start(self, plan_name: str, total_phases: int) -> None:
        """Start the UI context."""
        if self._app:
            self._app.start(plan_name, total_phases)

    def stop(self) -> None:
        """Stop the UI."""
        if self._app:
            self._app.stop()

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase."""
        if self._app:
            self._app.set_phase(phase, index)

    def set_state(self, state: UIState) -> None:
        """Update the UI state."""
        if self._app:
            self._app.set_state(state)

    def log(self, message: str) -> None:
        """Add a log message."""
        if self._app:
            self._app.log_message(message)

    def log_message(self, message: str) -> None:
        """Add a log message (alias for log)."""
        if self._app:
            self._app.log_message(message)

    def log_raw(self, message: str) -> None:
        """Add a raw log message."""
        if self._app:
            self._app.log_message_raw(message)

    def get_pending_action(self) -> UserAction:
        """Get pending user action."""
        if self._app:
            return self._app.get_pending_action()
        return UserAction.NONE

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging."""
        if self._app:
            return self._app.toggle_verbose()
        return True

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show status popup."""
        if self._app:
            self._app.show_status_popup(details)

    def confirm(self, message: str) -> bool:
        """Ask for confirmation."""
        if self._app:
            return self._app.confirm(message)
        return True

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics."""
        if self._app:
            self._app.update_token_stats(
                input_tokens, output_tokens, cost_usd, context_tokens, context_window
            )

    def set_active_agent(self, agent: str) -> None:
        """Update the active agent display."""
        if self._app:
            self._app.set_active_agent(agent)
