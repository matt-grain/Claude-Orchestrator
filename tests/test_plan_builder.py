"""Unit tests for the plan builder module.

Tests prompt construction, template loading, phase estimation,
Q&A handling, and plan generation with mocked Claude calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from debussy.planners.analyzer import AnalysisReport, Gap, GapType, IssueQuality
from debussy.planners.models import GitHubIssue, IssueSet
from debussy.planners.plan_builder import PlanBuilder
from debussy.planners.prompts import (
    MASTER_PLAN_PROMPT,
    PHASE_PLAN_PROMPT,
    SYSTEM_PROMPT,
    build_master_plan_prompt,
    build_phase_plan_prompt,
    format_issue_for_prompt,
    format_qa_for_prompt,
)
from debussy.planners.qa_handler import QAHandler

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_issue() -> GitHubIssue:
    """Create a sample GitHub issue for testing."""
    return GitHubIssue(
        number=1,
        title="Add user authentication",
        body="Implement JWT-based authentication for the API.",
        state="OPEN",
    )


@pytest.fixture
def sample_issue_set(sample_issue: GitHubIssue) -> IssueSet:
    """Create a sample issue set with one issue."""
    return IssueSet(issues=[sample_issue])


@pytest.fixture
def sample_analysis_report() -> AnalysisReport:
    """Create a sample analysis report with some gaps."""
    gap = Gap(
        gap_type=GapType.TECH_STACK,
        severity="warning",
        issue_number=1,
        description="No tech mentioned",
        suggested_question="What tech stack will be used?",
    )
    issue_quality = IssueQuality(
        issue_number=1,
        score=50,
        gaps=[gap],
    )
    return AnalysisReport(issues=[issue_quality])


@pytest.fixture
def multi_issue_set() -> IssueSet:
    """Create an issue set with multiple issues."""
    issues = [
        GitHubIssue(number=1, title="Feature A", body="Description A", state="OPEN"),
        GitHubIssue(number=2, title="Feature B", body="Description B", state="OPEN"),
        GitHubIssue(number=3, title="Feature C", body="Description C", state="OPEN"),
        GitHubIssue(number=4, title="Feature D", body="Description D", state="OPEN"),
        GitHubIssue(number=5, title="Feature E", body="Description E", state="OPEN"),
        GitHubIssue(number=6, title="Feature F", body="Description F", state="OPEN"),
    ]
    return IssueSet(issues=issues)


@pytest.fixture
def sample_gaps() -> list[Gap]:
    """Create sample gaps for testing Q&A handler."""
    return [
        Gap(GapType.ACCEPTANCE_CRITERIA, "critical", 1, "desc", "What are the acceptance criteria for issue #1?"),
        Gap(GapType.VALIDATION, "critical", 1, "desc", "How should we test issue #1?"),
        Gap(GapType.TECH_STACK, "warning", 2, "desc", "What tech stack for issue #2?"),
        Gap(GapType.CONTEXT, "warning", 2, "desc", "What is the context for issue #2?"),
        Gap(GapType.DEPENDENCIES, "warning", 3, "desc", "What are dependencies for issue #3?"),
    ]


# =============================================================================
# Test Prompt Templates
# =============================================================================


class TestPromptTemplates:
    """Test prompt template construction functions."""

    def test_format_issue_for_prompt(self, sample_issue: GitHubIssue) -> None:
        """Test formatting a single issue for prompt inclusion."""
        formatted = format_issue_for_prompt(
            number=sample_issue.number,
            title=sample_issue.title,
            body=sample_issue.body,
            labels=["feature", "auth"],
            state=sample_issue.state,
        )

        assert "### Issue #1: Add user authentication" in formatted
        assert "feature, auth" in formatted
        assert "OPEN" in formatted
        assert "Implement JWT-based" in formatted

    def test_format_issue_with_no_labels(self) -> None:
        """Test formatting an issue with no labels."""
        formatted = format_issue_for_prompt(
            number=1,
            title="Test",
            body="Body",
            labels=[],
            state="OPEN",
        )

        assert "**Labels:** none" in formatted

    def test_format_issue_with_empty_body(self) -> None:
        """Test formatting an issue with empty body."""
        formatted = format_issue_for_prompt(
            number=1,
            title="Test",
            body="",
            labels=[],
            state="OPEN",
        )

        assert "(no description)" in formatted

    def test_format_qa_for_prompt_with_answers(self) -> None:
        """Test formatting Q&A answers for prompt."""
        answers = {
            "What tech stack?": "Python with FastAPI",
            "What database?": "PostgreSQL",
        }
        formatted = format_qa_for_prompt(answers)

        assert "What tech stack?" in formatted
        assert "Python with FastAPI" in formatted
        assert "What database?" in formatted
        assert "PostgreSQL" in formatted

    def test_format_qa_for_prompt_empty(self) -> None:
        """Test formatting with no answers."""
        formatted = format_qa_for_prompt({})
        assert "No additional context provided" in formatted

    def test_build_master_plan_prompt(self) -> None:
        """Test building complete master plan prompt."""
        prompt = build_master_plan_prompt(
            formatted_issues="Issue content here",
            qa_answers="Q&A content here",
            master_template="Template content here",
        )

        assert "## Source Issues" in prompt
        assert "Issue content here" in prompt
        assert "## User-Provided Context" in prompt
        assert "Q&A content here" in prompt
        assert "## Template to Follow" in prompt
        assert "Template content here" in prompt
        assert "Generate a MASTER_PLAN.md" in prompt

    def test_build_phase_plan_prompt(self) -> None:
        """Test building complete phase plan prompt."""
        prompt = build_phase_plan_prompt(
            master_plan_summary="Summary here",
            phase_num=2,
            phase_focus="API implementation",
            related_issues="Issues here",
            phase_template="Template here",
        )

        assert "## Master Plan Context" in prompt
        assert "## Phase 2 Focus" in prompt
        assert "API implementation" in prompt
        assert "## Related Issues" in prompt
        assert "Issues here" in prompt
        assert "Template here" in prompt
        assert "phase-2.md" in prompt


# =============================================================================
# Test PlanBuilder Template Loading
# =============================================================================


class TestPlanBuilderTemplateLoading:
    """Test template loading functionality."""

    def test_load_templates_success(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that templates can be loaded from disk."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)

        # This should work if running from project root
        try:
            master_template, phase_template = builder._load_templates()
            assert "{feature}" in master_template or "Overview" in master_template
            assert "Tasks" in phase_template or "Gates" in phase_template
        except FileNotFoundError:
            # Skip if templates not found (CI environment)
            pytest.skip("Templates not found in test environment")

    def test_load_templates_caches_result(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that templates are cached after first load."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)

        try:
            t1 = builder._load_templates()
            t2 = builder._load_templates()
            assert t1 == t2
            assert builder._master_template is not None
            assert builder._phase_template is not None
        except FileNotFoundError:
            pytest.skip("Templates not found in test environment")


# =============================================================================
# Test PlanBuilder Prompt Construction
# =============================================================================


class TestPlanBuilderPromptConstruction:
    """Test prompt building methods."""

    def test_build_master_prompt_includes_issues(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that master prompt includes issue content."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)

        # Mock template loading
        builder._master_template = "MASTER_TEMPLATE"
        builder._phase_template = "PHASE_TEMPLATE"

        prompt = builder._build_master_prompt()

        assert "Add user authentication" in prompt
        assert "Implement JWT-based" in prompt
        assert SYSTEM_PROMPT in prompt

    def test_build_master_prompt_includes_answers(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that master prompt includes Q&A answers."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        builder._master_template = "MASTER_TEMPLATE"
        builder._phase_template = "PHASE_TEMPLATE"

        builder.set_answers({"What database?": "PostgreSQL"})
        prompt = builder._build_master_prompt()

        assert "What database?" in prompt
        assert "PostgreSQL" in prompt

    def test_build_phase_prompt_includes_phase_num(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that phase prompt includes phase number and focus."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        builder._master_template = "MASTER_TEMPLATE"
        builder._phase_template = "PHASE_TEMPLATE"

        prompt = builder._build_phase_prompt(3, "Database setup")

        assert "Phase 3" in prompt
        assert "Database setup" in prompt


# =============================================================================
# Test Phase Count Estimation
# =============================================================================


class TestPhaseCountEstimation:
    """Test phase count estimation heuristic."""

    def test_small_feature_estimate(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test estimate for 1-2 issues (small feature)."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        count = builder._estimate_phase_count()

        # 1 issue with 0 critical gaps -> 2 phases
        # 1 issue with >0 critical gaps -> 3 phases
        assert count in [2, 3]

    def test_medium_feature_estimate(self, multi_issue_set: IssueSet) -> None:
        """Test estimate for 3-5 issues (medium feature)."""
        # Use first 4 issues
        medium_set = IssueSet(issues=multi_issue_set.issues[:4])
        report = AnalysisReport(issues=[])

        builder = PlanBuilder(medium_set, report)
        count = builder._estimate_phase_count()

        assert count in [3, 4]

    def test_large_feature_estimate(self, multi_issue_set: IssueSet) -> None:
        """Test estimate for 6+ issues (large feature)."""
        report = AnalysisReport(issues=[])

        builder = PlanBuilder(multi_issue_set, report)
        count = builder._estimate_phase_count()

        assert count in [4, 5]

    def test_critical_gaps_increase_phases(self, sample_issue_set: IssueSet) -> None:
        """Test that critical gaps can increase phase count."""
        # Report with critical gaps
        gap = Gap(GapType.ACCEPTANCE_CRITERIA, "critical", 1, "d", "q")
        iq = IssueQuality(issue_number=1, score=50, gaps=[gap])
        report = AnalysisReport(issues=[iq])

        builder = PlanBuilder(sample_issue_set, report)
        count = builder._estimate_phase_count()

        # With critical gap, should be 3 phases for small feature
        assert count == 3


# =============================================================================
# Test QAHandler
# =============================================================================


class TestQAHandler:
    """Test Q&A handler functionality."""

    def test_question_batching_by_position(self) -> None:
        """Test basic batching without gap info."""
        questions = [f"Question {i}" for i in range(10)]
        handler = QAHandler(questions)

        batches = handler.batch_questions()

        # 10 questions / 4 per batch = 3 batches (4 + 4 + 2)
        assert len(batches) == 3
        assert len(batches[0].questions) == 4
        assert len(batches[1].questions) == 4
        assert len(batches[2].questions) == 2

    def test_question_batching_by_severity(self, sample_gaps: list[Gap]) -> None:
        """Test batching with gap info prioritizes critical gaps."""
        questions = [g.suggested_question for g in sample_gaps]
        handler = QAHandler(questions, sample_gaps)

        batches = handler.batch_questions()

        # First batch should be critical gaps
        assert batches[0].severity == "critical"

    def test_skip_question(self) -> None:
        """Test skipping a question."""
        questions = ["Q1", "Q2", "Q3"]
        handler = QAHandler(questions)

        handler.skip_question("Q2")

        assert "Q2" not in handler.pending_questions
        assert "Q1" in handler.pending_questions
        assert "Q3" in handler.pending_questions

    def test_skip_all_optional(self, sample_gaps: list[Gap]) -> None:
        """Test skipping all warning-severity questions."""
        questions = [g.suggested_question for g in sample_gaps]
        handler = QAHandler(questions, sample_gaps)

        # 2 critical, 3 warning gaps
        skipped = handler.skip_all_optional()

        assert skipped == 3
        # Only critical questions should remain pending
        assert len(handler.pending_questions) == 2

    def test_format_question_for_tui(self) -> None:
        """Test TUI format output."""
        handler = QAHandler(["What tech stack?"])
        formatted = handler.format_question_for_tui("What tech stack?")

        assert formatted["question"] == "What tech stack?"
        assert len(formatted["header"]) <= 12
        assert len(formatted["options"]) > 0
        assert isinstance(formatted["multiSelect"], bool)

    def test_format_question_with_options(self) -> None:
        """Test TUI format with custom options."""
        handler = QAHandler(["Choose database"])
        formatted = handler.format_question_for_tui("Choose database", default_options=["PostgreSQL", "MySQL", "MongoDB"])

        assert len(formatted["options"]) == 3
        assert formatted["options"][0]["label"] == "PostgreSQL"

    def test_record_answer(self) -> None:
        """Test recording an answer."""
        handler = QAHandler(["Q1", "Q2"])
        handler.record_answer("Q1", "Answer 1")

        assert "Q1" not in handler.pending_questions
        assert handler.all_answered is False

        handler.record_answer("Q2", "Answer 2")
        assert handler.all_answered is True

    def test_get_answers_by_question(self) -> None:
        """Test getting answers keyed by question text."""
        handler = QAHandler(["Q1", "Q2"])
        handler.record_answer("Q1", "A1")
        handler.record_answer("Q2", "A2")

        answers = handler.get_answers_by_question()

        assert answers["Q1"] == "A1"
        assert answers["Q2"] == "A2"

    def test_generate_header_tech_keyword(self) -> None:
        """Test header generation from tech keyword."""
        handler = QAHandler([])
        header = handler._generate_header("What tech stack should we use?")
        assert "Tech" in header or "Stack" in header

    def test_generate_header_fallback(self) -> None:
        """Test header generation fallback."""
        handler = QAHandler([])
        header = handler._generate_header("How many things?")
        assert len(header) <= 12
        assert len(header) > 0


# =============================================================================
# Test PlanBuilder Generation (Mocked)
# =============================================================================


class TestPlanBuilderGeneration:
    """Test plan generation with mocked Claude calls."""

    @patch("debussy.planners.plan_builder.subprocess.run")
    def test_generate_master_plan_calls_claude(
        self,
        mock_run: MagicMock,
        sample_issue_set: IssueSet,
        sample_analysis_report: AnalysisReport,
    ) -> None:
        """Test that generate_master_plan calls Claude CLI."""
        mock_run.return_value = MagicMock(stdout="# Master Plan Content")

        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        builder._master_template = "TEMPLATE"
        builder._phase_template = "TEMPLATE"

        result = builder.generate_master_plan()

        mock_run.assert_called_once()
        assert "Master Plan Content" in result

    @patch("debussy.planners.plan_builder.subprocess.run")
    def test_generate_phase_plan_calls_claude(
        self,
        mock_run: MagicMock,
        sample_issue_set: IssueSet,
        sample_analysis_report: AnalysisReport,
    ) -> None:
        """Test that generate_phase_plan calls Claude CLI."""
        mock_run.return_value = MagicMock(stdout="# Phase 1 Content")

        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        builder._master_template = "TEMPLATE"
        builder._phase_template = "TEMPLATE"

        result = builder.generate_phase_plan(1, "Setup")

        mock_run.assert_called_once()
        assert "Phase 1 Content" in result

    @patch("debussy.planners.plan_builder.subprocess.run")
    def test_generate_all_creates_expected_files(
        self,
        mock_run: MagicMock,
        sample_issue_set: IssueSet,
        sample_analysis_report: AnalysisReport,
    ) -> None:
        """Test that generate_all produces expected file structure."""
        # Master plan content with phases table
        master_content = """# Master Plan
