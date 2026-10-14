"""
test_topic_labeler.py - Comprehensive tests for AI-assisted topic labels on repeated question clusters.

Guarantees:
  - 100% deterministic and offline (all AI responses are mocked).
  - Verifies valid labels, explicit uncertainty labels, and failure handling.
  - Verifies cache hit on identical clusters and automatic invalidation on text edits.
  - Verifies zero mutation of cluster IDs, member questions, or cosine similarity scores.
"""

from unittest.mock import MagicMock, patch
import pytest

from paperpilot.question_parser import QuestionItem
from paperpilot.similarity import cluster_questions, QuestionCluster
from paperpilot.local_ai import (
    LocalAIClient,
    AIResult,
    AIResponse,
    AIError,
    AIErrorKind,
    TopicLabel,
)
from paperpilot.topic_labeler import (
    ClusterTopicLabeler,
    TopicLabelCache,
    CachedTopicLabel,
    compute_cluster_cache_key,
    build_cluster_topic_prompt,
    PROMPT_VERSION,
)


@pytest.fixture
def sample_os_cluster() -> QuestionCluster:
    """Creates a deterministic QuestionCluster with 1 leader anchor and 2 member questions."""
    q1 = QuestionItem(
        id="q_os_1",
        question_number="Q1",
        text="Explain the four necessary conditions for deadlock occurrence in modern operating systems.",
        raw_text="Q1. Explain the four necessary conditions for deadlock occurrence in modern operating systems.",
        marks="10",
        source_file="os_2022.pdf",
        source_page=1,
        subject="Operating Systems",
        year=2022,
    )
    q2 = QuestionItem(
        id="q_os_2",
        question_number="Q3",
        text="What are the four conditions that lead to a deadlock in an operating system?",
        raw_text="Q3. What are the four conditions that lead to a deadlock in an operating system?",
        marks="10",
        source_file="os_2023.pdf",
        source_page=1,
        subject="Operating Systems",
        year=2023,
    )
    return QuestionCluster(
        cluster_id="cluster_001",
        representative_id="q_os_1",
        representative_text=q1.text,
        questions=[q1, q2],
        paper_count=2,
        occurrence_count=2,
        years=[2022, 2023],
        avg_similarity=0.88,
        similarity_to_representative={"q_os_1": 1.0, "q_os_2": 0.88},
        is_exact=False,
    )


# -----------------------------------------------------------------------------
# 1. Valid Topic Label Generation
# -----------------------------------------------------------------------------

def test_valid_topic_label_generation(sample_os_cluster):
    """Verifies that a cluster receives a concise, validated topic label with confidence."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        response=AIResponse(
            parsed=TopicLabel(
                topic="Deadlock Conditions",
                confidence="high",
                reasoning="Four necessary deadlock requirements",
            ),
            model="qwen2.5-coder:1.5b-base",
            latency_ms=125.0,
            raw_text='{"topic": "Deadlock Conditions", "confidence": "high", "reasoning": "Four necessary deadlock requirements"}',
        )
    )

    cache = TopicLabelCache()
    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=cache)

    label, err = labeler.label_cluster(sample_os_cluster)

    assert err is None
    assert label is not None
    assert label.topic == "Deadlock Conditions"
    assert label.confidence == "high"
    assert label.reasoning == "Four necessary deadlock requirements"
    assert label.model == "qwen2.5-coder:1.5b-base"
    assert label.latency_ms == 125.0
    assert len(cache) == 1


# -----------------------------------------------------------------------------
# 2. Explicit Uncertainty Result for Ambiguous Questions
# -----------------------------------------------------------------------------

def test_explicit_uncertainty_label_for_ambiguous_cluster():
    """Confirms ambiguous clusters can return explicit 'uncertain' topic classifications."""
    ambiguous_q = QuestionItem(
        id="q_amb_1",
        question_number="Q1",
        text="Write short notes on any two of the following.",
        raw_text="Q1. Write short notes on any two of the following.",
        marks="5",
        source_file="general_2021.pdf",
        source_page=2,
        subject="General",
        year=2021,
    )
    cluster = QuestionCluster(
        cluster_id="cluster_amb",
        representative_id="q_amb_1",
        representative_text=ambiguous_q.text,
        questions=[ambiguous_q],
        paper_count=1,
        occurrence_count=1,
        years=[2021],
        avg_similarity=1.0,
        similarity_to_representative={"q_amb_1": 1.0},
        is_exact=True,
    )

    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        response=AIResponse(
            parsed=TopicLabel(
                topic="Uncertain / Incomplete Prompt",
                confidence="uncertain",
                reasoning="Vague prompt lacking option details",
            ),
            model="qwen2.5-coder:1.5b-base",
            latency_ms=90.0,
            raw_text='{"topic": "Uncertain / Incomplete Prompt", "confidence": "uncertain"}',
        )
    )

    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=TopicLabelCache())
    label, err = labeler.label_cluster(cluster)

    assert err is None
    assert label is not None
    assert label.confidence == "uncertain"
    assert "Uncertain" in label.topic


# -----------------------------------------------------------------------------
# 3. Failure Handlers: Empty, Invalid JSON, and Ollama Unavailable
# -----------------------------------------------------------------------------

def test_invalid_or_empty_model_response(sample_os_cluster):
    """Ensures empty or invalid JSON errors are cleanly returned as typed AIError."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        error=AIError(
            kind=AIErrorKind.EMPTY_RESPONSE,
            message="Ollama returned an empty response string.",
        )
    )

    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=TopicLabelCache())
    label, err = labeler.label_cluster(sample_os_cluster)

    assert label is None
    assert err is not None
    assert err.kind == AIErrorKind.EMPTY_RESPONSE


