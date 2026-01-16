"""Unit tests for the issue analyzer module."""

from __future__ import annotations

import pytest

from debussy.planners.analyzer import (
    AnalysisReport,
    Gap,
    GapType,
    IssueAnalyzer,
    IssueQuality,
    calculate_quality_score,
    detect_acceptance_criteria_gap,
    detect_context_gap,
    detect_dependencies_gap,
    detect_scope_gap,
    detect_tech_stack_gap,
    detect_validation_gap,
)
from debussy.planners.models import GitHubIssue, IssueSet

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_issue() -> GitHubIssue:
    """Create a minimal issue with almost no information."""
    return GitHubIssue(
        number=1,
        title="Fix item",
        body="The item needs to be updated.",
    )


@pytest.fixture
def well_formed_issue() -> GitHubIssue:
    """Create a well-formed issue with all recommended sections."""
    return GitHubIssue(
        number=42,
        title="Add user authentication with JWT",
        body="""## Problem

Currently our application has no authentication, leaving it vulnerable to unauthorized access.

## Solution

Implement JWT-based authentication using Python and FastAPI.

## Acceptance Criteria

- [ ] Users can register with email and password
- [ ] Users can log in and receive JWT token
- [ ] Protected endpoints require valid JWT
- [ ] Token refresh endpoint works correctly

## Dependencies

This depends on #40 (database setup).

## Testing

- Unit tests with pytest (>80% coverage)
- Integration tests for auth endpoints
- Manual QA verification
""",
    )


@pytest.fixture
def partial_issue() -> GitHubIssue:
    """Create an issue with some but not all recommended sections."""
    return GitHubIssue(
        number=10,
        title="Refactor user service",
        body="""## Background

The user service has grown too complex and needs refactoring.

## Tasks

- Extract helper functions
- Add type hints
- Improve handling
""",
    )


@pytest.fixture
def empty_body_issue() -> GitHubIssue:
    """Create an issue with empty body."""
    return GitHubIssue(
        number=99,
        title="Quick fix needed",
        body="",
    )


# =============================================================================
# Test Gap and IssueQuality Dataclass Creation
# =============================================================================


class TestDataclassCreation:
    """Test that dataclasses can be created properly."""

    def test_gap_creation(self) -> None:
        """Test Gap dataclass creation."""
        gap = Gap(
            gap_type=GapType.ACCEPTANCE_CRITERIA,
            severity="critical",
            issue_number=1,
            description="No acceptance criteria found",
            suggested_question="What defines done?",
        )
        assert gap.gap_type == GapType.ACCEPTANCE_CRITERIA
        assert gap.severity == "critical"
        assert gap.issue_number == 1
        assert gap.description == "No acceptance criteria found"
        assert gap.suggested_question == "What defines done?"

    def test_issue_quality_creation(self) -> None:
        """Test IssueQuality dataclass creation."""
        quality = IssueQuality(
            issue_number=5,
            score=75,
            gaps=[],
            has_problem=True,
            has_solution=False,
            has_criteria=True,
            has_validation=True,
        )
        assert quality.issue_number == 5
        assert quality.score == 75
        assert quality.gaps == []
        assert quality.has_problem is True
        assert quality.has_solution is False
        assert quality.critical_gap_count == 0
        assert quality.warning_gap_count == 0

    def test_issue_quality_gap_counts(self) -> None:
        """Test IssueQuality gap counting properties."""
        gaps = [
            Gap(GapType.ACCEPTANCE_CRITERIA, "critical", 1, "desc", "q"),
            Gap(GapType.VALIDATION, "critical", 1, "desc", "q"),
            Gap(GapType.TECH_STACK, "warning", 1, "desc", "q"),
        ]
        quality = IssueQuality(issue_number=1, score=50, gaps=gaps)
        assert quality.critical_gap_count == 2
        assert quality.warning_gap_count == 1

    def test_analysis_report_creation(self) -> None:
        """Test AnalysisReport dataclass creation."""
        report = AnalysisReport(issues=[])
        assert report.issues == []
        assert report.total_gaps == 0
        assert report.critical_gaps == 0
        assert report.questions_needed == []
        assert report.average_score == 0.0


# =============================================================================
# Test Acceptance Criteria Gap Detection
# =============================================================================


