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
| **📄 PDF Extraction** | Hybrid extraction: fast digital text extraction with PyMuPDF, falling back to local Tesseract OCR on scanned/image pages. | PyMuPDF (`pymupdf`) + Local Tesseract OCR (`pytesseract`, `Pillow`) |
| **🔍 Numbered Parser** | Detects question boundaries (`1.`, `2(a)`, `(i)`) while rejecting non-question headers (`Time: 3 Hours`, `Max Marks`). | Custom regex delimiter engine with lookahead & false-positive suppression |
| **🔁 Leader Clustering** | Groups repeated and similar questions across years using cosine similarity without transitive chain-merging. | TF-IDF Vectorizer + Cosine Similarity (`scikit-learn`) + Leader Clustering |
| **📈 Frequency Analytics** | Calculates recurrence counts, distinct paper distributions, and exam year breakdowns. | Tabular aggregation (`pandas`) |
| **📝 Revision Priority** | Scores each recurring question based on occurrence frequency and distinct papers. | Mathematical weighting engine |
| **💾 ACID Persistence** | Stores reviewed questions, exclusions, and papers locally in an ACID SQLite database. | Parameterized SQLite (`paperpilot.db`), completely excluded from Git |
| **📥 Offline Export** | One-click export of repeated clusters and revision checklists to clean CSV files. | Native CSV streaming (`pandas` / Streamlit) |
| **🤖 Optional Local AI** | Generates concise topic tags and grounded revision study notes with source traceability. | Local Ollama (`qwen2.5-coder:1.5b-base`) running on `localhost:11434` |

---

## ⚠️ Important Limitations

1. **Scanned PDFs & OCR Requirements:**  
   Standard digital text PDFs (where text can be highlighted) extract immediately with zero external tools. Scanned photocopies and smartphone camera images require the open-source **Tesseract-OCR** engine installed locally on your Windows machine. If Tesseract is not installed, digital PDFs continue working normally, and PaperPilot will display clear installation guidance.
2. **AI is 100% Optional:**  
   The entire core pipeline—question extraction, clustering, occurrence counts, revision checklists, and CSV exports—runs **completely offline with zero AI models installed**.
3. **Local AI Hardware:**  
   If you choose to use the optional AI topic labels and revision notes, you need the local [Ollama](https://ollama.com) runtime and approximately 1.5 GB of free system RAM or GPU VRAM for the `qwen2.5-coder:1.5b-base` model.
4. **Scanned Math & Diagram Limitations:**  
   OCR on low-resolution scans, handwritten text, complex mathematical matrices, or circuit diagrams may require manual corrections using the built-in Question Review drawer in Step 1.

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

## 🔍 Local OCR Setup (Tesseract for Scanned PDFs)

PaperPilot uses **hybrid PDF extraction**:
1. It reads each page with PyMuPDF. If selectable digital text is found, it extracts it instantly.
2. If a page is a scanned photo, photocopy, or image-only page, PaperPilot automatically renders the page at 300 DPI and invokes the local **Tesseract-OCR** engine.
3. In mixed PDFs (where some pages are typed and others are scanned), each page is handled appropriately without losing metadata or page numbers.

### Windows Installation Steps:
1. **Download Tesseract Installer:**  
   Download the latest 64-bit Windows installer from the official UB Mannheim build:  
   👉 [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)  
   *(e.g. `tesseract-ocr-w64-setup-5.4.0.xxxx.exe`)*
2. **Run Installer:**  
   Install to the standard default path: `C:\Program Files\Tesseract-OCR`.  
   PaperPilot auto-detects this path as well as `%LOCALAPPDATA%\Programs\Tesseract-OCR`.
3. **Optional Custom Path:**  
   If installed in a custom location, set the `TESSERACT_CMD` environment variable:
   ```cmd
   set TESSERACT_CMD=D:\Custom\Tesseract-OCR\tesseract.exe
   ```
4. **Language Packs:**  
   English (`eng`) is included by default. Additional language packs (`.traineddata` files) can be selected during installation or copied to `C:\Program Files\Tesseract-OCR\tessdata\`.
5. **Local Privacy:**  
   All OCR rendering and processing happen **100% locally on your PC**. No images or text are ever transmitted to the cloud.

---

## 🔒 Privacy & Local Data Handling Statement

PaperPilot was designed from day one to guarantee complete student privacy:

- **Local Storage Only:** All extracted questions, papers, and checklists are stored in a local SQLite file (`paperpilot.db`).
- **No Cloud Telemetry:** PaperPilot does not include Google Analytics, Mixpanel, or any tracking SDKs.
- **No Cloud AI APIs:** Unlike web apps that send your notes or PDFs to remote OpenAI or Google servers, PaperPilot only communicates with your own local Ollama instance on `localhost:11434`.
- **Local OCR:** PDF image rendering and OCR character recognition run strictly on local CPU without internet access.
- **Git Safety:** `paperpilot.db`, temporary files, virtual environments, and user-uploaded PDFs are strictly excluded via `.gitignore`.
- **Internet Usage Disclosure:** An internet connection is only needed during initial setup (`pip install` and `ollama pull`). Once installed, the application functions **100% offline**.

---

## 🛠️ Common Errors & Troubleshooting

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| `'python' is not recognized as an internal or external command` | Python was installed without checking "Add python.exe to PATH". | Reinstall Python from [python.org](https://www.python.org/downloads/) and check the box: **"Add python.exe to PATH"**. |
| `⚠️ Scanned PDF Detected (Tesseract not installed)` | The PDF contains image scans, and Tesseract-OCR is missing. | Install Tesseract-OCR from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Text-based PDFs continue to work without OCR. |
| `Port 8501 is already in use` | Another Streamlit instance or local service is running. | Streamlit will automatically attempt port 8502 or higher. To stop old instances, close their terminal windows. |
| `⚠️ Local Ollama service is not running` | Ollama is not started in the background. | Launch the Ollama application from your Start Menu or system tray. |
| `⚠️ Configured model 'qwen2.5-coder:1.5b-base' is not installed` | The candidate model has not been downloaded yet. | Run `ollama run qwen2.5-coder:1.5b-base` in your terminal once. |

---

## 🧪 Running the Test Suite

PaperPilot maintains a rigorous automated test suite of **165 tests** covering hybrid PDF extraction, local OCR, TF-IDF vectorization, leader clustering, ACID persistence, loopback security, and Streamlit UI flows:

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
- [x] Phase 5 (Stage 6): Student-friendly 3-step UI/UX redesign and 1-click sample paper onboarding.
- [x] Phase 5 (Stage 7): Hybrid PDF extraction with local Tesseract-OCR for scanned and mixed exam papers.
- [ ] Future: Single-file desktop installer (`.exe`) bundling Python for zero-terminal setup.
- [ ] Future: Department-level course syllabus mapping and multi-subject categorization.

---

*PaperPilot is an open-source educational study tool developed under Hacktoberfest.*