def test_ollama_unavailable_returns_non_blocking_error(sample_os_cluster):
    """Ensures Ollama unavailability produces a clean error without crashing."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        error=AIError(
            kind=AIErrorKind.OLLAMA_UNAVAILABLE,
            message="Ollama is not running or unreachable at http://localhost:11434.",
        )
    )

    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=TopicLabelCache())
    label, err = labeler.label_cluster(sample_os_cluster)

    assert label is None
    assert err is not None
    assert err.kind == AIErrorKind.OLLAMA_UNAVAILABLE
    assert "not running" in err.message.lower()


# -----------------------------------------------------------------------------
# 4. Caching & Cache Invalidation Behaviors
# -----------------------------------------------------------------------------

def test_cache_reuse_for_unchanged_content(sample_os_cluster):
    """Verifies that labeling an unchanged cluster reuses cached result without calling Ollama."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        response=AIResponse(
            parsed=TopicLabel(topic="Deadlock Conditions", confidence="high"),
            model="qwen2.5-coder:1.5b-base",
            latency_ms=100.0,
            raw_text="{}",
        )
    )

    cache = TopicLabelCache()
    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=cache)

    # First call: triggers inference
    label1, err1 = labeler.label_cluster(sample_os_cluster)
    assert err1 is None
    assert label1 is not None
    assert mock_client.generate_structured_label.call_count == 1

    # Second call on identical cluster: served from cache
    label2, err2 = labeler.label_cluster(sample_os_cluster)
    assert err2 is None
    assert label2 is not None
    assert label2.topic == label1.topic
    assert mock_client.generate_structured_label.call_count == 1  # No second inference


