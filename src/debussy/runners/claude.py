"""Claude CLI subprocess runner."""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from debussy.core.models import ComplianceIssue, ExecutionResult, Phase

logger = logging.getLogger(__name__)

# Docker sandbox image name
SANDBOX_IMAGE = "debussy-sandbox:latest"


def _get_docker_command() -> list[str]:
    """Get the docker command prefix, using WSL on Windows if needed."""
    if shutil.which("docker"):
        return ["docker"]
    # On Windows, try docker through WSL
    if platform.system() == "Windows" and shutil.which("wsl"):
        return ["wsl", "docker"]
    return ["docker"]  # Will fail, but gives clear error


def _is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is running."""
    docker_cmd = _get_docker_command()
    # If using WSL, we don't need which() check
    if docker_cmd[0] != "wsl" and not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            [*docker_cmd, "info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _is_sandbox_image_available() -> bool:
    """Check if the debussy-sandbox Docker image is built."""
    try:
        docker_cmd = _get_docker_command()
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


def _normalize_path_for_docker(path: Path, use_wsl: bool = False) -> str:
    """Convert Windows path to Docker-compatible format.

    When use_wsl=False (Docker Desktop native):
        C:\\Projects\\foo -> /c/Projects/foo
    When use_wsl=True (Docker via WSL):
        C:\\Projects\\foo -> /mnt/c/Projects/foo
    """
    if platform.system() == "Windows":
        path_str = str(path.resolve())
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            if use_wsl:
                return f"/mnt/{drive}{rest}"
            return f"/{drive}{rest}"
    return str(path)


# =============================================================================
# PID Registry - Global tracking of spawned Claude processes
# =============================================================================
# This is the safety net to ensure no Claude processes are left orphaned.
# It tracks all PIDs spawned by ClaudeRunner and provides cleanup functions.


class PIDRegistry:
    """Global registry of spawned Claude subprocess PIDs.

    This is a safety mechanism to ensure we can always clean up Claude
    processes, even on unexpected crashes or exits.
    """

    _instance: PIDRegistry | None = None
    _pids: set[int]
    _atexit_registered: bool

    def __new__(cls) -> PIDRegistry:
        """Singleton pattern for global PID tracking."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pids = set()
            cls._instance._atexit_registered = False
        return cls._instance

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


# Global singleton instance
pid_registry = PIDRegistry()

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