class TestAcceptanceCriteriaGap:
    """Test detect_acceptance_criteria_gap function."""

    def test_detects_missing_criteria(self, minimal_issue: GitHubIssue) -> None:
        """Test that gap is detected when no criteria present."""
        gap = detect_acceptance_criteria_gap(minimal_issue)
        assert gap is not None
        assert gap.gap_type == GapType.ACCEPTANCE_CRITERIA
        assert gap.severity == "critical"

    def test_no_gap_with_checkboxes(self) -> None:
        """Test that checkbox items count as acceptance criteria."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="- [ ] First item\n- [ ] Second item",
        )
        gap = detect_acceptance_criteria_gap(issue)
        assert gap is None

    def test_no_gap_with_criteria_keyword(self) -> None:
        """Test that 'criteria' keyword prevents gap detection."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="The acceptance criteria for this task are documented elsewhere.",
        )
        gap = detect_acceptance_criteria_gap(issue)
        assert gap is None

    def test_no_gap_with_section_header(self) -> None:
        """Test that Acceptance Criteria section header prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="## Acceptance Criteria\n\nSome criteria here.",
        )
        gap = detect_acceptance_criteria_gap(issue)
        assert gap is None


# =============================================================================
# Test Tech Stack Gap Detection
# =============================================================================


class TestTechStackGap:
    """Test detect_tech_stack_gap function."""

    def test_detects_missing_tech(self, minimal_issue: GitHubIssue) -> None:
        """Test that gap is detected when no tech mentioned."""
        gap = detect_tech_stack_gap(minimal_issue)
        assert gap is not None
        assert gap.gap_type == GapType.TECH_STACK
        assert gap.severity == "warning"

    def test_no_gap_with_python(self) -> None:
        """Test that Python keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Python script fix",
            body="Fix the script.",
        )
        gap = detect_tech_stack_gap(issue)
        assert gap is None

    def test_no_gap_with_framework(self) -> None:
        """Test that framework keywords prevent gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Update the React components.",
        )
        gap = detect_tech_stack_gap(issue)
        assert gap is None

    def test_no_gap_with_database(self) -> None:
        """Test that database keywords prevent gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Migrate data to PostgreSQL.",
        )
        gap = detect_tech_stack_gap(issue)
        assert gap is None


# =============================================================================
# Test Validation Gap Detection
# =============================================================================


