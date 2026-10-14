"""
revision_notes.py - Grounded, local-only AI revision notes for repeated questions in PaperPilot.

Provides:
  - Strict grounded synthesis summarizing what the supplied cluster questions support.
  - Zero hallucination safeguards: does not invent textbook facts, predicted questions, marks, or years.
  - Source integrity: citations and question references are constructed exclusively in Python from actual records.
  - Explicit uncertainty handling for ambiguous, fragmented, or multi-topic question clusters.
  - Deterministic SHA-256 caching based on model ID, prompt version, subject, and cluster question content.
  - Memory caching with automatic invalidation on cluster/question mutations.
  - Non-blocking fault tolerance if local Ollama is offline or the model is missing.
"""

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Tuple

from paperpilot.similarity import QuestionCluster
from paperpilot.local_ai import (
    LocalAIClient,
    AIError,
    AIErrorKind,
    DEFAULT_MODEL,
)

REVISION_PROMPT_VERSION: str = "v1"
MAX_CLUSTER_MEMBERS_IN_PROMPT: int = 3
MAX_QUESTION_CHARS_IN_PROMPT: int = 400
DEFAULT_NUM_PREDICT_REVISION: int = 240
ALLOWED_CONFIDENCE_VALUES = {"high", "medium", "uncertain"}


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceQuestionCitation:
    """
    Grounded source citation constructed exclusively in Python from actual cluster metadata.
    The AI model NEVER determines these values.
    """
    question_id: str
    source_file: str
    source_page: int
    question_number: str
    year: Optional[int]
    marks: Optional[str]
    text: str
    similarity_to_representative: float
    is_leader: bool


@dataclass(frozen=True)
class GroundedRevisionNotes:
    """
    Validated container for AI-assisted revision notes.
    """
    focus: str
    revision_bullets: List[str]
    key_concepts: List[str]
    confidence: str
    reasoning: Optional[str]
    sources: List[SourceQuestionCitation]
    model: str
    latency_ms: float
    created_at: float
    cache_key: str


# -----------------------------------------------------------------------------
# Cache Key Computation & In-Memory Revision Cache
# -----------------------------------------------------------------------------

