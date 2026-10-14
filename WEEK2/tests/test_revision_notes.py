"""
test_revision_notes.py - Unit tests for grounded AI revision notes in PaperPilot Phase 5 Stage 4.

Guarantees:
  - 100% deterministic and offline: tests run without Ollama installed or running.
  - Zero network requests: all HTTP interactions and client calls are mocked.
  - Strict grounding: verifies that citations are constructed in Python and never determined by the model.
  - Full coverage of schema validation, boundary recovery, uncertainty handling, caching, and pipeline integrity.
"""

from unittest.mock import MagicMock
import pytest

from paperpilot.question_parser import QuestionItem
from paperpilot.similarity import QuestionCluster, cluster_questions
from paperpilot.analytics import calculate_dataset_metrics
from paperpilot.local_ai import (
    LocalAIClient,
    AIError,
    AIErrorKind,
    DEFAULT_MODEL,
)
from paperpilot.revision_notes import (
    SourceQuestionCitation,
    GroundedRevisionNotes,
    RevisionNotesCache,
    ClusterRevisionNotesGenerator,
    validate_and_parse_revision_notes_json,
    build_cluster_revision_prompt,
    compute_revision_notes_cache_key,
    REVISION_PROMPT_VERSION,
    MAX_CLUSTER_MEMBERS_IN_PROMPT,
    MAX_QUESTION_CHARS_IN_PROMPT,
)


def _make_sample_cluster(missing_meta: bool = False) -> QuestionCluster:
    """Helper to create a reproducible QuestionCluster for tests."""
    q1 = QuestionItem(
        id="q_os_01",
        question_number="1(a)",
        text="Explain Banker's algorithm for deadlock avoidance in Operating Systems.",
        raw_text="1(a) Explain Banker's algorithm for deadlock avoidance in Operating Systems.",
        source_file="os_2022.pdf",
        source_page=2,
        subject="Operating Systems",
        year=None if missing_meta else 2022,
        marks=None if missing_meta else "10",
    )
    q2 = QuestionItem(
        id="q_os_02",
        question_number="3(b)",
        text="Discuss deadlock avoidance using Banker's resource allocation algorithm.",
        raw_text="3(b) Discuss deadlock avoidance using Banker's resource allocation algorithm.",
        source_file="os_2023.pdf",
        source_page=4,
        subject="Operating Systems",
        year=None if missing_meta else 2023,
        marks=None if missing_meta else "8",
    )
    return QuestionCluster(
        cluster_id="cluster_deadlock",
        representative_text=q1.text,
        representative_id=q1.id,
        questions=[q1, q2],
        similarity_to_representative={q1.id: 1.0, q2.id: 0.885},
        is_exact=False,
        distinct_papers=["os_2022.pdf", "os_2023.pdf"],
        paper_count=2,
        occurrence_count=2,
        avg_similarity=0.942,
        years=[] if missing_meta else [2022, 2023],
    )


# -----------------------------------------------------------------------------
# 1. Valid Grounded Revision Notes
# -----------------------------------------------------------------------------

def test_valid_grounded_revision_notes():
    """Confirms valid JSON output is parsed into GroundedRevisionNotes with correct sources."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_response_json = (
        '{"focus": "Banker\'s algorithm resource matrices and safety checks for deadlock avoidance", '
        '"revision_bullets": ['
        '"Understand Max, Allocation, Available, and Need matrices", '
        '"Practice Safety Algorithm steps to identify safe sequences", '
        '"Analyze Resource-Request algorithm grant conditions"], '
        '"key_concepts": ["Banker\'s Algorithm", "Safe State", "Deadlock Avoidance"], '
        '"confidence": "high", '
        '"reasoning": "Standard operating systems deadlock avoidance mechanism"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response_json, 145.0, None)

    cache = RevisionNotesCache()
    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=cache)
    cluster = _make_sample_cluster()

    notes, err = generator.generate_notes_for_cluster(cluster)

    assert err is None
    assert notes is not None
    assert notes.confidence == "high"
    assert "Banker's algorithm" in notes.focus
    assert len(notes.revision_bullets) == 3
    assert len(notes.key_concepts) == 3
    assert notes.latency_ms == 145.0
    assert len(notes.sources) == 2

    # Verify source citations
    s1, s2 = notes.sources
    assert s1.question_id == "q_os_01"
    assert s1.source_file == "os_2022.pdf"
    assert s1.source_page == 2
    assert s1.year == 2022
    assert s1.marks == "10"
    assert s1.is_leader is True
    assert s1.similarity_to_representative == 1.0

    assert s2.question_id == "q_os_02"
    assert s2.source_file == "os_2023.pdf"
    assert s2.source_page == 4
    assert s2.year == 2023
    assert s2.marks == "8"
    assert s2.is_leader is False
    assert s2.similarity_to_representative == 0.885


# -----------------------------------------------------------------------------
# 2. Ambiguous / Incomplete Questions Uncertainty Handling
# -----------------------------------------------------------------------------

def test_ambiguous_incomplete_questions_return_uncertainty():
    """Confirms ambiguous cluster prompts produce an explicit uncertain confidence result."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_response_json = (
        '{"focus": "Uncertain / Incomplete Scope", '
        '"revision_bullets": ["Question text lacks specific topics or sub-parts", "Check original exam paper for options"], '
        '"key_concepts": ["Uncertain Scope"], '
        '"confidence": "uncertain", '
        '"reasoning": "Generic question header without options"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response_json, 90.0, None)

    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=RevisionNotesCache())
    cluster = _make_sample_cluster()

    notes, err = generator.generate_notes_for_cluster(cluster)

    assert err is None
    assert notes is not None
    assert notes.confidence == "uncertain"
    assert notes.focus == "Uncertain / Incomplete Scope"


