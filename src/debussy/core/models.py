"""Core data models for the debussy."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PhaseStatus(str, Enum):
    """Status of a phase in the orchestration pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunStatus(str, Enum):
    """Status of an orchestration run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class ComplianceIssueType(str, Enum):
    """Types of compliance issues that can be detected."""

    NOTES_MISSING = "notes_missing"
    NOTES_INCOMPLETE = "notes_incomplete"
    GATES_FAILED = "gates_failed"
    AGENT_SKIPPED = "agent_skipped"
    STEP_SKIPPED = "step_skipped"


class RemediationStrategy(str, Enum):
    """Strategy for handling compliance failures."""

    WARN_AND_ACCEPT = "warn"  # Minor issues, log and continue
    TARGETED_FIX = "fix"  # Spawn remediation session
    FULL_RETRY = "retry"  # Fresh session, restart phase
    HUMAN_REQUIRED = "human"  # Pause for human decision


# =============================================================================
# Plan Models
# =============================================================================


class Task(BaseModel):
    """A task item from a phase plan."""

    id: str
    description: str
    completed: bool = False


class Gate(BaseModel):
    """A validation gate that must pass."""

    name: str
    command: str
    blocking: bool = True


class Phase(BaseModel):
    """A phase in the master plan."""

    id: str
    title: str
    path: Path
    status: PhaseStatus = PhaseStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    gates: list[Gate] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    required_steps: list[str] = Field(default_factory=list)
    notes_input: Path | None = None
    notes_output: Path | None = None


class MasterPlan(BaseModel):
    """A master plan containing multiple phases."""

    name: str
    path: Path
    phases: list[Phase]
    github_issues: list[int] | str | None = Field(
        default=None,
        description="GitHub issue numbers to sync (e.g., [10, 11] or '#10, #11')",
    )
    github_repo: str | None = Field(
        default=None,
        description="GitHub repo for sync (e.g., 'owner/repo'). Auto-detected if not set.",
    )
    jira_issues: list[str] | str | None = Field(
        default=None,
        description="Jira issue keys to sync (e.g., ['PROJ-123', 'PROJ-124'] or 'PROJ-123, PROJ-124')",
    )
    created_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Execution Models
# =============================================================================


class GateResult(BaseModel):
    """Result of running a single gate."""

    name: str
    command: str
    passed: bool
    output: str
    executed_at: datetime = Field(default_factory=datetime.now)


class ExecutionResult(BaseModel):
    """Result of executing a Claude session."""

    success: bool
    session_log: str
    exit_code: int
    duration_seconds: float
    pid: int | None = None


class CompletionSignal(BaseModel):
    """Signal sent by Claude worker when phase is done."""

    phase_id: str
    status: Literal["completed", "blocked", "failed"]
    reason: str | None = None
    report: dict[str, object] | None = None
    signaled_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Compliance Models
# =============================================================================


class ComplianceIssue(BaseModel):
    """A compliance issue found during verification."""

    type: ComplianceIssueType
    severity: Literal["low", "high", "critical"]
    details: str
    evidence: str | None = None


class ComplianceResult(BaseModel):
    """Result of compliance verification."""

    passed: bool
    issues: list[ComplianceIssue] = Field(default_factory=list)
    remediation: RemediationStrategy | None = None
    verified_steps: list[str] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)


# =============================================================================
# State Models
# =============================================================================


class PhaseExecution(BaseModel):
    """Record of a phase execution attempt."""

    id: int | None = None
    run_id: str
    phase_id: str
    attempt: int = 1
    status: PhaseStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    claude_pid: int | None = None
    log_path: Path | None = None
    error_message: str | None = None


class RunState(BaseModel):
    """State of an orchestration run."""

    id: str
    master_plan_path: Path
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
    current_phase: str | None = None
    phase_executions: list[PhaseExecution] = Field(default_factory=list)
