"""
test_storage.py - Unit tests for SQLite storage layer.

Verifies insert, retrieval, update, deletion, duplicate handling,
cascading foreign keys, and metadata preservation using isolated temporary databases.
"""

import sqlite3
import pytest
from paperpilot.question_parser import QuestionItem
from paperpilot.storage import PaperPilotStorage, StorageError


@pytest.fixture
def storage(tmp_path):
    """Provides an isolated SQLite storage instance in a temporary directory."""
    db_file = tmp_path / "test_paperpilot.db"
    return PaperPilotStorage(db_path=db_file)


def create_sample_question(
    q_id: str = "q1",
    num: str = "1.",
    text: str = "Explain Deadlock conditions.",
    source: str = "os_2022.pdf",
    page: int = 1,
    subject: str = "Operating Systems",
    year: int = 2022,
    marks: str = "[10 Marks]",
) -> QuestionItem:
    return QuestionItem(
        id=q_id,
        question_number=num,
        text=text,
        raw_text=f"{num} {text} {marks}",
        source_file=source,
        source_page=page,
        subject=subject,
        year=year,
        marks=marks,
    )


def test_insert_and_retrieve_paper_and_questions(storage):
    """Verifies storing a paper with questions and retrieving them intact."""
    q1 = create_sample_question("q1", "1.", "Explain Deadlock.", "os_2022.pdf", 1, "OS", 2022, "[10 Marks]")
    q2 = create_sample_question("q2", "2.", "Define Semaphore.", "os_2022.pdf", 2, "OS", 2022, "[5 Marks]")

    success = storage.save_paper(
        filename="os_2022.pdf",
        subject="OS",
        year=2022,
        questions=[q1, q2],
        overwrite=True,
    )
    assert success is True

    papers = storage.get_papers()
    assert len(papers) == 1
    assert papers[0]["filename"] == "os_2022.pdf"
    assert papers[0]["subject"] == "OS"
    assert papers[0]["year"] == 2022
    assert papers[0]["question_count"] == 2

    # Retrieve questions
    saved_questions = storage.get_questions(source_file="os_2022.pdf")
    assert len(saved_questions) == 2
    assert saved_questions[0].id == "q1"
    assert saved_questions[0].text == "Explain Deadlock."
    assert saved_questions[0].raw_text == "1. Explain Deadlock. [10 Marks]"
    assert saved_questions[0].source_page == 1
    assert saved_questions[0].marks == "[10 Marks]"
    assert saved_questions[0].year == 2022


def test_duplicate_paper_prevention(storage):
    """
    Verifies that when overwrite=False, attempting to re-save an existing paper
    returns False and does NOT create duplicates.
    When overwrite=True, it updates cleanly without orphaned records.
    """
    q1 = create_sample_question("q1", "1.", "First version of question.", "os_2022.pdf")
    storage.save_paper("os_2022.pdf", "OS", 2022, [q1], overwrite=True)

    # Attempt re-upload without overwrite
    q2 = create_sample_question("q2", "1.", "Second version of question.", "os_2022.pdf")
    res = storage.save_paper("os_2022.pdf", "OS", 2022, [q2], overwrite=False)
    assert res is False

    # Check that original remains
    papers = storage.get_papers()
    assert len(papers) == 1
    questions = storage.get_questions("os_2022.pdf")
    assert len(questions) == 1
    assert questions[0].id == "q1"

    # Now save with overwrite=True
    res_overwrite = storage.save_paper("os_2022.pdf", "Operating Systems", 2022, [q2], overwrite=True)
    assert res_overwrite is True

    papers_updated = storage.get_papers()
    assert len(papers_updated) == 1
    assert papers_updated[0]["subject"] == "Operating Systems"

    questions_updated = storage.get_questions("os_2022.pdf")
    assert len(questions_updated) == 1
    assert questions_updated[0].id == "q2"
    assert questions_updated[0].text == "Second version of question."


def test_update_question(storage):
    """Verifies updating text, marks, and exclusion state for reviewed questions."""
    q = create_sample_question("q1", "1.", "Raw question with error.", "os_2022.pdf")
    storage.save_paper("os_2022.pdf", "OS", 2022, [q])

    # Update question text and marks
    updated = storage.update_question(
        question_id="q1",
        text="Corrected question text.",
        marks="[15 Marks]",
    )
    assert updated is True

    retrieved = storage.get_question_by_id("q1")
    assert retrieved is not None
    assert retrieved.text == "Corrected question text."
    assert retrieved.marks == "[15 Marks]"
    assert retrieved.source_page == 1  # Unmodified field preserved

    # Exclude question
    storage.update_question("q1", is_excluded=True)
    assert len(storage.get_questions(include_excluded=False)) == 0
    assert len(storage.get_questions(include_excluded=True)) == 1

    # Check stats reflection
    stats = storage.get_stats()
    assert stats["active_questions"] == 0
    assert stats["excluded_questions"] == 1


