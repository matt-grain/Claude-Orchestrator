"""Tests for the JsonStreamParser module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from debussy.runners.stream_parser import JsonStreamParser, StreamParserCallbacks


@pytest.fixture
def text_collector() -> tuple[list[str], MagicMock]:
    """Create a text collector callback and return both collected list and mock."""
    collected: list[str] = []

    def on_text(text: str, _newline: bool) -> None:
        collected.append(text)

    mock = MagicMock(side_effect=on_text)
    return collected, mock


@pytest.fixture
def callbacks(text_collector: tuple[list[str], MagicMock]) -> StreamParserCallbacks:
    """Create callbacks with text collector."""
    _, mock = text_collector
    return StreamParserCallbacks(on_text=mock)


@pytest.fixture
def parser(callbacks: StreamParserCallbacks) -> JsonStreamParser:
    """Create a parser with default callbacks."""
    return JsonStreamParser(callbacks=callbacks, stream_output=True)


class TestJsonStreamParserInit:
    """Tests for JsonStreamParser initialization."""

    def test_default_state(self) -> None:
        """Parser initializes with default state."""
        parser = JsonStreamParser(callbacks=StreamParserCallbacks())
        assert parser.current_agent == "Debussy"
        assert parser.pending_task_ids == {}
        assert parser.get_full_text() == ""

    def test_with_jsonl_file(self, tmp_path: Path) -> None:
        """Parser can write to JSONL file."""
        jsonl_path = tmp_path / "test.jsonl"
        with jsonl_path.open("w") as f:
            parser = JsonStreamParser(
                callbacks=StreamParserCallbacks(),
                jsonl_file=f,
            )
            parser.parse_line('{"type": "test"}')

        assert jsonl_path.exists()
        content = jsonl_path.read_text()
        assert '{"type": "test"}' in content


class TestJsonStreamParserParsing:
    """Tests for JSON parsing functionality."""

    def test_parses_assistant_text(self, parser: JsonStreamParser) -> None:
        """Parser extracts text from assistant events."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello world"}]},
            }
        )
        result = parser.parse_line(event)

        assert result == "Hello world"
        assert parser.get_full_text() == "Hello world"

    def test_parses_content_block_delta(self, parser: JsonStreamParser) -> None:
        """Parser extracts text from content_block_delta events."""
        event = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "streaming text"},
            }
        )
        result = parser.parse_line(event)

        assert result == "streaming text"
        assert parser.get_full_text() == "streaming text"

    def test_accumulates_text(self, parser: JsonStreamParser) -> None:
        """Parser accumulates text from multiple events."""
        parser.parse_line(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello "},
                }
            )
        )
        parser.parse_line(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "world"},
                }
            )
        )

        assert parser.get_full_text() == "Hello world"

    def test_handles_empty_lines(self, parser: JsonStreamParser) -> None:
        """Parser handles empty lines gracefully."""
        result = parser.parse_line("")
        assert result is None
        result = parser.parse_line("   ")
        assert result is None

    def test_handles_invalid_json(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:  # noqa: ARG002
        """Parser handles non-JSON lines as plain text."""
        result = parser.parse_line("not json at all")

        # Should return the text and add to full_text
        assert result == "not json at all"
        assert "not json at all" in parser.get_full_text()

    def test_handles_unknown_event_types(self, parser: JsonStreamParser) -> None:
        """Parser ignores unknown event types."""
        event = json.dumps({"type": "unknown_event", "data": "something"})
        result = parser.parse_line(event)
        assert result is None


class TestJsonStreamParserToolUse:
    """Tests for tool use parsing."""

    def test_displays_read_tool(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser displays Read tool use."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/path/to/file.py"},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        collected, _ = text_collector
        assert any("[Read: file.py]" in t for t in collected)

    def test_displays_bash_tool(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser displays Bash tool use."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "pytest tests/"},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        collected, _ = text_collector
        assert any("[Bash: pytest tests/]" in t for t in collected)

    def test_truncates_long_bash_commands(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser truncates long bash commands."""
        long_cmd = "x" * 100
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": long_cmd},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        collected, _ = text_collector
        bash_output = next(t for t in collected if "[Bash:" in t)
        assert "..." in bash_output
        assert len(bash_output) < 100

    def test_displays_glob_tool(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser displays Glob tool use."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Glob",
                            "input": {"pattern": "**/*.py"},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        collected, _ = text_collector
        assert any("[Glob: **/*.py]" in t for t in collected)

    def test_displays_todo_write_tool(self, parser: JsonStreamParser, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser displays TodoWrite tool use."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "TodoWrite",
                            "input": {"todos": [{"content": "a"}, {"content": "b"}]},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        collected, _ = text_collector
        assert any("[TodoWrite: 2 items]" in t for t in collected)


class TestJsonStreamParserTaskTool:
    """Tests for Task tool and agent tracking."""

    def test_tracks_task_agent(self, parser: JsonStreamParser) -> None:
        """Parser tracks active agent from Task tool calls."""
        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task_123",
                            "name": "Task",
                            "input": {
                                "description": "Search codebase",
                                "subagent_type": "Explore",
                            },
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        assert parser.current_agent == "Explore"
        assert "task_123" in parser.pending_task_ids
        assert parser.pending_task_ids["task_123"] == "Explore"

    def test_calls_agent_change_callback(self) -> None:
        """Parser calls agent change callback."""
        agent_changes: list[str] = []
        callbacks = StreamParserCallbacks(
            on_text=lambda _t, _n: None,
            on_agent_change=lambda a: agent_changes.append(a),
        )
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        event = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task_123",
                            "name": "Task",
                            "input": {"subagent_type": "Explore"},
                        }
                    ]
                },
            }
        )
        parser.parse_line(event)

        assert agent_changes == ["Explore"]

    def test_resets_agent_on_task_result(self) -> None:
        """Parser resets agent to Debussy on Task result."""
        agent_changes: list[str] = []
        callbacks = StreamParserCallbacks(
            on_text=lambda _t, _n: None,
            on_agent_change=lambda a: agent_changes.append(a),
        )
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        # Start a Task
        parser.parse_line(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "task_123",
                                "name": "Task",
                                "input": {"subagent_type": "Explore"},
                            }
                        ]
                    },
                }
            )
        )

        # Receive result
        parser.parse_line(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "task_123",
                                "content": [{"type": "text", "text": "Done."}],
                            }
                        ]
                    },
                }
            )
        )

        assert parser.current_agent == "Debussy"
        assert "task_123" not in parser.pending_task_ids
        assert agent_changes == ["Explore", "Debussy"]


class TestJsonStreamParserToolResults:
    """Tests for tool result handling."""

    def test_displays_subagent_output(self, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser formats subagent output from Task results."""
        collected, mock = text_collector
        callbacks = StreamParserCallbacks(on_text=mock)
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        # Register pending task
        parser._pending_task_ids["task_123"] = "Explore"

        # Receive result
        parser.parse_line(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "task_123",
                                "content": [
                                    {"type": "text", "text": "Found 5 files.\nAnalysis done."},
                                    {"type": "text", "text": "agentId: xyz789"},
                                ],
                            }
                        ]
                    },
                }
            )
        )

        # Should display with agent prefix
        assert any("[Explore] Found 5 files." in t for t in collected)
        assert any("[Explore] Analysis done." in t for t in collected)
        # agentId should be skipped
        assert not any("agentId" in t for t in collected)

    def test_displays_string_subagent_output(self, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser handles string format subagent output."""
        collected, mock = text_collector
        callbacks = StreamParserCallbacks(on_text=mock)
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        parser._pending_task_ids["task_123"] = "CustomAgent"

        parser.parse_line(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "task_123",
                                "content": "Line 1\nLine 2",
                            }
                        ]
                    },
                }
            )
        )

        assert any("[CustomAgent] Line 1" in t for t in collected)
        assert any("[CustomAgent] Line 2" in t for t in collected)

    def test_displays_error_results(self, text_collector: tuple[list[str], MagicMock]) -> None:
        """Parser displays error tool results."""
        collected, mock = text_collector
        callbacks = StreamParserCallbacks(on_text=mock)
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        parser.parse_line(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "other_tool",
                                "is_error": True,
                                "content": "Permission denied",
                            }
                        ]
                    },
                    "tool_use_result": "Permission denied",
                }
            )
        )

        assert any("[ERROR:" in t for t in collected)
        assert any("Permission denied" in t for t in collected)


class TestJsonStreamParserTokenStats:
    """Tests for token statistics extraction."""

    def test_extracts_assistant_usage(self) -> None:
        """Parser extracts token stats from assistant messages."""
        stats_received: list[Any] = []

        def on_stats(stats: Any) -> None:
            stats_received.append(stats)

        callbacks = StreamParserCallbacks(
            on_text=lambda _t, _n: None,
            on_token_stats=on_stats,
        )
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        parser.parse_line(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "Hello"}],
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "cache_read_input_tokens": 10,
                            "cache_creation_input_tokens": 5,
                        },
                    },
                }
            )
        )

        assert len(stats_received) == 1
        stats = stats_received[0]
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50
        assert stats.cache_read_tokens == 10
        assert stats.cache_creation_tokens == 5

    def test_extracts_result_usage(self) -> None:
        """Parser extracts final stats from result events."""
        stats_received: list[Any] = []

        def on_stats(stats: Any) -> None:
            stats_received.append(stats)

        callbacks = StreamParserCallbacks(
            on_text=lambda _t, _n: None,
            on_token_stats=on_stats,
        )
        parser = JsonStreamParser(callbacks=callbacks, stream_output=True)

        parser.parse_line(
            json.dumps(
                {
                    "type": "result",
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 500,
                    },
                    "total_cost_usd": 0.05,
                    "modelUsage": {
                        "claude-3-opus": {"contextWindow": 200000},
                    },
                }
            )
        )

        assert len(stats_received) == 1
        stats = stats_received[0]
        assert stats.input_tokens == 1000
        assert stats.output_tokens == 500
        assert stats.cost_usd == 0.05
        assert stats.context_window == 200000


class TestJsonStreamParserReset:
    """Tests for parser reset functionality."""

    def test_reset_clears_state(self, parser: JsonStreamParser) -> None:
        """Parser reset clears all state."""
        # Modify state
        parser._current_agent = "Explore"
        parser._pending_task_ids["task_123"] = "Explore"
        parser._full_text.append("some text")

        parser.reset()

        assert parser.current_agent == "Debussy"
        assert parser.pending_task_ids == {}
        assert parser.get_full_text() == ""


class TestJsonStreamParserStreamOutput:
    """Tests for stream output control."""

    def test_no_output_when_disabled(self) -> None:
        """Parser doesn't emit output when stream_output=False."""
        text_emitted: list[str] = []
        callbacks = StreamParserCallbacks(
            on_text=lambda t, _n: text_emitted.append(t),
        )
        parser = JsonStreamParser(
            callbacks=callbacks,
            stream_output=False,  # Disabled
        )

        # Parse an event with tool use
        parser.parse_line(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": "test.py"},
                            }
                        ]
                    },
                }
            )
        )

        # No tool display output
        assert not any("[Read:" in t for t in text_emitted)

    def test_still_tracks_full_text_when_disabled(self) -> None:
        """Parser still tracks full text even when output disabled."""
        callbacks = StreamParserCallbacks()
        parser = JsonStreamParser(
            callbacks=callbacks,
            stream_output=False,
        )

        parser.parse_line(
            json.dumps(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello"},
                }
            )
        )

        # Full text is still tracked
        assert parser.get_full_text() == "Hello"


class TestJsonStreamParserWritesJsonl:
    """Tests for JSONL file writing."""

    def test_writes_to_jsonl_file(self, tmp_path: Path) -> None:
        """Parser writes raw JSON to JSONL file."""
        jsonl_path = tmp_path / "output.jsonl"
        with jsonl_path.open("w") as f:
            parser = JsonStreamParser(
                callbacks=StreamParserCallbacks(),
                jsonl_file=f,
            )
            parser.parse_line('{"type": "assistant", "message": {}}')
            parser.parse_line('{"type": "result"}')

        content = jsonl_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert '{"type": "assistant"' in lines[0]
        assert '{"type": "result"}' in lines[1]