class TestValidationGap:
    """Test detect_validation_gap function."""

    def test_detects_missing_validation(self, minimal_issue: GitHubIssue) -> None:
        """Test that gap is detected when no validation mentioned."""
        gap = detect_validation_gap(minimal_issue)
        assert gap is not None
        assert gap.gap_type == GapType.VALIDATION
        assert gap.severity == "critical"

    def test_no_gap_with_test_keyword(self) -> None:
        """Test that 'test' keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Add unit tests for the module.",
        )
        gap = detect_validation_gap(issue)
        assert gap is None

    def test_no_gap_with_pytest(self) -> None:
        """Test that pytest keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Run pytest after changes.",
        )
        gap = detect_validation_gap(issue)
        assert gap is None

    def test_no_gap_with_coverage(self) -> None:
        """Test that coverage keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Maintain 80% coverage.",
        )
        gap = detect_validation_gap(issue)
        assert gap is None


# =============================================================================
# Test Quality Score Calculation
# =============================================================================


class TestQualityScore:
    """Test calculate_quality_score function."""

    def test_minimal_issue_low_score(self, minimal_issue: GitHubIssue) -> None:
        """Test that minimal issue gets low score."""
        score, criteria = calculate_quality_score(minimal_issue)
        assert score < 30
        assert not criteria["acceptance_criteria"]
        assert not criteria["validation"]

    def test_well_formed_issue_high_score(self, well_formed_issue: GitHubIssue) -> None:
        """Test that well-formed issue gets high score."""
        score, criteria = calculate_quality_score(well_formed_issue)
        assert score >= 80
        assert criteria["acceptance_criteria"]
        assert criteria["validation"]
        assert criteria["tech_stack"]
        assert criteria["context"]
        assert criteria["dependencies"]

    def test_partial_issue_medium_score(self, partial_issue: GitHubIssue) -> None:
        """Test that partial issue gets some score but not full marks."""
        score, criteria = calculate_quality_score(partial_issue)
        # Partial issue has Background section (context = 10)
        # but lacks acceptance criteria, tech stack, validation, etc.
        assert 0 < score < 100
        assert criteria["context"]  # Has background section

    def test_score_in_valid_range(self, well_formed_issue: GitHubIssue) -> None:
        """Test that score is always between 0 and 100."""
        score, _ = calculate_quality_score(well_formed_issue)
        assert 0 <= score <= 100


# =============================================================================
# Test IssueAnalyzer Class
# =============================================================================


class TestIssueAnalyzer:
    """Test the IssueAnalyzer class."""

    def test_analyze_issue_minimal(self, minimal_issue: GitHubIssue) -> None:
        """Test analyzing a minimal issue."""
        analyzer = IssueAnalyzer()
        quality = analyzer.analyze_issue(minimal_issue)

        assert quality.issue_number == 1
        assert quality.score < 30
        assert len(quality.gaps) > 0
        # Should have critical gaps for acceptance criteria and validation
        assert quality.critical_gap_count >= 2

    def test_analyze_issue_well_formed(self, well_formed_issue: GitHubIssue) -> None:
        """Test analyzing a well-formed issue."""
        analyzer = IssueAnalyzer()
        quality = analyzer.analyze_issue(well_formed_issue)

        assert quality.issue_number == 42
        assert quality.score >= 80
        # Well-formed issue should have few or no gaps
        assert quality.critical_gap_count == 0

    def test_analyze_issue_set(self, minimal_issue: GitHubIssue, well_formed_issue: GitHubIssue) -> None:
        """Test analyzing a set of issues."""
        issue_set = IssueSet(issues=[minimal_issue, well_formed_issue])
        analyzer = IssueAnalyzer()
        report = analyzer.analyze_issue_set(issue_set)

        assert len(report.issues) == 2
        assert report.total_gaps > 0  # Minimal issue has gaps
        assert report.average_score > 0

    def test_analyze_empty_issue_set(self) -> None:
        """Test analyzing an empty issue set."""
        issue_set = IssueSet(issues=[])
        analyzer = IssueAnalyzer()
        report = analyzer.analyze_issue_set(issue_set)

        assert len(report.issues) == 0
        assert report.total_gaps == 0
        assert report.average_score == 0.0

    def test_generate_questions(self, minimal_issue: GitHubIssue, well_formed_issue: GitHubIssue) -> None:
        """Test question generation from report."""
        issue_set = IssueSet(issues=[minimal_issue, well_formed_issue])
        analyzer = IssueAnalyzer()
        report = analyzer.analyze_issue_set(issue_set)
        questions = analyzer.generate_questions(report)

        # Should have questions for gaps in minimal issue
        assert len(questions) > 0
        # Each question should be a non-empty string
        for q in questions:
            assert isinstance(q, str)
            assert len(q) > 0

    def test_prioritize_gaps(self, minimal_issue: GitHubIssue) -> None:
        """Test gap prioritization."""
        issue_set = IssueSet(issues=[minimal_issue])
        analyzer = IssueAnalyzer()
        report = analyzer.analyze_issue_set(issue_set)
        gaps = analyzer.prioritize_gaps(report)

        # Should have gaps sorted by severity (critical first)
        if len(gaps) >= 2:
            critical_seen = False
            for gap in gaps:
                if gap.severity == "warning":
                    critical_seen = True
                if gap.severity == "critical":
                    # No critical should come after warning
                    assert not critical_seen


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_body(self, empty_body_issue: GitHubIssue) -> None:
        """Test issue with empty body."""
        analyzer = IssueAnalyzer()
        quality = analyzer.analyze_issue(empty_body_issue)

        assert quality.score == 0
        # Should detect scope gap due to short body
        scope_gaps = [g for g in quality.gaps if g.gap_type == GapType.SCOPE]
        assert len(scope_gaps) > 0

    def test_none_body(self) -> None:
        """Test issue with None body (edge case)."""
        issue = GitHubIssue(
            number=1,
            title="Test",
            body="",  # Empty string, as None would need special handling
        )
        analyzer = IssueAnalyzer()
        # Should not raise
        quality = analyzer.analyze_issue(issue)
        assert quality.issue_number == 1

    def test_perfect_issue(self) -> None:
        """Test an issue that meets all criteria."""
        issue = GitHubIssue(
            number=100,
            title="Implement Python API endpoint with FastAPI",
            body="""## Problem

Currently we have no way to fetch user data via API.

## Solution

Create a REST API endpoint using FastAPI.

## Acceptance Criteria

- [ ] GET /users/{id} returns user data
- [ ] Returns 404 for unknown users
- [ ] Includes proper error handling

## Dependencies

Depends on #99 (database models).

## Testing