def test_delete_question(storage):
    """Verifies deleting an individual question updates paper count."""
    q1 = create_sample_question("q1", "1.", "Q1", "p.pdf")
    q2 = create_sample_question("q2", "2.", "Q2", "p.pdf")
    storage.save_paper("p.pdf", "OS", 2022, [q1, q2])

    assert storage.delete_question("q1") is True
    assert storage.get_question_by_id("q1") is None
    assert len(storage.get_questions("p.pdf")) == 1

    # Paper question count must update to 1
    papers = storage.get_papers()
    assert papers[0]["question_count"] == 1

    # Deleting non-existent ID returns False
    assert storage.delete_question("nonexistent") is False


def test_delete_paper_cascades_questions(storage):
    """Verifies deleting a paper removes its questions through foreign key cascade."""
    q1 = create_sample_question("q1", "1.", "Q1", "paper_a.pdf")
    q2 = create_sample_question("q2", "2.", "Q2", "paper_b.pdf")
    storage.save_paper("paper_a.pdf", "OS", 2021, [q1])
    storage.save_paper("paper_b.pdf", "OS", 2022, [q2])

    assert storage.delete_paper("paper_a.pdf") is True

    # Paper A questions should be wiped, Paper B questions should remain
    assert storage.get_question_by_id("q1") is None
    assert storage.get_question_by_id("q2") is not None
    assert len(storage.get_papers()) == 1


def test_filter_questions(storage):
    """Verifies filtering questions by subject, year, and source file."""
    q1 = create_sample_question("q1", "1.", "Q1", "os_2022.pdf", subject="OS", year=2022)
    q2 = create_sample_question("q2", "2.", "Q2", "os_2023.pdf", subject="OS", year=2023)
    q3 = create_sample_question("q3", "3.", "Q3", "dbms_2022.pdf", subject="DBMS", year=2022)

    storage.save_paper("os_2022.pdf", "OS", 2022, [q1])
    storage.save_paper("os_2023.pdf", "OS", 2023, [q2])
    storage.save_paper("dbms_2022.pdf", "DBMS", 2022, [q3])

    assert len(storage.get_questions(subject="OS")) == 2
    assert len(storage.get_questions(year=2022)) == 2
    assert len(storage.get_questions(subject="DBMS", year=2022)) == 1
    assert len(storage.get_questions(source_file="os_2023.pdf")) == 1


def test_missing_values_and_null_year(storage):
    """Verifies that null years and null marks do not raise database errors."""
    q_null = QuestionItem(
        id="q_null",
        question_number="1.",
        text="Question with no year or marks.",
        raw_text="1. Question with no year or marks.",
        source_file="nodate.pdf",
        source_page=1,
        subject="General",
        year=None,
        marks=None,
    )
    storage.save_paper("nodate.pdf", "General", year=None, questions=[q_null])

    retrieved = storage.get_question_by_id("q_null")
    assert retrieved is not None
    assert retrieved.year is None
    assert retrieved.marks is None


def test_clear_all_reset(storage):
    """Verifies complete reset wipes papers and questions."""
    q = create_sample_question("q1", "1.", "Text", "doc.pdf")
    storage.save_paper("doc.pdf", "CS", 2023, [q])

    storage.clear_all()
    assert len(storage.get_papers()) == 0
    assert len(storage.get_questions()) == 0
    stats = storage.get_stats()
    assert stats["total_papers"] == 0
    assert stats["active_questions"] == 0


def test_transaction_rollback_on_exception(storage):
    """Verifies that an error during an operation rolls back cleanly without leaving partial records."""
    q_valid = create_sample_question("q_valid", "1.", "Valid Question", "doc.pdf")
    storage.save_paper("doc.pdf", "CS", 2023, [q_valid])

    # Trigger integrity violation inside connection block
    with pytest.raises(sqlite3.IntegrityError):
        with storage._get_connection() as conn:
            conn.execute("INSERT INTO papers (filename, subject, year, uploaded_at) VALUES ('doc2.pdf', 'CS', 2023, 'now')")
            # Trigger duplicate PRIMARY KEY integrity error
            conn.execute("INSERT INTO papers (filename, subject, year, uploaded_at) VALUES ('doc2.pdf', 'CS', 2023, 'now')")

    # Verify 'doc2.pdf' was rolled back completely and does not exist
    papers = storage.get_papers()
    assert len(papers) == 1
    assert papers[0]["filename"] == "doc.pdf"


def test_concurrent_connections_isolated(storage):
    """Verifies multiple operations across threads do not conflict or share unsafe connections."""
    import concurrent.futures

    def worker(idx):
        q = create_sample_question(f"q_{idx}", f"{idx}.", f"Question {idx}", f"doc_{idx}.pdf")
        storage.save_paper(f"doc_{idx}.pdf", "CS", 2023, [q])
        return len(storage.get_questions(f"doc_{idx}.pdf"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(8)))

    assert all(r == 1 for r in results)
    assert len(storage.get_papers()) == 8
    assert len(storage.get_questions()) == 8

