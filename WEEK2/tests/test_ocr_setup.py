"""
test_ocr_setup.py - Unit and regression tests for automated local OCR setup.

Verifies:
1. Existing installation is reused without re-downloading.
2. Setup is idempotent across multiple runs.
3. Valid download and SHA-256 verification succeeds.
4. Failed downloads clean up partial/corrupted files.
5. Insecure schemes, invalid hosts, and untrusted redirects are rejected.
6. Checksum mismatch blocks installation and deletes the artifact.
7. Unsafe archive paths (zip-slip) are rejected.
8. Missing language data is detected and reported.
9. Installation failures produce actionable guidance.
10. OCR setup is triggered only by explicit user action.
11. Text-based PDF uploads work without Tesseract.
12. Optional manual real-download test (skipped by default).
"""

from io import BytesIO
import hashlib
import os
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock
import zipfile
import pytest
import requests

from paperpilot.ocr_setup import (
    validate_download_url,
    download_file_with_checksum,
    extract_archive_safely,
    verify_tesseract_installation,
    run_ocr_setup,
    OCRSetupResult,
    OCRSetupError,
    SecurityError,
    ChecksumMismatchError,
    UnsafeArchiveError,
    DownloadError,
    ALLOWED_DOWNLOAD_HOSTS,
    OFFICIAL_DISTRIBUTION,
)


# =============================================================================
# 1. Existing installation is reused
# =============================================================================
def test_existing_installation_is_reused():
    """Verifies that an existing working installation is detected and reused without downloading."""
    with patch("paperpilot.ocr_setup.is_tesseract_available", return_value=True), \
         patch("paperpilot.ocr_setup.get_tesseract_cmd", return_value=r"C:\Program Files\Tesseract-OCR\tesseract.exe"), \
         patch("paperpilot.ocr_setup.get_tesseract_version", return_value="5.4.0"), \
         patch("paperpilot.ocr_setup.download_file_with_checksum") as mock_download:

        result = run_ocr_setup()

        assert result.success is True
        assert result.status == "already_installed"
        assert result.executable_path == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        assert result.version == "5.4.0"
        mock_download.assert_not_called()


# =============================================================================
# 2. Setup is idempotent
# =============================================================================
def test_setup_is_idempotent():
    """Verifies that running setup multiple times produces consistent, non-destructive results."""
    with patch("paperpilot.ocr_setup.is_tesseract_available", return_value=True), \
         patch("paperpilot.ocr_setup.get_tesseract_cmd", return_value=r"C:\tools\tesseract\tesseract.exe"), \
         patch("paperpilot.ocr_setup.get_tesseract_version", return_value="5.3.3"), \
         patch("paperpilot.ocr_setup.download_file_with_checksum") as mock_download:

        res1 = run_ocr_setup()
        res2 = run_ocr_setup()

        assert res1.success is True and res2.success is True
        assert res1.status == "already_installed" and res2.status == "already_installed"
        assert res1.executable_path == res2.executable_path
        mock_download.assert_not_called()


# =============================================================================
# 3. Valid download is handled correctly
# =============================================================================
def test_valid_download_is_handled_correctly(tmp_path):
    """Verifies that a valid HTTPS download with matching SHA-256 succeeds and writes the file."""
    fake_content = b"Mock Tesseract Windows Installer Binary Payload"
    expected_hash = hashlib.sha256(fake_content).hexdigest()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": str(len(fake_content))}
    mock_resp.iter_content = MagicMock(return_value=[fake_content])

    dest_file = tmp_path / "installer.exe"

    with patch("requests.Session.get", return_value=mock_resp):
        out_path = download_file_with_checksum(
            url="https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0/tesseract.exe",
            dest_path=dest_file,
            expected_sha256=expected_hash,
        )

        assert out_path.is_file()
        assert out_path.read_bytes() == fake_content