# -----------------------------------------------------------------------------
# 3. Invalid & Truncated JSON Handling
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_raw", [
    "This is completely plain English text with no JSON.",
    '{"focus": "Deadlock", "revision_bullets": ["Study states',  # Truncated
    '{"focus": "Deadlock", "revision_bullets": [}',  # Syntax error
    '{ "focus": "Deadlock" "confidence": "high" }',  # Missing comma
])
def test_invalid_and_truncated_json_handling(invalid_raw):
    """Confirms invalid JSON syntax or truncated responses fail validation cleanly."""
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json(invalid_raw)
    assert parsed is None
    assert err_kind == AIErrorKind.INVALID_JSON
    assert "syntax" in err_msg.lower() or "json" in err_msg.lower()


# -----------------------------------------------------------------------------
# 4. Schema Violations: Missing, Unexpected, and Wrong Field Types
# -----------------------------------------------------------------------------

def test_schema_violation_missing_required_fields():
    """Rejects responses missing focus, revision_bullets, key_concepts, or confidence."""
    raw = '{"focus": "Deadlock avoidance"}'
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json(raw)
    assert parsed is None
    assert err_kind == AIErrorKind.SCHEMA_VIOLATION
    assert "missing required field" in err_msg


def test_schema_violation_disallowed_extraneous_keys():
    """Rejects responses with extraneous keys (e.g. hallucinated citations or predicted marks)."""
    raw = (
        '{"focus": "Deadlock avoidance", '
        '"revision_bullets": ["Review Banker\'s algorithm"], '
        '"key_concepts": ["Deadlock"], '
        '"confidence": "high", '
        '"predicted_marks": 10}'
    )
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json(raw)
    assert parsed is None
    assert err_kind == AIErrorKind.SCHEMA_VIOLATION
    assert "unexpected key" in err_msg


@pytest.mark.parametrize("bad_field_json", [
    '{"focus": 12345, "revision_bullets": ["Point A"], "key_concepts": ["OS"], "confidence": "high"}',
    '{"focus": "Deadlock", "revision_bullets": "not a list", "key_concepts": ["OS"], "confidence": "high"}',
    '{"focus": "Deadlock", "revision_bullets": [123], "key_concepts": ["OS"], "confidence": "high"}',
    '{"focus": "Deadlock", "revision_bullets": ["Point A"], "key_concepts": "not a list", "confidence": "high"}',
    '{"focus": "Deadlock", "revision_bullets": ["Point A"], "key_concepts": [456], "confidence": "high"}',
    '{"focus": "Deadlock", "revision_bullets": ["Point A"], "key_concepts": ["OS"], "confidence": 999}',
    '{"focus": "Deadlock", "revision_bullets": ["Point A"], "key_concepts": ["OS"], "confidence": "very_high"}',
])
def test_schema_violation_wrong_field_types_and_enums(bad_field_json):
    """Rejects responses with wrong types or invalid enum confidence."""
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json(bad_field_json)
    assert parsed is None
    assert err_kind == AIErrorKind.SCHEMA_VIOLATION


# -----------------------------------------------------------------------------
# 5. Empty or Excessive Output and Oversized Inputs
# -----------------------------------------------------------------------------

