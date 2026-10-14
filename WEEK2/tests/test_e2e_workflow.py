"""
test_e2e_workflow.py - End-to-End integration test simulating the Streamlit workflow.

Verifies:
1. Ingestion of sample_os_2022.pdf and sample_os_2023.pdf.
2. Question parsing and storage in SQLite.
3. Review and correction updates.
4. Dynamic threshold adjustments.
5. Generation of CSV data for question bank and revision checklist.
6. Persistence across storage re-initialization (app restart).
7. Reset / wipe confirmation.
"""

from pathlib import Path
import pytest
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

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data"
PDF_2022 = SAMPLE_DIR / "sample_os_2022.pdf"
PDF_2023 = SAMPLE_DIR / "sample_os_2023.pdf"


def test_full_e2e_workflow(tmp_path):
    # Step 1: Initialize temporary isolated database
    test_db = tmp_path / "e2e_paperpilot.db"
    storage = PaperPilotStorage(db_path=test_db)

    assert PDF_2022.exists(), "Sample 2022 PDF fixture missing!"
    assert PDF_2023.exists(), "Sample 2023 PDF fixture missing!"

    # Step 2: Ingest 2022 PDF
    doc_2022 = extract_text_from_pdf(PDF_2022)
    assert not doc_2022.is_scanned
    res_2022 = parse_questions(doc_2022.full_text, source_file="sample_os_2022.pdf", subject="Operating Systems", year=2022)
    assert len(res_2022.questions) == 7

    storage.save_paper(
        filename="sample_os_2022.pdf",
        subject="Operating Systems",
        year=2022,
        questions=res_2022.questions,
    )

    # Step 3: Ingest 2023 PDF
    doc_2023 = extract_text_from_pdf(PDF_2023)
    assert not doc_2023.is_scanned
    res_2023 = parse_questions(doc_2023.full_text, source_file="sample_os_2023.pdf", subject="Operating Systems", year=2023)
    assert len(res_2023.questions) == 7

    storage.save_paper(
        filename="sample_os_2023.pdf",
        subject="Operating Systems",
        year=2023,
        questions=res_2023.questions,
    )

    # Verify both papers stored
    papers = storage.get_papers()
    assert len(papers) == 2
    all_q = storage.get_questions(include_excluded=False)
    assert len(all_q) == 14

    # Step 4: Review and correct a question
    target_q = all_q[0]
    storage.update_question(target_q.id, text=target_q.text + " [Verified Corrected]")
    updated_q = storage.get_question_by_id(target_q.id)
    assert "[Verified Corrected]" in updated_q.text

    # Step 5: Test dynamic threshold clustering
    # At threshold 0.60, deadlock questions from 2022 and 2023 cluster together
    analysis_60 = cluster_questions(storage.get_questions(), similarity_threshold=0.60)
    assert len(analysis_60.repeated_clusters) == 1
    rep_cluster = analysis_60.repeated_clusters[0]
    assert rep_cluster.paper_count == 2
    assert rep_cluster.occurrence_count == 2
    assert sorted(rep_cluster.years) == [2022, 2023]
    assert len(rep_cluster.similarity_to_representative) == 2

    # At threshold 0.95 (near exact match only), they split
    analysis_95 = cluster_questions(storage.get_questions(), similarity_threshold=0.95)
    assert len(analysis_95.repeated_clusters) == 0

    # Step 6: Verify CSV generation and content
    q_df = get_all_questions_df(storage.get_questions())
    csv_bank = q_df.to_csv(index=False)
    assert "sample_os_2022.pdf" in csv_bank
    assert "sample_os_2023.pdf" in csv_bank
    assert "Question Text" in csv_bank

    chk_df = get_revision_checklist_df(analysis_60)
    csv_chk = chk_df.to_csv(index=False)
    assert "High Priority (Multi-Year)" in csv_chk
    assert "Distinct Papers" in csv_chk

    # Step 7: Persistence across restart simulation
    storage_restart = PaperPilotStorage(db_path=test_db)
    reloaded_papers = storage_restart.get_papers()
    assert len(reloaded_papers) == 2
    reloaded_questions = storage_restart.get_questions()
    assert len(reloaded_questions) == 14
    assert "[Verified Corrected]" in storage_restart.get_question_by_id(target_q.id).text

    # Step 8: Reset operation
    storage_restart.clear_all()
    assert len(storage_restart.get_papers()) == 0
    assert len(storage_restart.get_questions()) == 0

