"""Claude CLI subprocess runner."""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TextIO

from debussy.core.models import ComplianceIssue, ExecutionResult, Phase
from debussy.runners.docker_builder import DockerCommandBuilder
from debussy.runners.prompt_builder import build_phase_prompt, build_remediation_prompt
from debussy.runners.streaming import StreamingMixin

if TYPE_CHECKING:
    from debussy.runners.context_estimator import ContextEstimator

from debussy.runners.stream_parser import JsonStreamParser, StreamParserCallbacks
from debussy.utils.docker import (
    get_docker_command,
    is_docker_available,
)

logger = logging.getLogger(__name__)

# Docker sandbox image name
SANDBOX_IMAGE = "debussy-sandbox:latest"


def _is_sandbox_image_available() -> bool:
    """Check if the debussy-sandbox Docker image is built."""
    try:
        docker_cmd = get_docker_command()
        result = subprocess.run(
            [*docker_cmd, "images", "-q", SANDBOX_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return False


# =============================================================================
# PID Registry - Global tracking of spawned Claude processes
# =============================================================================
# This is the safety net to ensure no Claude processes are left orphaned.
# It tracks all PIDs spawned by ClaudeRunner and provides cleanup functions.


class PIDRegistry:
    """Global registry of spawned Claude subprocess PIDs.

    This is a safety mechanism to ensure we can always clean up Claude
    processes, even on unexpected crashes or exits.

    Use get_pid_registry() to obtain the singleton instance.
    """

    def __init__(self) -> None:
        """Initialize the registry. Use get_pid_registry() instead."""
        self._pids: set[int] = set()
        self._atexit_registered: bool = False

    def register(self, pid: int) -> None:
        """Register a PID as spawned by us."""
        self._pids.add(pid)
        self._ensure_atexit_handler()
        logger.debug(f"PID registry: registered {pid}, active: {self._pids}")

    def unregister(self, pid: int) -> None:
        """Unregister a PID (process completed normally)."""
        self._pids.discard(pid)
        logger.debug(f"PID registry: unregistered {pid}, active: {self._pids}")

    def get_active_pids(self) -> set[int]:
        """Get all currently registered PIDs."""
        return self._pids.copy()

    def is_process_alive(self, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            if sys.platform == "win32":
                # Windows: use tasklist to check
                import subprocess

                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return str(pid) in result.stdout
            else:
                # Unix: send signal 0 to check
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False

    def kill_all(self) -> list[int]:
        """Kill all registered processes. Returns list of PIDs that were killed."""
        killed = []
        for pid in list(self._pids):
            if self._kill_pid(pid):
                killed.append(pid)
            self._pids.discard(pid)
        return killed

    def verify_all_dead(self) -> list[int]:
        """Verify all registered PIDs are dead. Returns list of still-alive PIDs."""
        still_alive = []
        for pid in list(self._pids):
            if self.is_process_alive(pid):
                still_alive.append(pid)
            else:
                self._pids.discard(pid)
        return still_alive

    def _kill_pid(self, pid: int) -> bool:
        """Kill a single PID. Returns True if killed, False if already dead."""
        try:
            if sys.platform == "win32":
                # Windows: use taskkill for tree kill
                import subprocess

                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
                return True
            else:
                # Unix: try SIGTERM first, then SIGKILL
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    os.kill(pid, signal.SIGTERM)

                # Give it a moment to die gracefully
                time.sleep(0.5)

                # Force kill if still alive
                if self.is_process_alive(pid):
                    with suppress(ProcessLookupError, OSError):
                        try:
                            os.killpg(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            os.kill(pid, signal.SIGKILL)
                return True
        except (OSError, ProcessLookupError):
            return False

    def _ensure_atexit_handler(self) -> None:
        """Register atexit handler if not already registered."""
        if not self._atexit_registered:
            atexit.register(self._atexit_cleanup)
            self._atexit_registered = True

    def _atexit_cleanup(self) -> None:
        """Last-resort cleanup on Python exit."""
        if self._pids:
            logger.warning(f"atexit: Cleaning up {len(self._pids)} orphaned Claude processes")
            killed = self.kill_all()
            if killed:
                logger.warning(f"atexit: Killed PIDs: {killed}")


# Module-level singleton management
_pid_registry: PIDRegistry | None = None


def get_pid_registry() -> PIDRegistry:
    """Get the global PID registry singleton.

    This is the preferred way to access the registry.
    """
    global _pid_registry  # noqa: PLW0603
    if _pid_registry is None:
        _pid_registry = PIDRegistry()
    return _pid_registry


def reset_pid_registry() -> None:
    """Reset the global PID registry (for testing only).

    WARNING: Only call this in test fixtures, never in production code.
    """
    global _pid_registry  # noqa: PLW0603
    if _pid_registry is not None:
        _pid_registry._pids.clear()
    _pid_registry = None


# Keep backwards-compatible alias (but prefer get_pid_registry())
pid_registry = get_pid_registry()

OutputMode = Literal["terminal", "file", "both"]


@dataclass
class TokenStats:
    """Token usage statistics from a Claude session."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    context_window: int = 200_000

    @property
    def context_tokens(self) -> int:
        """Total tokens contributing to context."""
        return self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens


class ClaudeRunner(StreamingMixin):
    """Spawns and monitors Claude CLI sessions."""

    def __init__(
        self,
        project_root: Path,
        timeout: int = 1800,
        claude_command: str = "claude",
        stream_output: bool = True,
        model: str = "opus",
        output_mode: OutputMode = "terminal",
        log_dir: Path | None = None,
        output_callback: Callable[[str], None] | None = None,
        token_stats_callback: Callable[[TokenStats], None] | None = None,
        agent_change_callback: Callable[[str], None] | None = None,
        with_ltm: bool = False,
        sandbox_mode: Literal["none", "devcontainer"] = "none",
    ) -> None:
        self.project_root = project_root
        self.timeout = timeout
        self.claude_command = claude_command
        self.stream_output = stream_output
        self.model = model
        self.output_mode = output_mode
        self.log_dir = log_dir or (project_root / ".debussy" / "logs")
        self._current_log_file: TextIO | None = None
        self._current_jsonl_file: TextIO | None = None  # Raw JSONL stream for debugging
        self._output_callback = output_callback
        self._token_stats_callback = token_stats_callback
        self._agent_change_callback = agent_change_callback
        self._current_agent: str = "Debussy"  # Track current active agent
        self._needs_line_prefix: bool = True  # Emit prefix on next line output
        # Track active Task tool_use_ids -> subagent_type for subagent output display
        self._pending_task_ids: dict[str, str] = {}
        self._with_ltm = with_ltm  # Enable LTM learnings in prompts
        self._sandbox_mode = sandbox_mode  # Docker sandbox mode
        # Sandbox log file for Windows terminal buffering workaround
        self._sandbox_log_file: TextIO | None = None
        self._sandbox_log_path: Path | None = None
        # Track current phase for completion banner
        self._current_phase_id: str | None = None
        self._phase_start_time: float | None = None
        # Stream parser for JSON output
        self._parser: JsonStreamParser | None = None
        # Context estimator for monitoring token usage
        self._context_estimator: ContextEstimator | None = None
        self._restart_callback: Callable[[], None] | None = None
        # Tool use callback for checkpoint progress tracking
        self._tool_use_callback: Callable[[dict], None] | None = None
        # Graceful stop flag for context restart
        self._should_stop: bool = False

    def _create_parser(self) -> JsonStreamParser:
        """Create a configured stream parser for the current session."""
        return JsonStreamParser(
            callbacks=StreamParserCallbacks(
                on_text=self._on_parser_text,
                on_tool_use=self._tool_use_callback,  # For checkpoint progress tracking
                on_tool_result=None,  # Result display is handled internally by parser
                on_token_stats=self._token_stats_callback,
                on_agent_change=self._on_parser_agent_change,
            ),
            jsonl_file=self._current_jsonl_file,
            stream_output=self.stream_output,
        )

    def _on_parser_text(self, text: str, newline: bool) -> None:
        """Handle text output from parser."""
        self._write_output(text, newline=newline)

    def _on_parser_agent_change(self, agent: str) -> None:
        """Handle agent change from parser."""
        self._current_agent = agent
        self._needs_line_prefix = True
        if self._agent_change_callback:
            self._agent_change_callback(agent)

    def set_callbacks(
        self,
        output: Callable[[str], None] | None = None,
        token_stats: Callable[[TokenStats], None] | None = None,
        agent_change: Callable[[str], None] | None = None,
        tool_use: Callable[[dict], None] | None = None,
    ) -> None:
        """Configure runtime callbacks for UI integration.

        Args:
            output: Called with each line of Claude output
            token_stats: Called with token usage statistics
            agent_change: Called when active agent changes (Task tool)
            tool_use: Called when a tool is invoked (receives tool_use content block)
        """
        if output is not None:
            self._output_callback = output
        if token_stats is not None:
            self._token_stats_callback = token_stats
        if agent_change is not None:
            self._agent_change_callback = agent_change
        if tool_use is not None:
            self._tool_use_callback = tool_use

    def set_context_estimator(self, estimator: ContextEstimator) -> None:
        """Configure context estimator for token usage monitoring.

        Args:
            estimator: The ContextEstimator instance to use
        """
        self._context_estimator = estimator

    def set_restart_callback(self, callback: Callable[[], None]) -> None:
        """Configure callback to invoke when context threshold is reached.

        Args:
            callback: Called when should_restart() returns True
        """
        self._restart_callback = callback

    def request_stop(self) -> None:
        """Request graceful termination of the current session.

        Sets a flag that causes the stream processing loop to terminate
        after completing the current tool operation. This allows for
        a clean restart when context limits are reached.
        """
        logger.info("Graceful stop requested")
        self._should_stop = True

    def is_stop_requested(self) -> bool:
        """Check if graceful stop was requested.

        Returns:
            True if stop was requested via request_stop()
        """
        return self._should_stop

    def _open_sandbox_log(self) -> None:
        """Open temp file for sandbox output buffering (Windows workaround)."""
        if self._sandbox_mode == "devcontainer":
            # Create temp file in .debussy/logs for easy access
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self._sandbox_log_path = self.log_dir / "sandbox_stream.log"
            self._sandbox_log_file = self._sandbox_log_path.open("w", encoding="utf-8")

    def _close_sandbox_log(self) -> None:
        """Close sandbox log file."""
        if self._sandbox_log_file:
            self._sandbox_log_file.close()
            self._sandbox_log_file = None

    def _display_sandbox_log(self) -> None:
        """Display buffered sandbox output (Windows terminal workaround).

        On Windows, asyncio subprocess output doesn't display in real-time in some terminals.
        This reads the buffered log file and displays it directly to stdout (bypassing callback).
        """
        if not self._sandbox_log_path or not self._sandbox_log_path.exists():
            return

        # Read and display the buffered output
        content = self._sandbox_log_path.read_text(encoding="utf-8")
        if content:
            # Write directly to stdout, bypassing the callback which may have buffering issues
            print("\n--- Sandbox Output (buffered) ---", flush=True)
            for line in content.splitlines():
                print(line, flush=True)
            print("--- End Sandbox Output ---\n", flush=True)

    def _write_output(self, text: str, newline: bool = False) -> None:
        """Write output to terminal/file/callback based on output_mode."""
        # When we're inside a Task (subagent), prefix each NEW line
        # This ensures streaming output from subagents is clearly attributed
        in_subagent = self._current_agent != "Debussy"

        if in_subagent and "\n" in text:
            # Split by newlines and prefix each NEW line for subagent output
            lines = text.split("\n")
            for i, line in enumerate(lines):
                is_last = i == len(lines) - 1
                has_content = bool(line)
                ends_with_newline = not is_last  # All but last have implicit newline

                if has_content:
                    # Prefix this line only if we're at start of a new line
                    if self._needs_line_prefix:
                        self._write_single_line(f"[{self._current_agent}] {line}")
                    else:
                        self._write_single_line(line)
                    # After content, newline determines if next needs prefix
                    self._needs_line_prefix = ends_with_newline

                if ends_with_newline:
                    self._write_single_line("", newline=True)
                    self._needs_line_prefix = True

            if newline and not text.endswith("\n"):
                self._write_single_line("", newline=True)
                self._needs_line_prefix = True
        else:
            # No newlines in text - add prefix if needed, continue current line
            prefix = ""
            if self._needs_line_prefix:
                prefix = f"[{self._current_agent}] "
                self._needs_line_prefix = False

            self._write_single_line(prefix + text, newline=newline)
            if newline:
                self._needs_line_prefix = True

    def _write_single_line(self, text: str, newline: bool = False) -> None:
        """Write a single line to output destinations."""
        output = text + ("\n" if newline else "")

        # Route to UI callback if available (interactive mode)
        if self._output_callback:
            self._output_callback(text)
        elif self.output_mode in ("terminal", "both"):
            # Only write to stdout if no callback (non-interactive or YOLO mode)
            sys.stdout.write(output)
            sys.stdout.flush()

        if self.output_mode in ("file", "both") and self._current_log_file:
            self._current_log_file.write(output)
            self._current_log_file.flush()

        # For sandbox mode on Windows, also buffer to temp file for deferred display
        if self._sandbox_mode == "devcontainer" and self._sandbox_log_file:
            self._sandbox_log_file.write(output)
            self._sandbox_log_file.flush()

    def _open_log_file(self, run_id: str, phase_id: str) -> None:
        """Open log files for the current phase.

        Creates two files:
        - run_{run_id}_phase_{phase_id}.log - Human-readable formatted output
        - run_{run_id}_phase_{phase_id}.jsonl - Raw JSONL stream (for debugging)

        If files already exist (from a previous attempt), appends with a separator
        to preserve logs from all attempts.
        """
        # Track phase info for completion banner
        self._current_phase_id = phase_id
        self._phase_start_time = time.time()

        if self.output_mode in ("file", "both"):
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # Human-readable log
            log_path = self.log_dir / f"run_{run_id}_phase_{phase_id}.log"
            is_retry = log_path.exists()

            # Use append mode if file exists (preserves logs from previous attempts)
            mode = "a" if is_retry else "w"
            self._current_log_file = log_path.open(mode, encoding="utf-8")

            if is_retry:
                # Add separator for retry attempt
                self._current_log_file.write("\n" + "=" * 60 + "\n")
                self._current_log_file.write("=== RETRY ATTEMPT ===\n")
                self._current_log_file.write("=" * 60 + "\n\n")

            self._current_log_file.write(f"=== Phase {phase_id} Log ===\n")
            self._current_log_file.write(f"Run ID: {run_id}\n")
            self._current_log_file.write(f"Model: {self.model}\n")
            self._current_log_file.write("=" * 40 + "\n\n")

            # Raw JSONL log (for debugging when human-readable is incomplete)
            # Always append for JSONL to preserve all event data
            jsonl_path = self.log_dir / f"run_{run_id}_phase_{phase_id}.jsonl"
            jsonl_mode = "a" if jsonl_path.exists() else "w"
            self._current_jsonl_file = jsonl_path.open(jsonl_mode, encoding="utf-8")

    def _write_completion_banner(self, success: bool, duration: float | None = None) -> None:
        """Write phase completion banner to log file."""
        if not self._current_log_file:
            return

        phase_id = self._current_phase_id or "?"
        if duration is None and self._phase_start_time:
            duration = time.time() - self._phase_start_time

        status = "COMPLETED" if success else "FAILED"
        duration_str = f"{duration:.1f}s" if duration else "?"

        banner = f"""
{"=" * 60}
{"✓" if success else "✗"} PHASE {phase_id} {status}
  Duration: {duration_str}
{"=" * 60}
"""
        self._current_log_file.write(banner)
        self._current_log_file.flush()

    def _close_log_file(self, success: bool | None = None) -> None:
        """Close both log files (human-readable and JSONL).

        Args:
            success: If provided, writes a completion banner before closing.
        """
        if self._current_log_file:
            if success is not None:
                self._write_completion_banner(success)
            self._current_log_file.close()
            self._current_log_file = None
        if self._current_jsonl_file:
            self._current_jsonl_file.close()
            self._current_jsonl_file = None
        # Reset phase tracking
        self._current_phase_id = None
        self._phase_start_time = None

    def _build_claude_command(self, prompt: str) -> list[str]:
        """Build Claude CLI command, optionally wrapped in Docker.

        Returns the command list ready for asyncio.create_subprocess_exec().
        """
        if self._sandbox_mode == "devcontainer":
            # Use DockerCommandBuilder for sandbox mode
            builder = DockerCommandBuilder(
                project_root=self.project_root,
                model=self.model,
            )
            return builder.build_command(prompt)
        else:
            # Direct execution (no sandbox) - prompt passed directly, no shell quoting
            base_args = [
                "--print",
                "--verbose",
                "--output-format",
                "stream-json",
                "--dangerously-skip-permissions",
                "--model",
                self.model,
            ]
            return [self.claude_command, *base_args, "-p", prompt]

    def validate_sandbox_mode(self) -> None:
        """Validate that sandbox mode can be used. Raises RuntimeError if not."""
        if self._sandbox_mode != "devcontainer":
            return

        if not is_docker_available():
            raise RuntimeError("sandbox_mode is 'devcontainer' but Docker is not available.\nInstall Docker Desktop or set sandbox_mode: none in config.")

        if not _is_sandbox_image_available():
            raise RuntimeError(f"Docker image '{SANDBOX_IMAGE}' not found.\nBuild it with: debussy sandbox build")

    def _build_subprocess_kwargs(self) -> dict:
        """Build kwargs for asyncio.create_subprocess_exec."""
        # Increase line limit from default 64KB to 2MB to handle large tool results
        # (e.g., Claude reading files that get base64 encoded in JSON)
        line_limit = 2 * 1024 * 1024  # 2MB
        kwargs: dict = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "limit": line_limit,
        }
        # For Docker, don't set cwd (container has its own /workspace)
        if self._sandbox_mode != "devcontainer":
            kwargs["cwd"] = self.project_root
        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        return kwargs

    def _log_execution_mode(self) -> None:
        """Log the execution mode (local or Docker sandbox) to the output."""
        if self._sandbox_mode == "devcontainer":
            self._write_output(f"[Sandbox: Docker container {SANDBOX_IMAGE}]\n")
        else:
            project_path = str(self.project_root)
            self._write_output(f"[Local: {project_path}]\n")

    async def _kill_process_tree(self, process: asyncio.subprocess.Process) -> None:
        """Kill process and all its descendants (grandchildren, etc.).

        This is critical for cleanup because Claude may spawn subprocesses
        (Task tool agents, shell commands) that would otherwise be orphaned.
        """
        if process.returncode is not None:
            return  # Already dead

        pid = process.pid
        logger.debug(f"Killing process tree for PID {pid}")

        try:
            if sys.platform == "win32":
                # Windows: taskkill /T kills the entire process tree
                import subprocess as sp

                sp.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                # Unix: try to kill the process group
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    # No process group, kill individual process
                    os.kill(pid, signal.SIGTERM)

                # Give it time to exit gracefully
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except TimeoutError:
                    # Force kill if still alive
                    with suppress(ProcessLookupError, OSError):
                        try:
                            os.killpg(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            # Process already dead or inaccessible
            pass

        # Final wait to ensure cleanup
        with suppress(Exception):
            await process.wait()

    async def execute_phase(
        self,
        phase: Phase,
        custom_prompt: str | None = None,
        run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute a phase using Claude CLI.

        Args:
            phase: The phase to execute
            custom_prompt: Optional custom prompt (for remediation sessions)
            run_id: Optional run ID for log file naming

        Returns:
            ExecutionResult with success status and session log.
            If stop was requested (context limit), success=False and
            session_log starts with "CONTEXT_LIMIT_RESTART".
        """
        prompt = custom_prompt or self._build_phase_prompt(phase, with_ltm=self._with_ltm)

        # Reset agent tracking and stop flag at start of each phase
        self._reset_active_agent("Debussy")
        self._pending_task_ids.clear()
        self._should_stop = False

        # Reset context estimator for fresh session
        if self._context_estimator:
            self._context_estimator.reset()
            self._context_estimator.add_prompt(prompt)

        # Open log file if using file output
        if run_id:
            self._open_log_file(run_id, phase.id)

        # Open sandbox log for Windows buffering workaround
        self._open_sandbox_log()

        start_time = time.time()
        process: asyncio.subprocess.Process | None = None
        try:
            cmd = self._build_claude_command(prompt)
            logger.debug(f"Running command: {' '.join(cmd[:10])}...")

            # Show execution mode in logs
            self._log_execution_mode()

            process = await asyncio.create_subprocess_exec(cmd[0], *cmd[1:], **self._build_subprocess_kwargs())

            # Register PID for safety cleanup
            pid_registry.register(process.pid)
            logger.debug(f"Started Claude process with PID {process.pid}")

            raw_output: list[str] = []
            stderr_lines: list[str] = []
            was_stopped = False

            try:
                if process.stdout is None or process.stderr is None:
                    raise RuntimeError("Subprocess streams not initialized. This is a bug - please report it.")

                # Stream stdout (JSON) and stderr concurrently
                # Note: _stream_json_reader returns (text, was_stopped) tuple
                results = await asyncio.wait_for(
                    asyncio.gather(
                        self._stream_json_reader(process.stdout, raw_output),
                        self._stream_stderr(process.stderr, stderr_lines),
                    ),
                    timeout=self.timeout,
                )
                # Extract was_stopped from the tuple result
                _, was_stopped = results[0]  # First result is from _stream_json_reader

                if was_stopped:
                    # Graceful stop requested - kill process and return special result
                    logger.info(f"Graceful stop: killing process {process.pid}")
                    await self._kill_process_tree(process)
                    pid_registry.unregister(process.pid)
                    self._close_sandbox_log()
                    self._display_sandbox_log()

                    session_log = "".join(raw_output)
                    if stderr_lines:
                        session_log += f"\n\nSTDERR:\n{''.join(stderr_lines)}"

                    # Use special marker for context limit restart
                    self._close_log_file(success=False)
                    return ExecutionResult(
                        success=False,
                        session_log=f"CONTEXT_LIMIT_RESTART\n{session_log}",
                        exit_code=-2,  # Special exit code for context restart
                        duration_seconds=time.time() - start_time,
                        pid=process.pid,
                    )

                await process.wait()
            except TimeoutError:
                logger.warning(f"Process {process.pid} timed out, killing process tree")
                await self._kill_process_tree(process)
                pid_registry.unregister(process.pid)
                self._close_sandbox_log()
                self._display_sandbox_log()  # Show partial output on timeout
                return ExecutionResult(
                    success=False,
                    session_log=f"TIMEOUT after {self.timeout} seconds",
                    exit_code=-1,
                    duration_seconds=time.time() - start_time,
                    pid=process.pid,
                )
            except asyncio.CancelledError:
                # User cancelled (e.g., quit from TUI) - kill subprocess and re-raise
                logger.info(f"Cancellation requested, killing process tree for PID {process.pid}")
                await self._kill_process_tree(process)
                pid_registry.unregister(process.pid)
                self._close_sandbox_log()
                self._close_log_file(success=False)  # User cancelled = failed
                raise

            # Process completed normally - unregister from safety registry
            pid_registry.unregister(process.pid)

            # Use raw JSON output for session log (compliance checker can parse it)
            session_log = "".join(raw_output)
            if stderr_lines:
                session_log += f"\n\nSTDERR:\n{''.join(stderr_lines)}"

            if self.stream_output:
                self._write_output("\n")  # Newline after streaming output

            # Display buffered sandbox output for Windows terminal workaround
            self._close_sandbox_log()
            self._display_sandbox_log()

            phase_success = process.returncode == 0
            self._close_log_file(success=phase_success)
            return ExecutionResult(
                success=phase_success,
                session_log=session_log,
                exit_code=process.returncode or 0,
                duration_seconds=time.time() - start_time,
                pid=process.pid,
            )

        except FileNotFoundError:
            self._close_log_file(success=False)
            return ExecutionResult(
                success=False,
                session_log=f"Claude CLI not found: {self.claude_command}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
                pid=None,
            )
        except Exception as e:
            # Ensure cleanup even on unexpected exceptions
            if process is not None and process.returncode is None:
                logger.warning(f"Exception during execution, cleaning up PID {process.pid}")
                await self._kill_process_tree(process)
                pid_registry.unregister(process.pid)
            self._close_log_file(success=False)
            return ExecutionResult(
                success=False,
                session_log=f"Error spawning Claude: {e}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
                pid=process.pid if process else None,
            )

    def _build_phase_prompt(self, phase: Phase, with_ltm: bool = False) -> str:
        """Build the prompt for a phase execution.

        Delegates to prompt_builder.build_phase_prompt.
        """
        return build_phase_prompt(phase, with_ltm=with_ltm)

    def build_remediation_prompt(
        self,
        phase: Phase,
        issues: list[ComplianceIssue],
        with_ltm: bool = False,
    ) -> str:
        """Build a remediation prompt for a failed compliance check.

        Delegates to prompt_builder.build_remediation_prompt.
        """
        return build_remediation_prompt(phase, issues, with_ltm=with_ltm)
