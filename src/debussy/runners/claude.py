"""Claude CLI subprocess runner."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Literal, TextIO

from debussy.core.models import ComplianceIssue, ExecutionResult, Phase

OutputMode = Literal["terminal", "file", "both"]


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
    ) -> None:
        self.project_root = project_root
        self.timeout = timeout
        self.claude_command = claude_command
        self.stream_output = stream_output
        self.model = model
        self.output_mode = output_mode
        self.log_dir = log_dir or (project_root / ".debussy" / "logs")
        self._current_log_file: TextIO | None = None

    def _write_output(self, text: str, newline: bool = False) -> None:
        """Write output to terminal and/or file based on output_mode."""
        output = text + ("\n" if newline else "")

        if self.output_mode in ("terminal", "both"):
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

    def _display_tool_use(self, content: dict) -> None:
        """Display tool use with relevant details."""
        if not self.stream_output:
            return

        tool_name = content.get("name", "unknown")
        tool_input = content.get("input", {})

        # Format based on tool type
        if tool_name in ("Read", "Write", "Edit"):
            file_path = tool_input.get("file_path", "")
            # Show just filename, not full path
            filename = file_path.split("/")[-1].split("\\")[-1] if file_path else "?"
            if tool_name == "Edit":
                self._write_output(f"\n[Edit: {filename}]\n")
            elif tool_name == "Write":
                self._write_output(f"\n[Write: {filename}]\n")
            else:
                self._write_output(f"\n[Read: {filename}]\n")
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            # Truncate long commands
            if len(command) > 60:
                command = command[:57] + "..."
            self._write_output(f"\n[Bash: {command}]\n")
        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            self._write_output(f"\n[Glob: {pattern}]\n")
        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")
            self._write_output(f"\n[Grep: {pattern}]\n")
        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            self._write_output(f"\n[TodoWrite: {len(todos)} items]\n")
        elif tool_name == "Task":
            desc = tool_input.get("description", "")
            self._write_output(f"\n[Task: {desc}]\n")
        else:
            self._write_output(f"\n[{tool_name}]\n")

    def _display_tool_result(self, content: dict, result_text: str) -> None:
        """Display abbreviated tool result."""
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

        # Open log file if using file output
        if run_id:
            self._open_log_file(run_id, phase.id)

        start_time = time.time()
        try:
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
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )

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
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    session_log=f"TIMEOUT after {self.timeout} seconds",
                    exit_code=-1,
                    duration_seconds=time.time() - start_time,
                    pid=process.pid,
                )

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
            self._close_log_file()
            return ExecutionResult(
                success=False,
                session_log=f"Error spawning Claude: {e}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
                pid=None,
            )

    def _build_phase_prompt(self, phase: Phase) -> str:
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

        return f"""Execute the implementation phase defined in: `{phase.path}`

Read the phase plan file and follow the Process Wrapper EXACTLY.
{notes_context}
{required_agents}
{notes_output}
## Completion

When the phase is complete (all tasks done, all gates passing):
1. Write notes to the specified output path
2. Run: `debussy done --phase {phase.id} --report '{{...}}'`

If you encounter a blocker that prevents completion:
- Run: `debussy done --phase {phase.id} --status blocked --reason "description"`

## Important

- Follow the template Process Wrapper exactly
- Use the Task tool to invoke required agents (don't do their work yourself)
- Run all pre-validation commands until they pass
- The debussy will verify your work - be thorough
"""

    def build_remediation_prompt(
        self,
        phase: Phase,
        issues: list[ComplianceIssue],
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

        return f"""REMEDIATION SESSION for Phase {phase.id}: {phase.title}

The previous attempt FAILED compliance checks.

## Issues Found
{issues_text}

## Required Actions
{actions_text}

## Original Phase Plan
Read and follow: `{phase.path}`

## When Complete
Run: `debussy done --phase {phase.id} --report '{{...}}'`

IMPORTANT: This is a remediation session. Follow the template EXACTLY.
All required agents MUST be invoked via the Task tool - do not do their work yourself.
"""
