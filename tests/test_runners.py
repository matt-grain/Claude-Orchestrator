"""Tests for the runners module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from debussy.core.models import (
    ComplianceIssue,
    ComplianceIssueType,
    Gate,
    Phase,
    PhaseStatus,
)
from debussy.runners.claude import ClaudeRunner
from debussy.runners.gates import GateRunner


@pytest.fixture
def gate_runner(temp_dir: Path) -> GateRunner:
    """Create a GateRunner for testing."""
    return GateRunner(temp_dir, timeout=10)


@pytest.fixture
def simple_phase() -> Phase:
    """Create a simple phase with passing gates."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("test.md"),
        status=PhaseStatus.PENDING,
        gates=[
            Gate(name="echo", command="echo 'hello'", blocking=True),
        ],
    )


@pytest.fixture
def phase_with_multiple_gates() -> Phase:
    """Create a phase with multiple gates."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("test.md"),
        status=PhaseStatus.PENDING,
        gates=[
            Gate(name="first", command="echo 'first'", blocking=True),
            Gate(name="second", command="echo 'second'", blocking=True),
            Gate(name="third", command="echo 'third'", blocking=False),
        ],
    )


@pytest.fixture
def phase_with_failing_gate() -> Phase:
    """Create a phase with a failing gate."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("test.md"),
        status=PhaseStatus.PENDING,
        gates=[
            Gate(name="pass", command="echo 'pass'", blocking=True),
            Gate(name="fail", command="exit 1", blocking=True),
            Gate(name="skipped", command="echo 'skipped'", blocking=True),
        ],
    )


