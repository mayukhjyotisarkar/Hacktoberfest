"""
run_benchmark.py - Execution script for Phase 5 Stage 1 Local Model Benchmark.

Runs evaluation on the installed candidate models (qwen2.5-coder:1.5b-base and gemma4:latest),
captures latency, JSON validity, schema compliance, and hardware compatibility,
and outputs both machine-readable JSON and Markdown reports to data/.
"""

from dataclasses import asdict
import json
from pathlib import Path
import sys

from paperpilot.ai_benchmark import (
    BENCHMARK_DATASET,
    run_model_benchmark,
    generate_markdown_report,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def main():
    print("=" * 70)
    print("PAPERPILOT PHASE 5 — LOCAL MODEL BENCHMARK EXECUTION")
    print("=" * 70)
    print(f"Total Curated Evaluation Samples: {len(BENCHMARK_DATASET)}")
    print("Candidates to evaluate: ['qwen2.5-coder:1.5b-base', 'gemma4:latest']\n")

    candidates = ["qwen2.5-coder:1.5b-base", "gemma4:latest"]
    summaries = []

    for model in candidates:
        print(f">>> Running benchmark on '{model}'...")
        summary = run_model_benchmark(
            model_name=model,
            api_url="http://localhost:11434",
            samples=BENCHMARK_DATASET,
            timeout_s=70.0,
        )
        summaries.append(summary)

        print(f"    Status: {summary.status}")
        if summary.status == "completed":
            print(f"    Valid JSON Rate: {summary.valid_json_rate_pct}% ({summary.valid_json_count}/{summary.total_samples})")
            print(f"    Schema Compliance: {summary.schema_compliance_rate_pct}% ({summary.schema_compliant_count}/{summary.total_samples})")
            print(f"    Mean Accuracy: {summary.mean_accuracy_pct}%")
            print(f"    Cold Start Latency: {summary.cold_start_latency_s}s")
            print(f"    Median Warm Latency: {summary.median_latency_ms} ms")
            print(f"    Throughput: {summary.samples_per_minute} samples/min")
        else:
            print(f"    Error/Failure: {summary.error_message}")
        print()

    # Save Machine-Readable JSON
    json_path = DATA_DIR / "ai_benchmark_results.json"
    results_dict = {
        "benchmark_date": "2026-10-14",
        "total_samples": len(BENCHMARK_DATASET),
        "summaries": [asdict(s) for s in summaries],
    }
    json_path.write_text(json.dumps(results_dict, indent=2), encoding="utf-8")
    print(f"[Export] Machine-readable benchmark data saved to: {json_path}")

    # Save Markdown Report
    md_path = DATA_DIR / "ai_benchmark_report.md"
    generate_markdown_report(summaries, output_path=md_path)
    print(f"[Export] Detailed Markdown report saved to: {md_path}")
    print("\nBenchmark Execution Completed Successfully!")


if __name__ == "__main__":
    main()

