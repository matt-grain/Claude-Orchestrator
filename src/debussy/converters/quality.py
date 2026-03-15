"""Quality metrics for evaluating plan conversion fidelity.

This module provides metrics to evaluate how well a converted plan preserves
the content and intent of the original freeform plan.

Metrics are organized in tiers by complexity:
- Tier 1: Deterministic checks (phase count, agents, filenames)
- Tier 2: Keyword extraction (tech stack, task keywords, risk mentions)
- Tier 3a: Jaccard similarity (word-level overlap, no ML deps)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Re-export all public symbols so existing importers of quality.py continue to work.
from debussy.converters.checks import (
    AGENT_KEYWORDS,
    RISK_KEYWORDS,
    STOPWORDS,
    TECH_KEYWORDS,
    TEMPLATE_BOILERPLATE,
    extract_keywords,
    preprocess_markdown,
    tokenize,
)
from debussy.converters.checks.keywords import (
    extract_agent_references,
    extract_risk_mentions,
    extract_task_keywords,
    extract_tech_stack,
)
from debussy.converters.checks.similarity import (
    jaccard_similarity,
    preprocessed_jaccard_similarity,
    preprocessed_weighted_jaccard,
    weighted_jaccard_similarity,
)
from debussy.converters.checks.structure import (
    check_filename_convention,
    check_master_plan_exists,
    count_phases_in_directory,
    count_phases_in_freeform,
)

__all__ = [
    "AGENT_KEYWORDS",
    "RISK_KEYWORDS",
    "STOPWORDS",
    "TECH_KEYWORDS",
    "TEMPLATE_BOILERPLATE",
    "ConversionQuality",
    "ConversionQualityEvaluator",
    "check_filename_convention",
    "check_master_plan_exists",
    "count_phases_in_directory",
    "count_phases_in_freeform",
    "extract_agent_references",
    "extract_keywords",
    "extract_risk_mentions",
    "extract_task_keywords",
    "extract_tech_stack",
    "jaccard_similarity",
    "preprocess_markdown",
    "preprocessed_jaccard_similarity",
    "preprocessed_weighted_jaccard",
    "tokenize",
    "weighted_jaccard_similarity",
]


# =============================================================================
# ConversionQuality Dataclass
# =============================================================================


@dataclass
class ConversionQuality:
    """Comprehensive conversion quality metrics.

    Combines Tier 1-3a metrics for evaluating conversion fidelity.
    """

    # Tier 1: Deterministic checks
    source_phase_count: int = 0
    converted_phase_count: int = 0
    phase_count_match: bool = False

    master_plan_exists: bool = False
    filenames_valid: bool = False
    invalid_filenames: list[str] = field(default_factory=list)

    # Tier 2: Keyword preservation
    source_tech_stack: set[str] = field(default_factory=set)
    converted_tech_stack: set[str] = field(default_factory=set)
    tech_preserved: bool = False
    tech_lost: set[str] = field(default_factory=set)

    source_agents: set[str] = field(default_factory=set)
    converted_agents: set[str] = field(default_factory=set)
    agents_preserved: bool = False
    agents_lost: set[str] = field(default_factory=set)

    source_risks: set[str] = field(default_factory=set)
    converted_risks: set[str] = field(default_factory=set)
    risks_preserved: bool = False
    risks_lost: set[str] = field(default_factory=set)

    source_task_verbs: set[str] = field(default_factory=set)
    converted_task_verbs: set[str] = field(default_factory=set)

    # Tier 3a: Similarity metrics (raw)
    jaccard_similarity: float = 0.0
    weighted_jaccard_similarity: float = 0.0

    # Tier 3a: Similarity metrics (preprocessed - more accurate)
    preprocessed_jaccard: float = 0.0
    preprocessed_weighted_jaccard: float = 0.0

    # Gate validation (from audit)
    gates_valid: bool = False
    gates_count: int = 0

    @property
    def tier1_score(self) -> float:
        """Score from Tier 1 checks (0-1)."""
        checks = [
            self.phase_count_match,
            self.master_plan_exists,
            self.filenames_valid,
            self.gates_valid,
        ]
        return sum(checks) / len(checks) if checks else 0.0

    @property
    def tier2_score(self) -> float:
        """Score from Tier 2 keyword preservation (0-1)."""
        checks = [
            self.tech_preserved,
            self.agents_preserved,
            self.risks_preserved,
        ]
        return sum(checks) / len(checks) if checks else 0.0

    @property
    def tier3a_score(self) -> float:
        """Score from Tier 3a similarity (0-1).

        Uses preprocessed metrics if available, falls back to raw.
        """
        # Prefer preprocessed metrics (more accurate)
        if self.preprocessed_jaccard > 0 or self.preprocessed_weighted_jaccard > 0:
            return (self.preprocessed_jaccard + self.preprocessed_weighted_jaccard) / 2
        # Fall back to raw metrics
        return (self.jaccard_similarity + self.weighted_jaccard_similarity) / 2

    @property
    def quick_score(self) -> float:
        """Quick overall quality score using Tier 1-2 metrics (0-1)."""
        # Use preprocessed similarity if available (threshold 0.3 for preprocessed)
        similarity_ok = self.preprocessed_jaccard > 0.3 if self.preprocessed_jaccard > 0 else self.jaccard_similarity > 0.2
        checks = [
            self.phase_count_match,
            self.master_plan_exists,
            self.filenames_valid,
            self.gates_valid,
            self.tech_preserved,
            self.agents_preserved,
            similarity_ok,
        ]
        return sum(checks) / len(checks) if checks else 0.0

    @property
    def full_score(self) -> float:
        """Comprehensive quality score (0-1).

        Weighted combination of all tiers:
        - Tier 1: 40% (structural correctness is critical)
        - Tier 2: 35% (content preservation matters)
        - Tier 3a: 25% (similarity is a softer signal)
        """
        return self.tier1_score * 0.40 + self.tier2_score * 0.35 + self.tier3a_score * 0.25

    def summary(self) -> str:
        """Human-readable summary of quality metrics."""
        lines = [
            "Conversion Quality Report",
            "=" * 40,
            "",
            "Tier 1: Structural Checks",
            f"  Phase count: {self.source_phase_count} → {self.converted_phase_count} {'✓' if self.phase_count_match else '✗'}",
            f"  Master plan exists: {'✓' if self.master_plan_exists else '✗'}",
            f"  Filename convention: {'✓' if self.filenames_valid else '✗'}",
            f"  Gates valid: {'✓' if self.gates_valid else '✗'} ({self.gates_count} gates)",
            f"  Tier 1 Score: {self.tier1_score:.0%}",
            "",
            "Tier 2: Content Preservation",
            f"  Tech stack: {len(self.converted_tech_stack)}/{len(self.source_tech_stack)} preserved {'✓' if self.tech_preserved else '✗'}",
        ]

        if self.tech_lost:
            lines.append(f"    Lost: {', '.join(sorted(self.tech_lost))}")

        lines.extend(
            [
                f"  Agents: {len(self.converted_agents)}/{len(self.source_agents)} preserved {'✓' if self.agents_preserved else '✗'}",
            ]
        )

        if self.agents_lost:
            lines.append(f"    Lost: {', '.join(sorted(self.agents_lost))}")

        # Risk preservation: source risks should appear in converted (more is OK)
        risk_status = "✓" if self.risks_preserved else "✗"
        if len(self.source_risks) == 0:
            risk_display = "N/A (none in source)"
        elif self.risks_preserved:
            extra = len(self.converted_risks) - len(self.source_risks)
            risk_display = f"all {len(self.source_risks)} preserved (+{extra} added)" if extra > 0 else f"all {len(self.source_risks)} preserved"
        else:
            risk_display = f"{len(self.source_risks - self.risks_lost)}/{len(self.source_risks)} preserved"

        lines.append(f"  Risk mentions: {risk_display} {risk_status}")

        if self.risks_lost:
            lines.append(f"    Lost: {', '.join(sorted(self.risks_lost))}")

        lines.extend(
            [
                f"  Tier 2 Score: {self.tier2_score:.0%}",
                "",
                "Tier 3a: Text Similarity",
                f"  Raw Jaccard: {self.jaccard_similarity:.2%}",
                f"  Raw Weighted: {self.weighted_jaccard_similarity:.2%}",
                f"  Preprocessed Jaccard: {self.preprocessed_jaccard:.2%}",
                f"  Preprocessed Weighted: {self.preprocessed_weighted_jaccard:.2%}",
                f"  Tier 3a Score: {self.tier3a_score:.0%}",
                "",
                "=" * 40,
                f"Quick Score: {self.quick_score:.0%}",
                f"Full Score:  {self.full_score:.0%}",
            ]
        )

        return "\n".join(lines)


# =============================================================================
# Evaluator Class
# =============================================================================


class ConversionQualityEvaluator:
    """Evaluates the quality of a plan conversion."""

    def __init__(
        self,
        source_dir: Path,
        output_dir: Path,
        source_content: str | None = None,
        converted_content: str | None = None,
    ):
        """Initialize the evaluator.

        Args:
            source_dir: Directory containing source freeform plan.
            output_dir: Directory containing converted Debussy plan.
            source_content: Optional pre-loaded source content.
            converted_content: Optional pre-loaded converted content.
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self._source_content = source_content
        self._converted_content = converted_content

    def _load_source_content(self) -> str:
        """Load all source markdown files into single string."""
        if self._source_content:
            return self._source_content

        content_parts = []
        for md_file in sorted(self.source_dir.glob("*.md")):
            content_parts.append(md_file.read_text(encoding="utf-8"))

        return "\n\n".join(content_parts)

    def _load_converted_content(self) -> str:
        """Load all converted markdown files into single string."""
        if self._converted_content:
            return self._converted_content

        content_parts = []
        for md_file in sorted(self.output_dir.glob("*.md")):
            content_parts.append(md_file.read_text(encoding="utf-8"))

        return "\n\n".join(content_parts)

    def evaluate(
        self,
        audit_result: Any | None = None,
    ) -> ConversionQuality:
        """Evaluate conversion quality.

        Args:
            audit_result: Optional AuditResult from PlanAuditor for gate info.

        Returns:
            ConversionQuality with all metrics populated.
        """
        source = self._load_source_content()
        converted = self._load_converted_content()

        quality = ConversionQuality()

        # Tier 1: Structural checks
        quality.source_phase_count = max(
            count_phases_in_freeform(source),
            count_phases_in_directory(self.source_dir),
        )

        # Count converted phases from audit or files
        if audit_result and hasattr(audit_result, "summary"):
            quality.converted_phase_count = audit_result.summary.phases_found
            quality.gates_valid = audit_result.summary.errors == 0
            quality.gates_count = audit_result.summary.gates_total
        else:
            quality.converted_phase_count = len(list(self.output_dir.glob("phase-*.md")))

        quality.phase_count_match = quality.source_phase_count == quality.converted_phase_count

        quality.master_plan_exists = check_master_plan_exists(self.output_dir)

        quality.filenames_valid, quality.invalid_filenames = check_filename_convention(self.output_dir)

        # Tier 2: Keyword preservation
        quality.source_tech_stack = extract_tech_stack(source)
        quality.converted_tech_stack = extract_tech_stack(converted)
        quality.tech_lost = quality.source_tech_stack - quality.converted_tech_stack
        quality.tech_preserved = len(quality.tech_lost) == 0

        quality.source_agents = extract_agent_references(source)
        quality.converted_agents = extract_agent_references(converted)
        quality.agents_lost = quality.source_agents - quality.converted_agents
        quality.agents_preserved = len(quality.agents_lost) == 0

        quality.source_risks = extract_risk_mentions(source)
        quality.converted_risks = extract_risk_mentions(converted)
        quality.risks_lost = quality.source_risks - quality.converted_risks
        # Risk preservation = all source risks appear in converted
        # Having MORE risk terms in converted is fine (template adds standard terms)
        quality.risks_preserved = quality.source_risks <= quality.converted_risks

        quality.source_task_verbs = extract_task_keywords(source)
        quality.converted_task_verbs = extract_task_keywords(converted)

        # Tier 3a: Similarity metrics (raw)
        quality.jaccard_similarity = jaccard_similarity(source, converted)
        quality.weighted_jaccard_similarity = weighted_jaccard_similarity(source, converted)

        # Tier 3a: Similarity metrics (preprocessed - strips markdown & boilerplate)
        quality.preprocessed_jaccard = preprocessed_jaccard_similarity(source, converted)
        quality.preprocessed_weighted_jaccard = preprocessed_weighted_jaccard(source, converted)

        return quality