class ClaudeRunner:
    """Spawns and monitors Claude CLI sessions."""

    def __init__(
        self,
        project_root: Path,
        timeout: int = 1800,
        claude_command: str = "claude",
        stream_output: bool = True,
        model: str = "haiku",
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
        """Open a log file for the current phase."""
        if self.output_mode in ("file", "both"):
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.log_dir / f"run_{run_id}_phase_{phase_id}.log"
            self._current_log_file = log_path.open("w", encoding="utf-8")
            self._current_log_file.write(f"=== Phase {phase_id} Log ===\n")
            self._current_log_file.write(f"Run ID: {run_id}\n")
            self._current_log_file.write(f"Model: {self.model}\n")
            self._current_log_file.write("=" * 40 + "\n\n")

    def _close_log_file(self) -> None:
        """Close the current log file."""
        if self._current_log_file:
            self._current_log_file.close()
            self._current_log_file = None

    def _build_claude_command(self, prompt: str) -> list[str]:
        """Build Claude CLI command, optionally wrapped in Docker.

        Returns the command list ready for asyncio.create_subprocess_exec().
        """
        base_args = [
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
            "--model",
            self.model,
        ]

        if self._sandbox_mode == "devcontainer":
            # Run Claude inside Docker container
            # On Windows with Git Bash, we must wrap the entire docker command in 'wsl -e sh -c'
            # to prevent MSYS path conversion from mangling Linux paths like /home/claude
            docker_cmd = _get_docker_command()
            use_wsl = docker_cmd[0] == "wsl"
            project_path = _normalize_path_for_docker(self.project_root, use_wsl=use_wsl)

            # Build volume mounts (no // prefix needed when using sh -c wrapper)
            volumes = ["-v", f"{project_path}:/workspace:rw"]

            # Exclude host-specific directories by mounting empty tmpfs over them
            # This prevents Windows .venv, __pycache__, .git from breaking Linux container
            excluded_dirs = [
                ".venv",
                ".git",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ]
            for excluded in excluded_dirs:
                volumes.append(f"--mount type=tmpfs,destination=/workspace/{excluded}")

            # Mount Claude credentials for OAuth authentication
            # Note: mounted as rw because Claude writes to debug/, stats-cache.json, etc.
            claude_config_dir = Path.home() / ".claude"
            if claude_config_dir.exists():
                claude_config_path = _normalize_path_for_docker(claude_config_dir, use_wsl=use_wsl)
                volumes.append(f"-v {claude_config_path}:/home/claude/.claude:rw")

            # Build env vars
            # CRITICAL: Set PATH explicitly to prevent host PATH from overriding container.
            container_path = (
                "/home/claude/.local/bin:/usr/local/sbin:/usr/local/bin"
                ":/usr/sbin:/usr/bin:/sbin:/bin"
            )
            env_vars = [f"-e PATH={container_path}"]
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                env_vars.append(f"-e ANTHROPIC_API_KEY={api_key}")

            # Build the full docker command as a shell string
            # This prevents Git Bash from mangling paths when passed through WSL
            # CRITICAL: The prompt must be shell-quoted as it contains spaces, newlines, etc.
            quoted_prompt = shlex.quote(prompt)
            docker_args = [
                "docker run",
                "--rm",  # Remove container after exit
                # Attach to stdout/stderr to capture output (but NOT stdin to avoid hangs)
                "--attach=stdout",
                "--attach=stderr",
                *volumes,
                "-w /workspace",
                *env_vars,
                "--cap-add=NET_ADMIN",
                "--cap-add=NET_RAW",
                SANDBOX_IMAGE,
                *base_args,
                "-p",
                quoted_prompt,
            ]
            docker_command_str = " ".join(docker_args)

            if use_wsl:
                # Wrap in 'wsl -e sh -c' to avoid Git Bash path mangling
                # Use 'exec' to replace shell with docker so we properly wait for it
                return ["wsl", "-e", "sh", "-c", f"exec {docker_command_str}"]
            else:
                # Direct docker execution (non-Windows or native Docker)
                return ["sh", "-c", f"exec {docker_command_str}"]
        else:
            # Direct execution (no sandbox) - prompt passed directly, no shell quoting
            return [self.claude_command, *base_args, "-p", prompt]

    def validate_sandbox_mode(self) -> None:
        """Validate that sandbox mode can be used. Raises RuntimeError if not."""
        if self._sandbox_mode != "devcontainer":
            return

        if not _is_docker_available():
            raise RuntimeError(
                "sandbox_mode is 'devcontainer' but Docker is not available.\n"
                "Install Docker Desktop or set sandbox_mode: none in config."
            )

        if not _is_sandbox_image_available():
            raise RuntimeError(
                f"Docker image '{SANDBOX_IMAGE}' not found.\nBuild it with: debussy sandbox build"
            )

    def _build_subprocess_kwargs(self) -> dict:
        """Build kwargs for asyncio.create_subprocess_exec."""
        kwargs: dict = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        # For Docker, don't set cwd (container has its own /workspace)
        if self._sandbox_mode != "devcontainer":
            kwargs["cwd"] = self.project_root
        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        return kwargs

    async def _stream_json_reader(
        self,
        stream: asyncio.StreamReader,
        output_list: list[str],
    ) -> str:
        """Read JSON stream and display content in real-time.

        Returns the full text content for the session log.
        """
        full_text: list[str] = []

        while True:
            line = await stream.readline()
            if not line:
                break

            decoded = line.decode("utf-8", errors="replace").strip()
            output_list.append(decoded + "\n")

            if not decoded:
                continue

            try:
                event = json.loads(decoded)
                self._display_stream_event(event, full_text)
            except json.JSONDecodeError:
                # Not JSON, just print as-is
                if self.stream_output:
                    self._write_output(decoded, newline=True)
                full_text.append(decoded)

        return "\n".join(full_text)

    def _display_stream_event(self, event: dict, full_text: list[str]) -> None:
        """Display a streaming event and collect text content."""
        event_type = event.get("type", "")

        # Handle assistant text output
        if event_type == "assistant":
            message = event.get("message", {})
            content_list = message.get("content", [])
            for content in content_list:
                if content.get("type") == "text":
                    text = content.get("text", "")
                    if text and self.stream_output:
                        self._write_output(text)
                    full_text.append(text)
                elif content.get("type") == "tool_use":
                    self._display_tool_use(content)
            # Extract per-turn usage stats
            self._handle_assistant_usage(message)

        # Handle content block deltas (streaming chunks)
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text and self.stream_output:
                    self._write_output(text)
                full_text.append(text)

        # Handle tool results from user messages
        elif event_type == "user":
            message = event.get("message", {})
            content_list = message.get("content", [])
            for content in content_list:
                if content.get("type") == "tool_result":
                    self._display_tool_result(content, event.get("tool_use_result", ""))

        # Handle result event (final) - extract token stats
        elif event_type == "result":
            self._handle_result_event(event)

    def _handle_assistant_usage(self, message: dict) -> None:
        """Extract per-turn usage stats from assistant message."""
        if not self._token_stats_callback:
            return

        usage = message.get("usage", {})
        if not usage:
            return

        # Per-turn stats - these are cumulative within the session
        stats = TokenStats(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cost_usd=0.0,  # Cost only available in final result
            context_window=200_000,
        )
        self._token_stats_callback(stats)

    def _handle_result_event(self, event: dict) -> None:
        """Extract final token stats from the result event (includes cost)."""
        if not self._token_stats_callback:
            return

        usage = event.get("usage", {})
        model_usage = event.get("modelUsage", {})

        # Get context window from model usage (any model will do)
        context_window = 200_000
        for model_data in model_usage.values():
            if "contextWindow" in model_data:
                context_window = model_data["contextWindow"]
                break

        # Final result has session totals and cost
        stats = TokenStats(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cost_usd=event.get("total_cost_usd", 0.0),
            context_window=context_window,
        )
        self._token_stats_callback(stats)

    def _display_tool_use(self, content: dict) -> None:
        """Display tool use with relevant details."""
        if not self.stream_output:
            return

        tool_name = content.get("name", "unknown")
        tool_input = content.get("input", {})

        # Format based on tool type
        if tool_name in ("Read", "Write", "Edit"):
            self._display_file_tool(tool_name, tool_input)
        elif tool_name == "Bash":
            self._display_bash_tool(tool_input)
        elif tool_name in ("Glob", "Grep"):
            pattern = tool_input.get("pattern", "")
            self._write_output(f"[{tool_name}: {pattern}]\n")
        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            self._write_output(f"[TodoWrite: {len(todos)} items]\n")
        elif tool_name == "Task":
            self._display_task_tool(content)
        else:
            self._write_output(f"[{tool_name}]\n")

    def _display_file_tool(self, tool_name: str, tool_input: dict) -> None:
        """Display Read/Write/Edit tool use."""
        file_path = tool_input.get("file_path", "")
        filename = file_path.split("/")[-1].split("\\")[-1] if file_path else "?"
        self._write_output(f"[{tool_name}: {filename}]\n")

    def _display_bash_tool(self, tool_input: dict) -> None:
        """Display Bash tool use with truncated command."""
        command = tool_input.get("command", "")
        if len(command) > 60:
            command = command[:57] + "..."
        self._write_output(f"[Bash: {command}]\n")

    def _display_task_tool(self, content: dict) -> None:
        """Display Task tool use and track agent change."""
        tool_input = content.get("input", {})
        tool_id = content.get("id", "")
        desc = tool_input.get("description", "")
        subagent_type = tool_input.get("subagent_type", "")
        self._write_output(f"[Task: {desc}]\n")
        if subagent_type:
            self._set_active_agent(subagent_type)
            if tool_id:
                self._pending_task_ids[tool_id] = subagent_type

    def _set_active_agent(self, agent: str) -> None:
        """Update the active agent and notify callback."""
        if agent != self._current_agent:
            self._reset_active_agent(agent)

    def _reset_active_agent(self, agent: str) -> None:
        """Force-set the active agent (even if same) and emit prefix on next output."""
        self._current_agent = agent
        self._needs_line_prefix = True
        if self._agent_change_callback:
            self._agent_change_callback(agent)

    def _log_execution_mode(self) -> None:
        """Log the execution mode (local or Docker sandbox) to the output."""
        if self._sandbox_mode == "devcontainer":
            self._write_output(f"[Sandbox: Docker container {SANDBOX_IMAGE}]\n")
        else:
            project_path = str(self.project_root)
            self._write_output(f"[Local: {project_path}]\n")

    def _display_tool_result(self, content: dict, result_text: str) -> None:
        """Display abbreviated tool result."""
        tool_use_id = content.get("tool_use_id", "")
        result_content = content.get("content", "")

        # Check if this is a Task tool result
        if tool_use_id in self._pending_task_ids:
            agent_name = self._pending_task_ids.pop(tool_use_id)
            if self.stream_output:
                # Task results can be list format (built-in agents) or string (custom agents)
                if isinstance(result_content, list):
                    self._display_subagent_output(agent_name, result_content)
                elif isinstance(result_content, str) and result_content:
                    self._display_subagent_output_str(agent_name, result_content)
            self._reset_active_agent("Debussy")
            return

        if not self.stream_output:
            return

        # Check for errors
        if content.get("is_error"):
            error_msg = result_text or (result_content if isinstance(result_content, str) else "")
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            self._write_output(f"  [ERROR: {error_msg}]\n")

    def _display_subagent_output(self, agent_name: str, content_list: list) -> None:
        """Display subagent output from Task tool result.

        Task results have content as list of {type: "text", text: "..."} objects.
        Item 0 is the full subagent reasoning/output.
        Item 1+ may contain metadata (agentId, etc).
        """
        for item in content_list:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue

            text = item.get("text", "")
            if not text:
                continue

            # Skip metadata items (agentId lines)
            if text.startswith("agentId:"):
                continue

            # Display each meaningful line with agent prefix
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped:
                    self._write_output(f"[{agent_name}] {stripped}\n")

    def _display_subagent_output_str(self, agent_name: str, content: str) -> None:
        """Display subagent output from Task tool result (string format).

        Custom agents return content as a plain string, not a list.
        """
        if not content:
            return

        # Skip metadata lines
        if content.startswith("agentId:"):
            return

        # Display each meaningful line with agent prefix
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped:
                self._write_output(f"[{agent_name}] {stripped}\n")

    async def _stream_stderr(
        self,
        stream: asyncio.StreamReader,
        output_list: list[str],
    ) -> None:
        """Read stderr and display with prefix."""
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace")
            output_list.append(decoded)
            if self.stream_output:
                self._write_output(f"[ERR] {decoded}")

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

    async def execute_phase(  # noqa: PLR0915
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
            ExecutionResult with success status and session log
        """
        prompt = custom_prompt or self._build_phase_prompt(phase, with_ltm=self._with_ltm)

        # Reset agent tracking at start of each phase
        self._reset_active_agent("Debussy")
        self._pending_task_ids.clear()

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

            process = await asyncio.create_subprocess_exec(
                cmd[0], *cmd[1:], **self._build_subprocess_kwargs()
            )

            # Register PID for safety cleanup
            pid_registry.register(process.pid)
            logger.debug(f"Started Claude process with PID {process.pid}")

            raw_output: list[str] = []
            stderr_lines: list[str] = []

            try:
                assert process.stdout is not None
                assert process.stderr is not None

                # Stream stdout (JSON) and stderr concurrently
                await asyncio.wait_for(
                    asyncio.gather(
                        self._stream_json_reader(process.stdout, raw_output),
                        self._stream_stderr(process.stderr, stderr_lines),
                    ),
                    timeout=self.timeout,
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
                self._close_log_file()
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

            self._close_log_file()
            return ExecutionResult(
                success=process.returncode == 0,
                session_log=session_log,
                exit_code=process.returncode or 0,
                duration_seconds=time.time() - start_time,
                pid=process.pid,
            )

        except FileNotFoundError:
            self._close_log_file()
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
            self._close_log_file()
            return ExecutionResult(
                success=False,
                session_log=f"Error spawning Claude: {e}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
                pid=process.pid if process else None,
            )

    def _build_phase_prompt(self, phase: Phase, with_ltm: bool = False) -> str:
        """Build the prompt for a phase execution."""

        # Helper to convert Windows paths to forward slashes
        def to_posix(p: Path | None) -> str:
            return str(p).replace("\\", "/") if p else ""

        notes_context = ""
        if phase.notes_input and phase.notes_input.exists():
            notes_input_str = to_posix(phase.notes_input)
            notes_context = f"""
## Previous Phase Notes
Use the Read tool to read context from the previous phase: {notes_input_str}
"""

        required_agents = ""
        if phase.required_agents:
            agents_list = ", ".join(phase.required_agents)
            required_agents = f"""
## Required Agents
You MUST invoke these agents using the Task tool: {agents_list}
"""

        notes_output = ""
        if phase.notes_output:
            notes_output_str = to_posix(phase.notes_output)
            notes_output = f"""
## Notes Output
Use the Write tool to write notes to: {notes_output_str}
"""

        # LTM context recall for non-first phases
        ltm_recall = ""
        if with_ltm and phase.notes_input:
            ltm_recall = f"""
## Recall Previous Learnings
Run `/recall phase:{phase.id}` to retrieve learnings from previous runs of this phase.
"""

        # LTM learnings section - ADD to Process Wrapper steps
        ltm_learnings = ""
        if with_ltm:
            ltm_learnings = f"""
## ADDITIONAL Process Wrapper Step (LTM Enabled)
**IMPORTANT**: Add this step to the Process Wrapper BEFORE signaling completion:

- [ ] **Output `## Learnings` section in your notes file** with insights from this phase:
  - Errors encountered and how you fixed them
  - Project-specific patterns discovered
  - Gate failures and resolutions
  - Tips for future runs

- [ ] **Save each learning** using `/remember`:
  ```
  /remember --priority MEDIUM --tags phase:{phase.id},agent:Debussy "learning content"
  ```

This step is MANDATORY when LTM is enabled. Do not skip it.
"""

        # Build completion steps - vary based on LTM
        if with_ltm:
            completion_steps = f"""
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path (include `## Learnings` section!)
2. Call `/remember` for each learning you documented
3. Signal completion: `/debussy-done {phase.id}`

**Do NOT signal completion until you have saved your learnings with /remember.**

Fallback (if slash commands unavailable):
- `uv run debussy done --phase {phase.id} --status completed`
"""
        else:
            completion_steps = f"""
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path
2. Signal completion: `/debussy-done {phase.id}`

If you encounter a blocker:
- `/debussy-done {phase.id} blocked "reason for blocker"`

Fallback (if slash commands unavailable):
- `uv run debussy done --phase {phase.id} --status completed`
"""

        phase_path_str = to_posix(phase.path)

        return f"""Execute the implementation phase defined in the file: {phase_path_str}

**IMPORTANT: Use the Read tool to read this file path. Do NOT try to execute paths as commands.**

Read the phase plan file and follow the Process Wrapper EXACTLY.
{notes_context}{ltm_recall}
{required_agents}
{notes_output}
{ltm_learnings}
{completion_steps}
## Important

- Follow the template Process Wrapper exactly
- Use the Task tool to invoke required agents (don't do their work yourself)
- Run all pre-validation commands until they pass
- The compliance checker will verify your work - be thorough
- **File paths are for reading with the Read tool, not executing with Bash**
- **Slash commands like /debussy-done use the Skill tool, not Bash**
"""

    def build_remediation_prompt(
        self,
        phase: Phase,
        issues: list[ComplianceIssue],
        with_ltm: bool = False,
    ) -> str:
        """Build a remediation prompt for a failed compliance check."""

        # Helper to convert Windows paths to forward slashes
        def to_posix(p: Path | None) -> str:
            return str(p).replace("\\", "/") if p else ""

        issues_text = "\n".join(
            f"- [{issue.severity.upper()}] {issue.type.value}: {issue.details}" for issue in issues
        )

        notes_output_str = to_posix(phase.notes_output)
        required_actions: list[str] = []
        for issue in issues:
            if issue.type.value == "agent_skipped":
                agent_name = issue.details.split("'")[1]
                required_actions.append(f"- Invoke the {agent_name} agent using Task tool")
            elif issue.type.value == "notes_missing":
                required_actions.append(f"- Write notes to: {notes_output_str}")
            elif issue.type.value == "notes_incomplete":
                required_actions.append("- Complete all required sections in the notes file")
            elif issue.type.value == "gates_failed":
                required_actions.append(f"- Fix failing gate: {issue.details}")
            elif issue.type.value == "step_skipped":
                required_actions.append(f"- Complete step: {issue.details}")

        default_action = "- Review and fix all issues"
        actions_text = "\n".join(required_actions) if required_actions else default_action

        # LTM recall for remediation context
        ltm_section = ""
        if with_ltm:
            ltm_section = f"""
## Recall Previous Attempts (LTM Enabled)
Use the Skill tool to run: /recall phase:{phase.id}
This may include fixes for similar issues encountered before.
"""

        # LTM learnings for remediation
        ltm_learnings = ""
        if with_ltm:
            ltm_learnings = f"""
## Save Remediation Learnings
After fixing the issues, use the Skill tool to save what you learned:
/remember --priority HIGH --tags phase:{phase.id},agent:Debussy,remediation "description of fix"
High priority ensures this learning persists for future remediation attempts.
"""

        phase_path_str = to_posix(phase.path)

        return f"""REMEDIATION SESSION for Phase {phase.id}: {phase.title}

The previous attempt FAILED compliance checks.
{ltm_section}
## Issues Found
{issues_text}

## Required Actions
{actions_text}

## Original Phase Plan
Use the Read tool to read: {phase_path_str}
{ltm_learnings}
## When Complete
Use the Skill tool to signal completion: /debussy-done {phase.id}

Fallback: `uv run debussy done --phase {phase.id} --status completed`

IMPORTANT: This is a remediation session. Follow the template EXACTLY.
All required agents MUST be invoked via the Task tool - do not do their work yourself.
"""
