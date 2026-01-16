"""Parser for phase plan files."""

from __future__ import annotations

import re
from pathlib import Path

from debussy.core.models import Gate, Phase, PhaseStatus, Task


def parse_phase(phase_path: Path, phase_id: str | None = None) -> Phase:
    """Parse a phase plan markdown file.

    Expected format with markers for required elements:
    ```markdown
    # Feature Phase 1: Title

    **Status:** Pending

    ## Process Wrapper (MANDATORY)
    - [ ] Read previous notes: `notes/NOTES_*_phase_0.md`
    - [ ] **AGENT:doc-sync-manager** - sync tasks
    - [ ] **[IMPLEMENTATION]**
    - [ ] **AGENT:task-validator** - validation
    - [ ] Write notes to: `notes/NOTES_*_phase_1.md`

    ## Gates
    - ruff: 0 errors
    - pyright: 0 errors

    ## Tasks
    ### 1. Task Group
    - [ ] 1.1: Do something
    ```
    """
    content = phase_path.read_text(encoding="utf-8")

    # Extract title from first H1
    title_match = re.search(r"^#\s+.+Phase\s+\d+:\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else phase_path.stem

    # Extract phase ID from filename if not provided
    resolved_phase_id: str
    if phase_id is not None:
        resolved_phase_id = phase_id
    else:
        id_match = re.search(r"phase[_-]?(\d+)", phase_path.stem, re.IGNORECASE)
        resolved_phase_id = id_match.group(1) if id_match else "1"

    # Extract status
    status = _parse_status_field(content)

    # Extract dependencies
    depends_on = _parse_dependencies(content)

    # Extract gates
    gates = _parse_gates(content)

    # Extract tasks
    tasks = _parse_tasks(content)

    # Extract required agents from process wrapper
    required_agents = _parse_required_agents(content)

    # Extract required steps
    required_steps = _parse_required_steps(content)

    # Extract notes paths
    notes_input, notes_output = _parse_notes_paths(content)

    return Phase(
        id=resolved_phase_id,
        title=title,
        path=phase_path,
        status=status,
        depends_on=depends_on,
        gates=gates,
        tasks=tasks,
        required_agents=required_agents,
        required_steps=required_steps,
        notes_input=notes_input,
        notes_output=notes_output,
    )


def _parse_status_field(content: str) -> PhaseStatus:
    """Extract status from **Status:** field."""
    match = re.search(r"\*\*Status:\*\*\s*(\w+)", content)
    if match:
        status_str = match.group(1).lower()
        status_map = {
            "pending": PhaseStatus.PENDING,
            "running": PhaseStatus.RUNNING,
            "in_progress": PhaseStatus.RUNNING,
            "validating": PhaseStatus.VALIDATING,
            "completed": PhaseStatus.COMPLETED,
            "complete": PhaseStatus.COMPLETED,
            "failed": PhaseStatus.FAILED,
            "blocked": PhaseStatus.BLOCKED,
        }
        return status_map.get(status_str, PhaseStatus.PENDING)
    return PhaseStatus.PENDING


def _parse_dependencies(content: str) -> list[str]:
    """Extract phase dependencies.

    Only matches explicit dependency declarations, not casual mentions of "Phase X".
    Valid patterns:
    - **Depends On:** Phase 1, Phase 2
    - **Depends On:** Phase 1 (description)
    - Previous phase: Phase 1
    - Depends on Phase 1
    """
    deps: list[str] = []

    # Look for "Depends On:" field in header (most reliable)
    # Matches: **Depends On:** Phase 1, Phase 2, Phase 3
    # Also handles: **Depends On:** Phase 1 (description), Phase 2 (description)
    dep_header = re.search(r"\*\*Depends On:\*\*\s*(.+?)(?:\n|$)", content)
    if dep_header:
        dep_line = dep_header.group(1).strip()
        # Skip if explicitly no dependencies (N/A, None, etc.)
        if not dep_line.lower().startswith(("n/a", "none", "-", "no ")):
            # Find all Phase references in the Depends On line (may have multiple)
            phase_refs = re.findall(r"Phase\s+(\d+(?:\.\d+)?)", dep_line)
            deps.extend(phase_refs)

    # Check dependency section for explicit dependency declarations only
    dep_section = re.search(r"## Dependencies\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if dep_section:
        section_content = dep_section.group(1)
        # Only match lines that explicitly declare a dependency:
        # - Previous phase: Phase X
        # - Depends on: Phase X
        # - Requires: Phase X
        # NOT casual mentions like "used by Phase X" or "output for Phase X"
        explicit_dep_patterns = [
            r"Previous phase:\s*Phase\s+(\d+(?:\.\d+)?)",
            r"Depends on:\s*Phase\s+(\d+(?:\.\d+)?)",
            r"Requires:\s*Phase\s+(\d+(?:\.\d+)?)",
            r"^[-*]\s*Phase\s+(\d+(?:\.\d+)?)",  # Bullet point starting with Phase
        ]
        for pattern in explicit_dep_patterns:
            matches = re.findall(pattern, section_content, re.MULTILINE | re.IGNORECASE)
            deps.extend(matches)

    return list(set(deps))  # Deduplicate


def _parse_gates(content: str) -> list[Gate]:
    """Extract validation gates."""
    gates: list[Gate] = []

    # Find Gates section
    gates_section = re.search(r"## Gates.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not gates_section:
        return gates

    section_content = gates_section.group(1)

    # Parse gate lines: "- gate_name: requirement" or "- **gate_name**: requirement"
    # Note: [\w-]+ allows hyphenated names like "backend-lint", "type-check"
    gate_pattern = re.compile(r"^[-*]\s+\*{0,2}([\w-]+)\*{0,2}:\s*(.+)$", re.MULTILINE)
    for match in gate_pattern.finditer(section_content):
        name = match.group(1).strip()
        requirement = match.group(2).strip()

        # Generate command based on gate name
        command = _gate_name_to_command(name, requirement)

        gates.append(Gate(name=name, command=command, blocking=True))

    return gates


def _gate_name_to_command(name: str, _requirement: str) -> str:
    """Convert gate name to actual command."""
    # Common gate commands (requirement unused but kept for future use)
    gate_commands = {
        "ruff": "uv run ruff check .",
        "pyright": "uv run pyright",
        "ty": "uv run ty check .",
        "bandit": "uv run bandit -r src/ -x ./tests",
        "radon": "uv run radon cc src/ -a -nc",
        "tests": "uv run pytest",
        "pytest": "uv run pytest",
        "coverage": "uv run pytest --cov",
        "tsc": "pnpm exec tsc --noEmit",
        "eslint": "pnpm lint",
        "build": "pnpm build",
    }

    return gate_commands.get(name.lower(), f"echo 'Unknown gate: {name}'")


def _parse_tasks(content: str) -> list[Task]:
    """Extract tasks from the Tasks section."""
    tasks: list[Task] = []

    # Find Tasks section
    tasks_section = re.search(r"## Tasks\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not tasks_section:
        return tasks

    section_content = tasks_section.group(1)

    # Parse task lines: "- [ ] 1.1: Description" or "- [x] 1.1: Description"
    task_pattern = re.compile(r"^[-*]\s+\[([ xX])\]\s+(\d+\.\d+):\s*(.+)$", re.MULTILINE)
    for match in task_pattern.finditer(section_content):
        completed = match.group(1).lower() == "x"
        task_id = match.group(2)
        description = match.group(3).strip()

        tasks.append(Task(id=task_id, description=description, completed=completed))

    return tasks


def _parse_required_agents(content: str) -> list[str]:
    """Extract required agents from process wrapper."""
    agents: list[str] = []

    # Look for AGENT: markers in process wrapper
    # Pattern: **AGENT:agent-name** or AGENT:agent-name
    agent_pattern = re.compile(r"\*{0,2}AGENT:(\S+)\*{0,2}", re.IGNORECASE)
    for match in agent_pattern.finditer(content):
        agent_name = match.group(1).strip("*").strip()
        if agent_name not in agents:
            agents.append(agent_name)

    # Also look in "Agents to Use" table for REQUIRED agents
    agents_table = re.search(r"## Agents to Use.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if agents_table:
        # Find rows with REQUIRED
        required_rows = re.findall(r"\|\s*`?(\S+)`?\s*\|[^|]*REQUIRED", agents_table.group(1))
        for agent in required_rows:
            if agent not in agents:
                agents.append(agent)

    return agents


def _parse_required_steps(content: str) -> list[str]:
    """Extract required steps from process wrapper."""
    steps: list[str] = []

    # Find Process Wrapper section
    wrapper_section = re.search(r"## Process Wrapper.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not wrapper_section:
        return steps

    section_content = wrapper_section.group(1)

    # Common steps to look for
    step_patterns = [
        (r"Read previous notes", "read_previous_notes"),
        (r"doc-sync-manager|AGENT:doc-sync-manager", "doc_sync_manager"),
        (r"\[IMPLEMENTATION\]", "implementation"),
        (r"Pre-validation|pre-validation", "pre_validation"),
        (r"task-validator|AGENT:task-validator", "task_validator"),
        (r"Write.*notes|notes.*output", "write_notes"),
    ]

    for pattern, step_name in step_patterns:
        if re.search(pattern, section_content, re.IGNORECASE):
            steps.append(step_name)

    return steps


def _parse_notes_paths(content: str) -> tuple[Path | None, Path | None]:
    """Extract notes input and output paths."""
    notes_input = None
    notes_output = None

    # Look for notes input: "Read previous notes: `path`"
    input_match = re.search(r"Read previous notes:\s*`([^`]+)`", content)
    if input_match:
        path_str = input_match.group(1)
        if path_str.lower() not in ("n/a", "none", "n/a (first phase)"):
            notes_input = Path(path_str)

    # Look for notes output: "Write `path`" or "notes to: `path`"
    output_match = re.search(r"(?:Write|notes to:?)\s*`([^`]+)`", content, re.IGNORECASE)
    if output_match:
        notes_output = Path(output_match.group(1))

    return notes_input, notes_output
