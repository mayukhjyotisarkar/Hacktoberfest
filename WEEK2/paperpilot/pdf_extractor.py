"""
pdf_extractor.py - Hybrid PDF text extraction engine using PyMuPDF and local Tesseract OCR.

Extracts text page-by-page from digital and scanned PDF question papers while tracking
page numbers, running local OCR on image-only/scanned pages, preserving question structure,
and handling corrupted documents gracefully.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union, BinaryIO
import pymupdf

from paperpilot.ocr import (
    is_tesseract_available,
    run_ocr_on_page,
    TesseractMissingError,
    OCRLanguageUnavailableError,
    OCRError,
    INSTALL_GUIDANCE_MESSAGE,
)


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be opened or parsed."""
    pass


@dataclass
class ExtractedPage:
    """Represents text extracted from a single PDF page."""
    page_number: int  # 1-indexed for user readability
    text: str
    char_count: int
    extraction_method: str = "text"  # "text", "ocr", or "failed"
    ocr_confidence: Optional[float] = None
    ocr_word_count: int = 0
    error_message: Optional[str] = None


@dataclass
class ExtractedDocument:
    """Represents a complete extracted PDF document with metadata."""
    filename: str
    subject: str = "General"
    year: Optional[int] = None
    pages: List[ExtractedPage] = field(default_factory=list)
    total_pages: int = 0
    total_chars: int = 0
    is_scanned: bool = False
    warning_message: Optional[str] = None
    scanned_page_count: int = 0
    ocr_page_count: int = 0
    failed_page_count: int = 0
    ocr_available: bool = True
    ocr_warnings: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Concatenates text from all pages with page markers."""
        return "\n\n".join(
            f"--- [Page {p.page_number}] ---\n{p.text}" for p in self.pages
        )

    @property
    def avg_ocr_confidence(self) -> Optional[float]:
        """Calculates average OCR confidence across pages that were OCR'd."""
        confs = [
            p.ocr_confidence
            for p in self.pages
            if p.extraction_method == "ocr" and p.ocr_confidence is not None
        ]
        if not confs:
            return None
        return round(sum(confs) / len(confs), 2)


def extract_page_hybrid(
    page: pymupdf.Page,
    page_number: int,
    min_page_chars: int = 30,
    enable_ocr: bool = True,
    ocr_lang: str = "eng",
) -> ExtractedPage:
    """
    Extracts text from a single PDF page using hybrid digital text + local OCR.

    Parameters:
    -----------
    page : pymupdf.Page
        The open PyMuPDF page object.
    page_number : int
        1-indexed page number.
    min_page_chars : int
        Minimum character threshold below which a page is treated as scanned/image-only.
    enable_ocr : bool
        Whether to attempt local OCR if digital text is insufficient.
    ocr_lang : str
        Tesseract language code (defaults to 'eng').

    Returns:
    --------
    ExtractedPage
        Object containing the extracted text, char count, and extraction method.
    """
    # 1. Attempt standard digital text extraction first
    page_text = page.get_text("text").strip()
    char_count = len(page_text)

    if char_count >= min_page_chars:
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="text",
        )

    # 2. Digital text is absent or insufficient: Page is scanned / image-only
    if not enable_ocr:
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="failed" if char_count == 0 else "text",
            error_message="OCR is disabled for this page.",
        )

    # 3. Check Tesseract availability
    if not is_tesseract_available():
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="failed",
            error_message="Tesseract-OCR executable is not installed or not found on PATH.",
        )

    # 4. Run local OCR on rendered image
    try:
        ocr_result = run_ocr_on_page(page, lang=ocr_lang)
        if ocr_result.is_empty:
            return ExtractedPage(
                page_number=page_number,
                text="",
                char_count=0,
                extraction_method="failed",
                error_message="OCR processed the page but detected no usable text.",
            )

        return ExtractedPage(
            page_number=page_number,
            text=ocr_result.text,
            char_count=ocr_result.char_count,
            extraction_method="ocr",
            ocr_confidence=ocr_result.confidence,
            ocr_word_count=ocr_result.word_count,
        )

    except TesseractMissingError as e:
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="failed",
            error_message=str(e),
        )
    except OCRLanguageUnavailableError as e:
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="failed",
            error_message=str(e),
        )
    except Exception as e:
        return ExtractedPage(
            page_number=page_number,
            text=page_text,
            char_count=char_count,
            extraction_method="failed",
            error_message=f"OCR execution failed on page {page_number}: {e}",
        )


