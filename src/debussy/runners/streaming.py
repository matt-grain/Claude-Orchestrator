"""Streaming I/O mixin for ClaudeRunner.

Provides all methods related to reading subprocess output streams
and displaying tool-use/result events in real-time.

ClaudeRunner inherits from StreamingMixin to keep the streaming
logic in a separate, focused module.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class StreamingMixin:
    """Mixin providing stream-reading and event-display methods.

    Expects the host class to define the following attributes:
    - stream_output: bool
    - _should_stop: bool
    - _parser: JsonStreamParser | None
    - _current_agent: str
    - _needs_line_prefix: bool
    - _pending_task_ids: dict[str, str]
    - _token_stats_callback: Callable | None
    - _agent_change_callback: Callable | None
    - _context_estimator: ContextEstimator | None
    - _restart_callback: Callable | None
    - _create_parser() -> JsonStreamParser
    - _write_output(text, newline) -> None

    These are all defined in ClaudeRunner.__init__.
    """

    # ---------------------------------------------------------------------------
    # Active stream reading
    # ---------------------------------------------------------------------------

    async def _stream_json_reader(
        self,
        stream: asyncio.StreamReader,
        output_list: list[str],
    ) -> tuple[str, bool]:
        """Read JSON stream and display content in real-time.

        Returns:
            Tuple of (full_text_content, was_stopped)
            - full_text_content: The session log text
            - was_stopped: True if graceful stop was triggered
        """
        # Create parser for this session
        self._parser = self._create_parser()  # type: ignore[attr-defined]
        was_stopped = False

        while True:
            # Check for graceful stop request
            if self._should_stop:  # type: ignore[attr-defined]
                logger.info("Graceful stop: terminating stream read")
                was_stopped = True
                break

            line = await stream.readline()
            if not line:
                break

            decoded = line.decode("utf-8", errors="replace").strip()
            output_list.append(decoded + "\n")

            if not decoded:
                continue

            # Parser handles JSON parsing and emits callbacks
            self._parser.parse_line(decoded)  # type: ignore[union-attr]

        return self._parser.get_full_text(), was_stopped  # type: ignore[union-attr]

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
            if self.stream_output:  # type: ignore[attr-defined]
                self._write_output(f"[ERR] {decoded}")  # type: ignore[attr-defined]

    # ---------------------------------------------------------------------------
    # Legacy event-display methods (used directly by unit tests)
    # These mirror the logic in JsonStreamParser but operate on ClaudeRunner state.
    # ---------------------------------------------------------------------------

    def _display_stream_event(self, event: dict, full_text: list[str]) -> None:
        """Display a streaming event and collect text content."""
        from debussy.runners.claude import TokenStats

        event_type = event.get("type", "")

        # Handle assistant text output
        if event_type == "assistant":
            message = event.get("message", {})
            content_list = message.get("content", [])
            for content in content_list:
                if content.get("type") == "text":
                    text = content.get("text", "")
                    if text and self.stream_output:  # type: ignore[attr-defined]
                        self._write_output(text)  # type: ignore[attr-defined]
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
                if text and self.stream_output:  # type: ignore[attr-defined]
                    self._write_output(text)  # type: ignore[attr-defined]
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

        # Suppress unused import warning: TokenStats is imported for _handle_* callers
        _ = TokenStats

    def _handle_assistant_usage(self, message: dict) -> None:
        """Extract per-turn usage stats from assistant message."""
        from debussy.runners.claude import TokenStats

        if not self._token_stats_callback:  # type: ignore[attr-defined]
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
        self._token_stats_callback(stats)  # type: ignore[attr-defined]

    def _handle_result_event(self, event: dict) -> None:
        """Extract final token stats from the result event (includes cost)."""
        from debussy.runners.claude import TokenStats

        if not self._token_stats_callback:  # type: ignore[attr-defined]
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
        self._token_stats_callback(stats)  # type: ignore[attr-defined]

    def _display_tool_use(self, content: dict) -> None:
        """Display tool use with relevant details."""
        if not self.stream_output:  # type: ignore[attr-defined]
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
            self._write_output(f"[{tool_name}: {pattern}]\n")  # type: ignore[attr-defined]
        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            self._write_output(f"[TodoWrite: {len(todos)} items]\n")  # type: ignore[attr-defined]
        elif tool_name == "Task":
            self._display_task_tool(content)
        else:
            self._write_output(f"[{tool_name}]\n")  # type: ignore[attr-defined]

    def _display_file_tool(self, tool_name: str, tool_input: dict) -> None:
        """Display Read/Write/Edit tool use."""
        file_path = tool_input.get("file_path", "")
        filename = file_path.split("/")[-1].split("\\")[-1] if file_path else "?"
        self._write_output(f"[{tool_name}: {filename}]\n")  # type: ignore[attr-defined]

    def _display_bash_tool(self, tool_input: dict) -> None:
        """Display Bash tool use with truncated command."""
        command = tool_input.get("command", "")
        if len(command) > 60:
            command = command[:57] + "..."
        self._write_output(f"[Bash: {command}]\n")  # type: ignore[attr-defined]

    def _display_task_tool(self, content: dict) -> None:
        """Display Task tool use and track agent change."""
        tool_input = content.get("input", {})
        tool_id = content.get("id", "")
        desc = tool_input.get("description", "")
        subagent_type = tool_input.get("subagent_type", "")
        self._write_output(f"[Task: {desc}]\n")  # type: ignore[attr-defined]
        if subagent_type:
            self._set_active_agent(subagent_type)
            if tool_id:
                self._pending_task_ids[tool_id] = subagent_type  # type: ignore[attr-defined]

    def _set_active_agent(self, agent: str) -> None:
        """Update the active agent and notify callback."""
        if agent != self._current_agent:  # type: ignore[attr-defined]
            self._reset_active_agent(agent)

    def _reset_active_agent(self, agent: str) -> None:
        """Force-set the active agent (even if same) and emit prefix on next output."""
        self._current_agent = agent  # type: ignore[attr-defined]
        self._needs_line_prefix = True  # type: ignore[attr-defined]
        if self._agent_change_callback:  # type: ignore[attr-defined]
            self._agent_change_callback(agent)  # type: ignore[attr-defined]

    def _display_tool_result(self, content: dict, result_text: str) -> None:
        """Display abbreviated tool result."""
        tool_use_id = content.get("tool_use_id", "")
        result_content = content.get("content", "")
        tool_name = content.get("tool_name", "")

        # Track tool output with context estimator
        if self._context_estimator and result_text:  # type: ignore[attr-defined]
            if tool_name == "Read":
                # Track file content reads separately
                self._context_estimator.add_file_read(result_text)  # type: ignore[attr-defined]
            else:
                # Track all other tool outputs
                self._context_estimator.add_tool_output(result_text)  # type: ignore[attr-defined]

            # Check if we should restart
            if self._context_estimator.should_restart() and self._restart_callback:  # type: ignore[attr-defined]
                self._restart_callback()  # type: ignore[attr-defined]

        # Check if this is a Task tool result
        if tool_use_id in self._pending_task_ids:  # type: ignore[attr-defined]
            agent_name = self._pending_task_ids.pop(tool_use_id)  # type: ignore[attr-defined]
            if self.stream_output:  # type: ignore[attr-defined]
                # Task results can be list format (built-in agents) or string (custom agents)
                if isinstance(result_content, list):
                    self._display_subagent_output(agent_name, result_content)
                elif isinstance(result_content, str) and result_content:
                    self._display_subagent_output_str(agent_name, result_content)
            self._reset_active_agent("Debussy")
            return

        if not self.stream_output:  # type: ignore[attr-defined]
            return

        # Check for errors
        if content.get("is_error"):
            error_msg = result_text or (result_content if isinstance(result_content, str) else "")
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            self._write_output(f"  [ERROR: {error_msg}]\n")  # type: ignore[attr-defined]

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
                    self._write_output(f"[{agent_name}] {stripped}\n")  # type: ignore[attr-defined]

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
                self._write_output(f"[{agent_name}] {stripped}\n")  # type: ignore[attr-defined]
