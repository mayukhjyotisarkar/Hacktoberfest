"""
demo_phase3.py - Demonstrates Phase 3 question extraction, similarity clustering,
and recurrence metrics on synthetic exam papers.
"""

from paperpilot.pdf_extractor import extract_text_from_pdf
from paperpilot.question_parser import parse_questions_from_document
from paperpilot.similarity import cluster_questions
from paperpilot.analytics import calculate_dataset_metrics, get_repeated_clusters_df, get_revision_checklist_df


def run_demonstration():
    # Ingest 2022 and 2023 synthetic exam papers
    doc_22 = extract_text_from_pdf("data/sample_os_2022.pdf", "sample_os_2022.pdf", "Operating Systems", 2022)
    doc_23 = extract_text_from_pdf("data/sample_os_2023.pdf", "sample_os_2023.pdf", "Operating Systems", 2023)

    q_22 = parse_questions_from_document(doc_22).questions
    q_23 = parse_questions_from_document(doc_23).questions
    all_questions = q_22 + q_23

    print("=" * 70)
    print("PAPERPILOT PHASE 3 DEMONSTRATION")
    print("=" * 70)
    print(f"Total Extracted Questions: {len(all_questions)}")
    print(f"  - sample_os_2022.pdf: {len(q_22)} questions (Year 2022, Page 1)")
    print(f"  - sample_os_2023.pdf: {len(q_23)} questions (Year 2023, Page 1)\n")

    # Cluster at threshold 0.60
    threshold = 0.60
    res = cluster_questions(all_questions, similarity_threshold=threshold)
    metrics = calculate_dataset_metrics(res, all_questions)

    print(f"Summary Metrics (Threshold = {threshold}):")
    print(f"  - Total Questions: {metrics['total_questions']}")
    print(f"  - Distinct Papers: {metrics['distinct_papers']}")
    print(f"  - Total Clusters (Topics): {metrics['unique_topics']}")
    print(f"  - Repeated Clusters: {metrics['repeated_topics_count']}")
    print(f"  - Questions in Repeated Clusters: {metrics['questions_in_repeated']}")
    print(f"  - Repetition Rate: {metrics['repetition_rate_pct']}%\n")

    print("-" * 70)
    print("REPEATED QUESTION GROUPS (Occurrences >= 2)")
    print("-" * 70)
    for c in res.repeated_clusters:
        match_type = "Exact Duplicate" if c.is_exact else f"Similar (Average Sim: {c.avg_similarity * 100:.1f}%)"
        print(f"Cluster ID: {c.cluster_id}")
        print(f"  Representative Anchor: \"{c.representative_text}\"")
        print(f"  Match Type:           {match_type}")
        print(f"  Total Occurrences:    {c.occurrence_count}")
        print(f"  Distinct Papers:      {c.paper_count}")
        print(f"  Exam Years:           {c.years}")
        print("  Member Questions & Individual Similarity Scores to Anchor:")
        for q in c.questions:
            score = c.similarity_to_representative.get(q.id, 1.0)
            print(f"    * [{q.source_file} | Page {q.source_page} | Question {q.question_number} | Year {q.year}]")
            print(f"      Similarity to Anchor: {score:.3f}")
            print(f"      Text: \"{q.text}\"")
        print()

    print("-" * 70)
    print("STANDALONE TOPICS (Occurrences == 1)")
    print("-" * 70)
    print(f"Total Standalone Questions: {len(res.single_question_clusters)}")
    for idx, c in enumerate(res.single_question_clusters[:3], 1):
        q = c.questions[0]
        print(f"  {idx}. [{q.source_file} p.{q.source_page} ({q.year})] {c.representative_text[:75]}...")
    print(f"  ... and {len(res.single_question_clusters) - 3} more single-appearance questions.")

    print("\n" + "=" * 70)
    print("REVISION CHECKLIST (Derived from dataset evidence)")
    print("=" * 70)
    chk_df = get_revision_checklist_df(res)
    for idx, row in chk_df.head(4).iterrows():
        print(f"[{row['Priority']}] (Papers: {row['Distinct Papers']}, Total: {row['Total Occurrences']}, Years: {row['Exam Years']})")
        print(f"  {row['Topic / Question']}")
        print(f"  Source: {row['Sample Source']}\n")


if __name__ == "__main__":
    run_demonstration()

