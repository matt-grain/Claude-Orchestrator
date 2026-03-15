"""Tier 2 keyword extraction checks for plan conversion quality."""

from __future__ import annotations

import re

# Common technology keywords to look for
TECH_KEYWORDS = frozenset(
    {
        # Languages
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
        "ruby",
        # Backend frameworks
        "flask",
        "django",
        "fastapi",
        "express",
        "node",
        "nodejs",
        "rails",
        # Frontend frameworks
        "react",
        "vue",
        "angular",
        "svelte",
        "nextjs",
        "next.js",
        # Databases
        "postgresql",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
        "sqlite",
        # Auth
        "jwt",
        "oauth",
        "auth0",
        "cognito",
        # Cloud/Infra
        "docker",
        "kubernetes",
        "k8s",
        "aws",
        "gcp",
        "azure",
        # Testing
        "pytest",
        "jest",
        "mocha",
        "cypress",
        # Other
        "graphql",
        "rest",
        "api",
        "websocket",
        "celery",
        "rabbitmq",
    }
)


# Agent names that should be preserved
AGENT_KEYWORDS = frozenset(
    {
        "python-task-validator",
        "textual-tui-expert",
        "llm-security-expert",
        "explore",
        "debussy",
    }
)


# Risk-related terms
RISK_KEYWORDS = frozenset(
    {
        "risk",
        "risks",
        "mitigation",
        "mitigate",
        "blocker",
        "blockers",
        "dependency",
        "dependencies",
        "concern",
        "concerns",
        "issue",
        "issues",
        "critical",
        "high-priority",
        "security",
    }
)


def extract_keywords(text: str, vocabulary: frozenset[str]) -> set[str]:
    """Extract keywords from text that match a vocabulary set.

    Args:
        text: Source text to search.
        vocabulary: Set of keywords to look for.

    Returns:
        Set of matched keywords found in text.
    """
    text_lower = text.lower()
    # Use word boundaries for more accurate matching
    found = set()
    for keyword in vocabulary:
        # Handle multi-word keywords (like "python-task-validator")
        if "-" in keyword or "_" in keyword:
            if keyword in text_lower:
                found.add(keyword)
        # Use word boundary matching for single words
        elif re.search(rf"\b{re.escape(keyword)}\b", text_lower):
            found.add(keyword)
    return found


def extract_tech_stack(text: str) -> set[str]:
    """Extract technology keywords from text."""
    return extract_keywords(text, TECH_KEYWORDS)


def extract_agent_references(text: str) -> set[str]:
    """Extract agent names from text."""
    return extract_keywords(text, AGENT_KEYWORDS)


def extract_risk_mentions(text: str) -> set[str]:
    """Extract risk-related terms from text."""
    return extract_keywords(text, RISK_KEYWORDS)


def extract_task_keywords(text: str) -> set[str]:
    """Extract task action verbs from markdown task lines.

    Looks for `- [ ]` lines and extracts the main action verb.
    Handles numbered task prefixes like "1.1:" or "2.3:".

    Args:
        text: Markdown content with task checkboxes.

    Returns:
        Set of action verbs found in tasks.
    """
    action_verbs = set()

    # Match task lines: - [ ] or - [x] followed by text
    task_pattern = re.compile(r"^\s*-\s*\[[ x]\]\s*(.+)$", re.MULTILINE | re.IGNORECASE)

    # Pattern for numbered prefixes like "1.1:" or "2.3:"
    number_prefix = re.compile(r"^\d+(\.\d+)?:\s*")

    for match in task_pattern.finditer(text):
        task_text = match.group(1).strip()

        # Strip numbered prefix if present
        task_text = number_prefix.sub("", task_text)

        # Extract first word (likely the verb)
        words = task_text.split()
        if words:
            # Clean up: remove numbers, special chars
            verb = re.sub(r"[^a-zA-Z]", "", words[0].lower())
            if verb and len(verb) > 2:  # Filter out short non-words
                action_verbs.add(verb)

    return action_verbs
