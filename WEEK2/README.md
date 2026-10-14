# PaperPilot ✈️📚
> **Local-First AI Exam Paper Analyzer**

PaperPilot is an offline-capable, local-first tool designed to help students analyze previous-year question papers (PYQs). It extracts questions from text-based PDFs, detects exact and semantically similar questions across different years using TF-IDF and cosine similarity, highlights recurrent topics, and generates revision priorities.

---

## 🌟 Key Features

1. **PDF Text Extraction:** Page-accurate text extraction using PyMuPDF (`pymupdf`) with automatic scanned-PDF / image detection.
2. **Robust Question Parser:** Identifies question boundaries (`1.`, `Q2:`, `1(a)`, `(i)`) while rejecting non-question headers (`Time: 3 Hours`, `Max Marks`).
3. **Similarity Engine:** TF-IDF vectorization and cosine similarity to group repeated and similar questions across examination years without external APIs.
4. **Interactive Dashboard:** Built with Streamlit for reviewing extracted questions, exploring frequency metrics, and exporting clean CSV reports.
5. **Optional Local AI:** Integrates with local Ollama open models (e.g. `qwen2.5-coder:1.5b-base`, `gemma4:latest`) for topic tagging and revision planning.

---

## 📁 Project Structure

```text
WEEK2/
├── .gitignore                      # Prevents committing caches, databases, and uploaded PDFs
├── requirements.txt                # Pinned dependencies
├── README.md                       # Documentation & setup instructions
├── demo_phase3.py                  # Phase 3 similarity and analytics demonstration
├── paperpilot/                     # Core Python package
│   ├── __init__.py                 # Package declaration
│   ├── pdf_extractor.py            # PDF text extraction and error handling
│   ├── question_parser.py          # Question boundary detection and metadata extraction
│   ├── text_normalizer.py          # CS token preservation & boilerplate stripping
│   ├── similarity.py               # TF-IDF & representative-based clustering
│   └── analytics.py                # Frequency counts & revision prioritization
├── tests/                          # Automated Pytest suite
│   ├── test_pdf_extractor.py       # Extraction unit tests
│   ├── test_question_parser.py     # Parser unit tests
│   ├── test_similarity.py          # Similarity, token protection & clustering regression tests
│   └── test_analytics.py           # Recurrence, metadata preservation & checklist tests
└── data/                           # Test fixtures
    ├── generate_samples.py         # Synthetic question paper generator
    ├── sample_os_2022.pdf          # Operating Systems 2022 sample paper
    └── sample_os_2023.pdf          # Operating Systems 2023 sample paper
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Tests
```bash
python -m pytest tests/ -v
```

---

*Local-First • Privacy-First • No Cloud AI APIs Required*