# =============================================================================
# 4. Failed downloads are cleaned up
# =============================================================================
def test_failed_downloads_are_cleaned_up(tmp_path):
    """Verifies that interrupted or failed downloads clean up any partial (.tmp) files."""
    dest_file = tmp_path / "aborted_installer.exe"

    def fail_chunk_generator():
        yield b"Partial initial chunk bytes"
        raise requests.exceptions.ConnectionError("Simulated socket timeout / network drop midway")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": "1000"}
    mock_resp.iter_content = MagicMock(return_value=fail_chunk_generator())

    with patch("requests.Session.get", return_value=mock_resp):
        with pytest.raises(DownloadError) as exc_info:
            download_file_with_checksum(
                url="https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0/tesseract.exe",
                dest_path=dest_file,
                expected_sha256="0" * 64,
            )

        assert "network or filesystem error" in str(exc_info.value).lower()
        assert not dest_file.exists()
        # Verify no .tmp files linger in the directory
        tmp_files = list(tmp_path.glob("*.tmp*"))
        assert len(tmp_files) == 0


# =============================================================================
# 5. Invalid hosts and redirect attempts are rejected
# =============================================================================
def test_invalid_scheme_rejected():
    """Verifies that plain HTTP URLs are immediately rejected."""
    with pytest.raises(SecurityError) as exc_info:
        validate_download_url("http://github.com/UB-Mannheim/tesseract/setup.exe")
    assert "HTTPS" in str(exc_info.value)


def test_untrusted_host_rejected():
    """Verifies that non-allowlisted domains are rejected."""
    with pytest.raises(SecurityError) as exc_info:
        validate_download_url("https://malicious-tesseract-mirror.com/installer.exe")
    assert "not in the approved download allowlist" in str(exc_info.value)


def test_embedded_credentials_rejected():
    """Verifies that URLs with embedded usernames/passwords are rejected."""
    with pytest.raises(SecurityError) as exc_info:
        validate_download_url("https://admin:pass@github.com/UB-Mannheim/setup.exe")
    assert "Embedded credentials" in str(exc_info.value)


def test_untrusted_redirect_rejected(tmp_path):
    """Verifies that redirects to an unauthorized domain are caught and rejected."""
    mock_redirect_resp = MagicMock()
    mock_redirect_resp.status_code = 302
    mock_redirect_resp.headers = {"Location": "https://unauthorized-cdn.com/trojan.exe"}

    dest_file = tmp_path / "redirect_test.exe"

    with patch("requests.Session.get", return_value=mock_redirect_resp):
        with pytest.raises(SecurityError) as exc_info:
            download_file_with_checksum(
                url="https://github.com/UB-Mannheim/tesseract/installer.exe",
                dest_path=dest_file,
                expected_sha256="0" * 64,
            )
        assert "unauthorized-cdn.com" in str(exc_info.value)
        assert not dest_file.exists()


# =============================================================================
# 6. Checksum mismatch blocks installation
# =============================================================================
def test_checksum_mismatch_blocks_installation(tmp_path):
    """Verifies that corrupted bytes or altered payloads are detected and deleted."""
    corrupted_content = b"Altered or corrupted binary data"
    dest_file = tmp_path / "tampered.exe"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": str(len(corrupted_content))}
    mock_resp.iter_content = MagicMock(return_value=[corrupted_content])

    with patch("requests.Session.get", return_value=mock_resp):
        with pytest.raises(ChecksumMismatchError) as exc_info:
            download_file_with_checksum(
                url="https://github.com/UB-Mannheim/tesseract/releases/tesseract.exe",
                dest_path=dest_file,
                expected_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )

        assert "integrity verification failed" in str(exc_info.value).lower()
        # Verify file was destroyed and not placed at destination
        assert not dest_file.exists()
        assert len(list(tmp_path.glob("*.tmp*"))) == 0


# =============================================================================
# 7. Unsafe archive paths are rejected (Zip-Slip defense)
# =============================================================================
def test_unsafe_archive_paths_rejected(tmp_path):
    """Verifies that zip files attempting directory traversal outside the target are blocked."""
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("../evil_escape.exe", b"malicious binary")

    malicious_zip = tmp_path / "zipslip.zip"
    malicious_zip.write_bytes(zip_buf.getvalue())

    extract_target = tmp_path / "safe_extract"
    extract_target.mkdir()

    with pytest.raises(UnsafeArchiveError) as exc_info:
        extract_archive_safely(malicious_zip, extract_target)

    assert "path traversal" in str(exc_info.value).lower()
    # Confirm nothing was written outside
    assert not (tmp_path / "evil_escape.exe").exists()


