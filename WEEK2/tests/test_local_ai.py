"""
test_local_ai.py - Comprehensive unit tests for the isolated local Ollama AI client.

Guarantees:
  - 100% deterministic and offline: tests run without Ollama installed or running.
  - Zero network requests: all HTTP interactions and socket connections are mocked.
  - Full coverage of security boundaries, error taxonomy, schema validation, and timeouts.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from paperpilot.local_ai import (
    LocalAIClient,
    AIErrorKind,
    AIError,
    AIResponse,
    AIResult,
    TopicLabel,
    validate_loopback_url,
    validate_and_parse_topic_json,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_NUM_PREDICT,
)


# -----------------------------------------------------------------------------
# 1. Zero Network Activity at Import & Instantiation
# -----------------------------------------------------------------------------

def test_import_and_instantiation_makes_no_network_requests():
    """Confirms that importing and instantiating LocalAIClient performs zero HTTP calls."""
    with patch("requests.Session.get") as mock_get, \
         patch("requests.Session.post") as mock_post, \
         patch("requests.Session.request") as mock_req, \
         patch("requests.get") as mock_top_get, \
         patch("requests.post") as mock_top_post:

        client = LocalAIClient()
        assert client is not None
        assert client.base_url == "http://localhost:11434"
        assert client.default_model == DEFAULT_MODEL

        # Assert no network calls were made
        mock_get.assert_not_called()
        mock_post.assert_not_called()
        mock_req.assert_not_called()
        mock_top_get.assert_not_called()
        mock_top_post.assert_not_called()


# -----------------------------------------------------------------------------
# 2. Loopback Endpoint Validation & Security Rejections
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_url", [
    "http://api.openai.com/v1",
    "https://api.anthropic.com",
    "http://192.168.1.100:11434",
    "http://10.0.0.1:11434",
    "http://172.16.0.1:11434",
    "ftp://localhost:11434",
    "file:///etc/passwd",
    "http://external-server.com:11434",
    "",
    "   ",
])
def test_rejection_of_non_loopback_urls(invalid_url):
    """Ensures non-loopback URLs and non-http schemes are strictly rejected."""
    with pytest.raises(ValueError):
        validate_loopback_url(invalid_url)

    with pytest.raises(ValueError):
        LocalAIClient(base_url=invalid_url)


@pytest.mark.parametrize("valid_url,expected_normalized", [
    ("http://localhost:11434", "http://localhost:11434"),
    ("http://localhost:11434/", "http://localhost:11434"),
    ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
    ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
    ("http://[::1]:11434", "http://[::1]:11434"),
])
def test_valid_loopback_urls_accepted(valid_url, expected_normalized):
    """Ensures valid local loopback addresses are accepted and normalized."""
    client = LocalAIClient(base_url=valid_url)
    assert client.base_url == expected_normalized


# -----------------------------------------------------------------------------
# 3. Service Availability Check (Health Check)
# -----------------------------------------------------------------------------

def test_service_availability_check_success():
    """Verifies check_health returns True when Ollama responds with HTTP 200."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.object(client.session, "get", return_value=mock_resp):
        assert client.check_health() is True


@pytest.mark.parametrize("error_scenario", [
    requests.exceptions.ConnectionError("Connection refused"),
    requests.exceptions.Timeout("Read timeout"),
    requests.exceptions.RequestException("Generic network failure"),
])
def test_service_availability_check_network_failure(error_scenario):
    """Verifies check_health returns False safely without raising exceptions on network errors."""
    client = LocalAIClient()
    with patch.object(client.session, "get", side_effect=error_scenario):
        assert client.check_health() is False


