"""
test_ai_benchmark.py - Unit tests for AI benchmark evaluation engine.

Ensures that:
1. Benchmark dataset contains at least 20 valid, curated samples.
2. Scoring correctly evaluates exact matches, alias matches, and ambiguity.
3. Schema validation catches missing fields and invalid enums.
4. The benchmark runner handles model crashes and HTTP failures without crashing.
5. All tests use deterministic mocked responses and require NO live Ollama server or network calls.
"""

from pathlib import Path
import pytest
from paperpilot.ai_benchmark import (
    BENCHMARK_DATASET,
    BenchmarkSample,
    evaluate_prediction,
    build_instruct_prompt,
    build_base_completion_prompt,
    run_model_benchmark,
    generate_markdown_report,
)


def test_benchmark_dataset_integrity():
    """Verifies that the benchmark dataset contains at least 20 curated CS samples."""
    assert len(BENCHMARK_DATASET) >= 20
    subjects = set(s.subject for s in BENCHMARK_DATASET)
    assert "Operating Systems" in subjects
    assert "Data Structures & Algorithms" in subjects
    assert "Database Management Systems" in subjects
    assert "Computer Architecture" in subjects

    # Verify every sample has required non-empty fields
    for s in BENCHMARK_DATASET:
        assert s.id
        assert s.subject
        assert s.question
        assert s.reference_topic
        assert isinstance(s.acceptable_aliases, list)


def test_evaluate_prediction_exact_match():
    """Verifies that an exact or normalized reference match scores 1.0."""
    sample = BENCHMARK_DATASET[0]  # Deadlock conditions
    mock_resp = '{"topic": "Deadlock Conditions", "confidence": "high", "reasoning": "Discusses 4 conditions"}'

    is_json, is_schema, data, acc = evaluate_prediction(sample, mock_resp)
    assert is_json is True
    assert is_schema is True
    assert data["topic"] == "Deadlock Conditions"
    assert acc == 1.0


def test_evaluate_prediction_alias_match():
    """Verifies that matching an acceptable alias scores 1.0."""
    sample = BENCHMARK_DATASET[0]  # Acceptable aliases includes "Deadlock"
    mock_resp = '{"topic": "Deadlock", "confidence": "high", "reasoning": "Core concept"}'

    is_json, is_schema, data, acc = evaluate_prediction(sample, mock_resp)
    assert is_json is True
    assert is_schema is True
    assert acc == 1.0


def test_evaluate_prediction_ambiguous_case():
    """Verifies that declaring uncertainty on an incomplete prompt yields high accuracy."""
    ambiguous_sample = next(s for s in BENCHMARK_DATASET if s.is_ambiguous)
    
    # Correct response: declares uncertainty
    good_resp = '{"topic": "Incomplete Question", "confidence": "uncertain", "reasoning": "Missing prompt body"}'
    _, _, _, acc_good = evaluate_prediction(ambiguous_sample, good_resp)
    assert acc_good == 1.0

    # Bad response: hallucinates high confidence on a vague prompt
    bad_resp = '{"topic": "Quantum Computing", "confidence": "high", "reasoning": "Invented topic"}'
    _, _, _, acc_bad = evaluate_prediction(ambiguous_sample, bad_resp)
    assert acc_bad < 0.5


def test_evaluate_prediction_invalid_json():
    """Verifies handling of non-JSON responses."""
    sample = BENCHMARK_DATASET[0]
    is_json, is_schema, _, acc = evaluate_prediction(sample, "This is plain text with no JSON.")
    assert is_json is False
    assert is_schema is False
    assert acc == 0.0


def test_evaluate_prediction_schema_violation():
    """Verifies handling of JSON missing required schema keys or having invalid enums."""
    sample = BENCHMARK_DATASET[0]

    # Missing confidence
    resp_missing = '{"topic": "Deadlock"}'
    is_json, is_schema, _, acc = evaluate_prediction(sample, resp_missing)
    assert is_json is True
    assert is_schema is False
    assert acc == 0.0

    # Invalid confidence enum
    resp_bad_enum = '{"topic": "Deadlock", "confidence": "super_confident"}'
    is_json2, is_schema2, _, acc2 = evaluate_prediction(sample, resp_bad_enum)
    assert is_json2 is True
    assert is_schema2 is False
    assert acc2 == 0.0


def test_run_model_benchmark_with_mocked_success():
    """Verifies that run_model_benchmark computes all metrics properly using mocked sender."""
    test_samples = BENCHMARK_DATASET[:3]

    def mock_sender(payload, timeout):
        # Return mock JSON response with 50ms synthetic latency
        sample_q = payload["prompt"]
        topic = "Deadlock Conditions" if "Deadlock" in sample_q else "General Topic"
        resp = f'{{"topic": "{topic}", "confidence": "high", "reasoning": "Mocked test"}}'
        return resp, 50.0, None

    summary = run_model_benchmark(
        model_name="mock-model:test",
        samples=test_samples,
        request_sender=mock_sender,
    )

    assert summary.status == "completed"
    assert summary.total_samples == 3
    assert summary.successful_inferences == 3
    assert summary.valid_json_rate_pct == 100.0
    assert summary.schema_compliance_rate_pct == 100.0
    assert summary.mean_latency_ms == 50.0
    assert summary.samples_per_minute > 0


def test_run_model_benchmark_handles_http_failure():
    """Verifies that an HTTP error (like Gemma's 500) fails gracefully without crashing."""
    test_samples = BENCHMARK_DATASET[:2]

    def mock_failing_sender(payload, timeout):
        return None, 100.0, "HTTP 500: CUDA error: shared object initialization failed"

    summary = run_model_benchmark(
        model_name="crashing-model:test",
        samples=test_samples,
        request_sender=mock_failing_sender,
    )

    assert summary.status == "failed"
    assert summary.error_message is not None
    assert "HTTP 500" in summary.error_message
    assert summary.successful_inferences == 0


def test_generate_markdown_report_output(tmp_path):
    """Verifies that markdown report generation creates formatted tables."""
    # Create two synthetic summaries
    s1 = run_model_benchmark(
        model_name="qwen2.5-coder:1.5b-base",
        samples=BENCHMARK_DATASET[:2],
        request_sender=lambda p, t: ('{"topic": "Deadlock Conditions", "confidence": "high"}', 40.0, None)
    )
    s2 = run_model_benchmark(
        model_name="gemma4:latest",
        samples=BENCHMARK_DATASET[:2],
        request_sender=lambda p, t: (None, 100.0, "HTTP 500: Server terminated")
    )

    out_file = tmp_path / "report.md"
    report_text = generate_markdown_report([s1, s2], output_path=out_file)

    assert out_file.exists()
    assert "# PaperPilot Phase 5 — Local Model Benchmark Report" in report_text
    assert "qwen2.5-coder:1.5b-base" in report_text
    assert "gemma4:latest" in report_text
    assert "Executive Summary" in report_text