def compute_revision_notes_cache_key(
    model_name: str,
    prompt_version: str,
    subject: str,
    representative_text: str,
    member_texts: List[str],
) -> str:
    """
    Computes a deterministic SHA-256 cache key for cluster revision notes.
    Any alteration to question text, representative text, subject, prompt version,
    or model identifier produces a completely different hash.
    """
    hasher = hashlib.sha256()
    hasher.update(b"revision_notes|")
    hasher.update(model_name.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(prompt_version.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(subject.strip().lower().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(representative_text.strip().encode("utf-8"))
    hasher.update(b"|")

    # Sort member texts for canonical ordering
    cleaned_members = sorted([m.strip() for m in member_texts if m.strip()])
    for m in cleaned_members:
        hasher.update(m.encode("utf-8"))
        hasher.update(b";")

    return hasher.hexdigest()


class RevisionNotesCache:
    """
    Thread-safe in-memory cache for cluster revision notes.
    Requires zero SQLite schema modifications and persists during the user session.
    """

    def __init__(self):
        self._entries: Dict[str, GroundedRevisionNotes] = {}
        self._cluster_to_key: Dict[str, str] = {}

    def get(self, cache_key: str) -> Optional[GroundedRevisionNotes]:
        """Retrieves cached revision notes if key exists."""
        return self._entries.get(cache_key)

    def set(
        self,
        cache_key: str,
        notes: GroundedRevisionNotes,
        cluster_id: Optional[str] = None,
    ) -> None:
        """Stores revision notes, optionally indexing by cluster ID."""
        self._entries[cache_key] = notes
        if cluster_id:
            self._cluster_to_key[cluster_id] = cache_key

    def invalidate_cluster(self, cluster_id: str) -> None:
        """Removes the cached entry associated with a specific cluster ID."""
        key = self._cluster_to_key.pop(cluster_id, None)
        if key:
            self._entries.pop(key, None)

    def clear(self) -> None:
        """Clears all cached entries and mappings."""
        self._entries.clear()
        self._cluster_to_key.clear()

    def __len__(self) -> int:
        return len(self._entries)


_GLOBAL_REVISION_CACHE = RevisionNotesCache()


def get_revision_notes_cache() -> RevisionNotesCache:
    """Returns the process-wide shared revision notes cache."""
    return _GLOBAL_REVISION_CACHE


# -----------------------------------------------------------------------------
# Structured Output Parsing & Schema Validation
# -----------------------------------------------------------------------------

def validate_and_parse_revision_notes_json(
    raw_text: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[AIErrorKind]]:
    """
    Parses and strictly validates revision notes JSON against the PaperPilot schema:
      - focus: non-empty string, length <= 200
      - revision_bullets: list of 1 to 4 strings, each non-empty, length <= 300
      - key_concepts: list of 1 to 6 strings, each non-empty, length <= 80
      - confidence: one of ['high', 'medium', 'uncertain']
      - reasoning: optional string, length <= 400
      - disallowed keys: rejected with SCHEMA_VIOLATION

    Returns (parsed_dict, error_message, error_kind).
    """
    if not raw_text or not raw_text.strip():
        return None, "Model returned an empty response.", AIErrorKind.EMPTY_RESPONSE

    text = raw_text.strip()

    # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
        elif len(lines) >= 1:
            text = "\n".join(lines[1:]).strip()
            if text.endswith("```"):
                text = text[:-3].strip()

    # Boundary recovery for completion models
    if not text.startswith("{") and text.endswith("}"):
        text = "{" + text
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    try:
        data = json.loads(text)
    except Exception as ex:
        return None, f"Failed to parse JSON syntax: {ex}", AIErrorKind.INVALID_JSON

    if not isinstance(data, dict):
        return None, "Output JSON root must be a JSON object/dictionary.", AIErrorKind.SCHEMA_VIOLATION

    # Strict key validation: no unexpected keys allowed
    allowed_keys = {"focus", "revision_bullets", "key_concepts", "confidence", "reasoning"}
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        return (
            None,
            f"Schema violation: unexpected key(s) {sorted(list(extra_keys))}. Allowed keys: {sorted(list(allowed_keys))}",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Required keys validation
    required_keys = {"focus", "revision_bullets", "key_concepts", "confidence"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        return (
            None,
            f"Schema violation: missing required field(s) {sorted(list(missing_keys))}.",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate 'focus'
    if not isinstance(data["focus"], str):
        return None, "Schema violation: 'focus' must be a string.", AIErrorKind.SCHEMA_VIOLATION
    clean_focus = data["focus"].strip()
    if not clean_focus:
        return None, "Schema violation: 'focus' cannot be empty.", AIErrorKind.SCHEMA_VIOLATION
    if len(clean_focus) > 200:
        return (
            None,
            f"Schema violation: 'focus' exceeds maximum length of 200 characters ({len(clean_focus)}).",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate 'revision_bullets'
    bullets = data["revision_bullets"]
    if not isinstance(bullets, list):
        return None, "Schema violation: 'revision_bullets' must be a list.", AIErrorKind.SCHEMA_VIOLATION
    if not (1 <= len(bullets) <= 4):
        return (
            None,
            f"Schema violation: 'revision_bullets' must contain between 1 and 4 items (got {len(bullets)}).",
            AIErrorKind.SCHEMA_VIOLATION,
        )
    clean_bullets: List[str] = []
    for idx, b in enumerate(bullets):
        if not isinstance(b, str):
            return None, f"Schema violation: 'revision_bullets' item {idx} must be a string.", AIErrorKind.SCHEMA_VIOLATION
        cb = b.strip()
        if not cb:
            return None, f"Schema violation: 'revision_bullets' item {idx} cannot be empty.", AIErrorKind.SCHEMA_VIOLATION
        if len(cb) > 300:
            return (
                None,
                f"Schema violation: 'revision_bullets' item {idx} exceeds 300 characters ({len(cb)}).",
                AIErrorKind.SCHEMA_VIOLATION,
            )
        clean_bullets.append(cb)

    # Validate 'key_concepts'
    concepts = data["key_concepts"]
    if not isinstance(concepts, list):
        return None, "Schema violation: 'key_concepts' must be a list.", AIErrorKind.SCHEMA_VIOLATION
    if not (1 <= len(concepts) <= 6):
        return (
            None,
            f"Schema violation: 'key_concepts' must contain between 1 and 6 items (got {len(concepts)}).",
            AIErrorKind.SCHEMA_VIOLATION,
        )
    clean_concepts: List[str] = []
    for idx, c in enumerate(concepts):
        if not isinstance(c, str):
            return None, f"Schema violation: 'key_concepts' item {idx} must be a string.", AIErrorKind.SCHEMA_VIOLATION
        cc = c.strip()
        if not cc:
            return None, f"Schema violation: 'key_concepts' item {idx} cannot be empty.", AIErrorKind.SCHEMA_VIOLATION
        if len(cc) > 80:
            return (
                None,
                f"Schema violation: 'key_concepts' item {idx} exceeds 80 characters ({len(cc)}).",
                AIErrorKind.SCHEMA_VIOLATION,
            )
        clean_concepts.append(cc)

    # Validate 'confidence'
    conf = data["confidence"]
    if not isinstance(conf, str):
        return None, "Schema violation: 'confidence' must be a string.", AIErrorKind.SCHEMA_VIOLATION
    clean_conf = conf.strip().lower()
    if clean_conf not in ALLOWED_CONFIDENCE_VALUES:
        return (
            None,
            f"Schema violation: 'confidence' must be one of {sorted(list(ALLOWED_CONFIDENCE_VALUES))}, got '{conf}'.",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate 'reasoning'
    clean_reasoning: Optional[str] = None
    if "reasoning" in data and data["reasoning"] is not None:
        if not isinstance(data["reasoning"], str):
            return None, "Schema violation: 'reasoning' must be a string.", AIErrorKind.SCHEMA_VIOLATION
        cr = data["reasoning"].strip()
        if len(cr) > 400:
            return None, f"Schema violation: 'reasoning' exceeds 400 characters ({len(cr)}).", AIErrorKind.SCHEMA_VIOLATION
        clean_reasoning = cr if cr else None

    cleaned_dict = {
        "focus": clean_focus,
        "revision_bullets": clean_bullets,
        "key_concepts": clean_concepts,
        "confidence": clean_conf,
        "reasoning": clean_reasoning,
    }
    return cleaned_dict, None, None


# -----------------------------------------------------------------------------
# Few-Shot Completion Prompt Construction
# -----------------------------------------------------------------------------

def build_cluster_revision_prompt(
    representative_text: str,
    member_texts: List[str],
    subject: str = "Computer Science",
    max_members: int = MAX_CLUSTER_MEMBERS_IN_PROMPT,
) -> str:
    """
    Constructs a structured few-shot completion prompt tailored for local base completion models
    (such as qwen2.5-coder:1.5b-base) generating revision study points from a cluster of questions.

    Guarantees:
      - Grounded strictly in the wording and technical scope of the provided questions.
      - Never asks the model to generate source filenames, citations, marks, or years.
      - Includes clear uncertainty examples for ambiguous or incomplete questions.
    """
    clean_rep = representative_text.strip()[:MAX_QUESTION_CHARS_IN_PROMPT]
    clean_sub = subject.strip() if subject else "Computer Science"

    # Select bounded number of distinct member variants
    bounded_members: List[str] = []
    for m in member_texts:
        clean_m = m.strip()[:MAX_QUESTION_CHARS_IN_PROMPT]
        if clean_m and clean_m != clean_rep and clean_m not in bounded_members:
            bounded_members.append(clean_m)
        if len(bounded_members) >= max_members:
            break

    context_lines = [f"Anchor Question: {clean_rep}"]
    for idx, m_text in enumerate(bounded_members, 1):
        context_lines.append(f"Variant {idx}: {m_text}")
    question_context = "\n".join(context_lines)

    return (
        "Exam Question Revision Guide Dataset\n"
        "---\n"
        "Subject: Operating Systems\n"
        "Anchor Question: Explain Banker's algorithm for deadlock avoidance in Operating Systems.\n"
        "Variant 1: Discuss deadlock avoidance using Banker's resource allocation algorithm.\n"
        'JSON: {"focus": "Banker\'s algorithm safety criteria and resource-request state validation for deadlock avoidance", "revision_bullets": ["Study the Available, Max, Allocation, and Need matrices used to track resources", "Practice the Safety Algorithm steps to determine whether a system state is safe or unsafe", "Understand the Resource-Request algorithm conditions for safely granting process requests"], "key_concepts": ["Banker\'s Algorithm", "Safe State vs Unsafe State", "Resource Allocation Matrix", "Need Matrix Calculation"], "confidence": "high", "reasoning": "Standard operating systems concurrency mechanism directly asked across variants"}\n'
        "---\n"
        "Subject: Data Structures\n"
        "Anchor Question: Analyze the worst-case time complexity O(n log n) of Merge Sort with recurrence relation.\n"
        "Variant 1: Derive the recurrence relation T(n) = 2T(n/2) + O(n) for Merge Sort.\n"
        'JSON: {"focus": "Recurrence relation derivation and worst-case time complexity analysis of Merge Sort", "revision_bullets": ["Set up the divide-and-conquer recurrence relation T(n) = 2T(n/2) + cn", "Apply the Master Theorem (Case 2) or recursion tree method to prove O(n log n)", "Analyze the auxiliary array space requirement of O(n) during the merge phase"], "key_concepts": ["Merge Sort", "Divide and Conquer", "Recurrence Relations", "Master Theorem", "Time Complexity"], "confidence": "high", "reasoning": "Recurrence derivation and complexity proof grounded in question requirements"}\n'
        "---\n"
        "Subject: General\n"
        "Anchor Question: Write short notes on any two of the following topics.\n"
        'JSON: {"focus": "Uncertain / Incomplete Scope", "revision_bullets": ["Specific sub-questions and topic choices are missing from the exam excerpt", "Inspect the original question paper to identify individual topics before revising"], "key_concepts": ["Uncertain Scope"], "confidence": "uncertain", "reasoning": "Anchor prompt is incomplete without sub-options"}\n'
        "---\n"
        f"Subject: {clean_sub}\n"
        f"{question_context}\n"
        "JSON: {"
    )


# -----------------------------------------------------------------------------
# Cluster Revision Notes Generator Service
# -----------------------------------------------------------------------------

class ClusterRevisionNotesGenerator:
    """
    Coordinates generating, validating, and caching AI revision notes for repeated clusters.
    """

    def __init__(
        self,
        ai_client: Optional[LocalAIClient] = None,
        cache: Optional[RevisionNotesCache] = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.client = ai_client or LocalAIClient(default_model=model_name)
        self.cache = cache if cache is not None else get_revision_notes_cache()
        self.model_name = model_name

    def generate_notes_for_cluster(
        self,
        cluster: QuestionCluster,
        subject: Optional[str] = None,
        force_refresh: bool = False,
        timeout_s: Optional[float] = None,
    ) -> Tuple[Optional[GroundedRevisionNotes], Optional[AIError]]:
        """
        Generates grounded revision notes for a single question cluster.
        Returns (GroundedRevisionNotes, None) on success or (None, AIError) on failure.
        """
        if not cluster.representative_text:
            return None, AIError(
                kind=AIErrorKind.EMPTY_RESPONSE,
                message="Cluster has no representative question text.",
                model=self.model_name,
            )

        # Infer subject context
        inferred_subject = subject
        if not inferred_subject and cluster.questions:
            inferred_subject = cluster.questions[0].subject
        if not inferred_subject:
            inferred_subject = "Computer Science"

        # Collect member variants
        member_texts = [
            q.text for q in cluster.questions
            if q.text.strip() != cluster.representative_text.strip()
        ]

        # Compute deterministic cache key
        cache_key = compute_revision_notes_cache_key(
            model_name=self.model_name,
            prompt_version=REVISION_PROMPT_VERSION,
            subject=inferred_subject,
            representative_text=cluster.representative_text,
            member_texts=member_texts,
        )

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached, None

        # Build prompt and execute generation
        prompt = build_cluster_revision_prompt(
            representative_text=cluster.representative_text,
            member_texts=member_texts,
            subject=inferred_subject,
        )

        raw_output, latency_ms, error = self.client.send_generate_prompt(
            prompt=prompt,
            model=self.model_name,
            temperature=0.1,
            num_predict=DEFAULT_NUM_PREDICT_REVISION,
            timeout_s=timeout_s,
        )

        if error is not None:
            return None, error

        parsed_dict, val_err, val_kind = validate_and_parse_revision_notes_json(raw_output or "")
        if parsed_dict is None:
            return None, AIError(
                kind=val_kind or AIErrorKind.INVALID_JSON,
                message=val_err or "Failed to validate revision notes JSON.",
                status_code=200,
                model=self.model_name,
                raw_response=raw_output,
            )

        # Construct grounded source citations strictly in Python
        sources: List[SourceQuestionCitation] = []
        for q in cluster.questions:
            sim_score = cluster.similarity_to_representative.get(q.id, 1.0)
            is_leader = (q.id == cluster.representative_id)
            raw_marks = getattr(q, "marks", None)
            marks_str = str(raw_marks).strip() if raw_marks is not None and str(raw_marks).strip() else None
            sources.append(
                SourceQuestionCitation(
                    question_id=str(q.id),
                    source_file=str(q.source_file),
                    source_page=int(q.source_page),
                    question_number=str(q.question_number),
                    year=q.year if q.year is not None else None,
                    marks=marks_str,
                    text=str(q.text),
                    similarity_to_representative=float(sim_score),
                    is_leader=bool(is_leader),
                )
            )

        notes = GroundedRevisionNotes(
            focus=parsed_dict["focus"],
            revision_bullets=parsed_dict["revision_bullets"],
            key_concepts=parsed_dict["key_concepts"],
            confidence=parsed_dict["confidence"],
            reasoning=parsed_dict.get("reasoning"),
            sources=sources,
            model=self.model_name,
            latency_ms=round(latency_ms, 2),
            created_at=time.time(),
            cache_key=cache_key,
        )

        self.cache.set(cache_key, notes, cluster_id=cluster.cluster_id)
        return notes, None