def test_service_availability_check_non_200_status():
    """Verifies check_health returns False when Ollama responds with HTTP 503 or 500."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 503

    with patch.object(client.session, "get", return_value=mock_resp):
        assert client.check_health() is False


# -----------------------------------------------------------------------------
# 4. Model Discovery & Readiness Verification
# -----------------------------------------------------------------------------

def test_model_discovery_and_verification_installed():
    """Tests discovery of installed models and matching against configured candidate."""
    client = LocalAIClient(default_model="qwen2.5-coder:1.5b-base")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "qwen2.5-coder:1.5b-base", "size": 986000000},
            {"name": "llama3:8b", "size": 4700000000},
        ]
    }

    with patch.object(client.session, "get", return_value=mock_resp):
        models = client.get_installed_models()
        assert "qwen2.5-coder:1.5b-base" in models
        assert "llama3:8b" in models
        assert client.is_model_available("qwen2.5-coder:1.5b-base") is True
        assert client.is_model_available("mistral:latest") is False

        ready, err = client.verify_configured_model()
        assert ready is True
        assert err is None


def test_model_verification_missing_model():
    """Tests model verification failure when the target model is not installed."""
    client = LocalAIClient(default_model="missing-model:latest")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "qwen2.5-coder:1.5b-base"}]
    }

    with patch.object(client.session, "get", return_value=mock_resp):
        ready, err = client.verify_configured_model()
        assert ready is False
        assert err is not None
        assert err.kind == AIErrorKind.MODEL_NOT_INSTALLED
        assert "missing-model:latest" in err.message


def test_model_verification_ollama_unreachable():
    """Tests model verification failure when Ollama service is stopped or unreachable."""
    client = LocalAIClient()
    with patch.object(client.session, "get", side_effect=requests.exceptions.ConnectionError("Refused")):
        ready, err = client.verify_configured_model()
        assert ready is False
        assert err is not None
        assert err.kind == AIErrorKind.OLLAMA_UNAVAILABLE
        assert "not running or unreachable" in err.message


# -----------------------------------------------------------------------------
# 5. Successful Topic Label Generation & Schema Validation
# -----------------------------------------------------------------------------

def test_successful_topic_label_generation():
    """Tests complete successful inference flow with parsed TopicLabel output."""
    client = LocalAIClient(default_model="qwen2.5-coder:1.5b-base")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({
            "topic": "Deadlock Characterization",
            "confidence": "high",
            "reasoning": "Four necessary conditions for deadlock"
        }),
        "eval_count": 22,
        "prompt_eval_count": 58,
        "total_duration": 420000000,
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label(
            question_text="Explain the four conditions necessary for deadlock to occur.",
            subject="Operating Systems"
        )

        assert result.is_success is True
        assert result.error is None
        assert isinstance(result.response, AIResponse)
        assert result.response.parsed.topic == "Deadlock Characterization"
        assert result.response.parsed.confidence == "high"
        assert result.response.parsed.reasoning == "Four necessary conditions for deadlock"
        assert result.response.model == "qwen2.5-coder:1.5b-base"
        assert result.response.latency_ms >= 0.0
        assert result.response.metadata["eval_count"] == 22


def test_partial_json_boundary_recovery():
    """Tests recovery when completion model returns completion without leading brace."""
    raw_completion = ' "topic": "Banker\'s Algorithm", "confidence": "high", "reasoning": "Deadlock avoidance"}'
    label, err, kind = validate_and_parse_topic_json(raw_completion)

    assert err is None
    assert kind is None
    assert label is not None
    assert label.topic == "Banker's Algorithm"
    assert label.confidence == "high"


# -----------------------------------------------------------------------------
# 6. Failure Handlers: Empty, Malformed, Missing Fields, and Bad Enums
# -----------------------------------------------------------------------------

def test_empty_model_response():
    """Tests failure when Ollama returns an empty generation string."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": "   ",
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("What is a Semaphore?")
        assert result.is_success is False
        assert result.response is None
        assert result.error.kind == AIErrorKind.EMPTY_RESPONSE


def test_malformed_json_response():
    """Tests failure when model returns text that is not valid JSON."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": "The topic of this question is clearly Operating Systems {broken json",
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("What is a Semaphore?")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.INVALID_JSON


@pytest.mark.parametrize("missing_field_json,expected_missing", [
    (json.dumps({"confidence": "high"}), "topic"),
    (json.dumps({"topic": "Sorting Algorithms"}), "confidence"),
])
def test_valid_json_with_missing_required_fields(missing_field_json, expected_missing):
    """Tests schema rejection when required fields 'topic' or 'confidence' are omitted."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": missing_field_json,
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("What is Merge Sort?")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.SCHEMA_VIOLATION
        assert expected_missing in result.error.message


