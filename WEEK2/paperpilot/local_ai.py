"""
local_ai.py - Isolated, optional local Ollama AI client for PaperPilot Phase 5.

Provides a safe, local-only interface to an Ollama server running on the loopback
interface (localhost / 127.0.0.1 / ::1). Strictly rejects any remote or non-loopback
destinations. Performs no network calls at import time.

Initial candidate model: qwen2.5-coder:1.5b-base (with structured few-shot completion prompts).
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import requests

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------

DEFAULT_OLLAMA_URL: str = "http://localhost:11434"
DEFAULT_MODEL: str = "qwen2.5-coder:1.5b-base"
DEFAULT_TIMEOUT_S: float = 30.0
DEFAULT_TEMPERATURE: float = 0.1
DEFAULT_NUM_PREDICT: int = 80
MAX_TOPIC_LENGTH: int = 100

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
ALLOWED_CONFIDENCE_VALUES = {"high", "medium", "low", "uncertain"}


# -----------------------------------------------------------------------------
# Security & Loopback Validation
# -----------------------------------------------------------------------------

def validate_loopback_url(url: str) -> str:
    """
    Validates that a given URL strictly targets the local loopback interface
    (localhost, 127.0.0.1, or ::1). Rejects non-loopback hosts, non-http(s) schemes,
    and external endpoints to ensure user privacy and zero data leakage.

    Returns the normalized base URL string without trailing slashes.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Endpoint URL must be a non-empty string.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only 'http' or 'https' are permitted."
        )

    if parsed.username or parsed.password:
        raise ValueError("Security Violation: URLs with embedded user credentials are not permitted.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in LOOPBACK_HOSTNAMES:
        raise ValueError(
            f"Security Violation: Non-loopback endpoint '{url}' rejected. "
            f"PaperPilot only communicates with local services on localhost, 127.0.0.1, or ::1."
        )

    port_str = f":{parsed.port}" if parsed.port else ""
    host_repr = f"[{hostname}]" if ":" in hostname else hostname
    return f"{parsed.scheme}://{host_repr}{port_str}"


# -----------------------------------------------------------------------------
# Error Taxonomy & Response Models
# -----------------------------------------------------------------------------

class AIErrorKind(str, Enum):
    """Specific categories of local AI client failures."""
    OLLAMA_UNAVAILABLE = "ollama_unavailable"
    MODEL_NOT_INSTALLED = "model_not_installed"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    EMPTY_RESPONSE = "empty_response"
    INVALID_JSON = "invalid_json"
    SCHEMA_VIOLATION = "schema_violation"
    INVALID_ENDPOINT = "invalid_endpoint"


@dataclass
class AIError:
    """Structured, user-friendly error container without UI stack trace exposure."""
    kind: AIErrorKind
    message: str
    status_code: Optional[int] = None
    model: Optional[str] = None
    raw_response: Optional[str] = None
    details: Optional[str] = None


@dataclass
class TopicLabel:
    """Validated structured topic label prediction."""
    topic: str
    confidence: str
    reasoning: Optional[str] = None


@dataclass
class AIResponse:
    """Container for successful generation results."""
    parsed: TopicLabel
    model: str
    latency_ms: float
    raw_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResult:
    """Discriminated union wrapper for AI operations."""
    response: Optional[AIResponse] = None
    error: Optional[AIError] = None

    @property
    def is_success(self) -> bool:
        return self.response is not None and self.error is None


# -----------------------------------------------------------------------------
# Structured Output Parsing & Validation
# -----------------------------------------------------------------------------

def validate_and_parse_topic_json(
    raw_text: str,
) -> Tuple[Optional[TopicLabel], Optional[str], Optional[AIErrorKind]]:
    """
    Parses and strictly validates topic label JSON against the PaperPilot schema:
      - topic: non-empty string, length <= 100
      - confidence: one of ['high', 'medium', 'low', 'uncertain']
      - reasoning: optional string
      - disallowed keys: rejected with SCHEMA_VIOLATION

    Returns (TopicLabel, error_message, error_kind).
    """
    if not raw_text or not raw_text.strip():
        return None, "Model returned an empty response.", AIErrorKind.EMPTY_RESPONSE

    text = raw_text.strip()

    # Normalize partial JSON boundary from completion models or markdown fencing
    if not text.startswith("{") and text.endswith("}"):
        text = "{" + text
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]

    try:
        data = json.loads(text)
    except Exception as ex:
        return None, f"Failed to parse JSON syntax: {ex}", AIErrorKind.INVALID_JSON

    if not isinstance(data, dict):
        return None, "Output JSON root must be a JSON object/dictionary.", AIErrorKind.SCHEMA_VIOLATION

    # Strict key validation: no unexpected keys allowed
    allowed_keys = {"topic", "confidence", "reasoning"}
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        return (
            None,
            f"Schema violation: unexpected key(s) {sorted(list(extra_keys))}. Allowed keys: {sorted(list(allowed_keys))}",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate 'topic' field
    if "topic" not in data:
        return None, "Schema violation: missing required field 'topic'.", AIErrorKind.SCHEMA_VIOLATION

    if not isinstance(data["topic"], str):
        return None, "Schema violation: 'topic' must be a string.", AIErrorKind.SCHEMA_VIOLATION

    topic_str = data["topic"].strip()
    if not topic_str:
        return None, "Schema violation: 'topic' cannot be an empty string.", AIErrorKind.SCHEMA_VIOLATION

    if len(topic_str) > MAX_TOPIC_LENGTH:
        return (
            None,
            f"Schema violation: 'topic' exceeds maximum limit of {MAX_TOPIC_LENGTH} characters (length={len(topic_str)}).",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate 'confidence' field
    if "confidence" not in data:
        return None, "Schema violation: missing required field 'confidence'.", AIErrorKind.SCHEMA_VIOLATION

    if not isinstance(data["confidence"], str):
        return None, "Schema violation: 'confidence' must be a string.", AIErrorKind.SCHEMA_VIOLATION

    conf_str = data["confidence"].strip().lower()
    if conf_str not in ALLOWED_CONFIDENCE_VALUES:
        return (
            None,
            f"Schema violation: invalid confidence '{data['confidence']}'. Allowed values: {sorted(list(ALLOWED_CONFIDENCE_VALUES))}",
            AIErrorKind.SCHEMA_VIOLATION,
        )

    # Validate optional 'reasoning' field
    reasoning_str = None
    if "reasoning" in data and data["reasoning"] is not None:
        if not isinstance(data["reasoning"], str):
            return None, "Schema violation: 'reasoning' must be a string.", AIErrorKind.SCHEMA_VIOLATION
        reasoning_str = data["reasoning"].strip()

    return TopicLabel(topic=topic_str, confidence=conf_str, reasoning=reasoning_str), None, None


# -----------------------------------------------------------------------------
# Prompt Builders
# -----------------------------------------------------------------------------

def build_qwen_few_shot_prompt(question_text: str, subject: str = "Computer Science") -> str:
    """
    Constructs a structured few-shot completion prompt tailored for base foundation models
    (such as qwen2.5-coder:1.5b-base) that perform continuous code/text completion.
    """
    clean_q = question_text.strip()
    clean_sub = subject.strip() if subject else "Computer Science"
    return (
        "Exam Question Topic Classification Dataset\n"
        "---\n"
        "Subject: Operating Systems\n"
        "Question: Explain Banker's algorithm for deadlock avoidance in Operating Systems.\n"
        'JSON: {"topic": "Banker\'s Algorithm", "confidence": "high", "reasoning": "Resource allocation avoidance"}\n'
        "---\n"
        "Subject: Data Structures\n"
        "Question: Analyze the worst-case time complexity O(n log n) of Merge Sort.\n"
        'JSON: {"topic": "Sorting Algorithms & Complexity", "confidence": "high", "reasoning": "Merge sort complexity"}\n'
        "---\n"
        "Subject: General\n"
        "Question: What is it?\n"
        'JSON: {"topic": "Uncertain / Incomplete", "confidence": "uncertain", "reasoning": "Missing question context"}\n'
        "---\n"
        f"Subject: {clean_sub}\n"
        f"Question: {clean_q}\n"
        "JSON: {"
    )


# -----------------------------------------------------------------------------
# Local AI Client
# -----------------------------------------------------------------------------

class LocalAIClient:
    """
    Client for interacting with local Ollama instances on the loopback interface.

    Guarantees:
      - Validates loopback-only endpoints at initialization.
      - Zero network activity on import or instantiation (unless methods called).
      - Strict parameter bounds (temperature, num_predict, timeouts).
      - Typed results and errors with user-friendly diagnostics.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        default_model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = validate_loopback_url(base_url)
        self.default_model = default_model
        self.timeout_s = timeout_s
        self.default_temperature = DEFAULT_TEMPERATURE
        self.default_num_predict = DEFAULT_NUM_PREDICT

        self._owns_session = session is None
        self.session = session or requests.Session()

    def close(self) -> None:
        """Closes the underlying HTTP session if owned by this client."""
        if self._owns_session and self.session:
            self.session.close()

    def __enter__(self) -> "LocalAIClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def check_health(self, timeout_s: Optional[float] = None) -> bool:
        """
        Checks whether the local Ollama service is reachable.
        Returns True if the service responds with HTTP 200, False otherwise.
        Never raises network exceptions.
        """
        timeout = timeout_s if timeout_s is not None else min(self.timeout_s, 3.0)
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=timeout, allow_redirects=False)
            return resp.status_code == 200
        except Exception:
            return False

    def get_installed_models(self, timeout_s: Optional[float] = None) -> List[str]:
        """
        Discovers model names installed in the local Ollama instance.
        Returns a list of model identifier strings (e.g. ['qwen2.5-coder:1.5b-base']).
        Returns an empty list on failure without raising exceptions.
        """
        timeout = timeout_s if timeout_s is not None else min(self.timeout_s, 5.0)
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=timeout, allow_redirects=False)
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("models", [])
            return [m.get("name") for m in models if isinstance(m, dict) and "name" in m]
        except Exception:
            return []

    def is_model_available(
        self,
        model_name: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> bool:
        """
        Verifies whether the specified model (or configured default model) is installed.
        Matches exact model names or standard :latest aliases.
        """
        target = (model_name or self.default_model).strip()
        if not target:
            return False

        installed = self.get_installed_models(timeout_s=timeout_s)
        if target in installed:
            return True

        # Check with/without ':latest' suffix
        if ":" not in target and f"{target}:latest" in installed:
            return True
        if target.endswith(":latest") and target[:-7] in installed:
            return True

        return False

    def verify_configured_model(
        self,
        model_name: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> Tuple[bool, Optional[AIError]]:
        """
        Performs a full readiness check for the configured model.
        Returns (True, None) if ready, or (False, AIError) describing the exact issue.
        """
        target = (model_name or self.default_model).strip()
        timeout = timeout_s if timeout_s is not None else min(self.timeout_s, 5.0)

        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=timeout, allow_redirects=False)
        except requests.exceptions.Timeout as ex:
            return False, AIError(
                kind=AIErrorKind.TIMEOUT,
                message=f"Connection to Ollama timed out after {timeout:.1f}s.",
                details=str(ex),
            )
        except requests.exceptions.ConnectionError as ex:
            return False, AIError(
                kind=AIErrorKind.OLLAMA_UNAVAILABLE,
                message="Ollama is not running or unreachable at the local endpoint.",
                details=str(ex),
            )
        except Exception as ex:
            return False, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"Failed to query Ollama models: {ex}",
                details=str(ex),
            )

        is_redirect = (getattr(resp, "is_redirect", False) is True) or (isinstance(getattr(resp, "status_code", None), int) and 300 <= resp.status_code < 400)
        if is_redirect:
            return False, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"HTTP redirect (status {resp.status_code}) rejected: local AI endpoints must not issue redirects.",
                status_code=resp.status_code,
            )

        if resp.status_code != 200:
            return False, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"Ollama returned HTTP {resp.status_code} while listing models.",
                status_code=resp.status_code,
            )

        try:
            data = resp.json()
            models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
        except Exception as ex:
            return False, AIError(
                kind=AIErrorKind.INVALID_JSON,
                message=f"Failed to parse Ollama model listing: {ex}",
            )

        if target in models or (":" not in target and f"{target}:latest" in models):
            return True, None

        return False, AIError(
            kind=AIErrorKind.MODEL_NOT_INSTALLED,
            message=f"Configured model '{target}' is not installed in local Ollama.",
            model=target,
            details=f"Installed models: {models}",
        )

    def _send_generate_request(
        self,
        prompt: str,
        model: str,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], float, Optional[AIError]]:
        """
        Low-level internal generator sending bounded requests to /api/generate.
        Returns (response_json_dict, latency_ms, optional_error).
        """
        timeout = timeout_s if timeout_s is not None else self.timeout_s
        temp = temperature if temperature is not None else self.default_temperature
        tokens = num_predict if num_predict is not None else self.default_num_predict

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temp,
                "num_predict": tokens,
            },
        }

        start_time = time.perf_counter()
        try:
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as ex:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return None, latency_ms, AIError(
                kind=AIErrorKind.TIMEOUT,
                message=f"Ollama inference request timed out after {timeout:.1f}s.",
                model=model,
                details=str(ex),
            )
        except requests.exceptions.ConnectionError as ex:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return None, latency_ms, AIError(
                kind=AIErrorKind.OLLAMA_UNAVAILABLE,
                message="Ollama is not running or unreachable at the local endpoint.",
                model=model,
                details=str(ex),
            )
        except requests.exceptions.RequestException as ex:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return None, latency_ms, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"Network error while communicating with Ollama: {ex}",
                model=model,
                details=str(ex),
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        is_redirect = (getattr(resp, "is_redirect", False) is True) or (isinstance(getattr(resp, "status_code", None), int) and 300 <= resp.status_code < 400)
        if is_redirect:
            return None, latency_ms, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"HTTP redirect (status {resp.status_code}) rejected: local AI endpoints must not issue redirects.",
                status_code=resp.status_code,
                model=model,
                raw_response=resp.text,
            )
        elif resp.status_code == 404:
            return None, latency_ms, AIError(
                kind=AIErrorKind.MODEL_NOT_INSTALLED,
                message=f"Model '{model}' is not installed in local Ollama.",
                status_code=404,
                model=model,
                raw_response=resp.text,
            )
        elif resp.status_code != 200:
            return None, latency_ms, AIError(
                kind=AIErrorKind.HTTP_ERROR,
                message=f"Ollama returned HTTP error {resp.status_code}.",
                status_code=resp.status_code,
                model=model,
                raw_response=resp.text,
            )

        try:
            resp_data = resp.json()
        except Exception as ex:
            return None, latency_ms, AIError(
                kind=AIErrorKind.INVALID_JSON,
                message=f"Ollama API returned non-JSON response envelope: {ex}",
                status_code=resp.status_code,
                model=model,
                raw_response=resp.text,
            )

        if not isinstance(resp_data, dict):
            return None, latency_ms, AIError(
                kind=AIErrorKind.INVALID_JSON,
                message="Ollama API returned an unexpected response structure.",
                status_code=resp.status_code,
                model=model,
                raw_response=resp.text,
            )

        return resp_data, latency_ms, None

    def send_generate_prompt(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> Tuple[Optional[str], float, Optional[AIError]]:
        """
        Sends a bounded generation prompt to local Ollama.
        Returns (raw_response_text, latency_ms, error).
        """
        target_model = (model or self.default_model).strip()
        if not target_model:
            return None, 0.0, AIError(
                kind=AIErrorKind.MODEL_NOT_INSTALLED,
                message="No AI model specified.",
            )
        if not prompt or not prompt.strip():
            return None, 0.0, AIError(
                kind=AIErrorKind.EMPTY_RESPONSE,
                message="Prompt cannot be empty.",
                model=target_model,
            )

        resp_data, latency_ms, error = self._send_generate_request(
            prompt=prompt,
            model=target_model,
            temperature=temperature,
            num_predict=num_predict,
            timeout_s=timeout_s,
        )
        if error is not None:
            return None, latency_ms, error

        raw_output = resp_data.get("response", "") if resp_data else ""
        return raw_output, latency_ms, None

    def generate_structured_label(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> AIResult:
        """
        Sends a structured prompt to local Ollama and parses/validates the returned topic JSON.
        """
        target_model = (model or self.default_model).strip()
        if not target_model:
            return AIResult(
                error=AIError(
                    kind=AIErrorKind.MODEL_NOT_INSTALLED,
                    message="No AI model specified.",
                )
            )

        if not prompt or not prompt.strip():
            return AIResult(
                error=AIError(
                    kind=AIErrorKind.EMPTY_RESPONSE,
                    message="Prompt cannot be empty.",
                    model=target_model,
                )
            )

        resp_data, latency_ms, error = self._send_generate_request(
            prompt=prompt,
            model=target_model,
            timeout_s=timeout_s,
        )

        if error is not None:
            return AIResult(error=error)

        assert resp_data is not None
        raw_output = resp_data.get("response", "")

        parsed_label, val_msg, val_kind = validate_and_parse_topic_json(raw_output)
        if parsed_label is None:
            return AIResult(
                error=AIError(
                    kind=val_kind or AIErrorKind.INVALID_JSON,
                    message=val_msg or "Failed to validate topic JSON.",
                    status_code=200,
                    model=target_model,
                    raw_response=raw_output,
                )
            )

        metadata = {
            "eval_count": resp_data.get("eval_count"),
            "prompt_eval_count": resp_data.get("prompt_eval_count"),
            "total_duration_ns": resp_data.get("total_duration"),
        }

        return AIResult(
            response=AIResponse(
                parsed=parsed_label,
                model=target_model,
                latency_ms=round(latency_ms, 2),
                raw_text=raw_output,
                metadata=metadata,
            )
        )

    def generate_topic_label(
        self,
        question_text: str,
        subject: str = "Computer Science",
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> AIResult:
        """
        Generates and strictly validates a topic label for an exam question.

        Uses the verified candidate model (qwen2.5-coder:1.5b-base) with structured
        few-shot completion prompting and bounded token limits.
        """
        target_model = (model or self.default_model).strip()
        if not target_model:
            return AIResult(
                error=AIError(
                    kind=AIErrorKind.MODEL_NOT_INSTALLED,
                    message="No AI model specified.",
                )
            )

        if not question_text or not question_text.strip():
            return AIResult(
                error=AIError(
                    kind=AIErrorKind.EMPTY_RESPONSE,
                    message="Question text cannot be empty.",
                    model=target_model,
                )
            )

        prompt = build_qwen_few_shot_prompt(question_text=question_text, subject=subject)
        return self.generate_structured_label(
            prompt=prompt,
            model=target_model,
            timeout_s=timeout_s,
        )


