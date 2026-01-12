"""Unit tests for the compliance checker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.core.compliance import ComplianceChecker
from orchestrator.core.models import (
    ComplianceIssueType,
    Gate,
    GateResult,
    Phase,
    PhaseStatus,
    RemediationStrategy,
)
from orchestrator.runners.gates import GateRunner


def make_gate_result(name: str, passed: bool, output: str = "OK") -> GateResult:
    """Helper to create GateResult with required fields."""
    return GateResult(name=name, command=f"echo {name}", passed=passed, output=output)


@pytest.fixture
def mock_gate_runner() -> MagicMock:
    """Create a mock gate runner."""
    runner = MagicMock(spec=GateRunner)
    return runner


@pytest.fixture
def compliance_checker(mock_gate_runner: MagicMock, tmp_path: Path) -> ComplianceChecker:
    """Create a compliance checker with mocked gate runner."""
    return ComplianceChecker(mock_gate_runner, tmp_path)


@pytest.fixture
def sample_phase() -> Phase:
    """Create a sample phase for testing."""
    return Phase(
        id="1",
        title="Test Phase",
        path=Path("/tmp/phase1.md"),
        status=PhaseStatus.RUNNING,
        gates=[
            Gate(name="ruff", command="ruff check .", expected="0 errors"),
            Gate(name="pytest", command="pytest", expected="all passed"),
        ],
        required_agents=["doc-sync-manager", "task-validator"],
        notes_output=None,  # No notes for simpler testing
    )


def make_session_log_with_agents(agents: list[str]) -> str:
    """Create a session log that shows agent invocations."""
    lines = []
    for agent in agents:
        # Simulate Task tool invocation pattern in session logs
        lines.append('invoke name="Task"')
        lines.append(f'parameter name="subagent_type">{agent}')
    return "\n".join(lines)


class TestGateVerification:
    """Tests for gate verification."""

    @pytest.mark.asyncio
    async def test_all_gates_pass(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test compliance when all gates pass."""
        # Mock all gates passing
        mock_gate_runner.run_gates = AsyncMock(
            return_value=[
                make_gate_result("ruff", True, "OK"),
                make_gate_result("pytest", True, "5 passed"),
            ]
        )

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        assert result.passed
        assert len(result.issues) == 0
        assert len(result.gate_results) == 2

    @pytest.mark.asyncio
    async def test_gate_failure(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test compliance fails when a gate fails."""
        mock_gate_runner.run_gates = AsyncMock(
            return_value=[
                make_gate_result("ruff", False, "3 errors"),
                make_gate_result("pytest", True, "5 passed"),
            ]
        )

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        assert not result.passed
        assert len(result.issues) >= 1

        gate_issues = [i for i in result.issues if i.type == ComplianceIssueType.GATES_FAILED]
        assert len(gate_issues) == 1
        assert "ruff" in gate_issues[0].details

    @pytest.mark.asyncio
    async def test_multiple_gate_failures(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test compliance with multiple gate failures."""
        mock_gate_runner.run_gates = AsyncMock(
            return_value=[
                make_gate_result("ruff", False, "errors"),
                make_gate_result("pytest", False, "2 failed"),
            ]
        )

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        assert not result.passed
        gate_issues = [i for i in result.issues if i.type == ComplianceIssueType.GATES_FAILED]
        assert len(gate_issues) == 2


class TestAgentVerification:
    """Tests for required agent verification."""

    @pytest.mark.asyncio
    async def test_missing_agent(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test compliance fails when required agent is missing."""
        mock_gate_runner.run_gates = AsyncMock(return_value=[make_gate_result("test", True, "OK")])

        # Only invoke one of the two required agents
        session_log = make_session_log_with_agents(["doc-sync-manager"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        assert not result.passed
        agent_issues = [i for i in result.issues if i.type == ComplianceIssueType.AGENT_SKIPPED]
        assert len(agent_issues) >= 1
        assert "task-validator" in agent_issues[0].details

    @pytest.mark.asyncio
    async def test_all_agents_invoked(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test compliance passes when all agents are invoked."""
        mock_gate_runner.run_gates = AsyncMock(return_value=[make_gate_result("test", True, "OK")])

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        # Should pass (assuming gates pass)
        agent_issues = [i for i in result.issues if i.type == ComplianceIssueType.AGENT_SKIPPED]
        assert len(agent_issues) == 0

    @pytest.mark.asyncio
    async def test_no_required_agents(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
    ) -> None:
        """Test compliance when phase has no required agents."""
        phase = Phase(
            id="1",
            title="No Agents Phase",
            path=Path("/tmp/phase.md"),
            status=PhaseStatus.RUNNING,
            gates=[],
            required_agents=[],
        )

        mock_gate_runner.run_gates = AsyncMock(return_value=[])

        result = await compliance_checker.verify_completion(phase, "", completion_report=None)

        agent_issues = [i for i in result.issues if i.type == ComplianceIssueType.AGENT_SKIPPED]
        assert len(agent_issues) == 0


class TestRemediationStrategy:
    """Tests for remediation strategy determination."""

    @pytest.mark.asyncio
    async def test_targeted_fix_for_gate_failure(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test that gate failures suggest targeted fix."""
        mock_gate_runner.run_gates = AsyncMock(
            return_value=[
                make_gate_result("ruff", False, "errors"),
                make_gate_result("pytest", True, "OK"),
            ]
        )

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        # Single gate failure should suggest targeted fix
        assert result.remediation in (
            RemediationStrategy.TARGETED_FIX,
            RemediationStrategy.FULL_RETRY,
        )

    @pytest.mark.asyncio
    async def test_full_retry_for_missing_agents(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test that missing agents suggest full retry."""
        mock_gate_runner.run_gates = AsyncMock(return_value=[make_gate_result("test", True, "OK")])

        # No agents invoked
        session_log = ""

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        # Missing agents is a more serious issue
        assert result.remediation in (
            RemediationStrategy.FULL_RETRY,
            RemediationStrategy.HUMAN_REQUIRED,
        )


class TestCompletionReport:
    """Tests for completion report handling."""

    @pytest.mark.asyncio
    async def test_report_with_agents_used(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test processing completion report with agents_used field."""
        mock_gate_runner.run_gates = AsyncMock(return_value=[make_gate_result("test", True, "OK")])

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])
        report = {"agents_used": ["doc-sync-manager", "task-validator"]}

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=report
        )

        # Report should help verify compliance
        agent_issues = [i for i in result.issues if i.type == ComplianceIssueType.AGENT_SKIPPED]
        assert len(agent_issues) == 0


class TestEdgeCases:
    """Edge case tests for compliance checker."""

    @pytest.mark.asyncio
    async def test_empty_session_log(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test handling empty session log."""
        mock_gate_runner.run_gates = AsyncMock(return_value=[make_gate_result("test", True, "OK")])

        result = await compliance_checker.verify_completion(
            sample_phase, "", completion_report=None
        )

        # Empty log means agents weren't detected
        agent_issues = [i for i in result.issues if i.type == ComplianceIssueType.AGENT_SKIPPED]
        assert len(agent_issues) == len(sample_phase.required_agents)

    @pytest.mark.asyncio
    async def test_phase_with_no_gates(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test phase with no gates to run."""
        phase = Phase(
            id="1",
            title="No Gates",
            path=Path("/tmp/phase.md"),
            status=PhaseStatus.RUNNING,
            gates=[],
            required_agents=[],
        )

        result = await compliance_checker.verify_completion(phase, "", completion_report=None)

        # No gates to fail, no agents to check - should pass
        assert result.passed
        assert len(result.gate_results) == 0

    @pytest.mark.asyncio
    async def test_gate_timeout(
        self,
        compliance_checker: ComplianceChecker,
        mock_gate_runner: MagicMock,
        sample_phase: Phase,
    ) -> None:
        """Test handling gate timeout."""
        mock_gate_runner.run_gates = AsyncMock(
            return_value=[make_gate_result("slow", False, "Command timed out")]
        )

        session_log = make_session_log_with_agents(["doc-sync-manager", "task-validator"])

        result = await compliance_checker.verify_completion(
            sample_phase, session_log, completion_report=None
        )

        assert not result.passed