def extract_text_from_pdf(
    source: Union[str, Path, bytes, BinaryIO],
    filename: str = "unknown.pdf",
    subject: str = "General",
    year: Optional[int] = None,
    min_chars_threshold: int = 30,
    enable_ocr: bool = True,
    ocr_lang: str = "eng",
    min_page_chars: int = 30,
) -> ExtractedDocument:
    """
    Extracts text page-by-page from a PDF file path or byte buffer using hybrid extraction.

    For each page:
    - If digital text is present (>= min_page_chars), uses it without calling OCR.
    - If digital text is missing (< min_page_chars) and enable_ocr=True, renders the page
      and executes local Tesseract OCR.
    - If OCR is unavailable or fails on a page, that page is flagged as failed while
      other pages continue without crashing the document.

    Parameters:
    -----------
    source : Union[str, Path, bytes, BinaryIO]
        File path on disk, raw bytes, or file-like buffer (e.g. Streamlit UploadedFile).
    filename : str
        Human-readable name of the file for reporting and tracking.
    subject : str
        Academic subject assigned to this exam paper.
    year : Optional[int]
        Examination year (e.g. 2023, 2024).
    min_chars_threshold : int
        Minimum character count across digital text below which the document
        is flagged as a scanned image.
    enable_ocr : bool
        Whether to run local OCR on image-only/scanned pages.
    ocr_lang : str
        Tesseract language code (defaults to 'eng').
    min_page_chars : int
        Per-page character threshold below which OCR is triggered.

    Returns:
    --------
    ExtractedDocument
        Structured object containing extracted text, page references, OCR statistics, and metadata.

    Raises:
    -------
    PDFExtractionError
        If the file is corrupt, empty, or cannot be parsed by PyMuPDF.
    """
    doc = None
    try:
        # PyMuPDF supports opening from either filepath or byte stream
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise PDFExtractionError(f"File not found: {path}")
            if path.stat().st_size == 0:
                raise PDFExtractionError(f"File is empty (0 bytes): {filename}")
            doc = pymupdf.open(str(path))
        elif isinstance(source, bytes):
            if len(source) == 0:
                raise PDFExtractionError(f"PDF byte buffer is empty (0 bytes): {filename}")
            doc = pymupdf.open(stream=source, filetype="pdf")
        elif hasattr(source, "read"):
            content = source.read()
            if len(content) == 0:
                raise PDFExtractionError(f"Uploaded file stream is empty: {filename}")
            doc = pymupdf.open(stream=content, filetype="pdf")
        else:
            raise PDFExtractionError(f"Unsupported source type: {type(source)}")

        total_pages = len(doc)
        if total_pages == 0:
            raise PDFExtractionError(f"PDF document contains 0 pages: {filename}")

        pages: List[ExtractedPage] = []
        digital_chars = 0
        scanned_page_count = 0
        ocr_page_count = 0
        failed_page_count = 0
        ocr_available = True
        ocr_warnings: List[str] = []

        for page_idx in range(total_pages):
            page = doc[page_idx]
            extracted_page = extract_page_hybrid(
                page=page,
                page_number=page_idx + 1,  # 1-indexed
                min_page_chars=min_page_chars,
                enable_ocr=enable_ocr,
                ocr_lang=ocr_lang,
            )
            pages.append(extracted_page)

            if extracted_page.extraction_method == "text":
                digital_chars += extracted_page.char_count
            elif extracted_page.extraction_method == "ocr":
                scanned_page_count += 1
                ocr_page_count += 1
            elif extracted_page.extraction_method == "failed":
                scanned_page_count += 1
                failed_page_count += 1
                if extracted_page.error_message:
                    ocr_warnings.append(f"Page {page_idx + 1}: {extracted_page.error_message}")
                    if "tesseract" in extracted_page.error_message.lower():
                        ocr_available = False

        total_chars = sum(p.char_count for p in pages)
        is_scanned = (digital_chars < min_chars_threshold) or (scanned_page_count > 0 and digital_chars == 0)

        warning_msg: Optional[str] = None
        if is_scanned and ocr_page_count == 0 and total_chars < min_chars_threshold:
            warning_msg = (
                f"'{filename}' has only {total_chars} extractable character(s) across {total_pages} page(s). "
                "This document appears to be a scanned image or photo. "
            )
            if not ocr_available:
                warning_msg += (
                    "Local OCR was not available because Tesseract is not installed on this system.\n\n"
                    + INSTALL_GUIDANCE_MESSAGE
                )
            else:
                warning_msg += "OCR processed the document but detected no usable text."

        return ExtractedDocument(
            filename=filename,
            subject=subject,
            year=year,
            pages=pages,
            total_pages=total_pages,
            total_chars=total_chars,
            is_scanned=is_scanned,
            warning_message=warning_msg,
            scanned_page_count=scanned_page_count,
            ocr_page_count=ocr_page_count,
            failed_page_count=failed_page_count,
            ocr_available=ocr_available,
            ocr_warnings=ocr_warnings,
        )

    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(f"Failed to extract text from '{filename}': {str(e)}") from e
    finally:
        if doc is not None:
            doc.close()
