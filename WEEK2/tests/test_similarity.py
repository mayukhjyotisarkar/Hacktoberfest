"""
test_similarity.py - Unit tests for question similarity, token protection,
and representative-based clustering.
"""

from paperpilot.question_parser import QuestionItem
from paperpilot.text_normalizer import normalize_for_similarity, normalize_for_exact_match
from paperpilot.similarity import cluster_questions, build_tfidf_matrix


def create_dummy_q(q_id: str, text: str, source_file: str = "paper_2023.pdf", year: int = 2023) -> QuestionItem:
    return QuestionItem(
        id=q_id,
        question_number="1.",
        text=text,
        raw_text=text,
        source_file=source_file,
        source_page=1,
        subject="Computer Science",
        year=year,
    )


# =========================================================================
# Priority 3: Normalization & Token Protection Tests
# =========================================================================

def test_protected_technical_tokens():
    """Verifies that C++, C#, SQL, B+ Tree, B-Tree, normal forms, and Big-O survive normalization."""
    raw = (
        "Analyze the time complexity O(n log n) in C++ and C# "
        "when querying a B+ Tree vs B-Tree for 3NF and BCNF tables using SQL."
    )
    normalized = normalize_for_similarity(raw)

    assert "token_cpplang" in normalized
    assert "token_csharplang" in normalized
    assert "token_sql" in normalized
    assert "token_bplustree" in normalized
    assert "token_btree" in normalized
    assert "token_3nf" in normalized
    assert "token_bcnf" in normalized
    assert "token_big_o_nlogn" in normalized


def test_exact_duplicates_with_casing_and_whitespace():
    """Verifies exact duplicate detection handles differing whitespace, casing, and punctuation."""
    t1 = "  Explain DEADLOCK conditions!  "
    t2 = "explain deadlock conditions"
    t3 = "Explain Deadlock Conditions."

    assert normalize_for_exact_match(t1) == normalize_for_exact_match(t2)
    assert normalize_for_exact_match(t2) == normalize_for_exact_match(t3)

    q1 = create_dummy_q("q1", t1, "p1.pdf", 2022)
    q2 = create_dummy_q("q2", t2, "p2.pdf", 2023)
    q3 = create_dummy_q("q3", t3, "p3.pdf", 2024)

    res = cluster_questions([q1, q2, q3], similarity_threshold=0.7)
    assert len(res.repeated_clusters) == 1
    assert res.repeated_clusters[0].is_exact is True
    assert res.repeated_clusters[0].occurrence_count == 3
    assert res.repeated_clusters[0].paper_count == 3


def test_empty_and_short_text():
    """Verifies normalizer and clustering handle empty strings and 1-word inputs without errors."""
    assert normalize_for_similarity("") == ""
    assert normalize_for_exact_match("") == ""
    assert normalize_for_similarity("   ") == ""

    q_empty = create_dummy_q("qe", "")
    res = cluster_questions([q_empty])
    assert res.total_questions == 1
    assert len(res.clusters) == 1


def test_deterministic_clustering_output():
    """Verifies that clustering gives identical output regardless of initial array permutation."""
    q1 = create_dummy_q("q1", "Explain Deadlock necessary conditions in Operating Systems.", "p1.pdf")
    q2 = create_dummy_q("q2", "Explain Deadlock and necessary conditions in modern Operating Systems.", "p2.pdf")
    q3 = create_dummy_q("q3", "Differentiate paging and segmentation memory management.", "p3.pdf")

    # Run in order 1, 2, 3
    res1 = cluster_questions([q1, q2, q3], similarity_threshold=0.6)

    # Run in permuted order 3, 1, 2
    res2 = cluster_questions([q3, q1, q2], similarity_threshold=0.6)

    assert len(res1.clusters) == len(res2.clusters)
    assert len(res1.repeated_clusters) == len(res2.repeated_clusters)
    assert res1.repeated_clusters[0].representative_text == res2.repeated_clusters[0].representative_text


# =========================================================================
# Priority 1: Regression Test for Non-Transitive Chain-Merging
# =========================================================================

