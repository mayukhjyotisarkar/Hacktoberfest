"""
test_pdf_extractor.py - Unit tests for PyMuPDF text extraction.
"""

import pytest
import pymupdf
from pathlib import Path
from paperpilot.pdf_extractor import (
    extract_text_from_pdf,
    PDFExtractionError,
    ExtractedDocument,
)


@pytest.fixture
def sample_pdf_bytes():
    """Generates a synthetic 2-page text PDF in memory."""
    doc = pymupdf.open()

    page1 = doc.new_page()
    page1.insert_text((50, 72), "MID-TERM EXAMINATION 2023\nSubject: Operating Systems\n1. Explain CPU scheduling.")

    page2 = doc.new_page()
    page2.insert_text((50, 72), "2. What is deadlock? Discuss necessary conditions.\n3. Differentiate paging and segmentation.")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def empty_pdf_bytes():
    """Generates a PDF with pages but no text (simulating a scanned image PDF)."""
    doc = pymupdf.open()
    doc.new_page()  # Blank page
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_valid_pdf_bytes(sample_pdf_bytes):
    """Verifies that pages and text are extracted accurately from bytes."""
    doc = extract_text_from_pdf(
        source=sample_pdf_bytes,
        filename="test_os.pdf",
        subject="Operating Systems",
        year=2023,
    )

    assert isinstance(doc, ExtractedDocument)
    assert doc.filename == "test_os.pdf"
    assert doc.subject == "Operating Systems"
    assert doc.year == 2023
    assert doc.total_pages == 2
    assert not doc.is_scanned
    assert doc.warning_message is None

    # Check page 1
    assert doc.pages[0].page_number == 1
    assert "MID-TERM EXAMINATION 2023" in doc.pages[0].text
    assert "Explain CPU scheduling" in doc.pages[0].text

    # Check page 2
    assert doc.pages[1].page_number == 2
    assert "What is deadlock?" in doc.pages[1].text


def test_extract_from_file_path(tmp_path, sample_pdf_bytes):
    """Verifies extracting directly from a physical file path."""
    file_path = tmp_path / "sample_exam.pdf"
    file_path.write_bytes(sample_pdf_bytes)

    doc = extract_text_from_pdf(source=file_path, filename=file_path.name)
    assert doc.total_pages == 2
    assert "Explain CPU scheduling" in doc.full_text


def test_scanned_pdf_detection(empty_pdf_bytes):
    """Verifies that PDFs with no extractable text are flagged as scanned."""
    doc = extract_text_from_pdf(source=empty_pdf_bytes, filename="scanned_paper.pdf")
    assert doc.is_scanned is True
    assert doc.warning_message is not None
    assert "scanned image" in doc.warning_message.lower()


def test_empty_bytes_raises_error():
    """Verifies that passing 0-byte input raises PDFExtractionError."""
    with pytest.raises(PDFExtractionError) as exc_info:
        extract_text_from_pdf(source=b"", filename="zero_byte.pdf")
    assert "empty" in str(exc_info.value).lower()


def test_corrupt_bytes_raises_error():
    """Verifies that passing corrupt non-PDF bytes raises PDFExtractionError."""
    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf(source=b"NOT_A_REAL_PDF_CONTENT", filename="corrupt.pdf")


def test_nonexistent_file_raises_error():
    """Verifies that pointing to a nonexistent file path raises PDFExtractionError."""
    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf(source=Path("non_existent_file_123.pdf"))