def test_valid_json_with_invalid_enum_values():
    """Tests schema rejection when 'confidence' has an invalid enum value."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({"topic": "Deadlock", "confidence": "super_certain"}),
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Deadlock")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.SCHEMA_VIOLATION
        assert "invalid confidence" in result.error.message.lower()


def test_schema_violation_disallowed_keys():
    """Tests strict rejection when disallowed unexpected keys are returned."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({
            "topic": "Deadlock",
            "confidence": "high",
            "unauthorized_field": "injected",
        }),
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Deadlock")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.SCHEMA_VIOLATION
        assert "unexpected key" in result.error.message.lower()


def test_schema_violation_topic_length_exceeded():
    """Tests rejection when topic string exceeds maximum 100 characters."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({
            "topic": "A" * 105,
            "confidence": "high",
        }),
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Deadlock")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.SCHEMA_VIOLATION
        assert "exceeds maximum limit" in result.error.message.lower()


def test_empty_question_text_rejection():
    """Tests that client immediately returns an error if question text is blank."""
    client = LocalAIClient()
    result = client.generate_topic_label("   ")
    assert result.is_success is False
    assert result.error.kind == AIErrorKind.EMPTY_RESPONSE


# -----------------------------------------------------------------------------
# 7. Network, HTTP, and Timeout Failures
# -----------------------------------------------------------------------------

def test_request_timeout_handling():
    """Verifies timeout errors are caught and returned as structured AIError."""
    client = LocalAIClient(timeout_s=5.0)
    with patch.object(client.session, "post", side_effect=requests.exceptions.Timeout("Read timed out")):
        result = client.generate_topic_label("Explain Page Replacement")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.TIMEOUT
        assert "timed out after 5.0s" in result.error.message


def test_http_500_error_handling():
    """Verifies HTTP 500 server errors are captured and returned cleanly."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Page Replacement")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.HTTP_ERROR
        assert result.error.status_code == 500


def test_http_404_model_not_installed():
    """Verifies HTTP 404 response maps to MODEL_NOT_INSTALLED error."""
    client = LocalAIClient(default_model="nonexistent-model")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "model 'nonexistent-model' not found"

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Page Replacement")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.MODEL_NOT_INSTALLED
        assert result.error.status_code == 404


def test_connection_error_ollama_stopped():
    """Verifies connection refused maps to OLLAMA_UNAVAILABLE error."""
    client = LocalAIClient()
    with patch.object(client.session, "post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        result = client.generate_topic_label("Explain Page Replacement")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.OLLAMA_UNAVAILABLE
        assert "not running or unreachable" in result.error.message


# -----------------------------------------------------------------------------
# 8. Bounded Parameters Verification
# -----------------------------------------------------------------------------

def test_bounded_parameters_verification():
    """
    Confirms that client sends strictly bounded parameters:
      - temperature = 0.1
      - num_predict = 80
      - stream = False
      - format = 'json'
      - model = configured model
    """
    client = LocalAIClient(default_model="qwen2.5-coder:1.5b-base")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({"topic": "CPU Scheduling", "confidence": "high"}),
    }

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        client.generate_topic_label(
            question_text="Compare Round Robin and SJF scheduling algorithms.",
            subject="Operating Systems"
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]

        assert payload["model"] == "qwen2.5-coder:1.5b-base"
        assert payload["stream"] is False
        assert payload["format"] == "json"
        assert payload["options"]["temperature"] == DEFAULT_TEMPERATURE
        assert payload["options"]["num_predict"] == DEFAULT_NUM_PREDICT

        # Verify prompt format includes few-shot completion structure
        assert "Exam Question Topic Classification Dataset" in payload["prompt"]
        assert "Compare Round Robin and SJF scheduling algorithms." in payload["prompt"]
        assert payload["prompt"].endswith("JSON: {")


