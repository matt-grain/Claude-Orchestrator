"""Integration tests for the debussy system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from debussy.core.models import (
    GateResult,
    PhaseStatus,
    RunStatus,
)
from debussy.core.orchestrator import Orchestrator
from debussy.core.state import StateManager
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase


def make_gate_result(name: str, passed: bool, output: str = "OK") -> GateResult:
    """Helper to create GateResult with required fields."""
    return GateResult(name=name, command=f"echo {name}", passed=passed, output=output)


class TestParserIntegration:
    """Integration tests for parsers working together."""

    def test_parse_master_then_phases(self, temp_master_plan: Path) -> None:
        """Test parsing master plan and then enriching with phase details."""
        # Parse master plan
        plan = parse_master_plan(temp_master_plan)

        # Parse each phase
        for phase in plan.phases:
            phase_path = temp_master_plan.parent / f"phase{phase.id}.md"
            if phase_path.exists():
                detailed = parse_phase(phase_path, phase.id)
                assert detailed.id == phase.id

    def test_full_plan_parsing(self, temp_master_plan: Path) -> None:
        """Test complete plan parsing flow."""
        plan = parse_master_plan(temp_master_plan)

        # Verify master plan
        assert len(plan.phases) == 2

        # Verify phase 1
        phase1_path = temp_master_plan.parent / "phase1.md"
        phase1 = parse_phase(phase1_path, "1")
        assert "test-agent" in phase1.required_agents

        # Verify phase 2
        phase2_path = temp_master_plan.parent / "phase2.md"
        phase2 = parse_phase(phase2_path, "2")
        assert phase2.notes_input.as_posix() == "notes/NOTES_phase_1.md"


class TestStateOrchestratorIntegration:
    """Integration tests for state manager with debussy."""

    def test_orchestrator_creates_run_state(self, temp_master_plan: Path, temp_dir: Path) -> None:
        """Test that debussy correctly initializes state."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        # Create mock state manager pointing to temp db
        db_path = temp_dir / "state.db"
        state = StateManager(db_path)

        # Create a run
        assert debussy.plan is not None
        run_id = state.create_run(debussy.plan)

        # Verify state
        run_state = state.get_run(run_id)
        assert run_state is not None
        assert run_state.status == RunStatus.RUNNING

    def test_state_tracks_phase_execution(self, temp_master_plan: Path, temp_dir: Path) -> None:
        """Test that state correctly tracks phase execution."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        db_path = temp_dir / "state.db"
        state = StateManager(db_path)

        assert debussy.plan is not None
        run_id = state.create_run(debussy.plan)

        # Simulate phase execution
        state.set_current_phase(run_id, "1")
        state.create_phase_execution(run_id, "1", attempt=1)
        state.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
        state.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        # Verify state
        run_state = state.get_run(run_id)
        assert run_state is not None
        assert run_state.current_phase == "1"
        assert len(run_state.phase_executions) == 1
        assert run_state.phase_executions[0].status == PhaseStatus.COMPLETED


class TestOrchestratorFlow:
    """Integration tests for debussy execution flow."""

    @pytest.mark.asyncio
    async def test_successful_orchestration(
        self,
        temp_master_plan: Path,
        temp_dir: Path,  # noqa: ARG002
    ) -> None:
        """Test successful orchestration of a simple plan."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        # Mock the Claude runner to succeed
        mock_claude = MagicMock()
        mock_claude.execute_phase = AsyncMock(
            return_value=MagicMock(
                success=True,
                exit_code=0,
                session_log="Task completed successfully",
            )
        )
        debussy.claude = mock_claude

        # Mock gates to pass
        mock_gates = MagicMock()
        mock_gates.run_gate = AsyncMock(return_value=make_gate_result("test", True, "OK"))
        debussy.gates = mock_gates

        # Mock state manager
        with patch.object(debussy, "state") as mock_state:
            mock_state.create_run.return_value = "test-run-id"
            mock_state.get_completion_signal.return_value = None
            mock_state.get_attempt_count.return_value = 1

            # Run orchestration
            run_id = await debussy.run()

            assert run_id == "test-run-id"
            mock_state.create_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_phase_failure_handling(self, temp_master_plan: Path) -> None:
        """Test that debussy handles phase failures correctly."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        # Mock Claude runner to fail
        mock_claude = MagicMock()
        mock_claude.execute_phase = AsyncMock(
            return_value=MagicMock(
                success=False,
                exit_code=1,
                session_log="Error occurred",
            )
        )
        debussy.claude = mock_claude

        with patch.object(debussy, "state") as mock_state:
            mock_state.create_run.return_value = "test-run-id"
            mock_state.get_completion_signal.return_value = None

            await debussy.run()

            # Should update status to failed
            mock_state.update_run_status.assert_called_with("test-run-id", RunStatus.FAILED)


class TestDependencyResolution:
    """Tests for phase dependency resolution."""

    def test_dependencies_met_no_deps(self, temp_master_plan: Path) -> None:
        """Test dependency check when phase has no dependencies."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        assert debussy.plan is not None
        phase1 = debussy.plan.phases[0]

        # Phase 1 has no dependencies
        assert debussy._dependencies_met(phase1)

    def test_dependencies_not_met(self, temp_master_plan: Path) -> None:
        """Test dependency check when dependencies are not met."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        assert debussy.plan is not None
        phase2 = debussy.plan.phases[1]

        # Phase 2 depends on phase 1, which hasn't completed
        assert not debussy._dependencies_met(phase2)

    def test_dependencies_met_after_completion(self, temp_master_plan: Path) -> None:
        """Test dependency check after completing required phase."""
        debussy = Orchestrator(temp_master_plan)
        debussy.load_plan()

        assert debussy.plan is not None

        # Mark phase 1 as completed
        debussy.plan.phases[0].status = PhaseStatus.COMPLETED

        phase2 = debussy.plan.phases[1]
        assert debussy._dependencies_met(phase2)


class TestGateRunnerIntegration:
    """Integration tests for gate runner."""

    @pytest.mark.asyncio
    async def test_gate_command_execution(self, temp_dir: Path) -> None:
        """Test running a simple gate command."""
        from debussy.core.models import Gate
        from debussy.runners.gates import GateRunner

        runner = GateRunner(temp_dir)

        # Use a simple command that should work on any system
        gate = Gate(name="echo", command="echo hello", expected="hello")
        result = await runner.run_gate(gate)

        assert result.passed
        assert "hello" in result.output.lower()

    @pytest.mark.asyncio
    async def test_failing_gate(self, temp_dir: Path) -> None:
        """Test running a gate that fails."""
        from debussy.core.models import Gate
        from debussy.runners.gates import GateRunner

        runner = GateRunner(temp_dir)

        # Command that will fail (python returns exit code 1)
        gate = Gate(name="fail", command='python -c "exit(1)"', expected="")
        result = await runner.run_gate(gate)

        assert not result.passed


class TestCompleteWorkflow:
    """End-to-end workflow tests."""

    def test_dry_run_validation(self, temp_master_plan: Path) -> None:
        """Test dry run validation of a plan."""
        # Parse and validate without executing
        plan = parse_master_plan(temp_master_plan)

        assert plan is not None
        assert len(plan.phases) > 0

        # Validate each phase can be parsed
        for phase in plan.phases:
            phase_path = temp_master_plan.parent / f"phase{phase.id}.md"
            if phase_path.exists():
                detailed = parse_phase(phase_path, phase.id)
                assert detailed is not None

    def test_state_persistence(self, temp_dir: Path, temp_master_plan: Path) -> None:
        """Test that state persists across StateManager instances."""
        db_path = temp_dir / "persist_test.db"

        # Create run with first manager
        state1 = StateManager(db_path)
        plan = parse_master_plan(temp_master_plan)
        from debussy.core.models import MasterPlan, Phase

        master = MasterPlan(
            name=plan.name,
            path=plan.path,
            phases=[
                Phase(id=p.id, title=p.title, path=p.path, status=p.status) for p in plan.phases
            ],
        )
        run_id = state1.create_run(master)
        state1.set_current_phase(run_id, "1")

        # Close first manager (implicitly)
        del state1

        # Open new manager and verify state persisted
        state2 = StateManager(db_path)
        run_state = state2.get_run(run_id)

        assert run_state is not None
        assert run_state.id == run_id
        assert run_state.current_phase == "1"
