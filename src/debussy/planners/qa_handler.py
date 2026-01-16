"""Q&A handler for interactive gap-filling during plan generation.

This module provides the QAHandler class that manages interactive
question-and-answer sessions to fill gaps detected in issue analysis.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from debussy.planners.analyzer import Gap


class QuestionOption(TypedDict):
    """Option for a question in AskUserQuestion format."""

    label: str
    description: str


class FormattedQuestion(TypedDict):
    """Question formatted for AskUserQuestion tool."""

    question: str
    header: str
    options: list[QuestionOption]
    multiSelect: bool


@dataclass
class QuestionBatch:
    """A batch of related questions to ask together."""

    questions: list[str]
    gap_type: str
    severity: str


class QAHandler:
    """Manages interactive Q&A sessions for gap-filling.

    Handles batching related questions, formatting for TUI display,
    and tracking user answers.
    """

    MAX_QUESTIONS_PER_BATCH = 4

    def __init__(self, questions: list[str], gaps: list[Gap] | None = None) -> None:
        """Initialize the Q&A handler.

        Args:
            questions: List of questions to ask.
            gaps: Optional list of Gap objects for context. If provided,
                  enables better question batching by gap type and severity.
        """
        self._questions = questions
        self._gaps = gaps
        self._answers: dict[str, str] = {}
        self._skipped: set[str] = set()

    @property
    def answers(self) -> dict[str, str]:
        """Get all collected answers."""
        return self._answers.copy()

    @property
    def pending_questions(self) -> list[str]:
        """Get questions that haven't been answered or skipped."""
        return [q for q in self._questions if self._question_hash(q) not in self._answers and self._question_hash(q) not in self._skipped]

    @property
    def all_answered(self) -> bool:
        """Check if all questions have been answered or skipped."""
        return len(self.pending_questions) == 0

    def _question_hash(self, question: str) -> str:
        """Generate a hash key for a question.

        Args:
            question: The question text.

        Returns:
            Short hash string suitable for use as a dictionary key.
        """
        return hashlib.md5(question.encode(), usedforsecurity=False).hexdigest()[:12]

    def ask_questions_interactive(self) -> dict[str, str]:
        """Conduct interactive Q&A session in the terminal.

        Prompts user for each pending question via stdin/stdout.

        Returns:
            Dictionary mapping questions to user answers.
        """
        for question in self.pending_questions:
            print(f"\n{question}")
            print("(Enter your answer, or 'skip' to skip this question)")
            answer = input("> ").strip()

            if answer.lower() == "skip":
                self.skip_question(question)
            else:
                self._answers[self._question_hash(question)] = answer

        return self.answers

    def format_question_for_tui(
        self,
        question: str,
        default_options: list[str] | None = None,
    ) -> FormattedQuestion:
        """Format a single question for AskUserQuestion tool.

        Args:
            question: The question to format.
            default_options: Optional list of default answer options.

        Returns:
            Dictionary in AskUserQuestion tool format.
        """
        # Generate header from question (max 12 chars)
        header = self._generate_header(question)

        # Generate options
        options: list[QuestionOption]
        if default_options:
            options = [
                QuestionOption(label=opt, description=f"Select {opt}")
                for opt in default_options[:4]
            ]
        else:
            # Generic options for open-ended questions
            options = [
                QuestionOption(label="Yes", description="Confirm this requirement"),
                QuestionOption(label="No", description="Reject this requirement"),
                QuestionOption(label="Partial", description="Some aspects apply"),
                QuestionOption(label="Unsure", description="Need more information"),
            ]

        return FormattedQuestion(
            question=question,
            header=header,
            options=options,
            multiSelect=False,
        )

    def _generate_header(self, question: str) -> str:
        """Generate a short header for a question.

        Extracts key words from the question to create a header.

        Args:
            question: The question text.

        Returns:
            Header string (max 12 chars).
        """
        # Try to extract key terms
        keywords = ["tech", "stack", "criteria", "validation", "scope", "context", "dependency"]

        question_lower = question.lower()
        for keyword in keywords:
            if keyword in question_lower:
                return keyword.title()[:12]

        # Fallback: use first significant word
        words = question.split()
        for word in words:
            if len(word) > 3 and word.lower() not in {"what", "which", "does", "this", "that", "have", "with"}:
                return word[:12]

        return "Question"

    def batch_questions(self) -> list[QuestionBatch]:
        """Group questions into batches for efficient asking.

        Groups questions by gap type, with critical gaps first.
        Each batch has at most MAX_QUESTIONS_PER_BATCH questions.

        Returns:
            List of QuestionBatch objects.
        """
        if not self._gaps:
            # No gap info - batch by position only
            batches: list[QuestionBatch] = []
            pending = self.pending_questions

            for i in range(0, len(pending), self.MAX_QUESTIONS_PER_BATCH):
                chunk = pending[i : i + self.MAX_QUESTIONS_PER_BATCH]
                batches.append(
                    QuestionBatch(
                        questions=chunk,
                        gap_type="general",
                        severity="warning",
                    )
                )
            return batches

        # Group by gap type and severity
        critical_by_type: dict[str, list[str]] = {}
        warning_by_type: dict[str, list[str]] = {}

        pending_set = set(self.pending_questions)

        for gap in self._gaps:
            if gap.suggested_question not in pending_set:
                continue

            gap_type = gap.gap_type.value
            if gap.severity == "critical":
                if gap_type not in critical_by_type:
                    critical_by_type[gap_type] = []
                critical_by_type[gap_type].append(gap.suggested_question)
            else:
                if gap_type not in warning_by_type:
                    warning_by_type[gap_type] = []
                warning_by_type[gap_type].append(gap.suggested_question)

        # Build batches: critical first, then warnings
        batches = []

        for gap_type, questions in critical_by_type.items():
            for i in range(0, len(questions), self.MAX_QUESTIONS_PER_BATCH):
                chunk = questions[i : i + self.MAX_QUESTIONS_PER_BATCH]
                batches.append(
                    QuestionBatch(
                        questions=chunk,
                        gap_type=gap_type,
                        severity="critical",
                    )
                )

        for gap_type, questions in warning_by_type.items():
            for i in range(0, len(questions), self.MAX_QUESTIONS_PER_BATCH):
                chunk = questions[i : i + self.MAX_QUESTIONS_PER_BATCH]
                batches.append(
                    QuestionBatch(
                        questions=chunk,
                        gap_type=gap_type,
                        severity="warning",
                    )
                )

        return batches

    def skip_question(self, question: str) -> None:
        """Mark a question as skipped.

        Args:
            question: The question to skip.
        """
        self._skipped.add(self._question_hash(question))

    def skip_all_optional(self) -> int:
        """Skip all questions with warning severity.

        Returns:
            Number of questions skipped.
        """
        if not self._gaps:
            return 0

        skipped_count = 0
        for gap in self._gaps:
            if gap.severity == "warning":
                question = gap.suggested_question
                if self._question_hash(question) not in self._answers:
                    self.skip_question(question)
                    skipped_count += 1

        return skipped_count

    def record_answer(self, question: str, answer: str) -> None:
        """Record an answer for a question.

        Args:
            question: The question that was answered.
            answer: The user's answer.
        """
        self._answers[self._question_hash(question)] = answer

    def get_answers_by_question(self) -> dict[str, str]:
        """Get answers keyed by question text (not hash).

        Returns:
            Dictionary mapping question text to answers.
        """
        result: dict[str, str] = {}
        for question in self._questions:
            q_hash = self._question_hash(question)
            if q_hash in self._answers:
                result[question] = self._answers[q_hash]
        return result

    def format_batch_for_tui(self, batch: QuestionBatch) -> list[FormattedQuestion]:
        """Format a batch of questions for AskUserQuestion tool.

        Args:
            batch: The question batch to format.

        Returns:
            List of formatted questions (max 4).
        """
        return [self.format_question_for_tui(q) for q in batch.questions[: self.MAX_QUESTIONS_PER_BATCH]]
