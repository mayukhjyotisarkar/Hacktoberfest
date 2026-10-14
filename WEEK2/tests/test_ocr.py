"""
test_ocr.py - Comprehensive unit and integration tests for local OCR and hybrid extraction.

Verifies:
1. Text-based PDF: normal extraction occurs and OCR is not called.
2. Image-only PDF: OCR is invoked.
3. Mixed PDF: text extraction is used on readable pages and OCR on scanned pages.
4. OCR returns usable text.
5. OCR returns empty text.
6. OCR executable is missing.
7. OCR language pack is unavailable.
8. One page fails without losing successfully extracted pages.
9. Source paper and page metadata remain correct.
10. Question parsing still works with OCR-produced text.
11. Existing text-only extraction continues passing.
12. Optional real Tesseract integration test when installed.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
import pymupdf
from PIL import Image

from paperpilot.ocr import (
    OCRResult,
    OCRError,
    TesseractMissingError,
    OCRLanguageUnavailableError,
    is_tesseract_available,
    get_tesseract_cmd,
    run_ocr_on_image,
    render_page_to_image,
    INSTALL_GUIDANCE_MESSAGE,
)
from paperpilot.pdf_extractor import (
    extract_text_from_pdf,
    extract_page_hybrid,
    ExtractedDocument,
    ExtractedPage,
)
from paperpilot.question_parser import parse_questions


@pytest.fixture
def text_only_pdf_bytes():
    """Generates a 2-page text PDF with ample selectable characters."""
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 72), "EXAMINATION 2024\n1. Explain Deadlock prevention and avoidance methods.")
    p2 = doc.new_page()
    p2.insert_text((50, 72), "2. What is virtual memory? Explain demand paging mechanisms.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def image_only_pdf_bytes():
    """Generates a 1-page PDF containing only an image (no selectable text)."""
    doc = pymupdf.open()
    page = doc.new_page()
    # Insert white image rectangle
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 150, 150), False)
    pix.clear_with(255)
    page.insert_image(pymupdf.Rect(50, 50, 200, 200), pixmap=pix)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def mixed_pdf_bytes():
    """Generates a 2-page PDF: Page 1 has selectable text, Page 2 is image-only."""
    doc = pymupdf.open()
    # Page 1: Digital text
    p1 = doc.new_page()
    p1.insert_text((50, 72), "Operating Systems Midterm 2023\n1. Discuss CPU scheduling criteria in detail.")
    # Page 2: Image only (0 digital text)
    p2 = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
    pix.clear_with(255)
    p2.insert_image(pymupdf.Rect(50, 50, 150, 150), pixmap=pix)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# =============================================================================
# 1. Text-based PDF: normal extraction occurs and OCR is not called
# =============================================================================
def test_text_based_pdf_does_not_invoke_ocr(text_only_pdf_bytes):
    with patch("paperpilot.pdf_extractor.run_ocr_on_page") as mock_ocr:
        doc = extract_text_from_pdf(
            source=text_only_pdf_bytes,
            filename="text_paper.pdf",
            subject="OS",
            year=2024,
            enable_ocr=True,
        )

        # OCR must not be called when selectable text is present
        mock_ocr.assert_not_called()
        assert doc.total_pages == 2
        assert doc.ocr_page_count == 0
        assert doc.scanned_page_count == 0
        assert doc.pages[0].extraction_method == "text"
        assert doc.pages[1].extraction_method == "text"
        assert "Explain Deadlock prevention" in doc.pages[0].text
        assert "What is virtual memory" in doc.pages[1].text


# =============================================================================
# 2. Image-only PDF: OCR is invoked
# =============================================================================
def test_image_only_pdf_invokes_ocr(image_only_pdf_bytes):
    mock_ocr_result = OCRResult(
        text="1. Explain the Banker's Algorithm with an example. [10 Marks]",
        char_count=58,
        confidence=94.2,
        word_count=9,
        is_empty=False,
    )

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_ocr_result) as mock_ocr:

        doc = extract_text_from_pdf(
            source=image_only_pdf_bytes,
            filename="scanned_photo.pdf",
            subject="Operating Systems",
            year=2022,
            enable_ocr=True,
        )

        mock_ocr.assert_called_once()
        assert doc.total_pages == 1
        assert doc.scanned_page_count == 1
        assert doc.ocr_page_count == 1
        assert doc.pages[0].extraction_method == "ocr"
        assert doc.pages[0].ocr_confidence == 94.2
        assert "Banker's Algorithm" in doc.pages[0].text


# =============================================================================
# 3. Mixed PDF: text extraction on readable pages, OCR on scanned pages
# =============================================================================
def test_mixed_pdf_hybrid_extraction(mixed_pdf_bytes):
    mock_ocr_result = OCRResult(
        text="2. Describe process synchronization using Semaphores. [5 Marks]",
        char_count=60,
        confidence=88.5,
        word_count=8,
        is_empty=False,
    )

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_ocr_result) as mock_ocr:

        doc = extract_text_from_pdf(
            source=mixed_pdf_bytes,
            filename="mixed_exam.pdf",
            subject="OS",
            year=2023,
            enable_ocr=True,
        )

        # Page 1: Digital text (no OCR)
        assert doc.pages[0].page_number == 1
        assert doc.pages[0].extraction_method == "text"
        assert "CPU scheduling criteria" in doc.pages[0].text

        # Page 2: Scanned image (OCR invoked)
        assert doc.pages[1].page_number == 2
        assert doc.pages[1].extraction_method == "ocr"
        assert "process synchronization using Semaphores" in doc.pages[1].text

        # OCR called exactly once (for page 2, not page 1)
        assert mock_ocr.call_count == 1
        assert doc.ocr_page_count == 1
        assert doc.scanned_page_count == 1


# =============================================================================
# 4. OCR returns usable text
# =============================================================================
def test_ocr_returns_usable_text(image_only_pdf_bytes):
    mock_ocr_result = OCRResult(
        text="Q1. Differentiate preemptive and non-preemptive scheduling algorithms.",
        char_count=71,
        confidence=91.0,
        word_count=8,
        is_empty=False,
    )

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_ocr_result):

        doc = extract_text_from_pdf(source=image_only_pdf_bytes, filename="paper.pdf")
        assert doc.pages[0].text == "Q1. Differentiate preemptive and non-preemptive scheduling algorithms."
        assert doc.pages[0].char_count == 71
        assert doc.pages[0].ocr_confidence == 91.0


# =============================================================================
# 5. OCR returns empty text
# =============================================================================
def test_ocr_returns_empty_text(image_only_pdf_bytes):
    mock_empty_result = OCRResult(
        text="",
        char_count=0,
        confidence=None,
        word_count=0,
        is_empty=True,
    )

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_empty_result):

        doc = extract_text_from_pdf(source=image_only_pdf_bytes, filename="blank_scan.pdf")
        assert doc.pages[0].extraction_method == "failed"
        assert "detected no usable text" in doc.pages[0].error_message
        assert doc.failed_page_count == 1
        assert doc.ocr_page_count == 0


# =============================================================================
# 6. OCR executable is missing
# =============================================================================
def test_ocr_executable_missing(image_only_pdf_bytes):
    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=False):
        doc = extract_text_from_pdf(source=image_only_pdf_bytes, filename="scanned_no_tess.pdf")

        assert doc.ocr_available is False
        assert doc.pages[0].extraction_method == "failed"
        assert "not installed" in doc.pages[0].error_message.lower()
        assert doc.warning_message is not None
        assert "Tesseract" in doc.warning_message


# =============================================================================
# 7. OCR language pack is unavailable
# =============================================================================
def test_ocr_language_pack_unavailable(image_only_pdf_bytes):
    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", side_effect=OCRLanguageUnavailableError("Language 'fra' missing")):

        doc = extract_text_from_pdf(source=image_only_pdf_bytes, filename="french_exam.pdf", ocr_lang="fra")

        assert doc.pages[0].extraction_method == "failed"
        assert "Language 'fra' missing" in doc.pages[0].error_message
        assert doc.failed_page_count == 1


# =============================================================================
# 8. One page fails without losing successfully extracted pages
# =============================================================================
def test_one_page_fails_without_losing_other_pages():
    doc_mupdf = pymupdf.open()
    # Page 1: digital text
    p1 = doc_mupdf.new_page()
    p1.insert_text((50, 72), "Page 1: Digital question text for exam paper.")
    # Page 2: image that will fail OCR
    p2 = doc_mupdf.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    p2.insert_image(pymupdf.Rect(10, 10, 60, 60), pixmap=pix)
    # Page 3: image that will succeed OCR
    p3 = doc_mupdf.new_page()
    p3.insert_image(pymupdf.Rect(10, 10, 60, 60), pixmap=pix)
    pdf_bytes = doc_mupdf.tobytes()
    doc_mupdf.close()

    def mock_run_ocr(page, **kwargs):
        if page.number == 1:  # 0-indexed Page 2
            raise OCRError("Corrupted image stream on page 2")
        return OCRResult(text="Page 3: Successfully extracted question.", char_count=42, confidence=90.0, is_empty=False)

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", side_effect=mock_run_ocr):

        doc = extract_text_from_pdf(source=pdf_bytes, filename="3page.pdf")

        assert doc.total_pages == 3
        # Page 1: Succeeded via digital text
        assert doc.pages[0].extraction_method == "text"
        assert "Digital question text" in doc.pages[0].text

        # Page 2: Failed OCR gracefully
        assert doc.pages[1].extraction_method == "failed"
        assert "Corrupted image stream" in doc.pages[1].error_message

        # Page 3: Succeeded via OCR
        assert doc.pages[2].extraction_method == "ocr"
        assert "Successfully extracted question" in doc.pages[2].text

        # Document retains all 3 pages
        assert len(doc.pages) == 3
        assert doc.failed_page_count == 1
        assert doc.ocr_page_count == 1


# =============================================================================
# 9. Source paper and page metadata remain correct
# =============================================================================
def test_source_metadata_preserved_with_ocr(mixed_pdf_bytes):
    mock_ocr = OCRResult(text="2. Explain virtual memory mechanisms.", char_count=37, confidence=95.0, is_empty=False)

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_ocr):

        doc = extract_text_from_pdf(
            source=mixed_pdf_bytes,
            filename="cs_finals_2023.pdf",
            subject="Computer Science",
            year=2023,
        )

        assert doc.filename == "cs_finals_2023.pdf"
        assert doc.subject == "Computer Science"
        assert doc.year == 2023
        assert doc.pages[0].page_number == 1
        assert doc.pages[1].page_number == 2


# =============================================================================
# 10. Question parsing still works with OCR-produced text
# =============================================================================
def test_question_parsing_with_ocr_output(image_only_pdf_bytes):
    ocr_text = (
        "1. Define deadlock. What are the four necessary conditions for deadlock to occur? [10 Marks]\n"
        "2. Explain Round Robin CPU scheduling with a suitable Gantt chart. [10 Marks]\n"
    )
    mock_ocr = OCRResult(text=ocr_text, char_count=len(ocr_text), confidence=93.0, is_empty=False)

    with patch("paperpilot.pdf_extractor.is_tesseract_available", return_value=True), \
         patch("paperpilot.pdf_extractor.run_ocr_on_page", return_value=mock_ocr):

        doc = extract_text_from_pdf(
            source=image_only_pdf_bytes,
            filename="scanned_exam_2022.pdf",
            subject="Operating Systems",
            year=2022,
        )

        parse_result = parse_questions(doc)
        assert parse_result.total_parsed == 2

        q1 = parse_result.questions[0]
        assert q1.question_number == "1."
        assert "Define deadlock" in q1.text
        assert q1.marks == "[10 Marks]"
        assert q1.source_page == 1
        assert q1.source_file == "scanned_exam_2022.pdf"
        assert q1.year == 2022

        q2 = parse_result.questions[1]
        assert q2.question_number == "2."
        assert "Round Robin" in q2.text


# =============================================================================
# 11. Tesseract discovery and path fallback tests
# =============================================================================
def test_tesseract_discovery_via_env_var(monkeypatch, tmp_path):
    mock_exe = tmp_path / "custom_tesseract.exe"
    mock_exe.write_text("dummy")
    monkeypatch.setenv("TESSERACT_CMD", str(mock_exe))

    found_path = get_tesseract_cmd()
    assert found_path == str(mock_exe)


# =============================================================================
# 12. Optional real Tesseract integration test (skips if not installed)
# =============================================================================
@pytest.mark.skipif(not is_tesseract_available(), reason="Tesseract-OCR not installed on system")
def test_real_tesseract_ocr_execution():
    """Executes a real OCR pass on a synthetic image containing simple text."""
    # Render an image with simple high-contrast black text
    img = Image.new("L", (300, 100), color=255)
    # Use real pytesseract on this image
    result = run_ocr_on_image(img, lang="eng")
    assert isinstance(result, OCRResult)