# -----------------------------------------------------------------------------
# 9. Regression Tests: Redirects & Strict Boundary Recovery Safety
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("redirect_code", [301, 302, 307, 308])
def test_http_redirect_rejection_in_generate(redirect_code):
    """
    Safeguard 1: Ensures HTTP redirects cannot send requests or question data
    to an external or unexpected destination.
    """
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = redirect_code
    mock_resp.is_redirect = True
    mock_resp.text = f"Redirecting to http://evil.com/leak"

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        result = client.generate_topic_label("What is Virtual Memory?")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.HTTP_ERROR
        assert result.error.status_code == redirect_code
        assert "redirect" in result.error.message.lower()

        # Confirm allow_redirects=False was passed explicitly
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs.get("allow_redirects") is False


@pytest.mark.parametrize("redirect_code", [301, 302, 307, 308])
def test_http_redirect_rejection_in_verify_model(redirect_code):
    """Ensures HTTP redirects are rejected during model verification."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = redirect_code
    mock_resp.is_redirect = True

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        ready, err = client.verify_configured_model()
        assert ready is False
        assert err is not None
        assert err.kind == AIErrorKind.HTTP_ERROR
        assert err.status_code == redirect_code
        assert "redirect" in err.message.lower()
        assert mock_get.call_args.kwargs.get("allow_redirects") is False


@pytest.mark.parametrize("bad_confidence_value", [
    123,
    True,
    False,
    ["high"],
    {"conf": "high"},
    None,
])
def test_schema_rejection_of_non_string_confidence(bad_confidence_value):
    """Safeguard 2: Strictly rejects non-string confidence types."""
    client = LocalAIClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:1.5b-base",
        "response": json.dumps({"topic": "Deadlock", "confidence": bad_confidence_value}),
    }

    with patch.object(client.session, "post", return_value=mock_resp):
        result = client.generate_topic_label("Explain Deadlock")
        assert result.is_success is False
        assert result.error.kind == AIErrorKind.SCHEMA_VIOLATION
        assert "must be a string" in result.error.message.lower() or "missing" in result.error.message.lower()


@pytest.mark.parametrize("malformed_boundary_text", [
    ' "topic": "Deadlock", "confidence": ',   # Truncated value
    '{"topic": "Deadlock", "confidence": "high"',  # Missing closing brace
    ' "topic": "Deadlock" ',                  # Missing confidence and braces
    'Here is the JSON: { incomplete',         # Unclosed curly brace
    'Just random text with no json',          # No JSON tokens
    '{"topic": "Deadlock"} {"topic": "OS"}',  # Multiple JSON objects
])
def test_json_boundary_recovery_rejects_incomplete_or_malformed(malformed_boundary_text):
    """
    Safeguard 2: Confirms JSON boundary recovery never accepts truncated,
    unclosed, or malformed payloads.
    """
    label, err, kind = validate_and_parse_topic_json(malformed_boundary_text)
    assert label is None
    assert err is not None
    assert kind in (AIErrorKind.INVALID_JSON, AIErrorKind.SCHEMA_VIOLATION)


@pytest.mark.parametrize("cred_url", [
    "http://user:pass@localhost:11434",
    "http://admin@127.0.0.1:11434",
    "http://root:secret@[::1]:11434",
])
def test_rejection_of_embedded_credentials(cred_url):
    """Ensures endpoints with embedded user credentials are systematically rejected."""
    with pytest.raises(ValueError, match="embedded user credentials"):
        validate_loopback_url(cred_url)


def test_markdown_fence_trailing_boundary_extracted_cleanly():
    """Confirms that JSON with trailing markdown fences is extracted and parsed."""
    raw = '{"topic": "Deadlock Characterization", "confidence": "high"}\n```'
    label, err, kind = validate_and_parse_topic_json(raw)
    assert err is None
    assert kind is None
    assert label is not None
    assert label.topic == "Deadlock Characterization"
    assert label.confidence == "high"



