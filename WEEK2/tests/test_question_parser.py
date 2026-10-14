"""
test_question_parser.py - Unit tests for question segmentation and filtering.
"""

from paperpilot.pdf_extractor import ExtractedDocument, ExtractedPage
from paperpilot.question_parser import (
    parse_questions_from_document,
    is_false_positive_header,
    clean_question_body,
)


def test_false_positive_detection():
    """Verifies that non-question exam headers and instructions are identified."""
    assert is_false_positive_header("Time: 3 Hours") is True
    assert is_false_positive_header("Max Marks: 100") is True
    assert is_false_positive_header("Note: Answer any five questions.") is True
    assert is_false_positive_header("SECTION - A") is True
    assert is_false_positive_header("Page 1 of 3") is True
    assert is_false_positive_header("Roll No: 2021BCSE042") is True

    # Real questions should NOT be detected as false positive headers
    assert is_false_positive_header("1. Explain process scheduling algorithms.") is False
    assert is_false_positive_header("Q2. Define normal forms in DBMS.") is False


def test_clean_question_body():
    """Verifies that internal tabs, excess newlines, and trailing spaces are cleaned."""
    raw = "What is   a semaphore?\n  Explain counting  vs binary semaphores. \n"
    expected = "What is a semaphore? Explain counting vs binary semaphores."
    assert clean_question_body(raw) == expected


def test_parse_standard_numbered_questions():
    """Verifies parsing 1., 2., 3. style exam questions."""
    doc = ExtractedDocument(
        filename="dbms_2023.pdf",
        subject="Database Management Systems",
        year=2023,
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "UNIVERSITY EXAM 2023\n"
                    "Time: 3 Hours\n"
                    "Max Marks: 100\n"
                    "1. Explain the three-tier ANSI-SPARC architecture of DBMS. [10 Marks]\n"
                    "2. What is normalization? Explain 1NF, 2NF, and 3NF with examples. [15 Marks]\n"
                    "3. Differentiate between B-Tree and B+ Tree indexing.\n"
                ),
                char_count=260,
            )
        ],
        total_pages=1,
    )

    result = parse_questions_from_document(doc)

    assert result.total_parsed == 3
    q1, q2, q3 = result.questions

    assert q1.question_number in ["1.", "1"]
    assert "ANSI-SPARC architecture" in q1.text
    assert q1.marks == "[10 Marks]"
    assert q1.source_file == "dbms_2023.pdf"
    assert q1.source_page == 1

    assert "normalization" in q2.text.lower()
    assert q2.marks == "[15 Marks]"

    assert "B-Tree and B+ Tree" in q3.text
    assert q3.marks is None

    # Verify headers were preserved in unparsed_segments
    assert any("Time: 3 Hours" in s for s in result.unparsed_segments)


def test_parse_alphanumeric_subquestions():
    """Verifies parsing sub-questions like 1(a), 1(b), (i), Q2:."""
    doc = ExtractedDocument(
        filename="os_midterm.pdf",
        subject="Operating Systems",
        year=2024,
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "SECTION A\n"
                    "1(a) Define operating system system calls.\n"
                    "1(b) Describe PCB and its contents. [5]\n"
                    "Q2: Explain Bankers algorithm for deadlock avoidance. [10 Marks]\n"
                    "(i) What is thrashing in virtual memory?\n"
                ),
                char_count=230,
            )
        ],
        total_pages=1,
    )

    result = parse_questions_from_document(doc)
    assert result.total_parsed == 4

    numbers = [q.question_number for q in result.questions]
    assert any("1(a)" in n or "1" in n for n in numbers)
    assert any("Q2" in n or "2" in n for n in numbers)
    assert any("(i)" in n for n in numbers)


def test_multiline_question_accumulation():
    """Verifies that questions spanning multiple lines are merged without truncation."""
    doc = ExtractedDocument(
        filename="compiler_2022.pdf",
        subject="Compiler Design",
        year=2022,
        pages=[
            ExtractedPage(
                page_number=1,
                text=(
                    "1. Construct a predictive parsing table for the given grammar:\n"
                    "   E -> E + T | T\n"
                    "   T -> T * F | F\n"
                    "   Show each step clearly. [12 Marks]\n"
                    "2. Explain Lex and Yacc tools.\n"
                ),
                char_count=180,
            )
        ],
        total_pages=1,
    )

    result = parse_questions_from_document(doc)
    assert result.total_parsed == 2

    q1 = result.questions[0]
    assert "E -> E + T" in q1.text
    assert "Show each step clearly" in q1.text
    assert q1.marks == "[12 Marks]"


def test_no_questions_found_preserves_content():
    """Verifies documents with no recognized questions do not crash and preserve content."""
    doc = ExtractedDocument(
        filename="notes.pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text="This is a summary note without question numbers.\nChapter 1 covers OS introduction.",
                char_count=85,
            )
        ],
        total_pages=1,
    )

    result = parse_questions_from_document(doc)
    assert result.total_parsed == 0
    assert len(result.unparsed_segments) > 0

