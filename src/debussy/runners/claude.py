"""Claude CLI subprocess runner."""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import signal
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from debussy.core.models import ComplianceIssue, ExecutionResult, Phase

logger = logging.getLogger(__name__)


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
        model: str = "sonnet",
        output_mode: OutputMode = "terminal",
        log_dir: Path | None = None,
        output_callback: Callable[[str], None] | None = None,
        token_stats_callback: Callable[[TokenStats], None] | None = None,
        agent_change_callback: Callable[[str], None] | None = None,
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
        self._needs_agent_prefix: bool = True  # Emit prefix on next text output
        self._pending_task_ids: set[str] = set()  # Track active Task tool_use_ids

    def _write_output(self, text: str, newline: bool = False) -> None:
        """Write output to terminal/file/callback based on output_mode."""
        # Emit agent prefix if needed (start of new output block)
        prefix = ""
        if self._needs_agent_prefix:
            prefix = f"[{self._current_agent}] "
            self._needs_agent_prefix = False

        output = prefix + text + ("\n" if newline else "")

        # Route to UI callback if available (interactive mode)
        if self._output_callback:
            self._output_callback(prefix + text)
        elif self.output_mode in ("terminal", "both"):
            # Only write to stdout if no callback (non-interactive or YOLO mode)
            sys.stdout.write(output)
            sys.stdout.flush()

        if self.output_mode in ("file", "both") and self._current_log_file:
            self._current_log_file.write(output)
            self._current_log_file.flush()

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
            self._write_output(f"\n[{tool_name}: {pattern}]\n")
        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            self._write_output(f"\n[TodoWrite: {len(todos)} items]\n")
        elif tool_name == "Task":
            self._display_task_tool(content)
        else:
            self._write_output(f"\n[{tool_name}]\n")

    def _display_file_tool(self, tool_name: str, tool_input: dict) -> None:
        """Display Read/Write/Edit tool use."""
        file_path = tool_input.get("file_path", "")
        filename = file_path.split("/")[-1].split("\\")[-1] if file_path else "?"
        self._write_output(f"\n[{tool_name}: {filename}]\n")

    def _display_bash_tool(self, tool_input: dict) -> None:
        """Display Bash tool use with truncated command."""
        command = tool_input.get("command", "")
        if len(command) > 60:
            command = command[:57] + "..."
        self._write_output(f"\n[Bash: {command}]\n")

    def _display_task_tool(self, content: dict) -> None:
        """Display Task tool use and track agent change."""
        tool_input = content.get("input", {})
        tool_id = content.get("id", "")
        desc = tool_input.get("description", "")
        subagent_type = tool_input.get("subagent_type", "")
        self._write_output(f"\n[Task: {desc}]\n")
        if subagent_type:
            self._set_active_agent(subagent_type)
            if tool_id:
                self._pending_task_ids.add(tool_id)

    def _set_active_agent(self, agent: str) -> None:
        """Update the active agent and notify callback."""
        if agent != self._current_agent:
            self._reset_active_agent(agent)

    def _reset_active_agent(self, agent: str) -> None:
        """Force-set the active agent (even if same) and emit prefix on next output."""
        self._current_agent = agent
        self._needs_agent_prefix = True
        if self._agent_change_callback:
            self._agent_change_callback(agent)

    def _display_tool_result(self, content: dict, result_text: str) -> None:
        """Display abbreviated tool result."""
        # Check if this is a Task tool result - reset to Debussy
        tool_use_id = content.get("tool_use_id", "")
        if tool_use_id in self._pending_task_ids:
            self._pending_task_ids.discard(tool_use_id)
            self._reset_active_agent("Debussy")

        if not self.stream_output:
            return

        # Check for errors
        if content.get("is_error"):
            error_msg = result_text or content.get("content", "")
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            self._write_output(f"  [ERROR: {error_msg}]\n")

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
            ExecutionResult with success status and session log
        """
        prompt = custom_prompt or self._build_phase_prompt(phase)

        # Reset agent tracking at start of each phase
        self._reset_active_agent("Debussy")
        self._pending_task_ids.clear()

        # Open log file if using file output
        if run_id:
            self._open_log_file(run_id, phase.id)

        start_time = time.time()
        process: asyncio.subprocess.Process | None = None
        try:
            # On Unix, create new session for process group management
            create_kwargs: dict = {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "cwd": self.project_root,
            }
            if sys.platform != "win32":
                create_kwargs["start_new_session"] = True

            process = await asyncio.create_subprocess_exec(
                self.claude_command,
                "--print",
                "--verbose",
                "--output-format",
                "stream-json",
                "--dangerously-skip-permissions",  # Required for automated workflows
                "--model",
                self.model,
                "-p",
                prompt,
                **create_kwargs,
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
        notes_context = ""
        if phase.notes_input and phase.notes_input.exists():
            notes_context = f"""
## Previous Phase Notes
Read the context from the previous phase: `{phase.notes_input}`
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
            notes_output = f"""
## Notes Output
When complete, write notes to: `{phase.notes_output}`
"""

        # LTM context recall for non-first phases
        ltm_recall = ""
        if with_ltm and phase.notes_input:
            ltm_recall = """
## Recall Previous Context
Run `/recall` to retrieve memories from previous phases before starting.
"""

        # LTM memory instructions
        ltm_remember = ""
        if with_ltm:
            ltm_remember = """
2. Save key decisions: `/remember "Phase {phase_id}: <what you learned>"`"""

        completion_steps = f"""
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path{ltm_remember}
3. Signal completion: `/debussy-done {phase.id}`

If you encounter a blocker:
- `/debussy-done {phase.id} blocked "reason for blocker"`

Fallback (if slash commands unavailable):
- `uv run debussy done --phase {phase.id} --status completed`
"""

        return f"""Execute the implementation phase defined in: `{phase.path}`

Read the phase plan file and follow the Process Wrapper EXACTLY.
{notes_context}{ltm_recall}
{required_agents}
{notes_output}
{completion_steps}
## Important

- Follow the template Process Wrapper exactly
- Use the Task tool to invoke required agents (don't do their work yourself)
- Run all pre-validation commands until they pass
- The compliance checker will verify your work - be thorough
"""

    def build_remediation_prompt(
        self,
        phase: Phase,
        issues: list[ComplianceIssue],
        with_ltm: bool = False,
    ) -> str:
        """Build a remediation prompt for a failed compliance check."""
        issues_text = "\n".join(
            f"- [{issue.severity.upper()}] {issue.type.value}: {issue.details}" for issue in issues
        )

        required_actions: list[str] = []
        for issue in issues:
            if issue.type.value == "agent_skipped":
                agent_name = issue.details.split("'")[1]
                required_actions.append(f"- Invoke the {agent_name} agent using Task tool")
            elif issue.type.value == "notes_missing":
                required_actions.append(f"- Write notes to: {phase.notes_output}")
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
            ltm_section = """
## Recall Previous Attempt
Run `/recall` to see what was tried before and why it failed.
"""

        return f"""REMEDIATION SESSION for Phase {phase.id}: {phase.title}

The previous attempt FAILED compliance checks.
{ltm_section}
## Issues Found
{issues_text}

## Required Actions
{actions_text}

## Original Phase Plan
Read and follow: `{phase.path}`

## When Complete
Signal completion: `/debussy-done {phase.id}`

Fallback: `uv run debussy done --phase {phase.id} --status completed`

IMPORTANT: This is a remediation session. Follow the template EXACTLY.
All required agents MUST be invoked via the Task tool - do not do their work yourself.
"""