@pytest.fixture
def phase_with_non_blocking_fail() -> Phase:
    """Create a phase with a non-blocking failing gate."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("test.md"),
        status=PhaseStatus.PENDING,
        gates=[
            Gate(name="fail_non_blocking", command="exit 1", blocking=False),
            Gate(name="should_run", command="echo 'ran'", blocking=True),
        ],
    )


class TestGateRunner:
    """Tests for GateRunner."""

    async def test_run_single_passing_gate(
        self,
        gate_runner: GateRunner,
    ) -> None:
        """Test running a single passing gate."""
        gate = Gate(name="echo", command="echo 'hello'", blocking=True)
        result = await gate_runner.run_gate(gate)

        assert result.passed is True
        assert result.name == "echo"
        assert "hello" in result.output
        assert result.executed_at is not None

    async def test_run_single_failing_gate(
        self,
        gate_runner: GateRunner,
    ) -> None:
        """Test running a single failing gate."""
        gate = Gate(name="fail", command="exit 1", blocking=True)
        result = await gate_runner.run_gate(gate)

        assert result.passed is False
        assert result.name == "fail"

    async def test_run_gates_all_pass(
        self,
        gate_runner: GateRunner,
        phase_with_multiple_gates: Phase,
    ) -> None:
        """Test running multiple gates that all pass."""
        results = await gate_runner.run_gates(phase_with_multiple_gates)

        assert len(results) == 3
        assert all(r.passed for r in results)
        assert results[0].name == "first"
        assert results[1].name == "second"
        assert results[2].name == "third"

    async def test_run_gates_stops_on_blocking_failure(
        self,
        gate_runner: GateRunner,
        phase_with_failing_gate: Phase,
    ) -> None:
        """Test that gate execution stops on blocking failure."""
        results = await gate_runner.run_gates(phase_with_failing_gate)

        # Should stop after the failing gate
        assert len(results) == 2
        assert results[0].passed is True
        assert results[0].name == "pass"
        assert results[1].passed is False
        assert results[1].name == "fail"

    async def test_run_gates_continues_on_non_blocking_failure(
        self,
        gate_runner: GateRunner,
        phase_with_non_blocking_fail: Phase,
    ) -> None:
        """Test that gate execution continues on non-blocking failure."""
        results = await gate_runner.run_gates(phase_with_non_blocking_fail)

        # Should continue past non-blocking failure
        assert len(results) == 2
        assert results[0].passed is False
        assert results[0].name == "fail_non_blocking"
        assert results[1].passed is True
        assert results[1].name == "should_run"

    async def test_run_gates_empty_phase(
        self,
        gate_runner: GateRunner,
    ) -> None:
        """Test running gates on a phase with no gates."""
        phase = Phase(
            id="1",
            title="Test",
            path=Path("test.md"),
            status=PhaseStatus.PENDING,
            gates=[],
        )
        results = await gate_runner.run_gates(phase)
        assert results == []

    async def test_verify_all_gates_pass_success(
        self,
        gate_runner: GateRunner,
        simple_phase: Phase,
    ) -> None:
        """Test verify_all_gates_pass when all pass."""
        all_passed, results = await gate_runner.verify_all_gates_pass(simple_phase)

        assert all_passed is True
        assert len(results) == 1
        assert results[0].passed is True

    async def test_verify_all_gates_pass_failure(
        self,
        gate_runner: GateRunner,
        phase_with_failing_gate: Phase,
    ) -> None:
        """Test verify_all_gates_pass when one fails."""
        all_passed, _results = await gate_runner.verify_all_gates_pass(phase_with_failing_gate)

        assert all_passed is False

    async def test_run_single_gate_by_name_found(
        self,
        gate_runner: GateRunner,
        phase_with_multiple_gates: Phase,
    ) -> None:
        """Test running a gate by name when found."""
        result = await gate_runner.run_single_gate_by_name(
            phase_with_multiple_gates,
            "second",
        )

        assert result is not None
        assert result.name == "second"
        assert result.passed is True

    async def test_run_single_gate_by_name_case_insensitive(
        self,
        gate_runner: GateRunner,
        phase_with_multiple_gates: Phase,
    ) -> None:
        """Test that gate name lookup is case insensitive."""
        result = await gate_runner.run_single_gate_by_name(
            phase_with_multiple_gates,
            "FIRST",
        )

        assert result is not None
        assert result.name == "first"

    async def test_run_single_gate_by_name_not_found(
        self,
        gate_runner: GateRunner,
        phase_with_multiple_gates: Phase,
    ) -> None:
        """Test running a gate by name when not found."""
        result = await gate_runner.run_single_gate_by_name(
            phase_with_multiple_gates,
            "nonexistent",
        )

        assert result is None

    async def test_gate_captures_stderr(
        self,
        gate_runner: GateRunner,
    ) -> None:
        """Test that gate captures stderr output."""
        gate = Gate(
            name="stderr_test",
            command="echo 'error message' >&2 && exit 0",
            blocking=True,
        )
        result = await gate_runner.run_gate(gate)

        assert result.passed is True
        assert "STDERR" in result.output
        assert "error message" in result.output

    async def test_gate_timeout(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that gates timeout correctly."""
        runner = GateRunner(temp_dir, timeout=1)
        gate = Gate(
            name="slow",
            command="sleep 10",
            blocking=True,
        )
        result = await runner.run_gate(gate)

        assert result.passed is False
        assert "TIMEOUT" in result.output

    async def test_gate_invalid_command(
        self,
        gate_runner: GateRunner,
    ) -> None:
        """Test handling of invalid commands."""
        gate = Gate(
            name="invalid",
            command="nonexistent_command_xyz123",
            blocking=True,
        )
        result = await gate_runner.run_gate(gate)

        # Should fail but not crash
        assert result.passed is False

    async def test_gate_runs_in_project_root(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that gate runs in the project root directory."""
        # Create a test file in temp_dir
        test_file = temp_dir / "marker.txt"
        test_file.write_text("exists")

        runner = GateRunner(temp_dir)
        gate = Gate(
            name="check_cwd",
            command="cat marker.txt",
            blocking=True,
        )
        result = await runner.run_gate(gate)

        assert result.passed is True
        assert "exists" in result.output


# ============================================================================
# ClaudeRunner Tests
# ============================================================================


@pytest.fixture
def claude_runner(temp_dir: Path) -> ClaudeRunner:
    """Create a ClaudeRunner for testing."""
    return ClaudeRunner(
        temp_dir,
        timeout=10,
        stream_output=False,  # Disable output for tests
    )


@pytest.fixture
def phase_for_prompt() -> Phase:
    """Create a phase for prompt building tests."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("docs/phase1.md"),
        status=PhaseStatus.PENDING,
        required_agents=["doc-sync-manager", "task-validator"],
        notes_output=Path("notes/NOTES_phase_1.md"),
    )