| 1 | [Phase 1](phase-1.md) | Setup | Low | Pending |
| 2 | [Phase 2](phase-2.md) | Implement | Medium | Pending |
"""
        mock_run.return_value = MagicMock(stdout=master_content)

        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        builder._master_template = "TEMPLATE"
        builder._phase_template = "TEMPLATE"

        files = builder.generate_all()

        assert "MASTER_PLAN.md" in files
        # Should have phase files based on estimate (2-3 for small feature)
        assert any(k.startswith("phase-") for k in files)

    def test_extract_phase_focuses(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test extracting phase focuses from master plan content."""
        master_content = """| Phase | Title | Focus |
| 1 | [Setup](phase-1.md) | Project scaffolding | Low |
| 2 | [Auth](phase-2.md) | Authentication | Medium |
| 3 | [API](phase-3.md) | API endpoints | Low |
"""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        focuses = builder._extract_phase_focuses(master_content)

        assert focuses.get(1) == "Project scaffolding"
        assert focuses.get(2) == "Authentication"
        assert focuses.get(3) == "API endpoints"

    def test_extract_phase_focuses_empty(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test extracting from content without phases table."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)
        focuses = builder._extract_phase_focuses("No table here")

        assert focuses == {}


# =============================================================================
# Test PlanBuilder Set Answers
# =============================================================================


class TestPlanBuilderSetAnswers:
    """Test answer setting functionality."""

    def test_set_answers(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test setting Q&A answers."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)

        answers = {"Q1": "A1", "Q2": "A2"}
        builder.set_answers(answers)

        assert builder._answers == answers

    def test_set_answers_replaces_previous(self, sample_issue_set: IssueSet, sample_analysis_report: AnalysisReport) -> None:
        """Test that set_answers replaces previous answers."""
        builder = PlanBuilder(sample_issue_set, sample_analysis_report)

        builder.set_answers({"Q1": "A1"})
        builder.set_answers({"Q2": "A2"})

        assert "Q1" not in builder._answers
        assert builder._answers == {"Q2": "A2"}


# =============================================================================
# Test System Prompt
# =============================================================================


class TestSystemPrompt:
    """Test system prompt content."""

    def test_system_prompt_has_key_elements(self) -> None:
        """Test that system prompt contains essential guidance."""
        assert "expert software architect" in SYSTEM_PROMPT
        assert "Debussy" in SYSTEM_PROMPT
        assert "phase" in SYSTEM_PROMPT.lower()
        assert "actionable" in SYSTEM_PROMPT

    def test_master_plan_prompt_has_instructions(self) -> None:
        """Test that master plan prompt has clear instructions."""
        assert "MASTER_PLAN.md" in MASTER_PLAN_PROMPT
        assert "phases" in MASTER_PLAN_PROMPT.lower()

    def test_phase_plan_prompt_has_gates(self) -> None:
        """Test that phase plan prompt mentions gates."""
        assert "Gates" in PHASE_PLAN_PROMPT
        assert "ruff" in PHASE_PLAN_PROMPT or "validation" in PHASE_PLAN_PROMPT.lower()