def test_regression_non_transitive_chain_merging():
    """
    REGRESSION TEST FOR ACCIDENTAL CHAIN-MERGING:
    In graph connected components:
      If A is similar to B (>= threshold), and B is similar to C (>= threshold),
      A, B, and C are merged into ONE cluster even if A and C share 0 similarity.

    Representative-based clustering MUST prevent A and C from being merged together
    when C does not meet the threshold against the cluster representative!
    """
    # Question A is purely about CPU scheduling
    # Question B mentions CPU scheduling AND deadlock
    # Question C is purely about Deadlock
    qA = create_dummy_q(
        "qA",
        "Explain First-Come-First-Served FCFS CPU scheduling algorithm queue dispatch latency.",
        "paper_A.pdf"
    )
    qB = create_dummy_q(
        "qB",
        "Explain CPU scheduling algorithm queue dispatch with deadlock avoidance mechanisms.",
        "paper_B.pdf"
    )
    qC = create_dummy_q(
        "qC",
        "Explain deadlock avoidance mechanisms using Banker's Algorithm with resource vectors.",
        "paper_C.pdf"
    )

    # With a threshold of 0.40:
    # Sim(A, B) is moderate (~0.45+) because of CPU scheduling overlap.
    # Sim(A, C) is ~0.0 (no shared words between FCFS CPU scheduling and Banker's deadlock).
    # Connected components would have merged all three {A, B, C}.
    # Representative clustering with Leader A must REJECT C because Sim(C, A) < 0.40!
    res = cluster_questions([qA, qB, qC], similarity_threshold=0.40)

    # Verify that Question A and Question C are NOT in the same cluster!
    for cluster in res.clusters:
        member_ids = [q.id for q in cluster.questions]
        assert not ("qA" in member_ids and "qC" in member_ids), (
            f"Regression failed! Non-transitive chaining occurred in cluster '{cluster.cluster_id}'. "
            f"Question A and Question C were merged despite having negligible similarity!"
        )

    # Verify individual similarity scores to the representative are preserved
    rep_cluster = [c for c in res.clusters if "qA" in [q.id for q in c.questions]][0]
    assert "qA" in rep_cluster.similarity_to_representative
    assert rep_cluster.similarity_to_representative["qA"] == 1.0


# =========================================================================
# Clearly Similar vs Unrelated & Threshold Tests
# =========================================================================

def test_clearly_similar_questions():
    """Verifies that paraphrased questions on the same subject cluster together."""
    q1 = create_dummy_q("q1", "What is a Deadlock? Explain the four necessary conditions for deadlock occurrence.", "p1.pdf", 2022)
    q2 = create_dummy_q("q2", "Explain Deadlock. Discuss the necessary conditions for a deadlock to occur in a system.", "p2.pdf", 2023)

    res = cluster_questions([q1, q2], similarity_threshold=0.60)
    assert len(res.repeated_clusters) == 1
    cluster = res.repeated_clusters[0]
    assert cluster.occurrence_count == 2
    assert cluster.paper_count == 2
    assert "deadlock" in cluster.representative_text.lower()
    # Check that individual similarity is recorded
    assert q2.id in cluster.similarity_to_representative
    assert cluster.similarity_to_representative[q2.id] >= 0.60


def test_clearly_unrelated_questions():
    """Verifies that completely unrelated questions do not merge."""
    q1 = create_dummy_q("q1", "What is an Operating System?", "p1.pdf")
    q2 = create_dummy_q("q2", "Explain Deadlock conditions.", "p2.pdf")
    q3 = create_dummy_q("q3", "Differentiate paging and segmentation.", "p3.pdf")

    res = cluster_questions([q1, q2, q3], similarity_threshold=0.50)
    assert len(res.repeated_clusters) == 0
    assert len(res.clusters) == 3


def test_threshold_sensitivity():
    """Verifies that increasing the threshold splits questions with partial overlap."""
    q1 = create_dummy_q("q1", "Explain CPU scheduling. Compare FCFS and Round Robin.", "p1.pdf")
    q2 = create_dummy_q("q2", "Explain CPU scheduling criteria with turnaround time and waiting time.", "p2.pdf")

    # At loose threshold (0.10), they share 'cpu scheduling' and merge
    res_loose = cluster_questions([q1, q2], similarity_threshold=0.10)
    assert len(res_loose.repeated_clusters) == 1

    # At standard threshold (0.50), they are kept separate because the algorithms differ
    res_strict = cluster_questions([q1, q2], similarity_threshold=0.50)
    assert len(res_strict.repeated_clusters) == 0
    assert len(res_strict.clusters) == 2
