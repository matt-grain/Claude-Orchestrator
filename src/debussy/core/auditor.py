"""Plan auditor for deterministic validation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from debussy.core.audit import AuditIssue, AuditResult, AuditSeverity, AuditSummary
from debussy.parsers.master import parse_master_plan
from debussy.parsers.phase import parse_phase

if TYPE_CHECKING:
    from debussy.core.models import MasterPlan, Phase


class PlanAuditor:
    """Auditor for validating plan structure deterministically."""

    def audit(self, master_plan_path: Path) -> AuditResult:
        """Run all audit checks on a master plan.

        Args:
            master_plan_path: Path to the master plan markdown file.

        Returns:
            AuditResult with pass/fail and list of issues.
        """
        issues: list[AuditIssue] = []

        # Check master plan exists and can be parsed
        try:
            master = parse_master_plan(master_plan_path)
        except FileNotFoundError:
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.ERROR,
                    code="MASTER_NOT_FOUND",
                    message=f"Master plan not found: {master_plan_path}",
                    location=str(master_plan_path),
                )
            )
            return AuditResult(
                passed=False,
                issues=issues,
                summary=AuditSummary(
                    master_plan=str(master_plan_path),
                    phases_found=0,
                    phases_valid=0,
                    gates_total=0,
                    errors=1,
                    warnings=0,
                ),
            )
        except Exception as e:
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.ERROR,
                    code="MASTER_PARSE_ERROR",
                    message=f"Failed to parse master plan: {e}",
                    location=str(master_plan_path),
                )
            )
            return AuditResult(
                passed=False,
                issues=issues,
                summary=AuditSummary(
                    master_plan=str(master_plan_path),
                    phases_found=0,
                    phases_valid=0,
                    gates_total=0,
                    errors=1,
                    warnings=0,
                ),
            )

        # Validate master plan structure
        issues.extend(self._check_master_plan(master))

        # Parse and validate each phase
        phases_valid = 0
        gates_total = 0
        parsed_phases: list[Phase] = []

        for phase in master.phases:
            phase_issues = self._check_phase_file(phase)
            issues.extend(phase_issues)

            # Only parse if phase file exists
            if phase.path.exists():
                try:
                    detailed_phase = parse_phase(phase.path, phase.id)
                    parsed_phases.append(detailed_phase)

                    # Check gates and notes paths
                    issues.extend(self._check_gates(detailed_phase))
                    issues.extend(self._check_notes_paths(detailed_phase))

                    gates_total += len(detailed_phase.gates)
                    if not any(i.severity == AuditSeverity.ERROR for i in phase_issues):
                        phases_valid += 1
                except Exception as e:
                    issues.append(
                        AuditIssue(
                            severity=AuditSeverity.ERROR,
                            code="PHASE_PARSE_ERROR",
                            message=f"Failed to parse phase: {e}",
                            location=str(phase.path),
                        )
                    )

        # Check dependency graph
        issues.extend(self._check_dependencies(parsed_phases))

        # Calculate summary
        errors = sum(1 for i in issues if i.severity == AuditSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == AuditSeverity.WARNING)

        summary = AuditSummary(
            master_plan=master.name,
            phases_found=len(master.phases),
            phases_valid=phases_valid,
            gates_total=gates_total,
            errors=errors,
            warnings=warnings,
        )

        passed = errors == 0

        return AuditResult(passed=passed, issues=issues, summary=summary)

    def _check_master_plan(self, master: MasterPlan) -> list[AuditIssue]:
        """Validate master plan structure.

        Args:
            master: Parsed master plan.

        Returns:
            List of audit issues found.
        """
        issues: list[AuditIssue] = []

        # Check if phases table is empty
        if not master.phases:
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.ERROR,
                    code="NO_PHASES",
                    message="Master plan has no phases defined",
                    location=str(master.path),
                )
            )

        return issues

    def _check_phase_file(self, phase: Phase) -> list[AuditIssue]:
        """Validate phase file exists.

        Args:
            phase: Phase metadata from master plan.

        Returns:
            List of audit issues found.
        """
        issues: list[AuditIssue] = []

        if not phase.path.exists():
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.ERROR,
                    code="PHASE_NOT_FOUND",
                    message=f"Phase file not found: {phase.path.name}",
                    location=str(phase.path),
                )
            )

        return issues

    def _check_gates(self, phase: Phase) -> list[AuditIssue]:
        """Validate phase has gates defined.

        Args:
            phase: Parsed phase.

        Returns:
            List of audit issues found.
        """
        issues: list[AuditIssue] = []

        if not phase.gates:
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.ERROR,
                    code="MISSING_GATES",
                    message=f"Phase {phase.id} has no gates defined (critical for validation)",
                    location=str(phase.path),
                )
            )

        return issues

    def _check_notes_paths(self, phase: Phase) -> list[AuditIssue]:
        """Validate notes paths are specified.

        Args:
            phase: Parsed phase.

        Returns:
            List of audit issues found.
        """
        issues: list[AuditIssue] = []

        if not phase.notes_output:
            issues.append(
                AuditIssue(
                    severity=AuditSeverity.WARNING,
                    code="NO_NOTES_OUTPUT",
                    message=f"Phase {phase.id} has no notes output path specified",
                    location=str(phase.path),
                )
            )

        return issues

    def _check_dependencies(self, phases: list[Phase]) -> list[AuditIssue]:
        """Validate dependency graph is valid.

        Args:
            phases: List of parsed phases.

        Returns:
            List of audit issues found.
        """
        issues: list[AuditIssue] = []

        phase_ids = {p.id for p in phases}

        for phase in phases:
            # Check if dependencies exist
            for dep_id in phase.depends_on:
                if dep_id not in phase_ids:
                    issues.append(
                        AuditIssue(
                            severity=AuditSeverity.WARNING,
                            code="MISSING_DEPENDENCY",
                            message=f"Phase {phase.id} depends on non-existent phase {dep_id}",
                            location=str(phase.path),
                        )
                    )

            # Check for circular dependencies (simple case: self-reference)
            if phase.id in phase.depends_on:
                issues.append(
                    AuditIssue(
                        severity=AuditSeverity.ERROR,
                        code="CIRCULAR_DEPENDENCY",
                        message=f"Phase {phase.id} depends on itself",
                        location=str(phase.path),
                    )
                )

        # Check for circular dependencies (complex case: cycles in graph)
        issues.extend(self._check_dependency_cycles(phases))

        return issues

    def _check_dependency_cycles(self, phases: list[Phase]) -> list[AuditIssue]:
        """Check for circular dependencies in phase graph.

        Args:
            phases: List of parsed phases.

        Returns:
            List of audit issues for circular dependencies.
        """
        issues: list[AuditIssue] = []

        # Build adjacency list
        graph: dict[str, list[str]] = {p.id: p.depends_on for p in phases}

        # DFS to detect cycles
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(node: str, path: list[str]) -> list[str] | None:
            """DFS helper to detect cycles.

            Args:
                node: Current node ID.
                path: Current path from root.

            Returns:
                Path forming the cycle if found, None otherwise.
            """
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    cycle = has_cycle(neighbor, path[:])
                    if cycle:
                        return cycle
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return [*path[cycle_start:], neighbor]

            rec_stack.remove(node)
            return None

        # Check each unvisited node
        for phase in phases:
            if phase.id not in visited:
                cycle = has_cycle(phase.id, [])
                if cycle:
                    cycle_str = " -> ".join(cycle)
                    issues.append(
                        AuditIssue(
                            severity=AuditSeverity.ERROR,
                            code="CIRCULAR_DEPENDENCY",
                            message=f"Circular dependency detected: {cycle_str}",
                            location=None,
                        )
                    )
                    break  # Only report first cycle found

        return issues
