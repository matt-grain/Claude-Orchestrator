"""Parser for master plan files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from debussy.core.models import MasterPlan, Phase, PhaseStatus


def parse_master_plan(master_path: Path) -> MasterPlan:
    """Parse a master plan markdown file.

    Expected format:
    ```markdown
    # Feature Name - Master Plan

    ## Phases

    | Phase | Title | Focus | Risk | Status |
    |-------|-------|-------|------|--------|
    | 1 | [Unit of Work](feature-phase1.md) | ... | Low | Pending |
    | 2 | [State Model](feature-phase2.md) | ... | Low | Pending |
    ```
    """
    content = master_path.read_text(encoding="utf-8")

    # Extract name from first H1
    name_match = re.search(r"^#\s+(.+?)(?:\s*-\s*Master Plan)?$", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else master_path.stem

    # Find the phases table
    phases = _parse_phases_table(content, master_path.parent)

    return MasterPlan(
        name=name,
        path=master_path,
        phases=phases,
        created_at=datetime.now(),
    )


def _parse_phases_table(content: str, base_dir: Path) -> list[Phase]:
    """Parse the phases table from markdown content."""
    phases: list[Phase] = []

    # Find table with Phase column
    # Match table rows: | 1 | [Title](path.md) | Focus | Risk | Status |
    table_pattern = re.compile(
        r"^\|\s*(\d+)\s*\|"  # Phase number
        r"\s*\[([^\]]+)\]\(([^)]+)\)\s*\|"  # [Title](path.md)
        r"\s*[^|]*\|"  # Focus (skip)
        r"\s*[^|]*\|"  # Risk (skip)
        r"\s*(\w+)\s*\|",  # Status
        re.MULTILINE,
    )

    for match in table_pattern.finditer(content):
        phase_num = match.group(1)
        title = match.group(2).strip()
        rel_path = match.group(3).strip()
        status_str = match.group(4).strip().lower()

        # Convert status string to enum
        status = _parse_status(status_str)

        # Resolve path relative to master plan
        phase_path = base_dir / rel_path

        phases.append(
            Phase(
                id=phase_num,
                title=title,
                path=phase_path,
                status=status,
            )
        )

    return phases


def _parse_status(status_str: str) -> PhaseStatus:
    """Convert status string to PhaseStatus enum."""
    status_map = {
        "pending": PhaseStatus.PENDING,
        "in progress": PhaseStatus.RUNNING,
        "in_progress": PhaseStatus.RUNNING,
        "running": PhaseStatus.RUNNING,
        "validating": PhaseStatus.VALIDATING,
        "complete": PhaseStatus.COMPLETED,
        "completed": PhaseStatus.COMPLETED,
        "done": PhaseStatus.COMPLETED,
        "failed": PhaseStatus.FAILED,
        "blocked": PhaseStatus.BLOCKED,
        "awaiting": PhaseStatus.AWAITING_HUMAN,
        "awaiting_human": PhaseStatus.AWAITING_HUMAN,
    }
    return status_map.get(status_str.lower(), PhaseStatus.PENDING)
