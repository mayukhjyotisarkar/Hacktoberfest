"""
ocr_setup.py - Secure, automated local OCR bootstrapper for Windows.

Handles downloading, SHA-256 verification, safe archive extraction,
installer execution, and post-install validation for Tesseract-OCR.
Adheres strictly to local-first privacy, explicit user consent,
HTTPS allowlisting, and zip-slip path traversal prevention.
"""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import requests

from paperpilot.ocr import (
    is_tesseract_available,
    get_tesseract_cmd,
    get_tesseract_version,
    get_available_languages,
    ensure_tesseract_configured,
    INSTALL_GUIDANCE_MESSAGE,
)


# =============================================================================
# Custom Exceptions
# =============================================================================

class OCRSetupError(Exception):
    """Base exception for OCR setup failures."""
    pass


class SecurityError(OCRSetupError):
    """Raised when a download URL, host, or redirect violates security constraints."""
    pass


class ChecksumMismatchError(OCRSetupError):
    """Raised when downloaded file integrity verification fails."""
    pass


class UnsafeArchiveError(OCRSetupError):
    """Raised when an archive contains paths that would escape the target directory."""
    pass


class DownloadError(OCRSetupError):
    """Raised when network download fails, times out, or receives an HTTP error."""
    pass


class LanguageDataMissingError(OCRSetupError):
    """Raised when the required OCR language data (e.g. English) is missing."""
    pass


class ExecutionError(OCRSetupError):
    """Raised when Tesseract executable fails verification or cannot be started."""
    pass


class UnsupportedPlatformError(OCRSetupError):
    """Raised when automatic setup is invoked on an unsupported operating system."""
    pass


# =============================================================================
# Configuration & Allowlist
# =============================================================================

ALLOWED_DOWNLOAD_HOSTS: Set[str] = {
    "github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "digi.bib.uni-mannheim.de",
}

# Verified official Windows distribution metadata independently published and verified
OFFICIAL_DISTRIBUTION: Dict[str, Any] = {
    "version": "5.4.0.20240606",
    "url": "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe",
    "sha256": "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9",
    "filename": "tesseract-ocr-w64-setup-5.4.0.20240606.exe",
    "publisher": "Mannheim University Library / Tesseract-OCR Community",
    "license": "Apache-2.0",
}

DEFAULT_MANAGED_DIR = Path(".paperpilot") / "tools" / "tesseract"


@dataclass
class OCRSetupResult:
    """Encapsulates the result of an OCR setup or verification operation."""
    success: bool
    status: str  # "already_installed", "installed_successfully", "installer_launched", "failed"
    executable_path: Optional[str] = None
    version: Optional[str] = None
    message: str = ""
    error_kind: Optional[str] = None
    requires_user_action: bool = False


# =============================================================================
# URL & Host Validation
# =============================================================================

def validate_download_url(url: str, allowed_hosts: Optional[Set[str]] = None) -> None:
    """
    Validates that the download URL uses HTTPS and points to an explicitly allowlisted host.

    Raises:
    -------
    SecurityError:
        If the URL is malformed, uses an insecure scheme, embeds credentials,
        or targets an unauthorized destination host.
    """
    if not url or not isinstance(url, str):
        raise SecurityError("Download URL must be a non-empty string.")

    parsed = urlparse(url.strip())

    # Scheme must be strictly HTTPS
    if parsed.scheme.lower() != "https":
        raise SecurityError(
            f"Security violation: Only secure HTTPS download URLs are permitted. Received: '{parsed.scheme}'"
        )

    # Reject embedded userinfo (e.g. https://user:pass@evil.com/...)
    if parsed.username or parsed.password:
        raise SecurityError("Security violation: Embedded credentials in download URLs are forbidden.")

    # Check host allowlist
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SecurityError(f"Security violation: Missing or invalid hostname in URL: '{url}'")

    valid_hosts = allowed_hosts if allowed_hosts is not None else ALLOWED_DOWNLOAD_HOSTS
    if hostname not in valid_hosts:
        raise SecurityError(
            f"Security violation: Host '{hostname}' is not in the approved download allowlist ({sorted(valid_hosts)})."
        )


# =============================================================================
# Download with Hop-by-Hop Redirect Validation & Checksum Verification
# =============================================================================

