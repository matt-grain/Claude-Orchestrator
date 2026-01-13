"""Unit tests for the state manager - critical for state machine correctness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from debussy.core.models import (
    CompletionSignal,
    GateResult,
    MasterPlan,
    Phase,
    PhaseStatus,
    RunStatus,
)
from debussy.core.state import StateManager


def make_gate_result(name: str, passed: bool, output: str = "OK") -> GateResult:
    """Helper to create GateResult with required fields."""
    return GateResult(name=name, command=f"echo {name}", passed=passed, output=output)


@pytest.fixture
def state_manager(temp_db: Path) -> StateManager:
    """Create a state manager with a temporary database."""
    return StateManager(temp_db)


@pytest.fixture
def sample_plan() -> MasterPlan:
    """Create a sample master plan for testing."""
    return MasterPlan(
        name="Test Plan",
        path=Path("/tmp/test-plan.md"),
        phases=[
            Phase(
                id="1",
                title="Phase One",
                path=Path("/tmp/phase1.md"),
                status=PhaseStatus.PENDING,
            ),
            Phase(
                id="2",
                title="Phase Two",
                path=Path("/tmp/phase2.md"),
                status=PhaseStatus.PENDING,
                depends_on=["1"],
            ),
            Phase(
                id="3",
                title="Phase Three",
                path=Path("/tmp/phase3.md"),
                status=PhaseStatus.PENDING,
                depends_on=["2"],
            ),
        ],
    )


class TestRunManagement:
    """Tests for run creation and management."""

    def test_create_run(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test creating a new run."""
        run_id = state_manager.create_run(sample_plan)

        assert run_id is not None
        assert len(run_id) > 0

    def test_create_run_unique_ids(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that each run gets a unique ID."""
        run_id1 = state_manager.create_run(sample_plan)
        run_id2 = state_manager.create_run(sample_plan)

        assert run_id1 != run_id2

    def test_get_run(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test retrieving a run by ID."""
        run_id = state_manager.create_run(sample_plan)
        run_state = state_manager.get_run(run_id)

        assert run_state is not None
        assert run_state.id == run_id
        assert run_state.status == RunStatus.RUNNING
        assert run_state.master_plan_path == sample_plan.path

    def test_get_nonexistent_run(self, state_manager: StateManager) -> None:
        """Test getting a nonexistent run returns None."""
        result = state_manager.get_run("nonexistent-id")
        assert result is None

    def test_get_current_run(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test getting the current (most recent running) run."""
        run_id = state_manager.create_run(sample_plan)
        current = state_manager.get_current_run()

        assert current is not None
        assert current.id == run_id

    def test_get_current_run_none_when_empty(self, state_manager: StateManager) -> None:
        """Test get_current_run returns None when no runs exist."""
        current = state_manager.get_current_run()
        assert current is None

    def test_list_runs(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test listing runs."""
        run_id1 = state_manager.create_run(sample_plan)
        run_id2 = state_manager.create_run(sample_plan)

        runs = state_manager.list_runs(limit=10)

        assert len(runs) == 2
        run_ids = [r.id for r in runs]
        assert run_id1 in run_ids
        assert run_id2 in run_ids

    def test_list_runs_with_limit(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that list_runs respects the limit."""
        for _ in range(5):
            state_manager.create_run(sample_plan)

        runs = state_manager.list_runs(limit=3)
        assert len(runs) == 3


class TestRunStatusTransitions:
    """Tests for run status state transitions."""

    def test_update_run_status_to_completed(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test transitioning run to completed."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.COMPLETED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.status == RunStatus.COMPLETED
        assert run_state.completed_at is not None

    def test_update_run_status_to_failed(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test transitioning run to failed."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.FAILED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.status == RunStatus.FAILED

    def test_update_run_status_to_paused(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test transitioning run to paused."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.PAUSED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.status == RunStatus.PAUSED

    def test_set_current_phase(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test setting the current phase for a run."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.set_current_phase(run_id, "2")

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.current_phase == "2"


class TestPhaseExecution:
    """Tests for phase execution tracking."""

    def test_create_phase_execution(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test creating a phase execution record."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert len(run_state.phase_executions) == 1
        assert run_state.phase_executions[0].phase_id == "1"
        assert run_state.phase_executions[0].attempt == 1

    def test_multiple_phase_attempts(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test tracking multiple attempts for the same phase."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.create_phase_execution(run_id, "1", attempt=2)
        state_manager.create_phase_execution(run_id, "1", attempt=3)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert len(run_state.phase_executions) == 3

        attempts = [e.attempt for e in run_state.phase_executions]
        assert attempts == [1, 2, 3]

    def test_update_phase_status(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test updating phase status."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.phase_executions[0].status == PhaseStatus.RUNNING

    def test_phase_status_transitions(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test complete phase status transition flow."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)

        # Pending -> Running -> Validating -> Completed
        state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.VALIDATING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.phase_executions[0].status == PhaseStatus.COMPLETED

    def test_phase_status_with_error(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test setting phase status with error message."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(
            run_id, "1", PhaseStatus.FAILED, error_message="Gate failed: ruff check"
        )

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        exec_record = run_state.phase_executions[0]
        assert exec_record.status == PhaseStatus.FAILED
        assert exec_record.error_message == "Gate failed: ruff check"

    def test_get_attempt_count(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test getting the current attempt count for a phase."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.create_phase_execution(run_id, "1", attempt=2)

        count = state_manager.get_attempt_count(run_id, "1")
        assert count == 2


class TestGateResults:
    """Tests for gate result tracking."""

    def test_record_gate_result(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test recording a gate result."""
        run_id = state_manager.create_run(sample_plan)
        exec_id = state_manager.create_phase_execution(run_id, "1", attempt=1)

        gate_result = make_gate_result("ruff", True, "All checks passed")
        state_manager.record_gate_result(exec_id, gate_result)

        # Gate results are tracked in the execution record
        run_state = state_manager.get_run(run_id)
        assert run_state is not None

    def test_record_failed_gate(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test recording a failed gate result."""
        run_id = state_manager.create_run(sample_plan)
        exec_id = state_manager.create_phase_execution(run_id, "1", attempt=1)

        gate_result = make_gate_result("pytest", False, "2 tests failed")
        state_manager.record_gate_result(exec_id, gate_result)


class TestCompletionSignals:
    """Tests for completion signal handling."""

    def test_record_completion_signal(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test recording a completion signal from Claude worker."""
        run_id = state_manager.create_run(sample_plan)

        signal = CompletionSignal(
            phase_id="1",
            status="completed",
            signaled_at=datetime.now(),
        )
        state_manager.record_completion_signal(run_id, signal)

        # Retrieve the signal
        retrieved = state_manager.get_completion_signal(run_id, "1")
        assert retrieved is not None
        assert retrieved.status == "completed"

    def test_completion_signal_with_reason(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test recording a blocked completion signal with reason."""
        run_id = state_manager.create_run(sample_plan)

        signal = CompletionSignal(
            phase_id="1",
            status="blocked",
            reason="Missing dependency: libfoo",
            signaled_at=datetime.now(),
        )
        state_manager.record_completion_signal(run_id, signal)

        retrieved = state_manager.get_completion_signal(run_id, "1")
        assert retrieved is not None
        assert retrieved.status == "blocked"
        assert retrieved.reason == "Missing dependency: libfoo"

    def test_completion_signal_with_report(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test recording a completion signal with JSON report."""
        run_id = state_manager.create_run(sample_plan)

        signal = CompletionSignal(
            phase_id="1",
            status="completed",
            report={
                "tasks_completed": 5,
                "agents_used": ["doc-sync-manager", "task-validator"],
            },
            signaled_at=datetime.now(),
        )
        state_manager.record_completion_signal(run_id, signal)

        retrieved = state_manager.get_completion_signal(run_id, "1")
        assert retrieved is not None
        assert retrieved.report is not None
        assert retrieved.report["tasks_completed"] == 5

    def test_get_nonexistent_signal(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test getting a nonexistent completion signal."""
        run_id = state_manager.create_run(sample_plan)
        retrieved = state_manager.get_completion_signal(run_id, "nonexistent")
        assert retrieved is None


class TestProgressLogging:
    """Tests for progress logging (stuck detection)."""

    def test_log_progress(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test logging progress for a phase."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.log_progress(run_id, "1", "implementation:started")
        state_manager.log_progress(run_id, "1", "implementation:50%")
        state_manager.log_progress(run_id, "1", "implementation:completed")

        # Progress is logged for stuck detection
        # This is a fire-and-forget operation


class TestStateMachineIntegrity:
    """Tests for state machine integrity - ensuring no invalid state transitions."""

    def test_sequential_phase_execution(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test executing phases sequentially maintains correct state."""
        run_id = state_manager.create_run(sample_plan)

        # Execute phase 1
        state_manager.set_current_phase(run_id, "1")
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        # Execute phase 2
        state_manager.set_current_phase(run_id, "2")
        state_manager.create_phase_execution(run_id, "2", attempt=1)
        state_manager.update_phase_status(run_id, "2", PhaseStatus.RUNNING)
        state_manager.update_phase_status(run_id, "2", PhaseStatus.COMPLETED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.current_phase == "2"
        assert len(run_state.phase_executions) == 2

        # Verify both phases completed
        phase1_exec = next(e for e in run_state.phase_executions if e.phase_id == "1")
        phase2_exec = next(e for e in run_state.phase_executions if e.phase_id == "2")
        assert phase1_exec.status == PhaseStatus.COMPLETED
        assert phase2_exec.status == PhaseStatus.COMPLETED

    def test_retry_flow(self, state_manager: StateManager, sample_plan: MasterPlan) -> None:
        """Test retry flow when phase fails compliance."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.set_current_phase(run_id, "1")

        # Attempt 1 - fails
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.VALIDATING)
        state_manager.update_phase_status(
            run_id, "1", PhaseStatus.FAILED, error_message="Ruff check failed"
        )

        # Attempt 2 - succeeds
        state_manager.create_phase_execution(run_id, "1", attempt=2)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.VALIDATING)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None

        # Should have 2 execution records
        phase1_execs = [e for e in run_state.phase_executions if e.phase_id == "1"]
        assert len(phase1_execs) == 2
        assert phase1_execs[0].status == PhaseStatus.FAILED
        assert phase1_execs[1].status == PhaseStatus.COMPLETED

    def test_max_retries_exceeded(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test state when max retries are exceeded."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.set_current_phase(run_id, "1")

        # 3 attempts all fail
        for attempt in range(1, 4):
            state_manager.create_phase_execution(run_id, "1", attempt=attempt)
            state_manager.update_phase_status(run_id, "1", PhaseStatus.RUNNING)
            state_manager.update_phase_status(
                run_id, "1", PhaseStatus.FAILED, error_message=f"Attempt {attempt} failed"
            )

        state_manager.update_run_status(run_id, RunStatus.FAILED)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        assert run_state.status == RunStatus.FAILED
        assert len(run_state.phase_executions) == 3

    def test_human_intervention_state(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test state when human intervention is required."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.set_current_phase(run_id, "1")
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.AWAITING_HUMAN)

        run_state = state_manager.get_run(run_id)
        assert run_state is not None
        exec_record = run_state.phase_executions[0]
        assert exec_record.status == PhaseStatus.AWAITING_HUMAN

    def test_concurrent_runs_isolation(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that multiple runs maintain isolated state."""
        run_id1 = state_manager.create_run(sample_plan)
        run_id2 = state_manager.create_run(sample_plan)

        # Update run 1
        state_manager.set_current_phase(run_id1, "1")
        state_manager.create_phase_execution(run_id1, "1", attempt=1)
        state_manager.update_phase_status(run_id1, "1", PhaseStatus.COMPLETED)
        state_manager.update_run_status(run_id1, RunStatus.COMPLETED)

        # Update run 2 differently
        state_manager.set_current_phase(run_id2, "2")
        state_manager.create_phase_execution(run_id2, "2", attempt=1)
        state_manager.update_phase_status(run_id2, "2", PhaseStatus.FAILED)
        state_manager.update_run_status(run_id2, RunStatus.FAILED)

        # Verify isolation
        run1 = state_manager.get_run(run_id1)
        run2 = state_manager.get_run(run_id2)

        assert run1 is not None
        assert run2 is not None
        assert run1.status == RunStatus.COMPLETED
        assert run2.status == RunStatus.FAILED
        assert run1.current_phase == "1"
        assert run2.current_phase == "2"


class TestResumeAndSkip:
    """Tests for resume and skip completed phases feature."""

    def test_find_resumable_run_returns_paused(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test finding a paused run for the same plan."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.PAUSED)

        result = state_manager.find_resumable_run(sample_plan.path)

        assert result is not None
        assert result.id == run_id
        assert result.status == RunStatus.PAUSED

    def test_find_resumable_run_returns_failed(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test finding a failed run for the same plan."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.FAILED)

        result = state_manager.find_resumable_run(sample_plan.path)

        assert result is not None
        assert result.id == run_id
        assert result.status == RunStatus.FAILED

    def test_find_resumable_run_returns_running(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test finding a running (interrupted) run for the same plan."""
        run_id = state_manager.create_run(sample_plan)
        # Status is RUNNING by default

        result = state_manager.find_resumable_run(sample_plan.path)

        assert result is not None
        assert result.id == run_id
        assert result.status == RunStatus.RUNNING

    def test_find_resumable_run_ignores_completed(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that completed runs are not returned as resumable."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.COMPLETED)

        result = state_manager.find_resumable_run(sample_plan.path)

        assert result is None

    def test_find_resumable_run_returns_most_recent(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that the most recent incomplete run is returned."""
        # Create older run
        run_id1 = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id1, RunStatus.PAUSED)

        # Create newer run
        run_id2 = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id2, RunStatus.PAUSED)

        result = state_manager.find_resumable_run(sample_plan.path)

        assert result is not None
        assert result.id == run_id2  # Most recent

    def test_find_resumable_run_different_plan(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that runs for different plans are not returned."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.update_run_status(run_id, RunStatus.PAUSED)

        # Query for a different plan path
        result = state_manager.find_resumable_run(Path("/different/plan.md"))

        assert result is None

    def test_find_resumable_run_none_when_empty(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that None is returned when no runs exist."""
        result = state_manager.find_resumable_run(sample_plan.path)
        assert result is None

    def test_get_completed_phases_empty(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test getting completed phases when none are completed."""
        run_id = state_manager.create_run(sample_plan)

        completed = state_manager.get_completed_phases(run_id)

        assert completed == set()

    def test_get_completed_phases_single(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test getting a single completed phase."""
        run_id = state_manager.create_run(sample_plan)
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        completed = state_manager.get_completed_phases(run_id)

        assert completed == {"1"}

    def test_get_completed_phases_multiple(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test getting multiple completed phases."""
        run_id = state_manager.create_run(sample_plan)

        # Complete phases 1 and 2
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        state_manager.create_phase_execution(run_id, "2", attempt=1)
        state_manager.update_phase_status(run_id, "2", PhaseStatus.COMPLETED)

        # Phase 3 is still running
        state_manager.create_phase_execution(run_id, "3", attempt=1)
        state_manager.update_phase_status(run_id, "3", PhaseStatus.RUNNING)

        completed = state_manager.get_completed_phases(run_id)

        assert completed == {"1", "2"}

    def test_get_completed_phases_ignores_failed(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that failed phases are not included in completed set."""
        run_id = state_manager.create_run(sample_plan)

        # Phase 1 completed
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        # Phase 2 failed
        state_manager.create_phase_execution(run_id, "2", attempt=1)
        state_manager.update_phase_status(run_id, "2", PhaseStatus.FAILED)

        completed = state_manager.get_completed_phases(run_id)

        assert completed == {"1"}

    def test_get_completed_phases_with_retries(
        self, state_manager: StateManager, sample_plan: MasterPlan
    ) -> None:
        """Test that phases completed after retries are included."""
        run_id = state_manager.create_run(sample_plan)

        # Phase 1: fails first, then succeeds
        state_manager.create_phase_execution(run_id, "1", attempt=1)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.FAILED)

        state_manager.create_phase_execution(run_id, "1", attempt=2)
        state_manager.update_phase_status(run_id, "1", PhaseStatus.COMPLETED)

        completed = state_manager.get_completed_phases(run_id)

        assert completed == {"1"}
