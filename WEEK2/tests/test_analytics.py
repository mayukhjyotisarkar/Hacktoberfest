"""
test_analytics.py - Unit tests for frequency analytics, metadata preservation,
and priority rankings.
"""

from paperpilot.question_parser import QuestionItem
from paperpilot.similarity import cluster_questions
from paperpilot.analytics import (
    get_papers_summary_df,
    get_all_questions_df,
    get_repeated_clusters_df,
    get_revision_checklist_df,
    calculate_dataset_metrics,
)


def create_q(q_id: str, text: str, source_file: str, page: int = 1, subject: str = "OS", year=2023):
    return QuestionItem(
        id=q_id,
        question_number="1.",
        text=text,
        raw_text=text,
        source_file=source_file,
        source_page=page,
        subject=subject,
        year=year,
        marks="[10 Marks]",
    )


# =========================================================================
# Priority 2: Rigorous Analytics & Edge Case Tests
# =========================================================================

def test_three_occurrences_in_single_paper():
    """
    Case 1: Three occurrences in ONE paper MUST produce:
    total_occurrences = 3, distinct_papers = 1.
    """
    q1 = create_q("q1", "Explain Deadlock four conditions in detail.", "paper_2022.pdf", page=1, year=2022)
    q2 = create_q("q2", "Explain Deadlock four conditions in detail.", "paper_2022.pdf", page=2, year=2022)
    q3 = create_q("q3", "Explain Deadlock four conditions in detail.", "paper_2022.pdf", page=3, year=2022)

    res = cluster_questions([q1, q2, q3], similarity_threshold=0.70)
    assert len(res.repeated_clusters) == 1
    cluster = res.repeated_clusters[0]

    assert cluster.occurrence_count == 3
    assert cluster.paper_count == 1
    assert cluster.distinct_papers == ["paper_2022.pdf"]

    rep_df = get_repeated_clusters_df(res)
    assert rep_df.iloc[0]["Total Occurrences"] == 3
    assert rep_df.iloc[0]["Distinct Papers"] == 1


def test_one_occurrence_in_each_of_three_papers():
    """
    Case 2: One occurrence in EACH of three papers MUST produce:
    total_occurrences = 3, distinct_papers = 3.
    """
    q1 = create_q("q1", "What is an Operating System?", "paper_2021.pdf", year=2021)
    q2 = create_q("q2", "What is an Operating System?", "paper_2022.pdf", year=2022)
    q3 = create_q("q3", "What is an Operating System?", "paper_2023.pdf", year=2023)

    res = cluster_questions([q1, q2, q3], similarity_threshold=0.70)
    assert len(res.repeated_clusters) == 1
    cluster = res.repeated_clusters[0]

    assert cluster.occurrence_count == 3
    assert cluster.paper_count == 3
    assert sorted(cluster.distinct_papers) == ["paper_2021.pdf", "paper_2022.pdf", "paper_2023.pdf"]
    assert cluster.years == [2021, 2022, 2023]

    rep_df = get_repeated_clusters_df(res)
    assert rep_df.iloc[0]["Total Occurrences"] == 3
    assert rep_df.iloc[0]["Distinct Papers"] == 3


def test_missing_years_handled_safely():
    """
    Case 3: Questions with year=None must not raise exceptions and be reported cleanly.
    """
    q1 = create_q("q1", "Explain Bankers Algorithm.", "unknown_paper_a.pdf", year=None)
    q2 = create_q("q2", "Explain Bankers Algorithm.", "unknown_paper_b.pdf", year=None)

    res = cluster_questions([q1, q2], similarity_threshold=0.70)
    rep_df = get_repeated_clusters_df(res)
    chk_df = get_revision_checklist_df(res)

    assert len(rep_df) == 1
    assert rep_df.iloc[0]["Exam Years"] == "N/A"
    assert "N/A" in chk_df.iloc[0]["Exam Years"]

    paper_df = get_papers_summary_df([q1, q2])
    assert "Unknown" in paper_df["Year"].values


def test_metadata_survival_through_clustering():
    """
    Case 4: Filenames, page numbers, subjects, marks, and IDs must survive clustering intact.
    """
    q1 = create_q("spec_1", "Explain Semaphore.", "test_doc_alpha.pdf", page=4, subject="Operating Systems", year=2024)
    res = cluster_questions([q1])

    member = res.clusters[0].questions[0]
    assert member.id == "spec_1"
    assert member.source_file == "test_doc_alpha.pdf"
    assert member.source_page == 4
    assert member.subject == "Operating Systems"
    assert member.year == 2024
    assert member.marks == "[10 Marks]"


def test_empty_datasets_and_singletons():
    """
    Case 5: Empty inputs and singletons produce valid DataFrames without crashes.
    """
    empty_res = cluster_questions([])
    assert get_papers_summary_df([]).empty
    assert get_all_questions_df([]).empty
    assert get_repeated_clusters_df(empty_res).empty
    assert get_revision_checklist_df(empty_res).empty

    m = calculate_dataset_metrics(empty_res, [])
    assert m["total_questions"] == 0
    assert m["repetition_rate_pct"] == 0.0

    # Singleton
    single_q = create_q("s1", "Unique question text here.", "single.pdf")
    single_res = cluster_questions([single_q])
    assert single_res.total_questions == 1
    assert len(single_res.clusters) == 1
    assert len(single_res.repeated_clusters) == 0
    assert len(single_res.single_question_clusters) == 1


def test_revision_checklist_ranking_order():
    """
    Case 6: Multi-year recurrence gets High Priority; single-paper recurrence gets Medium;
    standalone questions get Standard priority.
    """
    # High Priority: 2 papers
    q_high_1 = create_q("qh1", "Deadlock detection and prevention.", "paper1.pdf", year=2021)
    q_high_2 = create_q("qh2", "Deadlock detection and prevention.", "paper2.pdf", year=2022)

    # Medium Priority: 1 paper, repeated twice
    q_med_1 = create_q("qm1", "Explain thrashing in virtual memory.", "paper3.pdf", page=1, year=2023)
    q_med_2 = create_q("qm2", "Explain thrashing in virtual memory.", "paper3.pdf", page=2, year=2023)

    # Standard Priority: 1 appearance
    q_std = create_q("qs1", "Define critical section problem.", "paper4.pdf", year=2024)

    all_questions = [q_high_1, q_high_2, q_med_1, q_med_2, q_std]
    res = cluster_questions(all_questions, similarity_threshold=0.70)
    chk = get_revision_checklist_df(res)

    assert len(chk) == 3
    assert "High Priority" in chk.iloc[0]["Priority"]
    assert chk.iloc[0]["Distinct Papers"] == 2

    assert "Medium Priority" in chk.iloc[1]["Priority"]
    assert chk.iloc[1]["Distinct Papers"] == 1
    assert chk.iloc[1]["Total Occurrences"] == 2

    assert "Standard" in chk.iloc[2]["Priority"]
    assert chk.iloc[2]["Distinct Papers"] == 1
    assert chk.iloc[2]["Total Occurrences"] == 1
