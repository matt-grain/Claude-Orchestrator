"""JSON stream parser for Claude CLI output."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

logger = logging.getLogger(__name__)


@dataclass
class StreamParserCallbacks:
    """Callbacks for stream parser events.

    All callbacks are optional. If not provided, the parser will
    still parse the stream but won't emit events.
    """

    on_text: Callable[[str, bool], None] | None = None  # (text, newline)
    on_tool_use: Callable[[dict], None] | None = None
    on_tool_result: Callable[[dict, str], None] | None = None
    on_token_stats: Callable[..., None] | None = None  # TokenStats callback
    on_agent_change: Callable[[str], None] | None = None


class JsonStreamParser:
    """Parses Claude's stream-json output format.

    Handles:
    - Assistant text messages
    - Tool use events (Task, Bash, Read, Edit, etc.)
    - Tool results with subagent output extraction
    - Token statistics from usage events
    - Active agent tracking for Task tool
    """

    def __init__(
        self,
        callbacks: StreamParserCallbacks,
        jsonl_file: TextIO | None = None,
        stream_output: bool = True,
    ) -> None:
        """Initialize the parser.

        Args:
            callbacks: Event callbacks for parsed content
            jsonl_file: Optional file to write raw JSON lines
            stream_output: Whether to emit output (default True)
        """
        self._callbacks = callbacks
        self._jsonl_file = jsonl_file
        self._stream_output = stream_output
        self._current_agent = "Debussy"
        self._pending_task_ids: dict[str, str] = {}  # tool_use_id -> agent_type
        self._needs_line_prefix = True
        self._full_text: list[str] = []

    @property
    def current_agent(self) -> str:
        """Get the currently active agent name."""
        return self._current_agent

    @property
    def pending_task_ids(self) -> dict[str, str]:
        """Get the pending task IDs mapping."""
        return self._pending_task_ids

    def parse_line(self, line: str) -> str | None:
        """Parse a single line of JSON stream output.

        Args:
            line: A line of text from Claude's stream-json output

        Returns:
            Text content if this line contained assistant text, None otherwise.
        """
        line = line.strip()
        if not line:
            return None

        # Write raw JSONL to file for debugging (captures everything)
        if self._jsonl_file:
            self._jsonl_file.write(line + "\n")
            self._jsonl_file.flush()

        try:
            event = json.loads(line)
            return self._handle_event(event)
        except json.JSONDecodeError:
            # Not JSON, just return as-is
            if self._stream_output and self._callbacks.on_text:
                self._callbacks.on_text(line, True)
            self._full_text.append(line)
            return line

    def _handle_event(self, event: dict) -> str | None:
        """Handle a parsed JSON event.

        Returns:
            Text content if this event contained assistant text, None otherwise.
        """
        event_type = event.get("type", "")
        text_result: str | None = None

        # Handle assistant text output
        if event_type == "assistant":
            text_result = self._handle_assistant_event(event)

        # Handle content block deltas (streaming chunks)
        elif event_type == "content_block_delta":
            text_result = self._handle_content_block_delta(event)

        # Handle tool results from user messages
        elif event_type == "user":
            self._handle_user_event(event)

        # Handle result event (final) - extract token stats
        elif event_type == "result":
            self._handle_result_event(event)

        return text_result

    def _handle_assistant_event(self, event: dict) -> str | None:
        """Handle assistant message events.

        Returns text if the message contained text content.
        """
        message = event.get("message", {})
        content_list = message.get("content", [])
        text_parts: list[str] = []

        for content in content_list:
            content_type = content.get("type")
            if content_type == "text":
                text = content.get("text", "")
                if text:
                    if self._stream_output and self._callbacks.on_text:
                        self._callbacks.on_text(text, False)
                    text_parts.append(text)
                    self._full_text.append(text)
            elif content_type == "tool_use":
                self._handle_tool_use(content)

        # Extract per-turn usage stats
        self._handle_assistant_usage(message)

        return "".join(text_parts) if text_parts else None

    def _handle_content_block_delta(self, event: dict) -> str | None:
        """Handle content block delta events (streaming chunks)."""
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            if text:
                if self._stream_output and self._callbacks.on_text:
                    self._callbacks.on_text(text, False)
                self._full_text.append(text)
                return text
        return None

    def _handle_user_event(self, event: dict) -> None:
        """Handle user message events (tool results)."""
        message = event.get("message", {})
        content_list = message.get("content", [])
        for content in content_list:
            if content.get("type") == "tool_result":
                self._handle_tool_result(content, event.get("tool_use_result", ""))

    def _handle_assistant_usage(self, message: dict) -> None:
        """Extract per-turn usage stats from assistant message."""
        if not self._callbacks.on_token_stats:
            return

        usage = message.get("usage", {})
        if not usage:
            return

        # Import here to avoid circular dependency
        from debussy.runners.claude import TokenStats

        # Per-turn stats - these are cumulative within the session
        stats = TokenStats(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cost_usd=0.0,  # Cost only available in final result
            context_window=200_000,
        )
        self._callbacks.on_token_stats(stats)

    def _handle_result_event(self, event: dict) -> None:
        """Extract final token stats from the result event (includes cost)."""
        if not self._callbacks.on_token_stats:
            return

        # Import here to avoid circular dependency
        from debussy.runners.claude import TokenStats

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
        self._callbacks.on_token_stats(stats)

    def _handle_tool_use(self, content: dict) -> None:
        """Handle tool_use content blocks."""
        if not self._stream_output:
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
            self._emit_text(f"[{tool_name}: {pattern}]\n")
        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            self._emit_text(f"[TodoWrite: {len(todos)} items]\n")
        elif tool_name == "Task":
            self._display_task_tool(content)
        else:
            self._emit_text(f"[{tool_name}]\n")

        # Notify callback
        if self._callbacks.on_tool_use:
            self._callbacks.on_tool_use(content)

    def _display_file_tool(self, tool_name: str, tool_input: dict) -> None:
        """Display Read/Write/Edit tool use."""
        file_path = tool_input.get("file_path", "")
        filename = file_path.split("/")[-1].split("\\")[-1] if file_path else "?"
        self._emit_text(f"[{tool_name}: {filename}]\n")

    def _display_bash_tool(self, tool_input: dict) -> None:
        """Display Bash tool use with truncated command."""
        command = tool_input.get("command", "")
        if len(command) > 60:
            command = command[:57] + "..."
        self._emit_text(f"[Bash: {command}]\n")

    def _display_task_tool(self, content: dict) -> None:
        """Display Task tool use and track agent change."""
        tool_input = content.get("input", {})
        tool_id = content.get("id", "")
        desc = tool_input.get("description", "")
        subagent_type = tool_input.get("subagent_type", "")
        self._emit_text(f"[Task: {desc}]\n")
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
        if self._callbacks.on_agent_change:
            self._callbacks.on_agent_change(agent)

    def _handle_tool_result(self, content: dict, result_text: str) -> None:
        """Handle tool_result content blocks."""
        tool_use_id = content.get("tool_use_id", "")
        result_content = content.get("content", "")

        # Check if this is a Task tool result
        if tool_use_id in self._pending_task_ids:
            agent_name = self._pending_task_ids.pop(tool_use_id)
            if self._stream_output:
                # Task results can be list format (built-in agents) or string (custom agents)
                if isinstance(result_content, list):
                    self._display_subagent_output(agent_name, result_content)
                elif isinstance(result_content, str) and result_content:
                    self._display_subagent_output_str(agent_name, result_content)
            self._reset_active_agent("Debussy")
            return

        if not self._stream_output:
            return

        # Check for errors
        if content.get("is_error"):
            error_msg = result_text or (result_content if isinstance(result_content, str) else "")
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            self._emit_text(f"  [ERROR: {error_msg}]\n")

        # Notify callback
        if self._callbacks.on_tool_result:
            self._callbacks.on_tool_result(content, result_text)

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
                    self._emit_text(f"[{agent_name}] {stripped}\n")

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
                self._emit_text(f"[{agent_name}] {stripped}\n")

    def _emit_text(self, text: str) -> None:
        """Emit text via callback."""
        if self._callbacks.on_text:
            self._callbacks.on_text(text, False)

    def get_full_text(self) -> str:
        """Get the accumulated full text from the stream."""
        return "".join(self._full_text)

    def reset(self) -> None:
        """Reset parser state for a new stream."""
        self._current_agent = "Debussy"
        self._pending_task_ids.clear()
        self._needs_line_prefix = True
        self._full_text.clear()
