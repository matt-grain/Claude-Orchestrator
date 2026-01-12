"""State management with SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from debussy.core.models import (
    CompletionSignal,
    GateResult,
    MasterPlan,
    PhaseExecution,
    PhaseStatus,
    RunState,
    RunStatus,
)

if TYPE_CHECKING:
    from collections.abc import Generator


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    master_plan_path TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,
    current_phase TEXT
);

CREATE TABLE IF NOT EXISTS phase_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    phase_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    claude_pid INTEGER,
    log_path TEXT,
    error_message TEXT,
    UNIQUE(run_id, phase_id, attempt)
);

CREATE TABLE IF NOT EXISTS gate_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_execution_id INTEGER NOT NULL REFERENCES phase_executions(id),
    gate_name TEXT NOT NULL,
    command TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    output TEXT,
    executed_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS completion_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    phase_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    report TEXT,
    signaled_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    phase_id TEXT NOT NULL,
    step TEXT NOT NULL,
    logged_at TIMESTAMP NOT NULL
);
"""


class StateManager:
    """Manages orchestration state in SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # =========================================================================
    # Run Operations
    # =========================================================================

    def create_run(self, master_plan: MasterPlan) -> str:
        """Create a new orchestration run."""
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, master_plan_path, started_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, str(master_plan.path), now, RunStatus.RUNNING.value),
            )

        return run_id

    def get_run(self, run_id: str) -> RunState | None:
        """Get a run by ID."""
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()

            if row is None:
                return None

            # Get phase executions
            exec_rows = conn.execute(
                "SELECT * FROM phase_executions WHERE run_id = ? ORDER BY attempt",
                (run_id,),
            ).fetchall()

            executions = [
                PhaseExecution(
                    id=r["id"],
                    run_id=r["run_id"],
                    phase_id=r["phase_id"],
                    attempt=r["attempt"],
                    status=PhaseStatus(r["status"]),
                    started_at=_parse_datetime(r["started_at"]),
                    completed_at=_parse_datetime(r["completed_at"]),
                    claude_pid=r["claude_pid"],
                    log_path=Path(r["log_path"]) if r["log_path"] else None,
                    error_message=r["error_message"],
                )
                for r in exec_rows
            ]

            return RunState(
                id=row["id"],
                master_plan_path=Path(row["master_plan_path"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=_parse_datetime(row["completed_at"]),
                status=RunStatus(row["status"]),
                current_phase=row["current_phase"],
                phase_executions=executions,
            )

    def get_current_run(self) -> RunState | None:
        """Get the most recent running or paused run."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM runs
                WHERE status IN (?, ?)
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (RunStatus.RUNNING.value, RunStatus.PAUSED.value),
            ).fetchone()

            if row is None:
                return None

            return self.get_run(row["id"])

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        """Update the status of a run."""
        is_terminal = status in (RunStatus.COMPLETED, RunStatus.FAILED)
        now = datetime.now().isoformat() if is_terminal else None

        with self._connection() as conn:
            if now:
                conn.execute(
                    "UPDATE runs SET status = ?, completed_at = ? WHERE id = ?",
                    (status.value, now, run_id),
                )
            else:
                conn.execute(
                    "UPDATE runs SET status = ? WHERE id = ?",
                    (status.value, run_id),
                )

    def set_current_phase(self, run_id: str, phase_id: str | None) -> None:
        """Set the current phase for a run."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE runs SET current_phase = ? WHERE id = ?",
                (phase_id, run_id),
            )

    # =========================================================================
    # Phase Execution Operations
    # =========================================================================

    def create_phase_execution(
        self,
        run_id: str,
        phase_id: str,
        attempt: int = 1,
    ) -> int:
        """Create a new phase execution record."""
        now = datetime.now().isoformat()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO phase_executions (run_id, phase_id, attempt, status, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, phase_id, attempt, PhaseStatus.RUNNING.value, now),
            )
            return cursor.lastrowid or 0

    def update_phase_status(
        self,
        run_id: str,
        phase_id: str,
        status: PhaseStatus,
        error_message: str | None = None,
    ) -> None:
        """Update the status of the latest phase execution."""
        now = (
            datetime.now().isoformat()
            if status
            in (
                PhaseStatus.COMPLETED,
                PhaseStatus.FAILED,
                PhaseStatus.BLOCKED,
            )
            else None
        )

        with self._connection() as conn:
            if now:
                conn.execute(
                    """
                    UPDATE phase_executions
                    SET status = ?, completed_at = ?, error_message = ?
                    WHERE run_id = ? AND phase_id = ?
                    AND id = (
                        SELECT MAX(id) FROM phase_executions
                        WHERE run_id = ? AND phase_id = ?
                    )
                    """,
                    (status.value, now, error_message, run_id, phase_id, run_id, phase_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE phase_executions
                    SET status = ?, error_message = ?
                    WHERE run_id = ? AND phase_id = ?
                    AND id = (
                        SELECT MAX(id) FROM phase_executions
                        WHERE run_id = ? AND phase_id = ?
                    )
                    """,
                    (status.value, error_message, run_id, phase_id, run_id, phase_id),
                )

    def set_phase_pid(self, run_id: str, phase_id: str, pid: int) -> None:
        """Set the Claude process PID for a phase execution."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE phase_executions
                SET claude_pid = ?
                WHERE run_id = ? AND phase_id = ?
                AND id = (
                    SELECT MAX(id) FROM phase_executions
                    WHERE run_id = ? AND phase_id = ?
                )
                """,
                (pid, run_id, phase_id, run_id, phase_id),
            )

    def set_phase_log_path(self, run_id: str, phase_id: str, log_path: Path) -> None:
        """Set the log file path for a phase execution."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE phase_executions
                SET log_path = ?
                WHERE run_id = ? AND phase_id = ?
                AND id = (
                    SELECT MAX(id) FROM phase_executions
                    WHERE run_id = ? AND phase_id = ?
                )
                """,
                (str(log_path), run_id, phase_id, run_id, phase_id),
            )

    def get_attempt_count(self, run_id: str, phase_id: str) -> int:
        """Get the number of attempts for a phase."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM phase_executions WHERE run_id = ? AND phase_id = ?",
                (run_id, phase_id),
            ).fetchone()
            return row["count"] if row else 0

    # =========================================================================
    # Gate Results
    # =========================================================================

    def record_gate_result(
        self,
        phase_execution_id: int,
        result: GateResult,
    ) -> None:
        """Record a gate result."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO gate_results
                    (phase_execution_id, gate_name, command, passed, output, executed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    phase_execution_id,
                    result.name,
                    result.command,
                    result.passed,
                    result.output,
                    result.executed_at.isoformat(),
                ),
            )

    def get_gate_results(self, phase_execution_id: int) -> list[GateResult]:
        """Get all gate results for a phase execution."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM gate_results WHERE phase_execution_id = ?",
                (phase_execution_id,),
            ).fetchall()

            return [
                GateResult(
                    name=r["gate_name"],
                    command=r["command"],
                    passed=bool(r["passed"]),
                    output=r["output"] or "",
                    executed_at=datetime.fromisoformat(r["executed_at"]),
                )
                for r in rows
            ]

    # =========================================================================
    # Completion Signals
    # =========================================================================

    def record_completion_signal(self, run_id: str, signal: CompletionSignal) -> None:
        """Record a completion signal from a Claude worker."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO completion_signals
                    (run_id, phase_id, status, reason, report, signaled_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    signal.phase_id,
                    signal.status,
                    signal.reason,
                    json.dumps(signal.report) if signal.report else None,
                    signal.signaled_at.isoformat(),
                ),
            )

    def get_completion_signal(self, run_id: str, phase_id: str) -> CompletionSignal | None:
        """Get the latest completion signal for a phase."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM completion_signals
                WHERE run_id = ? AND phase_id = ?
                ORDER BY signaled_at DESC
                LIMIT 1
                """,
                (run_id, phase_id),
            ).fetchone()

            if row is None:
                return None

            return CompletionSignal(
                phase_id=row["phase_id"],
                status=row["status"],
                reason=row["reason"],
                report=json.loads(row["report"]) if row["report"] else None,
                signaled_at=datetime.fromisoformat(row["signaled_at"]),
            )

    # =========================================================================
    # Progress Logging
    # =========================================================================

    def log_progress(self, run_id: str, phase_id: str, step: str) -> None:
        """Log a progress step."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO progress_log (run_id, phase_id, step, logged_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, phase_id, step, datetime.now().isoformat()),
            )

    def get_progress(self, run_id: str, phase_id: str) -> list[tuple[str, datetime]]:
        """Get progress log for a phase."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT step, logged_at FROM progress_log
                WHERE run_id = ? AND phase_id = ?
                ORDER BY logged_at
                """,
                (run_id, phase_id),
            ).fetchall()

            return [(r["step"], datetime.fromisoformat(r["logged_at"])) for r in rows]

    # =========================================================================
    # Utilities
    # =========================================================================

    def list_runs(self, limit: int = 10) -> list[RunState]:
        """List recent runs."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            runs: list[RunState] = []
            for r in rows:
                run = self.get_run(r["id"])
                if run is not None:
                    runs.append(run)
            return runs


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string."""
    if value is None:
        return None
    return datetime.fromisoformat(value)