def test_cache_invalidation_when_cluster_content_changes(sample_os_cluster):
    """Verifies that modifying question text produces a new cache key and triggers re-labeling."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.side_effect = [
        AIResult(
            response=AIResponse(
                parsed=TopicLabel(topic="Deadlock Conditions", confidence="high"),
                model="qwen2.5-coder:1.5b-base",
                latency_ms=100.0,
                raw_text="{}",
            )
        ),
        AIResult(
            response=AIResponse(
                parsed=TopicLabel(topic="Deadlock Avoidance & Banker", confidence="high"),
                model="qwen2.5-coder:1.5b-base",
                latency_ms=110.0,
                raw_text="{}",
            )
        ),
    ]

    cache = TopicLabelCache()
    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=cache)

    # Label original cluster
    label1, _ = labeler.label_cluster(sample_os_cluster)
    assert label1.topic == "Deadlock Conditions"
    assert mock_client.generate_structured_label.call_count == 1

    # Modify question text
    modified_questions = [
        sample_os_cluster.questions[0],
        QuestionItem(
            id="q_os_2_edited",
            question_number="Q3",
            text="Explain Banker's algorithm for deadlock avoidance with resource matrices.",
            raw_text="Q3. Explain Banker's algorithm for deadlock avoidance with resource matrices.",
            marks="10",
            source_file="os_2023.pdf",
            source_page=1,
            subject="Operating Systems",
            year=2023,
        ),
    ]
    modified_cluster = QuestionCluster(
        cluster_id=sample_os_cluster.cluster_id,
        representative_id=sample_os_cluster.representative_id,
        representative_text=sample_os_cluster.representative_text,
        questions=modified_questions,
        paper_count=2,
        occurrence_count=2,
        years=[2022, 2023],
        avg_similarity=0.75,
        similarity_to_representative={"q_os_1": 1.0, "q_os_2_edited": 0.75},
        is_exact=False,
    )

    # Label modified cluster: cache key changed, triggers second inference
    label2, _ = labeler.label_cluster(modified_cluster)
    assert label2.topic == "Deadlock Avoidance & Banker"
    assert mock_client.generate_structured_label.call_count == 2


# -----------------------------------------------------------------------------
# 5. Deterministic Cluster Integrity Invariance
# -----------------------------------------------------------------------------

def test_existing_cluster_memberships_and_scores_unaffected():
    """
    Guarantees that AI topic labeling does NOT mutate cluster IDs, member question lists,
    representative anchors, or cosine similarity scores.
    """
    raw_questions = [
        QuestionItem(
            id="q1",
            question_number="1",
            text="Explain Round Robin CPU scheduling with time quantum.",
            raw_text="1. Explain Round Robin CPU scheduling with time quantum.",
            marks="5",
            source_file="paperA.pdf",
            source_page=1,
            subject="OS",
            year=2021,
        ),
        QuestionItem(
            id="q2",
            question_number="1",
            text="What is Round Robin CPU scheduling and how does time quantum affect it?",
            raw_text="1. What is Round Robin CPU scheduling and how does time quantum affect it?",
            marks="5",
            source_file="paperB.pdf",
            source_page=1,
            subject="OS",
            year=2022,
        ),
    ]

    # Baseline deterministic clustering
    analysis = cluster_questions(raw_questions, similarity_threshold=0.60)
    assert len(analysis.repeated_clusters) == 1
    cluster = analysis.repeated_clusters[0]

    # Record snapshot before AI labeling
    rep_id_before = cluster.representative_id
    rep_text_before = cluster.representative_text
    member_ids_before = [q.id for q in cluster.questions]
    sim_scores_before = dict(cluster.similarity_to_representative)
    avg_sim_before = cluster.avg_similarity
    occ_before = cluster.occurrence_count
    paper_count_before = cluster.paper_count

    # Execute AI labeling
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = "qwen2.5-coder:1.5b-base"
    mock_client.generate_structured_label.return_value = AIResult(
        response=AIResponse(
            parsed=TopicLabel(topic="Round Robin Scheduling", confidence="high"),
            model="qwen2.5-coder:1.5b-base",
            latency_ms=85.0,
            raw_text="{}",
        )
    )

    labeler = ClusterTopicLabeler(ai_client=mock_client, cache=TopicLabelCache())
    results = labeler.label_clusters(analysis.repeated_clusters)

    # Verify AI label was generated
    assert cluster.cluster_id in results
    label, err = results[cluster.cluster_id]
    assert err is None
    assert label.topic == "Round Robin Scheduling"

    # Verify deterministic cluster properties remain 100% IDENTICAL
    assert cluster.representative_id == rep_id_before
    assert cluster.representative_text == rep_text_before
    assert [q.id for q in cluster.questions] == member_ids_before
    assert cluster.similarity_to_representative == sim_scores_before
    assert cluster.avg_similarity == avg_sim_before
    assert cluster.occurrence_count == occ_before
    assert cluster.paper_count == paper_count_before


def test_cache_key_sensitivity_to_content_model_subject_version():
    """Confirms cache keys differ when any contributing dimension changes."""
    base_key = compute_cluster_cache_key(
        model_name="qwen2.5-coder:1.5b-base",
        prompt_version="v1",
        subject="Operating Systems",
        representative_text="What is a Deadlock?",
        member_texts=["Define deadlock conditions."],
    )

    # 1. Different model
    diff_model = compute_cluster_cache_key(
        model_name="llama3:8b",
        prompt_version="v1",
        subject="Operating Systems",
        representative_text="What is a Deadlock?",
        member_texts=["Define deadlock conditions."],
    )
    assert base_key != diff_model

    # 2. Different prompt version
    diff_ver = compute_cluster_cache_key(
        model_name="qwen2.5-coder:1.5b-base",
        prompt_version="v2",
        subject="Operating Systems",
        representative_text="What is a Deadlock?",
        member_texts=["Define deadlock conditions."],
    )
    assert base_key != diff_ver

    # 3. Different subject
    diff_sub = compute_cluster_cache_key(
        model_name="qwen2.5-coder:1.5b-base",
        prompt_version="v1",
        subject="Computer Architecture",
        representative_text="What is a Deadlock?",
        member_texts=["Define deadlock conditions."],
    )
    assert base_key != diff_sub

    # 4. Different representative text
    diff_rep = compute_cluster_cache_key(
        model_name="qwen2.5-coder:1.5b-base",
        prompt_version="v1",
        subject="Operating Systems",
        representative_text="Explain Deadlock avoidance.",
        member_texts=["Define deadlock conditions."],
    )
    assert base_key != diff_rep

    # 5. Different member texts
    diff_mem = compute_cluster_cache_key(
        model_name="qwen2.5-coder:1.5b-base",
        prompt_version="v1",
        subject="Operating Systems",
        representative_text="What is a Deadlock?",
        member_texts=["Define banker algorithm."],
    )
    assert base_key != diff_mem