def test_empty_or_whitespace_response():
    """Rejects empty or whitespace-only model output."""
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json("   \n\t  ")
    assert parsed is None
    assert err_kind == AIErrorKind.EMPTY_RESPONSE


def test_excessive_lengths_rejected():
    """Rejects outputs exceeding defined string or array bounds."""
    # Focus > 200 chars
    long_focus = "A" * 220
    raw = f'{{"focus": "{long_focus}", "revision_bullets": ["Point"], "key_concepts": ["Concept"], "confidence": "high"}}'
    parsed, err_msg, err_kind = validate_and_parse_revision_notes_json(raw)
    assert parsed is None
    assert err_kind == AIErrorKind.SCHEMA_VIOLATION
    assert "focus" in err_msg

    # Bullets > 4
    many_bullets = '["1", "2", "3", "4", "5"]'
    raw_b = f'{{"focus": "Focus", "revision_bullets": {many_bullets}, "key_concepts": ["Concept"], "confidence": "high"}}'
    parsed_b, err_msg_b, err_kind_b = validate_and_parse_revision_notes_json(raw_b)
    assert parsed_b is None
    assert err_kind_b == AIErrorKind.SCHEMA_VIOLATION


def test_prompt_bounds_oversized_inputs():
    """Confirms prompt construction bounds input lengths and number of member variants."""
    giant_text = "What is deadlock? " * 50  # ~900 chars
    variants = [f"Variant question {i} " * 40 for i in range(10)]  # 10 large variants

    prompt = build_cluster_revision_prompt(
        representative_text=giant_text,
        member_texts=variants,
        subject="Operating Systems",
        max_members=MAX_CLUSTER_MEMBERS_IN_PROMPT,
    )

    # Member variants must not exceed MAX_CLUSTER_MEMBERS_IN_PROMPT
    assert f"Variant {MAX_CLUSTER_MEMBERS_IN_PROMPT}:" in prompt
    assert f"Variant {MAX_CLUSTER_MEMBERS_IN_PROMPT + 1}:" not in prompt


# -----------------------------------------------------------------------------
# 6. Cache Hits Avoiding Model Requests
# -----------------------------------------------------------------------------

def test_cache_hits_avoid_model_request():
    """Confirms that subsequent calls with identical cluster content return from cache."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_response = (
        '{"focus": "Deadlock avoidance", '
        '"revision_bullets": ["Point A", "Point B"], '
        '"key_concepts": ["Deadlock"], '
        '"confidence": "high"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response, 120.0, None)

    cache = RevisionNotesCache()
    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=cache)
    cluster = _make_sample_cluster()

    # Call 1: Cache Miss
    notes1, err1 = generator.generate_notes_for_cluster(cluster)
    assert err1 is None
    assert mock_client.send_generate_prompt.call_count == 1

    # Call 2: Cache Hit
    notes2, err2 = generator.generate_notes_for_cluster(cluster)
    assert err2 is None
    assert notes2.cache_key == notes1.cache_key
    assert mock_client.send_generate_prompt.call_count == 1  # Not called again!


# -----------------------------------------------------------------------------
# 7. Cache Invalidation after Edits or Membership Changes
# -----------------------------------------------------------------------------

def test_cache_invalidation_after_cluster_modification():
    """Confirms that modifying cluster question text changes the cache key and misses cache."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_response = (
        '{"focus": "Deadlock avoidance", '
        '"revision_bullets": ["Point A", "Point B"], '
        '"key_concepts": ["Deadlock"], '
        '"confidence": "high"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response, 120.0, None)

    cache = RevisionNotesCache()
    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=cache)
    cluster = _make_sample_cluster()

    # Generate initial notes
    notes1, _ = generator.generate_notes_for_cluster(cluster)
    assert mock_client.send_generate_prompt.call_count == 1

    # Modify cluster representative text
    cluster.representative_text = "Differentiate between deadlock prevention and deadlock avoidance."

    # Generate notes again
    notes2, _ = generator.generate_notes_for_cluster(cluster)
    assert mock_client.send_generate_prompt.call_count == 2  # Invoked again!
    assert notes2.cache_key != notes1.cache_key


# -----------------------------------------------------------------------------
# 8. Source Metadata Built Strictly in Python
# -----------------------------------------------------------------------------

