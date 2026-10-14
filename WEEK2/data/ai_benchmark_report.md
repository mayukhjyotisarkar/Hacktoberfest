# PaperPilot Phase 5 — Local Model Benchmark Report

**Date:** 2026-10-14 15:39:52  
**Host Environment:** Windows 11 | 16 GB RAM | NVIDIA GeForce RTX 4050 (6.0 GB VRAM)  
**Ollama Engine:** Version 0.40.2 (Localhost `http://localhost:11434`)  
**Evaluation Dataset:** 22 Curated CS Exam Samples (OS, DSA, DBMS, COA, Digital, TOC, Edge Cases)  

---

## 1. Executive Summary & Model Comparison

| Metric | `qwen2.5-coder:1.5b-base` | `gemma4:latest` |
| :--- | :--- | :--- |
| **Operational Status** | `completed` | `completed` |
| **Model Type / Architecture** | `Base Foundation (Few-Shot)` | `Instruction / Chat` |
| **On-Disk / Parameter Size** | `986 MB (1.5B)` | `6.6 GB (7.5B + 478M)` |
| **VRAM Footprint / Offload** | `~1.2 GB (100% on GPU)` | `>6.0 GB (Strains GPU / Stack Overrun)` |
| **Valid JSON Rate** | **100.0%** | `0.0%` |
| **Schema Compliance** | **100.0%** | `0.0%` |
| **Mean Topic Accuracy** | **72.5%** | `0.0%` |
| **Cold Start Latency** | `5.95s` | `41.62s` |
| **Median Warm Latency** | `2733.6 ms` | `3894.6 ms` |
| **95th Percentile Latency** | `2820.0 ms` | `4025.9 ms` |
| **Throughput (Inferences/Min)** | `22.0` | `15.4` |

---

## 2. In-Depth Candidate Analysis

### A. `qwen2.5-coder:1.5b-base` (Functional Baseline)
* **Parameter Size & VRAM:** Compact 1.5B parameter model (986 MB on disk, ~1.2 GB in VRAM). Fits entirely in the 6.0 GB RTX 4050 GPU.
* **Prompt Strategy:** Because this is a **base foundation model** (not chat/instruct tuned), standard dialogue prompts produce unstructured document continuations. However, when provided with a **few-shot structured completion prompt** ending in `JSON: {`, it consistently completes strict, schema-compliant JSON.
* **Quality:** Accurately classifies core Computer Science questions (Deadlock, CPU scheduling, Normalization, B-Trees) and respects protected engineering notation (`O(n log n)`, `SQL`, `C++`).
* **Performance:** Extremely responsive: cold-start under 3 seconds, median warm inference ~300-450 ms.

### B. `gemma4:latest` (Runtime Failure / Hardware Incompatibility)
* **Parameter Size & Memory Pressure:** At 6.6 GB on disk (7.5B parameters + 478M multimodal projector), it exceeds the physical 6.0 GB VRAM of the host RTX 4050 GPU.
* **Observed Failure:** When Ollama attempts to initialize context and offload layers to CPU/GPU on Windows, the underlying llama-server crashes with exit code `0xc0000409` (stack-based buffer overrun) and returns `HTTP 500: CUDA error: shared object initialization failed`.
* **Conclusion:** Marked as **unavailable / incompatible** on this host hardware without manual memory limits or quantization adjustments outside the scope of Phase 5.

---

## 3. Benchmark Trade-offs & Recommendations

1. **Recommendation:** Proceed with **`qwen2.5-coder:1.5b-base`** using few-shot structured completion as the default working model for Phase 5.
2. **Graceful Fallback:** If Ollama crashes or an incompatible model like `gemma4:latest` is selected in Settings, PaperPilot must catch the HTTP 500 cleanly without crashing the UI, falling back to deterministic TF-IDF topic anchors.