- Unit tests with pytest
- Integration tests
- 90% coverage target
""",
        )
        analyzer = IssueAnalyzer()
        quality = analyzer.analyze_issue(issue)

        # Perfect issue should have high score and no critical gaps
        assert quality.score >= 90
        assert quality.critical_gap_count == 0

    def test_issue_with_only_title_tech(self) -> None:
        """Test that tech in title is detected."""
        issue = GitHubIssue(
            number=1,
            title="Fix React component rendering",
            body="The component is broken.",
        )
        gap = detect_tech_stack_gap(issue)
        assert gap is None  # React in title should be detected

    def test_dependencies_with_issue_reference(self) -> None:
        """Test that GitHub issue references are detected as dependencies."""
        issue = GitHubIssue(
            number=5,
            title="Follow-up task",
            body="This is a follow-up to #4.",
        )
        gap = detect_dependencies_gap(issue)
        assert gap is None  # #4 reference should be detected

    def test_analysis_report_properties(self) -> None:
        """Test AnalysisReport computed properties."""
        gap1 = Gap(GapType.ACCEPTANCE_CRITERIA, "critical", 1, "d", "q1")
        gap2 = Gap(GapType.TECH_STACK, "warning", 1, "d", "q2")
        gap3 = Gap(GapType.VALIDATION, "critical", 2, "d", "q3")

        iq1 = IssueQuality(issue_number=1, score=40, gaps=[gap1, gap2])
        iq2 = IssueQuality(issue_number=2, score=60, gaps=[gap3])

        report = AnalysisReport(issues=[iq1, iq2])

        assert report.total_gaps == 3
        assert report.critical_gaps == 2
        assert report.average_score == 50.0
        assert len(report.questions_needed) == 3
        assert "q1" in report.questions_needed
        assert "q2" in report.questions_needed
        assert "q3" in report.questions_needed


# =============================================================================
# Test Gap Type Coverage
# =============================================================================


class TestGapTypeCoverage:
    """Ensure all gap types can be detected."""

    def test_all_gap_types_have_detectors(self) -> None:
        """Test that all GapType enum values have corresponding detectors."""
        # Create an issue that should trigger all gap types
        issue = GitHubIssue(number=1, title="X", body="Y")

        detectors_by_type = {
            GapType.ACCEPTANCE_CRITERIA: detect_acceptance_criteria_gap,
            GapType.TECH_STACK: detect_tech_stack_gap,
            GapType.DEPENDENCIES: detect_dependencies_gap,
            GapType.VALIDATION: detect_validation_gap,
            GapType.SCOPE: detect_scope_gap,
            GapType.CONTEXT: detect_context_gap,
        }

        # Verify all enum values have detectors
        for gap_type in GapType:
            assert gap_type in detectors_by_type, f"No detector for {gap_type}"

        # Verify detectors return correct gap types when gap detected
        for gap_type, detector in detectors_by_type.items():
            gap = detector(issue)
            if gap is not None:
                assert gap.gap_type == gap_type


class TestContextGap:
    """Test detect_context_gap function."""

    def test_detects_missing_context(self, minimal_issue: GitHubIssue) -> None:
        """Test that gap is detected when no context present."""
        gap = detect_context_gap(minimal_issue)
        assert gap is not None
        assert gap.gap_type == GapType.CONTEXT
        assert gap.severity == "warning"

    def test_no_gap_with_problem_keyword(self) -> None:
        """Test that 'problem' keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="The problem is that the service is slow.",
        )
        gap = detect_context_gap(issue)
        assert gap is None

    def test_no_gap_with_background_section(self) -> None:
        """Test that Background section prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="## Background\n\nSome context here.",
        )
        gap = detect_context_gap(issue)
        assert gap is None


class TestScopeGap:
    """Test detect_scope_gap function."""

    def test_detects_short_body(self) -> None:
        """Test that short body triggers scope gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="Fix it.",  # Very short
        )
        gap = detect_scope_gap(issue)
        assert gap is not None
        assert gap.gap_type == GapType.SCOPE

    def test_no_gap_with_structured_body(self) -> None:
        """Test that structured body with headers prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="""## Section 1

Some content here that is long enough to pass the length check and also has structure.

## Section 2

More content here to ensure we have enough characters in the body.
""",
        )
        gap = detect_scope_gap(issue)
        assert gap is None

    def test_no_gap_with_list_structure(self) -> None:
        """Test that list structure prevents gap even without headers."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="""Some introduction text that explains what needs to be done in this task.

- First item to complete
- Second item to complete
- Third item to complete
- Fourth item to complete

Additional context and details about the implementation requirements.
""",
        )
        gap = detect_scope_gap(issue)
        assert gap is None


class TestDependenciesGap:
    """Test detect_dependencies_gap function."""

    def test_detects_missing_dependencies(self, minimal_issue: GitHubIssue) -> None:
        """Test that gap is detected when no dependencies mentioned."""
        gap = detect_dependencies_gap(minimal_issue)
        assert gap is not None
        assert gap.gap_type == GapType.DEPENDENCIES
        assert gap.severity == "warning"

    def test_no_gap_with_depends_keyword(self) -> None:
        """Test that 'depends' keyword prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="This depends on the auth module being ready.",
        )
        gap = detect_dependencies_gap(issue)
        assert gap is None

    def test_no_gap_with_blocked_by(self) -> None:
        """Test that 'blocked by' prevents gap."""
        issue = GitHubIssue(
            number=1,
            title="Task",
            body="This is blocked by the database migration.",
        )
        gap = detect_dependencies_gap(issue)
        assert gap is None
