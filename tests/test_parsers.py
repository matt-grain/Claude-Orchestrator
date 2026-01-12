"""Unit tests for plan parsers."""

from __future__ import annotations

from pathlib import Path

import pytest

from debussy.core.models import PhaseStatus
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase


class TestMasterPlanParser:
    """Tests for master plan parsing."""

    def test_parse_master_plan_basic(self, sample_master_plan: Path) -> None:
        """Test parsing a basic master plan."""
        plan = parse_master_plan(sample_master_plan)

        assert "Test Feature" in plan.name
        assert len(plan.phases) == 3

    def test_parse_master_plan_phases(self, sample_master_plan: Path) -> None:
        """Test that phases are extracted correctly."""
        plan = parse_master_plan(sample_master_plan)

        assert plan.phases[0].id == "1"
        assert plan.phases[0].title == "Setup Infrastructure"
        assert "test-feature-phase1.md" in str(plan.phases[0].path)

        assert plan.phases[1].id == "2"
        assert plan.phases[1].title == "Add Logic"

        assert plan.phases[2].id == "3"
        assert plan.phases[2].title == "Polish"

    def test_parse_master_plan_status(self, sample_master_plan: Path) -> None:
        """Test that phase status is parsed correctly."""
        plan = parse_master_plan(sample_master_plan)

        # All phases in sample are Pending
        for phase in plan.phases:
            assert phase.status == PhaseStatus.PENDING

    def test_parse_master_plan_temp(self, temp_master_plan: Path) -> None:
        """Test parsing a temporary master plan."""
        plan = parse_master_plan(temp_master_plan)

        assert plan.name == "Test Plan - Master"
        assert len(plan.phases) == 2

    def test_parse_nonexistent_file(self, temp_dir: Path) -> None:
        """Test parsing a nonexistent file raises an error."""
        with pytest.raises(FileNotFoundError):
            parse_master_plan(temp_dir / "nonexistent.md")


class TestPhaseParser:
    """Tests for phase file parsing."""

    def test_parse_phase_basic(self, sample_phase: Path) -> None:
        """Test parsing a basic phase file."""
        phase = parse_phase(sample_phase, "1")

        assert phase.id == "1"
        assert "Infrastructure" in phase.title or "Setup" in phase.title

    def test_parse_phase_gates(self, sample_phase: Path) -> None:
        """Test that gates are extracted correctly."""
        phase = parse_phase(sample_phase, "1")

        assert len(phase.gates) == 2
        gate_names = [g.name for g in phase.gates]
        assert "ruff" in gate_names
        assert "pytest" in gate_names

    def test_parse_phase_tasks(self, sample_phase: Path) -> None:
        """Test that tasks are extracted correctly."""
        phase = parse_phase(sample_phase, "1")

        # Should have at least some tasks from task group 1
        assert len(phase.tasks) >= 2
        task_ids = [t.id for t in phase.tasks]
        assert "1.1" in task_ids
        assert "1.2" in task_ids

    def test_parse_phase_required_agents(self, sample_phase: Path) -> None:
        """Test that required agents are extracted."""
        phase = parse_phase(sample_phase, "1")

        assert "doc-sync-manager" in phase.required_agents
        assert "task-validator" in phase.required_agents

    def test_parse_phase_notes_output(self, sample_phase: Path) -> None:
        """Test that notes output path is extracted."""
        phase = parse_phase(sample_phase, "1")

        assert phase.notes_output.as_posix() == "notes/NOTES_test_phase_1.md"

    def test_parse_phase_dependencies(self, sample_phase2: Path) -> None:
        """Test parsing dependencies from phase 2."""
        phase = parse_phase(sample_phase2, "2")

        # Phase 2 depends on Phase 1
        assert phase.depends_on is not None
        assert len(phase.depends_on) > 0

    def test_parse_phase_notes_input(self, sample_phase2: Path) -> None:
        """Test that notes input path is extracted."""
        phase = parse_phase(sample_phase2, "2")

        assert phase.notes_input.as_posix() == "notes/NOTES_test_phase_1.md"

    def test_parse_phase_with_temp_plan(self, temp_master_plan: Path) -> None:
        """Test parsing phase from temporary plan."""
        phase1_path = temp_master_plan.parent / "phase1.md"
        phase = parse_phase(phase1_path, "1")

        assert phase.id == "1"
        assert "test-agent" in phase.required_agents
        assert phase.notes_output.as_posix() == "notes/NOTES_phase_1.md"


class TestParserEdgeCases:
    """Edge case tests for parsers."""

    def test_parse_empty_phases_table(self, temp_dir: Path) -> None:
        """Test parsing a master plan with empty phases table."""
        plan_content = """\
# Empty Plan

**Status:** Draft

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
"""
        plan_path = temp_dir / "empty-master.md"
        plan_path.write_text(plan_content)

        plan = parse_master_plan(plan_path)
        assert len(plan.phases) == 0

    def test_parse_phase_no_gates(self, temp_dir: Path) -> None:
        """Test parsing a phase with no gates section."""
        phase_content = """\
# Phase Without Gates

**Status:** Pending

## Tasks

### 1. Only Tasks
- [ ] 1.1: Do something
"""
        phase_path = temp_dir / "no-gates.md"
        phase_path.write_text(phase_content)

        phase = parse_phase(phase_path, "1")
        assert len(phase.gates) == 0
        assert len(phase.tasks) == 1

    def test_parse_phase_no_agents(self, temp_dir: Path) -> None:
        """Test parsing a phase with no required agents."""
        phase_content = """\
# Phase Without Agents

**Status:** Pending

## Process Wrapper (MANDATORY)
- [ ] **[IMPLEMENTATION]**

## Tasks

### 1. Tasks
- [ ] 1.1: Task one
"""
        phase_path = temp_dir / "no-agents.md"
        phase_path.write_text(phase_content)

        phase = parse_phase(phase_path, "1")
        assert len(phase.required_agents) == 0

    def test_parse_completed_tasks(self, temp_dir: Path) -> None:
        """Test parsing phases with completed tasks."""
        phase_content = """\
# Phase With Done Tasks

**Status:** In Progress

## Tasks

### 1. Mixed Tasks
- [x] 1.1: Completed task
- [ ] 1.2: Pending task
"""
        phase_path = temp_dir / "mixed-tasks.md"
        phase_path.write_text(phase_content)

        phase = parse_phase(phase_path, "1")
        assert len(phase.tasks) == 2

        completed = [t for t in phase.tasks if t.completed]
        pending = [t for t in phase.tasks if not t.completed]
        assert len(completed) == 1
        assert len(pending) == 1
