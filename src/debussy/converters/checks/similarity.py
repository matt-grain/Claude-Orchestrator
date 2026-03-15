"""Tier 3a Jaccard similarity checks for plan conversion quality."""

from __future__ import annotations

import re

from debussy.converters.checks.keywords import AGENT_KEYWORDS, TECH_KEYWORDS

# Common stopwords to filter out (minimal set to avoid dependencies)
STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "now",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "if",
        "then",
        "else",
        "because",
        "while",
        "although",
        "though",
        "after",
        "before",
        "during",
        "until",
        "unless",
    }
)

# Template boilerplate phrases to strip (Debussy-specific)
TEMPLATE_BOILERPLATE = [
    # Process wrapper boilerplate
    r"Process Wrapper \(MANDATORY\)",
    r"Read previous notes:.*",
    r"\*\*\[IMPLEMENTATION - see Tasks below\]\*\*",
    r"Pre-validation \(ALL required\):",
    r"Fix loop: repeat pre-validation until clean",
    r"Write `notes/NOTES_.*\.md` \(REQUIRED\)",
    # Gate boilerplate
    r"Gates \(must pass before completion\)",
    r"\*\*ALL gates are BLOCKING\.\*\*",
    r"lint: 0 errors \(command:.*\)",
    r"type-check: 0 errors \(command:.*\)",
    r"tests: All tests pass \(command:.*\)",
    r"security: No high severity issues \(command:.*\)",
    # Common commands
    r"uv run ruff format.*",
    r"uv run ruff check.*",
    r"uv run pyright.*",
    r"uv run pytest.*",
    r"uv run bandit.*",
    r"npm run lint.*",
    r"npm run type-check.*",
    r"npm test.*",
    # Status markers
    r"\*\*Status:\*\* Pending",
    r"\*\*Master Plan:\*\*.*",
    r"\*\*Depends On:\*\*.*",
    r"\*\*Created:\*\*.*",
]


def preprocess_markdown(text: str, strip_boilerplate: bool = True) -> str:
    """Preprocess markdown text for similarity comparison.

    Removes:
    - Markdown syntax (headers, bold, italic, links, code blocks)
    - Table formatting
    - Template boilerplate (optional)
    - Extra whitespace

    Args:
        text: Raw markdown text.
        strip_boilerplate: Whether to remove Debussy template boilerplate.

    Returns:
        Cleaned plain text for comparison.
    """
    result = text

    # Remove code blocks (fenced and inline)
    result = re.sub(r"```[\s\S]*?```", " ", result)
    result = re.sub(r"`[^`]+`", " ", result)

    # Remove HTML tags if any
    result = re.sub(r"<[^>]+>", " ", result)

    # Remove markdown links but keep link text: [text](url) -> text
    result = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", result)

    # Remove image syntax: ![alt](url) -> alt
    result = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", result)

    # Remove headers (keep the text)
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Remove bold/italic markers
    result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
    result = re.sub(r"\*([^*]+)\*", r"\1", result)
    result = re.sub(r"__([^_]+)__", r"\1", result)
    result = re.sub(r"_([^_]+)_", r"\1", result)

    # Remove table formatting (keep cell content)
    result = re.sub(r"\|", " ", result)
    result = re.sub(r"^[\s\-:]+$", "", result, flags=re.MULTILINE)

    # Remove horizontal rules
    result = re.sub(r"^[\-*_]{3,}$", "", result, flags=re.MULTILINE)

    # Remove list markers
    result = re.sub(r"^\s*[-*+]\s+", " ", result, flags=re.MULTILINE)
    result = re.sub(r"^\s*\d+\.\s+", " ", result, flags=re.MULTILINE)

    # Remove checkbox markers
    result = re.sub(r"\[[ x]\]", " ", result, flags=re.IGNORECASE)

    # Remove blockquotes
    result = re.sub(r"^>\s*", "", result, flags=re.MULTILINE)

    # Strip template boilerplate if requested
    if strip_boilerplate:
        for pattern in TEMPLATE_BOILERPLATE:
            result = re.sub(pattern, " ", result, flags=re.IGNORECASE)

    # Normalize whitespace
    result = re.sub(r"\s+", " ", result)

    return result.strip()