def download_file_with_checksum(
    url: str,
    dest_path: Path,
    expected_sha256: str,
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
    chunk_size: int = 65536,
    timeout: float = 30.0,
    max_redirects: int = 5,
    allowed_hosts: Optional[Set[str]] = None,
) -> Path:
    """
    Downloads a binary artifact from an allowlisted HTTPS source.

    Safeguards:
    1. Validates the initial URL against the host allowlist and HTTPS requirement.
    2. Inspects every redirect hop (e.g. GitHub to AWS S3 CDN) ensuring no redirect
       switches to HTTP or traverses to an untrusted domain.
    3. Streams content directly into a temporary (.tmp) file while computing SHA-256.
    4. On any network or integrity failure, cleans up the partial .tmp file.
    5. Validates the final computed SHA-256 against expected_sha256 before committing
       the file to the destination path.
    """
    validate_download_url(url, allowed_hosts=allowed_hosts)

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + f".tmp.{os.getpid()}")

    hasher = hashlib.sha256()
    current_url = url
    redirect_count = 0

    session = requests.Session()
    try:
        # Follow redirects manually to validate each hop
        while redirect_count <= max_redirects:
            validate_download_url(current_url, allowed_hosts=allowed_hosts)

            response = session.get(
                current_url,
                stream=True,
                allow_redirects=False,
                timeout=timeout,
            )

            # Handle redirects
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise DownloadError(f"Redirect response {response.status_code} missing Location header.")

                # Resolve relative redirects if necessary
                if not location.startswith("http://") and not location.startswith("https://"):
                    parsed_curr = urlparse(current_url)
                    location = f"{parsed_curr.scheme}://{parsed_curr.netloc}{location}"

                validate_download_url(location, allowed_hosts=allowed_hosts)
                current_url = location
                redirect_count += 1
                continue

            # Check response status
            if response.status_code != 200:
                raise DownloadError(
                    f"HTTP error {response.status_code} while downloading artifact from {current_url}"
                )

            # Stream download to temp file
            total_size: Optional[int] = None
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                total_size = int(content_length)

            bytes_written = 0
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        hasher.update(chunk)
                        bytes_written += len(chunk)
                        if progress_callback:
                            try:
                                progress_callback(bytes_written, total_size)
                            except Exception:
                                pass  # Do not allow callback exceptions to interrupt download

            break  # Download completed successfully

        if redirect_count > max_redirects:
            raise DownloadError(f"Exceeded maximum allowed redirects ({max_redirects}).")

        # Verify SHA-256 integrity
        computed_sha256 = hasher.hexdigest().lower()
        expected_clean = expected_sha256.strip().lower()

        if computed_sha256 != expected_clean:
            raise ChecksumMismatchError(
                f"Artifact integrity verification failed!\n"
                f"Expected SHA-256: {expected_clean}\n"
                f"Computed SHA-256: {computed_sha256}\n"
                f"The downloaded file was discarded to prevent execution of unverified binaries."
            )

        # Atomically replace destination file
        if dest_path.exists():
            dest_path.unlink()
        temp_path.rename(dest_path)
        return dest_path

    except (requests.RequestException, OSError) as e:
        if isinstance(e, OCRSetupError):
            raise
        raise DownloadError(f"Download failed due to network or filesystem error: {e}") from e

    finally:
        session.close()
        # Clean up temporary file if it still exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


# =============================================================================
# Safe Archive Extraction (Zip-Slip Protection)
# =============================================================================