def test_source_metadata_strictly_from_cluster_records():
    """Verifies that citations are built from cluster objects and never model output."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    # Model response doesn't mention q_os_01 or os_2022.pdf
    mock_response = (
        '{"focus": "Deadlock avoidance", '
        '"revision_bullets": ["Point A", "Point B"], '
        '"key_concepts": ["Deadlock"], '
        '"confidence": "high"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response, 80.0, None)

    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=RevisionNotesCache())
    cluster = _make_sample_cluster()

    notes, _ = generator.generate_notes_for_cluster(cluster)
    assert len(notes.sources) == 2
    assert notes.sources[0].question_id == "q_os_01"
    assert notes.sources[0].source_file == "os_2022.pdf"
    assert notes.sources[1].question_id == "q_os_02"
    assert notes.sources[1].source_file == "os_2023.pdf"


# -----------------------------------------------------------------------------
# 9. Missing Year & Marks Metadata Remain Missing
# -----------------------------------------------------------------------------

def test_missing_year_and_marks_remain_missing():
    """Confirms that when year and marks are None, they remain None in citations."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_response = (
        '{"focus": "Deadlock avoidance", '
        '"revision_bullets": ["Point A", "Point B"], '
        '"key_concepts": ["Deadlock"], '
        '"confidence": "high"}'
    )
    mock_client.send_generate_prompt.return_value = (mock_response, 80.0, None)

    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=RevisionNotesCache())
    cluster = _make_sample_cluster(missing_meta=True)

    notes, _ = generator.generate_notes_for_cluster(cluster)
    assert notes.sources[0].year is None
    assert notes.sources[0].marks is None
    assert notes.sources[1].year is None
    assert notes.sources[1].marks is None


# -----------------------------------------------------------------------------
# 10. Ollama Unavailable & Model Missing Handling
# -----------------------------------------------------------------------------

def test_ollama_unavailable_and_model_missing():
    """Confirms non-blocking error return when Ollama is offline or model is missing."""
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_client.send_generate_prompt.return_value = (
        None,
        0.0,
        AIError(
            kind=AIErrorKind.OLLAMA_UNAVAILABLE,
            message="Ollama is not running or unreachable at local endpoint.",
        ),
    )

    generator = ClusterRevisionNotesGenerator(ai_client=mock_client, cache=RevisionNotesCache())
    cluster = _make_sample_cluster()

    notes, err = generator.generate_notes_for_cluster(cluster)
    assert notes is None
    assert err is not None
    assert err.kind == AIErrorKind.OLLAMA_UNAVAILABLE
    assert "not running" in err.message


# -----------------------------------------------------------------------------
# 11. Pipeline Integrity: Clusters & Metrics Unchanged
# -----------------------------------------------------------------------------

def test_pipeline_integrity_unaffected_by_revision_notes():
    """Guarantees clustering, similarity scores, and analytics metrics are 100% unaltered."""
    q1 = QuestionItem(id="1", question_number="1", text="Explain Banker's algorithm in OS.", raw_text="1", source_file="p1.pdf", source_page=1, subject="OS", year=2022)
    q2 = QuestionItem(id="2", question_number="2", text="Explain Banker's resource algorithm in OS.", raw_text="2", source_file="p2.pdf", source_page=1, subject="OS", year=2023)
    q3 = QuestionItem(id="3", question_number="3", text="What is Quick Sort time complexity?", raw_text="3", source_file="p1.pdf", source_page=2, subject="DS", year=2022)

    # Initial deterministic analysis
    analysis_before = cluster_questions([q1, q2, q3], similarity_threshold=0.60)
    metrics_before = calculate_dataset_metrics(analysis_before, [q1, q2, q3])

    # Run revision notes generator
    mock_client = MagicMock(spec=LocalAIClient)
    mock_client.default_model = DEFAULT_MODEL
    mock_client.send_generate_prompt.return_value = (
        '{"focus": "Deadlock avoidance", "revision_bullets": ["Study matrices"], "key_concepts": ["OS"], "confidence": "high"}',
        50.0,
        None,
    )
    generator = ClusterRevisionNotesGenerator(ai_client=mock_client)
    for c in analysis_before.repeated_clusters:
        generator.generate_notes_for_cluster(c)

    # Verify analysis after is completely identical
    assert len(analysis_before.clusters) == 2
    assert len(analysis_before.repeated_clusters) == 1
    rep_cluster = analysis_before.repeated_clusters[0]
    assert rep_cluster.paper_count == 2
    assert rep_cluster.occurrence_count == 2
    assert rep_cluster.similarity_to_representative[rep_cluster.representative_id] == 1.0
    assert rep_cluster.similarity_to_representative[q1.id] == 0.836
    assert metrics_before["total_questions"] == 3
    assert metrics_before["repeated_clusters_count"] == 1
