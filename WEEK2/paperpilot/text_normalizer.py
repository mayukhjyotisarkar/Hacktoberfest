"""
text_normalizer.py - Text normalization engine for exam questions.

Cleans and prepares question text for similarity comparisons while strictly
preserving essential Computer Science and engineering symbols such as
Big-O notation (e.g., O(n log n)), C++, C#, B+ Trees, SQL, normal forms (1NF, 2NF),
and algorithmic acronyms (FIFO, LRU, SJF, PCB).
"""

import re
import string
from typing import List, Tuple, Callable, Any

# Protected tokens and technical expressions
PROTECTED_PATTERNS: List[Tuple[re.Pattern, Any]] = [
    (re.compile(r"\b[cC]\+\+"), "token_cpplang"),
    (re.compile(r"\b[cC]\#"), "token_csharplang"),
    (re.compile(r"\b[sS][qQ][lL]\b"), "token_sql"),
    (re.compile(r"\b[bB]\+\s*[tT]ree\b", re.IGNORECASE), "token_bplustree"),
    (re.compile(r"\b[bB]\-\s*[tT]ree\b", re.IGNORECASE), "token_btree"),
    (re.compile(r"\b([1-5]\s*[nN][fF]|BCNF|bcnf)\b", re.IGNORECASE), lambda m: "token_" + re.sub(r"\s+", "", m.group(0)).lower()),
    (re.compile(r"\b[oO]\s*\([^\)]+\)"), lambda m: "token_big_o_" + re.sub(r"[\s\(\)]+", "", m.group(0)[1:]).lower()),
]

# Decorative boilerplate phrases that professors append to prompts without changing the core subject
BOILERPLATE_FILLER_PHRASES = [
    r"\bwrite\s+(a\s+)?short\s+notes?\s+on\b",
    r"\bwhat\s+do\s+you\s+(mean|understand)\s+by\b",
    r"\bwith\s+(the\s+)?help\s+of\s+(a\s+)?neat\s+diagrams?\b",
    r"\bwith\s+(a\s+)?neat\s+diagrams?\b",
    r"\bwith\s+(suitable\s+)?diagrams?\b",
    r"\bwith\s+(an?\s+)?(clear\s+)?(illustrative\s+)?(suitable\s+)?examples?\b",
    r"\bin\s+detail\b",
]
BOILERPLATE_REGEX = re.compile("|".join(BOILERPLATE_FILLER_PHRASES), re.IGNORECASE)


def normalize_for_similarity(text: str) -> str:
    """
    Normalizes question text for TF-IDF vectorization and similarity comparison.

    Processing Steps:
    -----------------
    1. Replaces protected technical expressions (e.g. C++, SQL, B+ Tree, O(n log n))
       with collision-safe placeholders so punctuation stripping doesn't corrupt them.
    2. Strips common non-topical boilerplate padding (e.g. 'with a neat diagram').
    3. Retains all core topical words and structural words (e.g. 'compare', 'differentiate')
       without aggressive deletion, avoiding artificial similarity inflation.
    4. Converts to lowercase and replaces non-alphanumeric punctuation with spaces.
    5. Restores protected tokens and collapses redundant whitespace.

    Parameters:
    -----------
    text : str
        Original question text.

    Returns:
    --------
    str
        Clean normalized text suitable for vectorization.
    """
    if not text:
        return ""

    processed = text.strip()

    # Step 1: Shield protected tokens using reverse-index replacement to preserve offsets
    placeholders = {}
    for idx, (pattern, repl) in enumerate(PROTECTED_PATTERNS):
        matches = list(pattern.finditer(processed))
        for m in reversed(matches):
            val = repl(m) if callable(repl) else repl
            key = f"__PRTOK_{len(placeholders)}__"
            placeholders[key] = val
            processed = processed[:m.start()] + key + processed[m.end():]

    # Step 2: Strip common boilerplate filler phrases
    processed = BOILERPLATE_REGEX.sub(" ", processed)

    # Step 3: Lowercase
    processed = processed.lower()

    # Step 4: Strip remaining punctuation (except alphanumeric and spaces)
    processed = re.sub(r"[^\w\s]", " ", processed)

    # Step 5: Restore protected tokens safely using word boundary replacement
    for key, original in placeholders.items():
        clean_key = re.sub(r"[^\w\s]", " ", key.lower()).strip()
        processed = re.sub(rf"\b{clean_key}\b", original, processed)

    # Step 6: Collapse whitespace
    processed = re.sub(r"\s+", " ", processed).strip()
    return processed


def normalize_for_exact_match(text: str) -> str:
    """
    Creates a strict fingerprint for identifying exact duplicate questions.
    Normalizes case, collapses whitespace, and strips punctuation.
    """
    if not text:
        return ""
    cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", cleaned).strip()