def extract_archive_safely(
    archive_path: Path,
    target_dir: Path,
) -> Path:
    """
    Extracts a ZIP archive into target_dir with strict path traversal prevention.

    Raises:
    -------
    UnsafeArchiveError:
        If any archive member contains directory traversal sequences ('..')
        or absolute paths attempting to write outside target_dir.
    """
    import zipfile

    archive_path = Path(archive_path)
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not archive_path.is_file():
        raise OCRSetupError(f"Archive file not found: {archive_path}")

    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.infolist():
            member_name = member.filename

            # Calculate destination path
            destination = (target_dir / member_name).resolve()

            # Zip-slip validation: destination must be inside target_dir
            try:
                destination.relative_to(target_dir)
            except ValueError:
                raise UnsafeArchiveError(
                    f"Security violation: Archive member '{member_name}' attempts "
                    f"path traversal outside target directory '{target_dir}'."
                )

            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(destination, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    return target_dir


# =============================================================================
# Post-Installation Verification & Configuration
# =============================================================================

def verify_tesseract_installation(
    executable_path: Path,
    check_language: str = "eng",
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies that a candidate Tesseract binary starts successfully, outputs
    its version string, and has the required language pack installed.

    Returns:
    --------
    Tuple[bool, Optional[str], Optional[str]]:
        (is_valid, version_string, error_message)
    """
    exe = Path(executable_path).resolve()
    if not exe.is_file():
        return False, None, f"Executable file does not exist at '{exe}'."

    # Test 1: Check if binary executes and outputs version
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return False, None, f"Tesseract execution returned non-zero code {proc.returncode}: {proc.stderr}"

        output = proc.stdout or proc.stderr
        version_line = output.splitlines()[0] if output else "Tesseract"
    except Exception as e:
        return False, None, f"Failed to execute Tesseract binary at '{exe}': {e}"

    # Test 2: Verify language data
    # Check tessdata directory alongside executable or TESSDATA_PREFIX
    tessdata_dir = exe.parent / "tessdata"
    has_lang = False

    if tessdata_dir.is_dir():
        lang_file = tessdata_dir / f"{check_language}.traineddata"
        if lang_file.is_file():
            has_lang = True

    if not has_lang and "TESSDATA_PREFIX" in os.environ:
        prefix_path = Path(os.environ["TESSDATA_PREFIX"])
        if (prefix_path / f"{check_language}.traineddata").is_file():
            has_lang = True

    # Alternatively query via command line: tesseract --list-langs
    if not has_lang:
        try:
            lang_proc = subprocess.run(
                [str(exe), "--list-langs"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if check_language in (lang_proc.stdout or ""):
                has_lang = True
        except Exception:
            pass

    if not has_lang:
        return False, version_line, f"Tesseract is installed, but language pack '{check_language}' was not found in tessdata."

    return True, version_line, None


# =============================================================================
# Package Manager & Installer Helpers
# =============================================================================

def is_winget_available() -> bool:
    """Returns True if the Windows Package Manager (winget) is installed and available."""
    if sys.platform != "win32":
        return False
    return shutil.which("winget") is not None


def install_via_winget(
    package_id: str = "UB-Mannheim.TesseractOCR",
    timeout: int = 180,
) -> bool:
    """
    Attempts to install Tesseract OCR using Windows Package Manager (winget).
    Returns True if winget exited with code 0, False otherwise.
    """
    if not is_winget_available():
        return False

    cmd = [
        "winget", "install",
        "--id", package_id,
        "-e",
        "--accept-source-agreements",
        "--accept-package-agreements",
        "--silent",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode == 0
    except Exception:
        return False


def launch_installer_wizard(installer_path: Path) -> subprocess.Popen:
    """
    Launches the verified Windows installer GUI wizard.
    The user can review options and grant administrator permission if prompted by Windows UAC.
    """
    return subprocess.Popen([str(installer_path)])


# =============================================================================
# Main Orchestrator
# =============================================================================

def run_ocr_setup(
    progress_callback: Optional[Callable[[str, float], None]] = None,
    allow_winget: bool = True,
    download_dir: Optional[Path] = None,
    interactive_launch: bool = True,
) -> OCRSetupResult:
    """
    Automates local OCR setup with safety checks and clear user guidance.

    Workflow:
    1. Check if Tesseract is already installed and verified. If yes, reuses it immediately.
    2. Check operating system (Windows required for installer automation).
    3. If winget is available and allow_winget=True, attempts clean winget installation.
    4. If winget is not available, downloads the official verified UB-Mannheim installer
       from the allowlisted GitHub release.
    5. Validates the SHA-256 hash against the official expected checksum.
    6. Launches the verified installer wizard, informing the user that Windows UAC
       approval will be requested.
    7. Configures pytesseract and environment variables.

    Parameters:
    -----------
    progress_callback: Optional[Callable[[str, float], None]]
        Callback accepting (status_message, progress_fraction_from_0_to_1).
    allow_winget: bool
        Whether to attempt silent installation via winget before downloading.
    download_dir: Optional[Path]
        Directory to store the verified installer. Defaults to '.paperpilot/cache'.
    interactive_launch: bool
        Whether to launch the installer GUI wizard if downloaded.

    Returns:
    --------
    OCRSetupResult:
        Structured result indicating success, status, executable path, and next steps.
    """
    def report(msg: str, progress: float) -> None:
        if progress_callback:
            try:
                progress_callback(msg, progress)
            except Exception:
                pass

    # 1. Check if working Tesseract is already present on the system
    report("Checking for existing Tesseract installation...", 0.05)
    if is_tesseract_available():
        cmd = get_tesseract_cmd()
        ver = get_tesseract_version()
        return OCRSetupResult(
            success=True,
            status="already_installed",
            executable_path=cmd,
            version=ver,
            message=f"Tesseract-OCR is already installed and ready at '{cmd}' (version: {ver}).",
        )

    # 2. Operating system check
    if sys.platform != "win32":
        return OCRSetupResult(
            success=False,
            status="failed",
            error_kind="unsupported_platform",
            message=(
                "Automatic installer setup is configured for Windows.\n"
                "On macOS: run 'brew install tesseract'\n"
                "On Linux: run 'sudo apt install tesseract-ocr'"
            ),
        )

    # 3. Attempt winget if available
    if allow_winget and is_winget_available():
        report("Attempting installation via Windows Package Manager (winget)...", 0.20)
        winget_ok = install_via_winget()
        if winget_ok:
            ensure_tesseract_configured()
            if is_tesseract_available():
                cmd = get_tesseract_cmd()
                ver = get_tesseract_version()
                report("Tesseract installed successfully via winget!", 1.0)
                return OCRSetupResult(
                    success=True,
                    status="installed_successfully",
                    executable_path=cmd,
                    version=ver,
                    message="Tesseract-OCR was installed and configured successfully via Windows Package Manager.",
                )

    # 4. Download verified official installer
    report("Connecting to verified official Tesseract release...", 0.30)
    target_dir = download_dir or Path(".paperpilot") / "cache"
    installer_filename = OFFICIAL_DISTRIBUTION["filename"]
    installer_path = target_dir / installer_filename
    expected_sha256 = OFFICIAL_DISTRIBUTION["sha256"]

    # Check if a previously verified installer already exists in cache
    already_cached = False
    if installer_path.is_file():
        with open(installer_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest().lower()
        if h == expected_sha256.lower():
            already_cached = True

    if not already_cached:
        report("Downloading official Tesseract installer...", 0.40)
        try:
            def dl_cb(downloaded: int, total: Optional[int]) -> None:
                if total and total > 0:
                    pct = 0.40 + (downloaded / total) * 0.45
                    report(f"Downloading installer: {int(downloaded / (1024 * 1024))} MB / {int(total / (1024 * 1024))} MB...", pct)
                else:
                    report(f"Downloading installer: {int(downloaded / (1024 * 1024))} MB...", 0.50)

            download_file_with_checksum(
                url=OFFICIAL_DISTRIBUTION["url"],
                dest_path=installer_path,
                expected_sha256=expected_sha256,
                progress_callback=dl_cb,
            )
        except ChecksumMismatchError as e:
            return OCRSetupResult(
                success=False,
                status="failed",
                error_kind="checksum_mismatch",
                message=str(e),
            )
        except DownloadError as e:
            return OCRSetupResult(
                success=False,
                status="failed",
                error_kind="download_error",
                message=f"Failed to download installer: {e}\n\nPlease check your internet connection or install manually using the UB-Mannheim installer.",
            )
        except SecurityError as e:
            return OCRSetupResult(
                success=False,
                status="failed",
                error_kind="security_error",
                message=str(e),
            )

    report("Installer verified! Preparing setup...", 0.90)

    # 5. Launch installer
    if interactive_launch:
        try:
            launch_installer_wizard(installer_path)
            report("Installer wizard launched.", 1.0)
            return OCRSetupResult(
                success=True,
                status="installer_launched",
                requires_user_action=True,
                message=(
                    "The official Tesseract-OCR installer has been launched.\n\n"
                    "1. Follow the on-screen setup wizard (Windows will ask for administrator permission).\n"
                    "2. Keep the default installation directory ('C:\\Program Files\\Tesseract-OCR').\n"
                    "3. Once the installer finishes, click 'Verify Installation' below to activate OCR."
                ),
            )
        except Exception as e:
            return OCRSetupResult(
                success=False,
                status="failed",
                error_kind="launch_error",
                message=f"Could not launch installer executable: {e}\nYou can run it manually from: {installer_path}",
            )

    return OCRSetupResult(
        success=True,
        status="installer_ready",
        requires_user_action=True,
        message=f"Installer downloaded and verified at: {installer_path}",
    )