@pytest.fixture
def phase_with_input_notes(temp_dir: Path) -> Phase:
    """Create a phase with input notes."""
    notes_file = temp_dir / "notes" / "NOTES_phase_0.md"
    notes_file.parent.mkdir(parents=True, exist_ok=True)
    notes_file.write_text("Previous phase notes")

    return Phase(
        id="2",
        title="Phase Two",
        path=Path("docs/phase2.md"),
        status=PhaseStatus.PENDING,
        notes_input=notes_file,
        notes_output=Path("notes/NOTES_phase_2.md"),
    )


class TestClaudeRunnerPrompts:
    """Tests for ClaudeRunner prompt building."""

    def test_build_phase_prompt_basic(
        self,
        claude_runner: ClaudeRunner,
    ) -> None:
        """Test building a basic phase prompt."""
        phase = Phase(
            id="1",
            title="Test",
            path=Path("test.md"),
            status=PhaseStatus.PENDING,
        )
        prompt = claude_runner._build_phase_prompt(phase)

        assert "Execute the implementation phase" in prompt
        assert "test.md" in prompt
        assert "debussy done --phase 1" in prompt

    def test_build_phase_prompt_with_agents(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test prompt includes required agents."""
        prompt = claude_runner._build_phase_prompt(phase_for_prompt)

        assert "Required Agents" in prompt
        assert "doc-sync-manager" in prompt
        assert "task-validator" in prompt
        assert "Task tool" in prompt

    def test_build_phase_prompt_with_notes_output(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test prompt includes notes output path."""
        prompt = claude_runner._build_phase_prompt(phase_for_prompt)

        assert "Notes Output" in prompt
        assert "NOTES_phase_1.md" in prompt

    def test_build_phase_prompt_with_notes_input(
        self,
        claude_runner: ClaudeRunner,
        phase_with_input_notes: Phase,
    ) -> None:
        """Test prompt includes previous phase notes."""
        prompt = claude_runner._build_phase_prompt(phase_with_input_notes)

        assert "Previous Phase Notes" in prompt
        assert "NOTES_phase_0.md" in prompt

    def test_build_remediation_prompt(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test building a remediation prompt."""
        issues = [
            ComplianceIssue(
                type=ComplianceIssueType.AGENT_SKIPPED,
                severity="critical",
                details="Required agent 'doc-sync-manager' was not invoked",
            ),
            ComplianceIssue(
                type=ComplianceIssueType.NOTES_MISSING,
                severity="high",
                details="Notes file not found",
            ),
        ]

        prompt = claude_runner.build_remediation_prompt(phase_for_prompt, issues)

        assert "REMEDIATION SESSION" in prompt
        assert "Phase 1" in prompt
        assert "Test Phase" in prompt
        assert "Issues Found" in prompt
        assert "agent_skipped" in prompt
        assert "notes_missing" in prompt
        assert "Required Actions" in prompt
        assert "doc-sync-manager" in prompt

    def test_build_remediation_prompt_gates_failed(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test remediation prompt for failed gates."""
        issues = [
            ComplianceIssue(
                type=ComplianceIssueType.GATES_FAILED,
                severity="critical",
                details="Gate 'ruff' failed",
            ),
        ]

        prompt = claude_runner.build_remediation_prompt(phase_for_prompt, issues)

        assert "Fix failing gate" in prompt
        assert "ruff" in prompt

    def test_build_remediation_prompt_step_skipped(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test remediation prompt for skipped steps."""
        issues = [
            ComplianceIssue(
                type=ComplianceIssueType.STEP_SKIPPED,
                severity="high",
                details="Step 'validation' was not completed",
            ),
        ]

        prompt = claude_runner.build_remediation_prompt(phase_for_prompt, issues)

        assert "Complete step" in prompt
        assert "validation" in prompt

    def test_build_remediation_prompt_notes_incomplete(
        self,
        claude_runner: ClaudeRunner,
        phase_for_prompt: Phase,
    ) -> None:
        """Test remediation prompt for incomplete notes."""
        issues = [
            ComplianceIssue(
                type=ComplianceIssueType.NOTES_INCOMPLETE,
                severity="high",
                details="Missing sections",
            ),
        ]

        prompt = claude_runner.build_remediation_prompt(phase_for_prompt, issues)

        assert "Complete all required sections" in prompt


class TestClaudeRunnerOutput:
    """Tests for ClaudeRunner output handling."""

    def test_display_tool_use_read(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Read tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Read",
            "input": {"file_path": "/path/to/file.py"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            mock_write.assert_called_once()
            assert "Read: file.py" in mock_write.call_args[0][0]

    def test_display_tool_use_write(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Write tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Write",
            "input": {"file_path": "/path/to/output.txt"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            mock_write.assert_called_once()
            assert "Write: output.txt" in mock_write.call_args[0][0]

    def test_display_tool_use_edit(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Edit tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Edit",
            "input": {"file_path": "C:\\Users\\test\\file.py"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            mock_write.assert_called_once()
            assert "Edit: file.py" in mock_write.call_args[0][0]

    def test_display_tool_use_bash(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Bash tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Bash",
            "input": {"command": "pytest tests/"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            mock_write.assert_called_once()
            assert "Bash: pytest tests/" in mock_write.call_args[0][0]

    def test_display_tool_use_bash_truncates_long_commands(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that long bash commands are truncated."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        long_command = "x" * 100
        content = {
            "name": "Bash",
            "input": {"command": long_command},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            output = mock_write.call_args[0][0]
            assert "..." in output
            assert len(output) < 100

    def test_display_tool_use_glob(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Glob tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Glob",
            "input": {"pattern": "**/*.py"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            assert "Glob: **/*.py" in mock_write.call_args[0][0]

    def test_display_tool_use_grep(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Grep tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Grep",
            "input": {"pattern": "def test_"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            assert "Grep: def test_" in mock_write.call_args[0][0]

    def test_display_tool_use_todo_write(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of TodoWrite tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "TodoWrite",
            "input": {"todos": [{"content": "a"}, {"content": "b"}]},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            assert "TodoWrite: 2 items" in mock_write.call_args[0][0]

    def test_display_tool_use_task(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of Task tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "Task",
            "input": {"description": "Run tests"},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            assert "Task: Run tests" in mock_write.call_args[0][0]

    def test_display_tool_use_unknown(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of unknown tool."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {
            "name": "CustomTool",
            "input": {},
        }

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            assert "[CustomTool]" in mock_write.call_args[0][0]

    def test_display_tool_use_disabled(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that tool display is skipped when streaming is disabled."""
        runner = ClaudeRunner(temp_dir, stream_output=False)
        content = {"name": "Read", "input": {"file_path": "test.py"}}

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_use(content)
            mock_write.assert_not_called()

    def test_display_tool_result_error(
        self,
        temp_dir: Path,
    ) -> None:
        """Test display of tool result with error."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        content = {"is_error": True, "content": "Permission denied"}

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_result(content, "Permission denied")
            assert "ERROR" in mock_write.call_args[0][0]
            assert "Permission denied" in mock_write.call_args[0][0]

    def test_display_tool_result_error_truncated(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that long error messages are truncated."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        long_error = "x" * 200
        content = {"is_error": True, "content": long_error}

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_result(content, long_error)
            output = mock_write.call_args[0][0]
            assert "..." in output
            assert len(output) < 150

    def test_display_tool_result_disabled(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that result display is skipped when streaming is disabled."""
        runner = ClaudeRunner(temp_dir, stream_output=False)
        content = {"is_error": True, "content": "error"}

        with patch.object(runner, "_write_output") as mock_write:
            runner._display_tool_result(content, "error")
            mock_write.assert_not_called()


class TestClaudeRunnerLogFiles:
    """Tests for ClaudeRunner log file handling."""

    def test_open_log_file_creates_directory(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that log directory is created."""
        log_dir = temp_dir / "logs"
        runner = ClaudeRunner(temp_dir, output_mode="file", log_dir=log_dir)

        runner._open_log_file("run123", "phase1")
        runner._close_log_file()

        assert log_dir.exists()
        log_file = log_dir / "run_run123_phase_phase1.log"
        assert log_file.exists()

    def test_open_log_file_writes_header(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that log file header is written."""
        log_dir = temp_dir / "logs"
        runner = ClaudeRunner(
            temp_dir,
            output_mode="file",
            log_dir=log_dir,
            model="haiku",
        )

        runner._open_log_file("run123", "phase1")
        runner._close_log_file()

        log_file = log_dir / "run_run123_phase_phase1.log"
        content = log_file.read_text()
        assert "Phase phase1 Log" in content
        assert "Run ID: run123" in content
        assert "Model: haiku" in content

    def test_open_log_file_not_created_in_terminal_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that no log file is created in terminal mode."""
        log_dir = temp_dir / "logs"
        runner = ClaudeRunner(temp_dir, output_mode="terminal", log_dir=log_dir)

        runner._open_log_file("run123", "phase1")
        runner._close_log_file()

        assert not log_dir.exists()

    def test_write_output_terminal_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _write_output in terminal mode."""
        runner = ClaudeRunner(temp_dir, output_mode="terminal")

        with patch("sys.stdout.write") as mock_stdout:
            runner._write_output("test output")
            mock_stdout.assert_called_once_with("test output")

    def test_write_output_file_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _write_output in file mode."""
        log_dir = temp_dir / "logs"
        runner = ClaudeRunner(temp_dir, output_mode="file", log_dir=log_dir)

        runner._open_log_file("run123", "phase1")
        runner._write_output("test content")
        runner._close_log_file()

        log_file = log_dir / "run_run123_phase_phase1.log"
        content = log_file.read_text()
        assert "test content" in content

    def test_write_output_both_mode(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _write_output in both mode."""
        log_dir = temp_dir / "logs"
        runner = ClaudeRunner(temp_dir, output_mode="both", log_dir=log_dir)

        runner._open_log_file("run123", "phase1")

        with patch("sys.stdout.write") as mock_stdout:
            runner._write_output("test output")
            mock_stdout.assert_called_once_with("test output")

        runner._close_log_file()

        log_file = log_dir / "run_run123_phase_phase1.log"
        content = log_file.read_text()
        assert "test output" in content

    def test_write_output_with_newline(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _write_output adds newline when requested."""
        runner = ClaudeRunner(temp_dir, output_mode="terminal")

        with patch("sys.stdout.write") as mock_stdout:
            runner._write_output("test", newline=True)
            mock_stdout.assert_called_once_with("test\n")


class TestClaudeRunnerStreamEvents:
    """Tests for ClaudeRunner stream event handling."""

    def test_display_stream_event_assistant_text(
        self,
        temp_dir: Path,
    ) -> None:
        """Test handling assistant text event."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        event = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello world"}]},
        }
        full_text: list[str] = []

        with patch.object(runner, "_write_output"):
            runner._display_stream_event(event, full_text)

        assert "Hello world" in full_text

    def test_display_stream_event_content_block_delta(
        self,
        temp_dir: Path,
    ) -> None:
        """Test handling content block delta event."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        event = {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "streaming text"},
        }
        full_text: list[str] = []

        with patch.object(runner, "_write_output"):
            runner._display_stream_event(event, full_text)

        assert "streaming text" in full_text

    def test_display_stream_event_tool_use(
        self,
        temp_dir: Path,
    ) -> None:
        """Test handling assistant event with tool use."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        event = {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "x.py"}}]
            },
        }
        full_text: list[str] = []

        with patch.object(runner, "_display_tool_use") as mock_tool:
            runner._display_stream_event(event, full_text)
            mock_tool.assert_called_once()

    def test_display_stream_event_user_tool_result(
        self,
        temp_dir: Path,
    ) -> None:
        """Test handling user event with tool result."""
        runner = ClaudeRunner(temp_dir, stream_output=True)
        event = {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "is_error": False}]},
            "tool_use_result": "success",
        }
        full_text: list[str] = []

        with patch.object(runner, "_display_tool_result") as mock_result:
            runner._display_stream_event(event, full_text)
            mock_result.assert_called_once()
