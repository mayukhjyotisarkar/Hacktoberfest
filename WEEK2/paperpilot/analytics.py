"""
analytics.py - Frequency metrics, recurrence analysis, and revision prioritization.

Derives all counts strictly from the uploaded dataset, clearly distinguishing
total occurrences from distinct paper appearances, and generates structured
DataFrames ready for interactive Streamlit display and CSV downloads.
"""

from typing import List, Dict, Any, Optional
import pandas as pd

from paperpilot.question_parser import QuestionItem
from paperpilot.similarity import SimilarityAnalysisResult, QuestionCluster


def get_papers_summary_df(questions: List[QuestionItem]) -> pd.DataFrame:
    """
    Summarizes question count, subject, and year for each distinct uploaded paper.
    """
    if not questions:
        return pd.DataFrame(columns=["Filename", "Subject", "Year", "Questions Extracted"])

    paper_dict: Dict[str, Dict[str, Any]] = {}
    for q in questions:
        fname = q.source_file
        if fname not in paper_dict:
            paper_dict[fname] = {
                "Filename": fname,
                "Subject": q.subject,
                "Year": q.year if q.year is not None else "Unknown",
                "Questions Extracted": 0,
            }
        paper_dict[fname]["Questions Extracted"] += 1

    df = pd.DataFrame(list(paper_dict.values()))
    df = df.sort_values(by="Questions Extracted", ascending=False).reset_index(drop=True)
    return df


def get_all_questions_df(questions: List[QuestionItem]) -> pd.DataFrame:
    """
    Converts list of QuestionItems into a searchable DataFrame.
    """
    if not questions:
        return pd.DataFrame(columns=[
            "ID", "Question No", "Question Text", "Paper", "Page", "Subject", "Year", "Marks"
        ])

    data = []
    for q in questions:
        data.append({
            "ID": q.id,
            "Question No": q.question_number,
            "Question Text": q.text,
            "Paper": q.source_file,
            "Page": q.source_page,
            "Subject": q.subject,
            "Year": q.year if q.year is not None else "Unknown",
            "Marks": q.marks or "-",
        })
    return pd.DataFrame(data)


def get_repeated_clusters_df(result: SimilarityAnalysisResult) -> pd.DataFrame:
    """
    Constructs a detailed summary table of repeated question clusters.

    Crucial Distinction:
    - Distinct Papers: Number of different exam papers where this question appeared.
    - Total Occurrences: Total count of times this question was asked across all papers.
    """
    if not result.repeated_clusters:
        return pd.DataFrame(columns=[
            "Cluster ID", "Representative Question", "Match Type",
            "Distinct Papers", "Total Occurrences", "Exam Years", "Sources"
        ])

    data = []
    for c in result.repeated_clusters:
        match_type = "Exact Match" if c.is_exact else f"Similar (~{int(c.avg_similarity * 100)}%)"
        years_str = ", ".join(str(y) for y in c.years) if c.years else "N/A"
        sources_str = "; ".join([
            f"{q.source_file} (p.{q.source_page}, {q.question_number}, sim: {c.similarity_to_representative.get(q.id, 1.0)})"
            for q in c.questions
        ])

        data.append({
            "Cluster ID": c.cluster_id,
            "Representative Question": c.representative_text,
            "Match Type": match_type,
            "Distinct Papers": c.paper_count,
            "Total Occurrences": c.occurrence_count,
            "Exam Years": years_str,
            "Sources": sources_str,
        })

    df = pd.DataFrame(data)
    return df


def get_revision_checklist_df(result: SimilarityAnalysisResult) -> pd.DataFrame:
    """
    Ranks questions into high, medium, and low revision priority tiers based on
    cross-paper recurrence.

    Priority Tiers:
    - High Priority: Appears across 2 or more distinct exam papers/years.
    - Medium Priority: Repeated within the same paper or borderline similarity.
    - Standard Priority: Appeared in only 1 paper so far.
    """
    data = []
    for c in result.clusters:
        if c.paper_count >= 2:
            priority = "High Priority (Multi-Year)"
            priority_rank = 1
        elif c.occurrence_count >= 2:
            priority = "Medium Priority (Repeated)"
            priority_rank = 2
        else:
            priority = "Standard (Single Appearance)"
            priority_rank = 3

        years_str = ", ".join(str(y) for y in c.years) if c.years else "N/A"

        data.append({
            "Priority": priority,
            "Priority Rank": priority_rank,
            "Topic / Question": c.representative_text,
            "Distinct Papers": c.paper_count,
            "Total Occurrences": c.occurrence_count,
            "Exam Years": years_str,
            "Sample Source": f"{c.questions[0].source_file} (p.{c.questions[0].source_page})"
        })

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(
            by=["Priority Rank", "Distinct Papers", "Total Occurrences"],
            ascending=[True, False, False]
        ).reset_index(drop=True)
        df = df.drop(columns=["Priority Rank"])
    return df


def calculate_dataset_metrics(result: SimilarityAnalysisResult, questions: List[QuestionItem]) -> Dict[str, Any]:
    """
    Computes high-level analytics metrics for the dashboard header.
    """
    total_q = len(questions)
    unique_clusters = len(result.clusters)
    repeated_clusters_count = len(result.repeated_clusters)
    distinct_papers = len(set(q.source_file for q in questions))

    # Calculate repetition rate: percentage of questions that belong to a repeated cluster
    questions_in_repeated = sum(c.occurrence_count for c in result.repeated_clusters)
    repetition_rate = (questions_in_repeated / total_q * 100) if total_q > 0 else 0.0

    return {
        "total_questions": total_q,
        "distinct_papers": distinct_papers,
        "unique_topics": unique_clusters,
        "repeated_topics_count": repeated_clusters_count,
        "questions_in_repeated": questions_in_repeated,
        "repetition_rate_pct": round(repetition_rate, 1),
    }
