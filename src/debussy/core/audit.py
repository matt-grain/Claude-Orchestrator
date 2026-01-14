"""Audit models for plan validation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AuditSeverity(str, Enum):
    """Severity level for audit issues."""

    ERROR = "error"  # Plan cannot run
    WARNING = "warning"  # Plan may have issues
    INFO = "info"  # Suggestions


class AuditIssue(BaseModel):
    """An issue found during plan audit."""

    severity: AuditSeverity
    code: str  # e.g., "MISSING_GATES", "PHASE_NOT_FOUND"
    message: str
    location: str | None = None  # e.g., "phase-1.md:45"


class AuditSummary(BaseModel):
    """Summary of audit results."""

    master_plan: str
    phases_found: int
    phases_valid: int
    gates_total: int
    errors: int
    warnings: int


class AuditResult(BaseModel):
    """Result of auditing a plan."""

    passed: bool
    issues: list[AuditIssue]
    summary: AuditSummary
