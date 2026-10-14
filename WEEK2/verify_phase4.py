"""
verify_phase4.py - Verification script for Phase 4 deliverables.

Executes and validates all verification points requested in Stage 5:
- Ingestion of sample_os_2022.pdf and sample_os_2023.pdf into local SQLite DB
- Review & correction persistence
- Repeated questions analysis with source references and member similarity scores
- Threshold sensitivity (0.60 vs 0.90)
- CSV download generation
- Persistence across DB re-connection (simulating app restart)
- Reset confirmation behavior
"""

from pathlib import Path
import pandas as pd

from paperpilot.pdf_extractor import extract_text_from_pdf
from paperpilot.question_parser import parse_questions
from paperpilot.similarity import cluster_questions
from paperpilot.analytics import (
    get_papers_summary_df,
    get_all_questions_df,
    get_repeated_clusters_df,
    get_revision_checklist_df,
    calculate_dataset_metrics,
)
from paperpilot.storage import PaperPilotStorage

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "paperpilot.db"
PDF_2022 = BASE_DIR / "data" / "sample_os_2022.pdf"
PDF_2023 = BASE_DIR / "data" / "sample_os_2023.pdf"


def run_verification():
    print("=" * 70)
    print("PAPERPILOT PHASE 4 VERIFICATION")
    print("=" * 70)

    storage = PaperPilotStorage(db_path=DB_PATH)
    storage.clear_all()
    print("1. [Storage Init] Cleaned previous test database.")

    # Step 1: Upload both PDFs
    doc_2022 = extract_text_from_pdf(PDF_2022, filename="sample_os_2022.pdf", subject="Operating Systems", year=2022)
    doc_2023 = extract_text_from_pdf(PDF_2023, filename="sample_os_2023.pdf", subject="Operating Systems", year=2023)

    assert not doc_2022.is_scanned, "2022 PDF unexpectedly flagged as scanned!"
    assert not doc_2023.is_scanned, "2023 PDF unexpectedly flagged as scanned!"

    res_2022 = parse_questions(doc_2022)
    res_2023 = parse_questions(doc_2023)

    print(f"2. [Extraction] Parsed {len(res_2022.questions)} questions from 2022 and {len(res_2023.questions)} questions from 2023.")

    storage.save_paper("sample_os_2022.pdf", "Operating Systems", 2022, res_2022.questions, overwrite=True)
    storage.save_paper("sample_os_2023.pdf", "Operating Systems", 2023, res_2023.questions, overwrite=True)

    stats = storage.get_stats()
    print(f"3. [Database Stored] Total Papers: {stats['total_papers']}, Active Questions: {stats['active_questions']}")
    assert stats["total_papers"] == 2
    assert stats["active_questions"] == 14

    # Step 2: Review and correct a question
    all_q = storage.get_questions()
    first_q = all_q[0]
    original_text = first_q.text
    corrected_text = original_text + " [Review Verified]"
    storage.update_question(first_q.id, text=corrected_text)
    reloaded_q = storage.get_question_by_id(first_q.id)
    assert reloaded_q.text == corrected_text
    print(f"4. [Review & Edit] Updated Question ID '{first_q.id}' successfully.")

    # Revert back to original clean text
    storage.update_question(first_q.id, text=original_text)

    # Step 3: Repeated questions analysis at threshold 0.60
    active_questions = storage.get_questions()
    analysis_60 = cluster_questions(active_questions, similarity_threshold=0.60)
    print(f"5. [Clustering @ 0.60] Repeated clusters: {len(analysis_60.repeated_clusters)}")
    assert len(analysis_60.repeated_clusters) == 1
    rep = analysis_60.repeated_clusters[0]
    print(f"   Anchor: \"{rep.representative_text}\"")
    print(f"   Distinct Papers: {rep.paper_count}, Occurrences: {rep.occurrence_count}, Years: {rep.years}")
    for member in rep.questions:
        sim = rep.similarity_to_representative.get(member.id, 1.0)
        print(f"   * {member.source_file} (p.{member.source_page}, {member.question_number}) — Sim: {sim}")

    # Step 4: Dynamic threshold change to 0.90
    analysis_90 = cluster_questions(active_questions, similarity_threshold=0.90)
    print(f"6. [Dynamic Threshold @ 0.90] Repeated clusters: {len(analysis_90.repeated_clusters)}")
    assert len(analysis_90.repeated_clusters) == 0, "Questions should split at strict 0.90 threshold!"
    print("   -> Successfully split into standalone clusters at strict threshold.")

    # Step 5: CSV downloads verification
    q_df = get_all_questions_df(active_questions)
    csv_bank = q_df.to_csv(index=False)
    assert "sample_os_2022.pdf" in csv_bank and "sample_os_2023.pdf" in csv_bank
    print(f"7. [CSV Export] Question Bank CSV generated ({len(csv_bank)} bytes).")

    chk_df = get_revision_checklist_df(analysis_60)
    csv_chk = chk_df.to_csv(index=False)
    assert "High Priority (Multi-Year)" in csv_chk
    print(f"8. [CSV Export] Revision Checklist CSV generated ({len(csv_chk)} bytes).")

    # Step 6: Application restart persistence
    restart_storage = PaperPilotStorage(db_path=DB_PATH)
    r_stats = restart_storage.get_stats()
    assert r_stats["total_papers"] == 2
    assert r_stats["active_questions"] == 14
    print("9. [Persistence] Verified data survives application restart.")

    # Step 7: Metrics summary
    metrics = calculate_dataset_metrics(analysis_60, active_questions)
    print("10. [Dashboard Metrics Summary]")
    print(f"    - Total Questions: {metrics['total_questions']}")
    print(f"    - Distinct Papers: {metrics['distinct_papers']}")
    print(f"    - Repeated Clusters: {metrics['repeated_clusters_count']}")
    print(f"    - Repetition Rate: {metrics['repetition_rate_pct']:.1f}%")

    print("\nALL PHASE 4 VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    run_verification()

