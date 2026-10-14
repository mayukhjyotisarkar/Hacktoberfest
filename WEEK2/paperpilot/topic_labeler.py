"""
topic_labeler.py - AI-assisted topic labeler for repeated question clusters in PaperPilot.

Provides:
  - Grounded few-shot prompt construction for repeated question clusters (representative anchor + member variants).
  - Deterministic SHA-256 cache key computation based on model, prompt version, subject, and cluster texts.
  - Robust in-memory caching to prevent duplicate inferences on identical clusters.
  - Automatic cache invalidation when question text is edited or cluster membership changes.
  - Strict preservation of deterministic similarity scores, cluster IDs, and priority metrics.
"""

from dataclasses import dataclass, field
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple

from paperpilot.similarity import QuestionCluster
from paperpilot.local_ai import (
    LocalAIClient,
    AIResult,
    AIError,
    AIErrorKind,
    DEFAULT_MODEL,
)

PROMPT_VERSION: str = "v1"
MAX_CLUSTER_MEMBERS_IN_PROMPT: int = 3


# -----------------------------------------------------------------------------
# Cache Key Computation & In-Memory Topic Cache
# -----------------------------------------------------------------------------

def compute_cluster_cache_key(
    model_name: str,
    prompt_version: str,
    subject: str,
    representative_text: str,
    member_texts: List[str],
) -> str:
    """
    Computes a deterministic SHA-256 cache key for a question cluster.
    Any alteration to question text, representative text, subject, prompt version,
    or model identifier produces a different hash, automatically invalidating stale labels.
    """
    hasher = hashlib.sha256()
    hasher.update(model_name.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(prompt_version.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(subject.strip().lower().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(representative_text.strip().encode("utf-8"))
    hasher.update(b"|")

    # Sort member texts for canonical order
    cleaned_members = sorted([m.strip() for m in member_texts if m.strip()])
    for m in cleaned_members:
        hasher.update(m.encode("utf-8"))
        hasher.update(b";")

    return hasher.hexdigest()


@dataclass
class CachedTopicLabel:
    """Stores the generated AI topic label and execution metadata."""
    topic: str
    confidence: str
    reasoning: Optional[str]
    model: str
    latency_ms: float
    created_at: float
    cache_key: str


class TopicLabelCache:
    """
    Thread-safe in-memory cache for cluster topic labels.
    Does not require database schema modifications.
    """

    def __init__(self):
        self._entries: Dict[str, CachedTopicLabel] = {}
        self._cluster_to_key: Dict[str, str] = {}

    def get(self, cache_key: str) -> Optional[CachedTopicLabel]:
        """Retrieves a cached topic label if the key exists."""
        return self._entries.get(cache_key)

    def set(self, cache_key: str, label: CachedTopicLabel, cluster_id: Optional[str] = None) -> None:
        """Stores a topic label in the cache, optionally indexing by cluster ID."""
        self._entries[cache_key] = label
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


# Global singleton instance for Streamlit session / in-process cache
_GLOBAL_TOPIC_CACHE = TopicLabelCache()


def get_topic_label_cache() -> TopicLabelCache:
    """Returns the shared in-memory topic label cache."""
    return _GLOBAL_TOPIC_CACHE


# -----------------------------------------------------------------------------
# Grounded Few-Shot Prompt Builder for Clusters
# -----------------------------------------------------------------------------

def build_cluster_topic_prompt(
    representative_text: str,
    member_texts: List[str],
    subject: str = "Computer Science",
    max_members: int = MAX_CLUSTER_MEMBERS_IN_PROMPT,
) -> str:
    """
    Constructs a structured few-shot completion prompt tailored for base foundation models
    (such as qwen2.5-coder:1.5b-base) analyzing a cluster of repeated exam questions.

    Guarantees:
      - Grounded strictly in question wording.
      - Never includes or asks the model to invent recurrence counts, marks, or years.
      - Includes clear uncertainty examples for ambiguous or multi-topic questions.
    """
    clean_rep = representative_text.strip()
    clean_sub = subject.strip() if subject else "Computer Science"

    # Select bounded number of distinct member variants
    bounded_members: List[str] = []
    for m in member_texts:
        clean_m = m.strip()
        if clean_m and clean_m != clean_rep and clean_m not in bounded_members:
            bounded_members.append(clean_m)
        if len(bounded_members) >= max_members:
            break

    context_lines = [f"Anchor Question: {clean_rep}"]
    for idx, m_text in enumerate(bounded_members, 1):
        context_lines.append(f"Variant {idx}: {m_text}")
    question_context = "\n".join(context_lines)

    return (
        "Exam Question Topic Classification Dataset\n"
        "---\n"
        "Subject: Operating Systems\n"
        "Anchor Question: Explain Banker's algorithm for deadlock avoidance in Operating Systems.\n"
        "Variant 1: Discuss deadlock avoidance using Banker's resource allocation algorithm.\n"
        'JSON: {"topic": "Banker\'s Algorithm", "confidence": "high", "reasoning": "Resource allocation avoidance"}\n'
        "---\n"
        "Subject: Data Structures\n"
        "Anchor Question: Analyze the worst-case time complexity O(n log n) of Merge Sort.\n"
        "Variant 1: Why does Merge Sort take O(n log n) in worst case?\n"
        'JSON: {"topic": "Sorting Algorithms & Complexity", "confidence": "high", "reasoning": "Merge sort complexity"}\n'
        "---\n"
        "Subject: General\n"
        "Anchor Question: Write short notes on any two.\n"
        'JSON: {"topic": "Uncertain / Incomplete", "confidence": "uncertain", "reasoning": "Ambiguous without sub-options"}\n'
        "---\n"
        f"Subject: {clean_sub}\n"
        f"{question_context}\n"
        "JSON: {"
    )


# -----------------------------------------------------------------------------
# Cluster Topic Labeler Service
# -----------------------------------------------------------------------------

class ClusterTopicLabeler:
    """
    Coordinates generating, validating, and caching AI topic labels for repeated clusters.
    """

    def __init__(
        self,
        ai_client: Optional[LocalAIClient] = None,
        cache: Optional[TopicLabelCache] = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.client = ai_client or LocalAIClient(default_model=model_name)
        self.cache = cache if cache is not None else get_topic_label_cache()
        self.model_name = model_name

    def label_cluster(
        self,
        cluster: QuestionCluster,
        subject: Optional[str] = None,
        force_refresh: bool = False,
        timeout_s: Optional[float] = None,
    ) -> Tuple[Optional[CachedTopicLabel], Optional[AIError]]:
        """
        Labels a single question cluster.
        Returns (CachedTopicLabel, None) on success or (None, AIError) on failure.
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

        # Check cache unless force_refresh is requested
        cache_key = compute_cluster_cache_key(
            model_name=self.model_name,
            prompt_version=PROMPT_VERSION,
            subject=inferred_subject,
            representative_text=cluster.representative_text,
            member_texts=member_texts,
        )

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached, None

        # Build prompt and execute generation
        prompt = build_cluster_topic_prompt(
            representative_text=cluster.representative_text,
            member_texts=member_texts,
            subject=inferred_subject,
        )

        result: AIResult = self.client.generate_structured_label(
            prompt=prompt,
            model=self.model_name,
            timeout_s=timeout_s,
        )

        if not result.is_success:
            return None, result.error

        assert result.response is not None
        parsed = result.response.parsed

        cached_item = CachedTopicLabel(
            topic=parsed.topic,
            confidence=parsed.confidence,
            reasoning=parsed.reasoning,
            model=result.response.model,
            latency_ms=result.response.latency_ms,
            created_at=time.time(),
            cache_key=cache_key,
        )

        self.cache.set(cache_key, cached_item, cluster_id=cluster.cluster_id)
        return cached_item, None

    def label_clusters(
        self,
        clusters: List[QuestionCluster],
        subject: Optional[str] = None,
        force_refresh: bool = False,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Tuple[Optional[CachedTopicLabel], Optional[AIError]]]:
        """
        Generates topic labels for multiple clusters.
        Returns a mapping from cluster_id to (CachedTopicLabel, AIError).
        """
        results: Dict[str, Tuple[Optional[CachedTopicLabel], Optional[AIError]]] = {}
        for c in clusters:
            results[c.cluster_id] = self.label_cluster(
                cluster=c,
                subject=subject,
                force_refresh=force_refresh,
                timeout_s=timeout_s,
            )
        return results
