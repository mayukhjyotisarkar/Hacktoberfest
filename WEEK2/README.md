# PaperPilot ✈️📚
> **Local-First, Student-Ready Previous-Year Question Paper (PYQ) Analyzer**

PaperPilot is a privacy-first, offline-capable study tool built for college students. Instead of spending hours manually cross-referencing five years of past university examination papers, PaperPilot automatically extracts questions from PDF papers, identifies recurring and semantically similar questions across different years, and ranks topics by revision priority.

---

## 🎯 Who Is PaperPilot For?

- **University & College Students:** Preparing for semester midterms and finals who want to know: *"Which questions and topics are asked almost every single year?"*
- **Study Groups & Class Representatives:** Organizing question banks and high-yield revision checklists for their classmates.
- **Privacy-Conscious Learners:** Students who want their exam papers, notes, and study habits stored strictly on their own machine, with zero cloud tracking, zero data mining, and zero subscriptions.

---

## ✨ Key Features & Architecture

| Feature | Description | Architecture / Implementation |
| :--- | :--- | :--- |
| **📄 PDF Extraction** | Extracts text with accurate page tracking and automatic scanned-PDF detection. | PyMuPDF (`pymupdf`) |
| **🔍 Numbered Parser** | Detects question boundaries (`1.`, `2(a)`, `(i)`) while rejecting non-question headers (`Time: 3 Hours`, `Max Marks`). | Custom regex delimiter engine with lookahead & false-positive suppression |
| **🔁 Leader Clustering** | Groups repeated and similar questions across years using cosine similarity without transitive chain-merging. | TF-IDF Vectorizer + Cosine Similarity (`scikit-learn`) + Leader Clustering |
| **📈 Frequency Analytics** | Calculates recurrence counts, distinct paper distributions, and exam year breakdowns. | Tabular aggregation (`pandas`) |
| **📝 Revision Priority** | Scores each recurring question based on occurrence frequency and distinct papers. | Mathematical weighting engine |
| **💾 ACID Persistence** | Stores reviewed questions, exclusions, and papers locally in an ACID SQLite database. | Parameterized SQLite (`paperpilot.db`), completely excluded from Git |
| **📥 Offline Export** | One-click export of repeated clusters and revision checklists to clean CSV files. | Native CSV streaming (`pandas` / Streamlit) |
| **🤖 Optional Local AI** | Generates concise topic tags and grounded revision study notes with source traceability. | Local Ollama (`qwen2.5-coder:1.5b-base`) running on `localhost:11434` |

---

## ⚠️ Important Limitations

1. **Text-Based PDFs Only (No Scanned Image OCR in Current MVP):**  
   PaperPilot expects standard digital text-based PDFs (where you can select and copy text). If an uploaded PDF is a scanned photocopy or smartphone camera picture, PaperPilot will detect it and display an informative warning. OCR support is planned for a future release.
2. **AI is 100% Optional:**  
   The entire core pipeline—question extraction, clustering, occurrence counts, revision checklists, and CSV exports—runs **completely offline with zero AI models installed**.
