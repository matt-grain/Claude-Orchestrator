"""Tier 1 deterministic structural checks for plan conversion quality."""

from __future__ import annotations

import re
from pathlib import Path


def count_phases_in_freeform(content: str) -> int:
    """Count phases in freeform plan content.

    Detects common patterns:
    - "### Phase:" or "## Phase:" headers
    - "Phase 1:", "Phase 2:" numbered
    - "Sprint 1:", "Sprint 2:" agile style
    - "Module 1:", "Module 2:" modular style

    Args:
        content: Raw markdown content of the source plan.

    Returns:
        Estimated number of phases/sprints/modules found.
    """
    patterns = [
        r"^#{1,3}\s*Phase[:\s]",  # ### Phase: or ## Phase
        r"^#{1,3}\s*Phase\s+\d+",  # ### Phase 1
        r"^#{1,3}\s*Sprint[:\s]",  # ### Sprint:
        r"^#{1,3}\s*Sprint\s+\d+",  # ### Sprint 1
        r"^#{1,3}\s*Module[:\s]",  # ### Module:
        r"^#{1,3}\s*Module\s+\d+",  # ### Module 1
        r"^\d+\.\s*(Phase|Sprint|Module)",  # 1. Phase, 2. Sprint
    ]

    combined = "|".join(f"({p})" for p in patterns)
    matches = re.findall(combined, content, re.MULTILINE | re.IGNORECASE)
    return len(matches)


def count_phases_in_directory(source_dir: Path) -> int:
    """Count phases by looking at separate phase files in directory.

    Args:
        source_dir: Directory containing source plan files.

    Returns:
        Number of phase-like files found (excluding master/overview files).
    """
    if not source_dir.is_dir():
        return 0

    # Common patterns for phase files
    phase_patterns = [
        r"phase[-_]?\d+",
        r"sprint[-_]?\d+",
        r"module[-_]?\d+",
        r".*_phase\.md$",
        r".*_sprint\.md$",
        r".*_module\.md$",
    ]

    # Files to exclude (master/overview)
    exclude_patterns = [
        r"master",
        r"overview",
        r"readme",
        r"project_plan",
        r"plan_overview",
    ]

    count = 0
    for md_file in source_dir.glob("*.md"):
        name = md_file.stem.lower()

        # Skip master/overview files
        if any(re.search(p, name) for p in exclude_patterns):
            continue

        # Count if matches phase pattern
        if any(re.search(p, name) for p in phase_patterns):
            count += 1

    return count


def check_filename_convention(output_dir: Path) -> tuple[bool, list[str]]:
    """Check if output files follow Debussy naming convention.

    Expected pattern: phase-{N}.md or phase-{N}-{title}.md

    Args:
        output_dir: Directory containing converted plan files.

    Returns:
        Tuple of (all_valid, list of invalid filenames).
    """
    invalid = []
    valid_pattern = re.compile(r"^phase-\d+(-[\w-]+)?\.md$", re.IGNORECASE)

    for md_file in output_dir.glob("phase-*.md"):
        if not valid_pattern.match(md_file.name.lower()):
            invalid.append(md_file.name)

    return len(invalid) == 0, invalid


def check_master_plan_exists(output_dir: Path) -> bool:
    """Check if MASTER_PLAN.md exists in output directory."""
    return (output_dir / "MASTER_PLAN.md").exists()