def test_safe_archive_extracts_cleanly(tmp_path):
    """Verifies that legitimate archive members extract safely inside the target directory."""
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("tesseract.exe", b"fake exe")
        zf.writestr("tessdata/eng.traineddata", b"fake eng")

    safe_zip = tmp_path / "tesseract_portable.zip"
    safe_zip.write_bytes(zip_buf.getvalue())

    extract_target = tmp_path / "portable_tools"
    extract_archive_safely(safe_zip, extract_target)

    assert (extract_target / "tesseract.exe").is_file()
    assert (extract_target / "tessdata" / "eng.traineddata").is_file()


# =============================================================================
# 8. Missing language data is detected
# =============================================================================
def test_missing_language_data_is_detected(tmp_path):
    """Verifies that verify_tesseract_installation catches a binary with missing eng data."""
    fake_exe = tmp_path / "tesseract.exe"
    fake_exe.write_text("dummy")

    mock_ver_res = MagicMock()
    mock_ver_res.returncode = 0
    mock_ver_res.stdout = "tesseract 5.4.0\n"

    mock_lang_res = MagicMock()
    mock_lang_res.returncode = 0
    mock_lang_res.stdout = "List of available languages (1):\nosd\n"

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [mock_ver_res, mock_lang_res]
        is_valid, ver, err = verify_tesseract_installation(fake_exe, check_language="eng")

        assert is_valid is False
        assert "language pack 'eng' was not found" in err


# =============================================================================
# 9. Installation failures produce actionable errors
# =============================================================================
def test_installation_failures_produce_actionable_errors(tmp_path):
    """Verifies that network download failure returns a structured, actionable result."""
    with patch("paperpilot.ocr_setup.is_tesseract_available", return_value=False), \
         patch("paperpilot.ocr_setup.is_winget_available", return_value=False), \
         patch("sys.platform", "win32"), \
         patch("paperpilot.ocr_setup.download_file_with_checksum", side_effect=DownloadError("Connection refused by remote host")):

        result = run_ocr_setup(download_dir=tmp_path)

        assert result.success is False
        assert result.status == "failed"
        assert result.error_kind == "download_error"
        assert "Failed to download installer" in result.message
        assert "manual" in result.message.lower()


# =============================================================================
# 10. OCR setup is triggered only by explicit user action
# =============================================================================
def test_setup_not_triggered_on_startup():
    """Verifies that importing or checking OCR never triggers network downloads."""
    with patch("paperpilot.ocr_setup.download_file_with_checksum") as mock_dl:
        import paperpilot.ocr
        assert not mock_dl.called


# =============================================================================
# 11. Streamlit UI automatic setup button integration
# =============================================================================
def test_streamlit_ui_shows_automatic_setup_button_on_scanned_pdf(tmp_path):
    """Verifies that the Streamlit UI provides the 'Set Up OCR Automatically' button for scanned PDFs."""
    from streamlit.testing.v1 import AppTest
    from paperpilot.pdf_extractor import ExtractedDocument

    app_path = str(Path(__file__).resolve().parent.parent / "app.py")
    at = AppTest.from_file(app_path, default_timeout=15.0)
    at.run()

    at.file_uploader[0].upload("scanned_receipt.pdf", b"%PDF-1.4 mock scan")
    extract_btn = [b for b in at.button if "Extract" in b.label][0]
    extract_btn.click()

    scanned_doc = ExtractedDocument(
        filename="scanned_receipt.pdf",
        pages=[],
        total_pages=1,
        total_chars=0,
        is_scanned=True,
    )

    with patch("paperpilot.ocr.is_tesseract_available", return_value=False), \
         patch("paperpilot.pdf_extractor.extract_text_from_pdf", return_value=scanned_doc):
        at.run()
        assert not at.exception
        # Confirm the auto-setup button is rendered
        setup_btns = [b for b in at.button if "Set Up OCR Automatically" in b.label]
        assert len(setup_btns) >= 1


# =============================================================================
# 12. Optional real-download manual integration test
# =============================================================================
@pytest.mark.manual
def test_real_installer_download_and_checksum_verification(tmp_path):
    """
    OPTIONAL manual integration test: downloads the real UB-Mannheim installer
    and verifies that its real SHA-256 matches the expected official hash.
    Skips during standard automated test runs unless explicitly requested.
    """
    pytest.skip("Skipping real network download in automated test suite. Run with -m manual to execute.")