3. **Local AI Hardware:**  
   If you choose to use the optional AI topic labels and revision notes, you need the local [Ollama](https://ollama.com) runtime and approximately 1.5 GB of free system RAM or GPU VRAM for the `qwen2.5-coder:1.5b-base` model.

---

## 💻 Supported Environments

- **Operating Systems:** Windows 10, Windows 11 (64-bit). *(macOS and Linux supported via standard Python commands).*
- **Supported Python Versions:** **Python 3.10, 3.11, 3.12, 3.13, and 3.14** (64-bit).
- **RAM:** 4 GB minimum (8 GB recommended if running local Ollama AI concurrently).

---

## 🚀 Getting Started (Windows)

### Option 1: Automated 2-Click Setup (Recommended for Students)

1. **Download or Clone the Repository:**
   ```bash
   git clone https://github.com/mayukhjyotisarkar/Hacktoberfest.git
   cd Hacktoberfest/WEEK2
   ```
2. **Run the Setup Assistant:**
   Double-click `setup_windows.bat`.
   - Checks that Python 3.10+ is installed and on your system PATH.
   - Automatically creates an isolated virtual environment in `.venv`.
   - Installs all verified dependencies from `requirements.txt`.
   - Generates synthetic sample question papers in `data/` if missing.
3. **Launch PaperPilot:**
   Double-click `run_paperpilot.bat`.
   - Automatically opens your default browser at `http://localhost:8501`.

---

### Option 2: Manual Terminal Setup

```bash
# 1. Navigate to project directory
cd WEEK2

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows Command Prompt:
.venv\Scripts\activate.bat
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Launch dashboard
streamlit run app.py
```

---

## 📖 First-Run Student Tutorial

### Step 1: Upload Your Question Papers
1. In the sidebar, navigate to **📤 Upload & Review**.
2. Drag and drop your exam papers, or test with the two included synthetic papers:
   - `data/sample_os_2022.pdf` (Operating Systems 2022 Exam)
   - `data/sample_os_2023.pdf` (Operating Systems 2023 Exam)
3. Click **🚀 Extract & Store Questions**.
4. Review extracted questions in the table. You can edit text, fix question numbers, or exclude irrelevant instructions.

### Step 2: Explore Repeated Questions
1. In the sidebar, navigate to **🔁 Repeated Questions**.
2. See recurring questions grouped by similarity (e.g., questions asking about *Deadlock Conditions* or *CPU Scheduling*).
3. Inspect each question variant, its source paper, page number, and similarity score against the leader anchor question.

### Step 3: Check Revision Priority & Export
1. In the sidebar, navigate to **📝 Revision Checklist**.
2. Review questions sorted by **Priority Score** (High / Medium / Low).
3. Check off questions as you study them—your checklist progress is saved automatically to the local database.
4. Click **📥 Download Revision Checklist (CSV)** to print or save for offline study.

---

## 🤖 Optional: Setting Up Local AI (Ollama)

If you want AI-generated topic badges (e.g., `🏷️ [Banker's Algorithm]`) and grounded revision notes with source citations:

1. **Install Ollama:**
   Download the installer from [https://ollama.com](https://ollama.com) and install it.
2. **Download the Verified Candidate Model:**
   Open a terminal and run:
   ```bash
   ollama run qwen2.5-coder:1.5b-base
   ```
   *(This downloads a lightweight ~1.2 GB model optimized for code and technical reasoning).*
3. **Use in PaperPilot:**
   - In **🔁 Repeated Questions**, click **🏷️ Generate AI Topic Labels** to label all clusters.
   - Click **📝 Generate Revision Notes** on any cluster card to get a 2-3 bullet study focus grounded strictly in those questions.

> **Zero Cloud Leakage Guarantee:** PaperPilot validates that AI requests strictly target local loopback (`http://localhost:11434`). It explicitly rejects remote IP addresses, external hostnames, embedded credentials, and HTTP redirects.

---

## 🔒 Privacy & Local Data Handling Statement

PaperPilot was designed from day one to guarantee complete student privacy:

- **Local Storage Only:** All extracted questions, papers, and checklists are stored in a local SQLite file (`paperpilot.db`).
- **No Cloud Telemetry:** PaperPilot does not include Google Analytics, Mixpanel, or any tracking SDKs.
- **No Cloud AI APIs:** Unlike web apps that send your notes or PDFs to remote OpenAI or Google servers, PaperPilot only communicates with your own local Ollama instance on `localhost:11434`.
- **Git Safety:** `paperpilot.db`, temporary files, virtual environments, and user-uploaded PDFs are strictly excluded via `.gitignore`.
- **Internet Usage Disclosure:** An internet connection is only needed during initial setup (`pip install` and `ollama pull`). Once installed, the application functions **100% offline**.

---

## 🛠️ Common Errors & Troubleshooting

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| `'python' is not recognized as an internal or external command` | Python was installed without checking "Add python.exe to PATH". | Reinstall Python from [python.org](https://www.python.org/downloads/) and check the box: **"Add python.exe to PATH"**. |
| `⚠️ Scanned PDF Detected` | The PDF contains image scans rather than selectable text. | Use a PDF that has selectable text, or re-export the document from Word / Google Docs as a digital PDF. |
| `Port 8501 is already in use` | Another Streamlit instance or local service is running. | Streamlit will automatically attempt port 8502 or higher. To stop old instances, close their terminal windows. |
| `⚠️ Local Ollama service is not running` | Ollama is not started in the background. | Launch the Ollama application from your Start Menu or system tray. |
| `⚠️ Configured model 'qwen2.5-coder:1.5b-base' is not installed` | The candidate model has not been downloaded yet. | Run `ollama run qwen2.5-coder:1.5b-base` in your terminal once. |

---

## 🧪 Running the Test Suite

PaperPilot maintains a rigorous automated test suite of **151 tests** covering PDF parsing, TF-IDF vectorization, leader clustering, ACID persistence, loopback security, and Streamlit UI flows:

```bash
# Activate your virtual environment first
.venv\Scripts\activate.bat

# Run the complete test suite
python -m pytest tests/ -v
```

---

## 🤝 Student Feedback & Contributing

We are actively validating PaperPilot with real college students!
- **Feedback & Testing Guide:** See [`docs/USER_VALIDATION.md`](docs/USER_VALIDATION.md) for our 5-minute testing protocol and questionnaire.
- **Reporting Bugs:** Please use our [GitHub Issue Template](.github/ISSUE_TEMPLATE/bug_report.md) with details about your OS, Python version, and PDF format.

---

## 🗺️ Roadmap

- [x] Phase 1: PDF extraction, scanned-PDF detection, and question parser.
- [x] Phase 2: Text normalization with CS token protection and TF-IDF similarity.
- [x] Phase 3: Leader clustering preventing chain-merging, frequency analytics, and revision priority.
- [x] Phase 4: Streamlit multi-tab dashboard and SQLite persistence engine.
- [x] Phase 5 (Stages 1–4): Local Ollama benchmarking, loopback client, topic tags, and grounded revision notes.
- [x] Phase 5 (Stage 5): Windows-friendly packaging, 1-click batch scripts, diagnostics, and student validation protocol.
- [ ] Future: Single-file desktop installer (`.exe`) bundling Python for zero-terminal setup.
- [ ] Future: Lightweight local OCR engine for scanned photocopies and handwritten notes.
- [ ] Future: Department-level course syllabus mapping and multi-subject categorization.

---

*PaperPilot is an open-source educational study tool developed under Hacktoberfest.*