def tokenize(text: str, preprocess: bool = False, remove_stopwords: bool = False) -> set[str]:
    """Tokenize text into lowercase words.

    Args:
        text: Text to tokenize.
        preprocess: Whether to apply markdown preprocessing first.
        remove_stopwords: Whether to remove common stopwords.

    Returns:
        Set of lowercase word tokens.
    """
    if preprocess:
        text = preprocess_markdown(text)

    # Remove remaining non-word chars, keep alphanumeric and hyphens
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    words = cleaned.split()

    # Filter short words and pure numbers
    tokens = {w for w in words if len(w) > 2 and not w.isdigit()}

    if remove_stopwords:
        tokens = tokens - STOPWORDS

    return tokens


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts (raw, no preprocessing).

    Jaccard = |A intersection B| / |A union B|

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    words1 = tokenize(text1)
    words2 = tokenize(text2)

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def preprocessed_jaccard_similarity(
    text1: str,
    text2: str,
    remove_stopwords: bool = True,
) -> float:
    """Calculate Jaccard similarity with markdown preprocessing.

    Strips markdown syntax, template boilerplate, and optionally stopwords
    before calculating similarity. This gives a cleaner comparison of
    actual content.

    Args:
        text1: First markdown text.
        text2: Second markdown text.
        remove_stopwords: Whether to remove common stopwords.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    words1 = tokenize(text1, preprocess=True, remove_stopwords=remove_stopwords)
    words2 = tokenize(text2, preprocess=True, remove_stopwords=remove_stopwords)

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def weighted_jaccard_similarity(
    text1: str,
    text2: str,
    important_terms: frozenset[str] | set[str] | None = None,
    weight: float = 2.0,
) -> float:
    """Jaccard similarity with higher weight for important terms (raw, no preprocessing).

    Args:
        text1: First text.
        text2: Second text.
        important_terms: Terms to weight more heavily.
        weight: Multiplier for important terms (default 2.0).

    Returns:
        Weighted similarity score between 0.0 and 1.0.
    """
    words1 = tokenize(text1)
    words2 = tokenize(text2)

    if not words1 or not words2:
        return 0.0

    terms = TECH_KEYWORDS | AGENT_KEYWORDS if important_terms is None else important_terms

    # Calculate weighted intersection and union
    intersection = words1 & words2
    union = words1 | words2

    # Weight important terms
    weighted_intersection = 0.0
    weighted_union = 0.0

    for word in union:
        w = weight if word in terms else 1.0
        weighted_union += w
        if word in intersection:
            weighted_intersection += w

    return weighted_intersection / weighted_union if weighted_union > 0 else 0.0


def preprocessed_weighted_jaccard(
    text1: str,
    text2: str,
    important_terms: frozenset[str] | set[str] | None = None,
    weight: float = 2.0,
    remove_stopwords: bool = True,
) -> float:
    """Weighted Jaccard with markdown preprocessing.

    Combines preprocessing (strip markdown, boilerplate) with weighted
    scoring for important terms.

    Args:
        text1: First markdown text.
        text2: Second markdown text.
        important_terms: Terms to weight more heavily.
        weight: Multiplier for important terms (default 2.0).
        remove_stopwords: Whether to remove common stopwords.

    Returns:
        Weighted similarity score between 0.0 and 1.0.
    """
    words1 = tokenize(text1, preprocess=True, remove_stopwords=remove_stopwords)
    words2 = tokenize(text2, preprocess=True, remove_stopwords=remove_stopwords)

    if not words1 or not words2:
        return 0.0

    terms = TECH_KEYWORDS | AGENT_KEYWORDS if important_terms is None else important_terms

    intersection = words1 & words2
    union = words1 | words2

    weighted_intersection = 0.0
    weighted_union = 0.0

    for word in union:
        w = weight if word in terms else 1.0
        weighted_union += w
        if word in intersection:
            weighted_intersection += w

    return weighted_intersection / weighted_union if weighted_union > 0 else 0.0
