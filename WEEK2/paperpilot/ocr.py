"""
ocr.py - Local Optical Character Recognition (OCR) engine for scanned PDFs.

Provides local-only, privacy-preserving OCR using pytesseract and Tesseract-OCR.
Includes automated Windows executable discovery, configurable language selection,
confidence scoring, and non-blocking failure reporting.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
from PIL import Image
import pymupdf
import pytesseract


class OCRError(Exception):
    """Base exception for OCR processing failures."""
    pass


class TesseractMissingError(OCRError):
    """Raised when the Tesseract executable is not installed or cannot be called."""
    pass


class OCRLanguageUnavailableError(OCRError):
    """Raised when the specified language pack is not installed in Tesseract."""
    pass


@dataclass
class OCRResult:
    """Encapsulates the result of OCR extraction on a single image/page."""
    text: str
    char_count: int
    confidence: Optional[float] = None  # Average confidence (0.0 to 100.0)
    word_count: int = 0
    is_empty: bool = True
    raw_data: Optional[Dict[str, Any]] = None


# Default Windows installation locations to search if 'tesseract' is not on PATH
COMMON_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"PaperPilot\tools\tesseract\tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"PaperPilot\tesseract\tesseract.exe"),
    str(Path(".paperpilot/tools/tesseract/tesseract.exe").resolve()),
    r"C:\tools\tesseract\tesseract.exe",
]

INSTALL_GUIDANCE_MESSAGE = (
    "Tesseract-OCR is required to read scanned or image-only PDF pages locally.\n\n"
    "To enable local OCR on Windows:\n"
    "• Automatic Setup: Click '⚡ Set Up OCR Automatically' to let PaperPilot set up the verified engine.\n"
    "• Manual Setup: Download the official installer from: https://github.com/UB-Mannheim/tesseract/wiki\n"
    "  (Default path 'C:\\Program Files\\Tesseract-OCR' is automatically detected).\n\n"
    "Note: Text-based PDFs will continue to work normally even without Tesseract installed."
)


def get_tesseract_cmd() -> Optional[str]:
    """
    Locates the Tesseract executable on the system.

    Checks in order:
    1. TESSERACT_CMD environment variable (if explicitly set)
    2. pytesseract default command if already pointing to a valid executable
    3. System PATH via shutil.which('tesseract')
    4. Common default Windows installation directories and PaperPilot managed paths
    """
    # 1. Custom environment variable
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and Path(env_cmd).is_file():
        return env_cmd

    # 2. Check if current pytesseract.pytesseract.tesseract_cmd points to a valid file
    curr_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if curr_cmd != "tesseract" and Path(curr_cmd).is_file():
        return curr_cmd

    # 3. Check system PATH
    path_which = shutil.which("tesseract")
    if path_which:
        return path_which

    # 4. Search common Windows locations
    for win_path in COMMON_WINDOWS_TESSERACT_PATHS:
        if win_path and Path(win_path).is_file():
            return win_path

    return None


def ensure_tesseract_configured() -> bool:
    """
    Configures pytesseract with the discovered executable path if available.
    Also ensures TESSDATA_PREFIX points to the adjacent tessdata directory if not set.
    Returns True if an executable was found and configured, False otherwise.
    """
    cmd = get_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        # Ensure TESSDATA_PREFIX is configured if tessdata exists alongside executable
        if "TESSDATA_PREFIX" not in os.environ:
            adjacent_tessdata = Path(cmd).parent / "tessdata"
            if adjacent_tessdata.is_dir():
                os.environ["TESSDATA_PREFIX"] = str(adjacent_tessdata)
        return True
    return False


def is_tesseract_available() -> bool:
    """
    Verifies that Tesseract is installed and can be successfully invoked.
    Never throws an unhandled exception.
    """
    if not ensure_tesseract_configured():
        return False

    try:
        ver = pytesseract.get_tesseract_version()
        return ver is not None
    except (pytesseract.TesseractNotFoundError, FileNotFoundError, PermissionError, Exception):
        return False


def get_tesseract_version() -> Optional[str]:
    """Returns the installed Tesseract version string, or None if unavailable."""
    if not ensure_tesseract_configured():
        return None
    try:
        ver = pytesseract.get_tesseract_version()
        return str(ver)
    except Exception:
        return None


def get_available_languages() -> List[str]:
    """
    Returns list of installed Tesseract language pack codes (e.g. ['eng', 'osd']).
    Returns empty list if Tesseract is not installed or callable.
    """
    if not is_tesseract_available():
        return []
    try:
        return pytesseract.get_languages()
    except Exception:
        return []


def is_language_available(lang: str) -> bool:
    """Checks whether the requested OCR language code is installed."""
    installed = get_available_languages()
    if not installed:
        return False
    return lang in installed


def render_page_to_image(page: pymupdf.Page, dpi: int = 300) -> Image.Image:
    """
    Renders a PyMuPDF PDF page into a high-resolution PIL Image suitable for OCR.

    Uses 300 DPI (zoom = 300 / 72 ≈ 4.167) to ensure crisp character edges for
    mathematical symbols, sub/superscripts, and small font sizes while avoiding
    excessive memory consumption. Converts to grayscale for optimal contrast.
    """
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)

    # Convert PyMuPDF pixmap buffer directly into PIL Image
    img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    # Convert to grayscale to remove color noise without aggressive thresholding
    return img.convert("L")


def run_ocr_on_image(
    image: Image.Image,
    lang: str = "eng",
    psm: int = 3,
) -> OCRResult:
    """
    Executes local Tesseract OCR on a PIL Image.

    Parameters:
    -----------
    image : Image.Image
        The page image to process.
    lang : str
        The Tesseract language code (defaults to 'eng').
    psm : int
        Page segmentation mode (default 3: Fully automatic page segmentation).

    Returns:
    --------
    OCRResult
        Structured OCR output including text, average confidence, and word counts.

    Raises:
    -------
    TesseractMissingError
        If Tesseract is not installed on the system.
    OCRLanguageUnavailableError
        If the requested language pack is missing.
    OCRError
        If OCR execution fails.
    """
    if not is_tesseract_available():
        raise TesseractMissingError(
            "Tesseract executable is not found or not callable.\n" + INSTALL_GUIDANCE_MESSAGE
        )

    config_flags = f"--psm {psm}"

    try:
        # 1. Extract plain text (preserves layout and linebreaks)
        raw_text = pytesseract.image_to_string(image, lang=lang, config=config_flags)
        cleaned_text = raw_text.strip()

        # 2. Extract structured word-level confidence data
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=config_flags,
            output_type=pytesseract.Output.DICT,
        )

        conf_values = []
        word_count = 0

        # pytesseract returns conf values as integers or strings; -1 indicates layout blocks without text
        for conf, word in zip(data.get("conf", []), data.get("text", [])):
            if str(word).strip():
                try:
                    conf_f = float(conf)
                    if conf_f >= 0:
                        conf_values.append(conf_f)
                        word_count += 1
                except (ValueError, TypeError):
                    pass

        avg_conf: Optional[float] = None
        if conf_values:
            avg_conf = round(sum(conf_values) / len(conf_values), 2)

        return OCRResult(
            text=cleaned_text,
            char_count=len(cleaned_text),
            confidence=avg_conf,
            word_count=word_count,
            is_empty=len(cleaned_text) == 0,
            raw_data=data,
        )

    except pytesseract.TesseractNotFoundError as e:
        raise TesseractMissingError(
            "Tesseract executable is not found or not callable.\n" + INSTALL_GUIDANCE_MESSAGE
        ) from e
    except pytesseract.TesseractError as e:
        err_msg = str(e)
        if "traineddata" in err_msg.lower() or "failed loading language" in err_msg.lower():
            raise OCRLanguageUnavailableError(
                f"Tesseract language pack '{lang}' is not installed or could not be loaded: {err_msg}"
            ) from e
        raise OCRError(f"Tesseract OCR failed: {err_msg}") from e
    except Exception as e:
        raise OCRError(f"Unexpected error during OCR processing: {e}") from e


def run_ocr_on_page(
    page: pymupdf.Page,
    lang: str = "eng",
    psm: int = 3,
    dpi: int = 300,
) -> OCRResult:
    """
    Renders a PyMuPDF page and runs local OCR on it.
    """
    img = render_page_to_image(page, dpi=dpi)
    return run_ocr_on_image(img, lang=lang, psm=psm)
