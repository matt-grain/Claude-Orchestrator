"""Validation gate runner."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from debussy.core.models import Gate, GateResult, Phase


class GateRunner:
    """Executes validation gates."""

    def __init__(self, project_root: Path, timeout: int = 300) -> None:
        self.project_root = project_root
        self.timeout = timeout  # Per-gate timeout

    async def run_gates(self, phase: Phase) -> list[GateResult]:
        """Run all gates for a phase.

        Args:
            phase: The phase containing gate definitions

        Returns:
            List of GateResult objects
        """
        results: list[GateResult] = []

        for gate in phase.gates:
            result = await self._run_single_gate(gate)
            results.append(result)

            # Stop on first blocking failure
            if not result.passed and gate.blocking:
                break

        return results

    async def run_gate(self, gate: Gate) -> GateResult:
        """Run a single gate.

        Args:
            gate: The gate to run

        Returns:
            GateResult with pass/fail status
        """
        return await self._run_single_gate(gate)

    async def _run_single_gate(self, gate: Gate) -> GateResult:
        """Execute a single gate command."""
        try:
            process = await asyncio.create_subprocess_shell(
                gate.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return GateResult(
                    name=gate.name,
                    command=gate.command,
                    passed=False,
                    output=f"TIMEOUT after {self.timeout} seconds",
                    executed_at=datetime.now(),
                )

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += f"\n\nSTDERR:\n{stderr.decode('utf-8', errors='replace')}"

            return GateResult(
                name=gate.name,
                command=gate.command,
                passed=process.returncode == 0,
                output=output,
                executed_at=datetime.now(),
            )

        except Exception as e:
            return GateResult(
                name=gate.name,
                command=gate.command,
                passed=False,
                output=f"Error executing gate: {e}",
                executed_at=datetime.now(),
            )

    async def run_single_gate_by_name(
        self,
        phase: Phase,
        gate_name: str,
    ) -> GateResult | None:
        """Run a single gate by name.

        Args:
            phase: The phase containing gate definitions
            gate_name: Name of the gate to run

        Returns:
            GateResult or None if gate not found
        """
        for gate in phase.gates:
            if gate.name.lower() == gate_name.lower():
                return await self._run_single_gate(gate)
        return None

    async def verify_all_gates_pass(self, phase: Phase) -> tuple[bool, list[GateResult]]:
        """Verify that all gates pass.

        Returns:
            Tuple of (all_passed, results)
        """
        results = await self.run_gates(phase)
        all_passed = all(r.passed for r in results)
        return all_passed, results
