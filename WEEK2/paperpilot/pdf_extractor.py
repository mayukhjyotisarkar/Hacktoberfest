"""
pdf_extractor.py - PDF text extraction engine using PyMuPDF.

Extracts text from PDF question papers while tracking page numbers,
detecting scanned/image-only PDFs, and handling corrupted documents gracefully.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union, BinaryIO
import pymupdf


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be opened or parsed."""
    pass


@dataclass
class ExtractedPage:
    """Represents text extracted from a single PDF page."""
    page_number: int  # 1-indexed for user readability
    text: str
    char_count: int


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

    @property
    def full_text(self) -> str:
        """Concatenates text from all pages with page markers."""
        return "\n\n".join(
            f"--- [Page {p.page_number}] ---\n{p.text}" for p in self.pages
        )


def extract_text_from_pdf(
    source: Union[str, Path, bytes, BinaryIO],
    filename: str = "unknown.pdf",
    subject: str = "General",
    year: Optional[int] = None,
    min_chars_threshold: int = 30,
) -> ExtractedDocument:
    """
    Extracts text page-by-page from a PDF file path or byte buffer.

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
        Minimum character count across all pages below which the document
        is flagged as a scanned image requiring OCR.

    Returns:
    --------
    ExtractedDocument
        Structured object containing extracted text, page references, and metadata.

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
        total_chars = 0

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            char_count = len(page_text)
            total_chars += char_count

            pages.append(
                ExtractedPage(
                    page_number=page_idx + 1,  # 1-indexed
                    text=page_text,
                    char_count=char_count,
                )
            )

        # Check if PDF is a scanned image (almost zero extractable digital text)
        is_scanned = total_chars < min_chars_threshold
        warning_msg = None
        if is_scanned:
            warning_msg = (
                f"'{filename}' has only {total_chars} extractable character(s) across {total_pages} page(s). "
                "This document appears to be a scanned image or photo. "
                "Scanned PDFs require Optical Character Recognition (OCR), which is outside the scope of this MVP."
            )

        return ExtractedDocument(
            filename=filename,
            subject=subject,
            year=year,
            pages=pages,
            total_pages=total_pages,
            total_chars=total_chars,
            is_scanned=is_scanned,
            warning_message=warning_msg,
        )

    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(f"Failed to extract text from '{filename}': {str(e)}") from e
    finally:
        if doc is not None:
            doc.close()

