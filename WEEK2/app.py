"""
app.py - Student-Friendly Streamlit Web Interface for PaperPilot.

Local-first, privacy-focused Previous Year Question Paper (PYQ) analyzer.
Redesigned around a guided 3-step student study workflow:
  1. Upload Papers (with 1-click sample paper onboarding)
  2. Find Important Questions (readable recurrence cards & optional local AI)
  3. My Revision Plan (priority-ranked study checklist & offline CSV export)
"""

import os
from pathlib import Path
import re
from typing import List, Optional
import pandas as pd
import streamlit as st

from paperpilot.pdf_extractor import extract_text_from_pdf, PDFExtractionError
from paperpilot.ocr import (
    is_tesseract_available,
    get_tesseract_cmd,
    get_tesseract_version,
    INSTALL_GUIDANCE_MESSAGE,
)
from paperpilot.ocr_setup import run_ocr_setup, OCRSetupResult
from paperpilot.question_parser import parse_questions, QuestionItem
from paperpilot.similarity import cluster_questions, SimilarityAnalysisResult
from paperpilot.analytics import (
    get_papers_summary_df,
    get_all_questions_df,
    get_repeated_clusters_df,
    get_revision_checklist_df,
    calculate_dataset_metrics,
)
from paperpilot.storage import PaperPilotStorage, StorageError
from paperpilot.local_ai import LocalAIClient, AIErrorKind
from paperpilot.topic_labeler import (
    ClusterTopicLabeler,
    get_topic_label_cache,
    compute_cluster_cache_key,
    PROMPT_VERSION,
)
from paperpilot.revision_notes import (
    ClusterRevisionNotesGenerator,
    get_revision_notes_cache,
    compute_revision_notes_cache_key,
    REVISION_PROMPT_VERSION,
)

# Set Streamlit page layout and title
st.set_page_config(
    page_title="PaperPilot — Exam Revision Assistant",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom styling for a clean, accessible, modern educational-product aesthetic
st.markdown(
    """
    <style>
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .hero-banner {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
    }
    .hero-banner h2 {
        color: white !important;
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
    }
    .hero-banner p {
        color: #e0e7ff !important;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }
    .step-card {
        background-color: #f8f9fa;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .metric-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-exact { background-color: #dcfce7; color: #166534; }
    .badge-similar { background-color: #fef3c7; color: #92400e; }
    .badge-high { background-color: #fee2e2; color: #991b1b; }
    .badge-medium { background-color: #fef3c7; color: #92400e; }
    .badge-standard { background-color: #f1f5f9; color: #334155; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize SQLite Storage
DB_PATH = Path(os.environ.get("PAPERPILOT_DB_PATH", str(Path(__file__).resolve().parent / "paperpilot.db")))


@st.cache_resource
def get_storage(db_path_str: str) -> PaperPilotStorage:
    """Returns a singleton instance of PaperPilotStorage for the given path."""
    return PaperPilotStorage(db_path=Path(db_path_str))


storage = get_storage(str(DB_PATH))

# Initialize session state keys
if "similarity_threshold" not in st.session_state:
    st.session_state["similarity_threshold"] = 0.65

if "analysis_cache" not in st.session_state:
    st.session_state["analysis_cache"] = None

if "cache_dirty" not in st.session_state:
    st.session_state["cache_dirty"] = True

if "review_file_filter" not in st.session_state:
    st.session_state["review_file_filter"] = "All Papers"

if "ai_cluster_labels" not in st.session_state:
    st.session_state["ai_cluster_labels"] = {}

if "ai_cluster_errors" not in st.session_state:
    st.session_state["ai_cluster_errors"] = {}

if "ai_cluster_revision_notes" not in st.session_state:
    st.session_state["ai_cluster_revision_notes"] = {}

if "ai_cluster_revision_errors" not in st.session_state:
    st.session_state["ai_cluster_revision_errors"] = {}


def get_current_analysis(force_recompute: bool = False) -> SimilarityAnalysisResult:
    """
    Computes or retrieves cached similarity clusters from active reviewed questions.
    Recomputes automatically when threshold changes or when questions are modified.
    """
    cached_threshold = st.session_state.get("cached_threshold")
    threshold = st.session_state["similarity_threshold"]

    if (
        st.session_state["analysis_cache"] is None
        or st.session_state["cache_dirty"]
        or cached_threshold != threshold
        or force_recompute
    ):
        active_questions = storage.get_questions(include_excluded=False)
        result = cluster_questions(active_questions, similarity_threshold=threshold)
        st.session_state["analysis_cache"] = result
        st.session_state["cached_threshold"] = threshold
        st.session_state["cache_dirty"] = False
        return result

    return st.session_state["analysis_cache"]


def mark_data_dirty() -> None:
    """Flags that underlying questions or settings have changed and need re-analysis."""
    st.session_state["cache_dirty"] = True
    if "ai_cluster_labels" in st.session_state:
        st.session_state["ai_cluster_labels"] = {}
    if "ai_cluster_errors" in st.session_state:
        st.session_state["ai_cluster_errors"] = {}
    if "ai_cluster_revision_notes" in st.session_state:
        st.session_state["ai_cluster_revision_notes"] = {}
    if "ai_cluster_revision_errors" in st.session_state:
        st.session_state["ai_cluster_revision_errors"] = {}
    get_topic_label_cache().clear()
    get_revision_notes_cache().clear()


# =============================================================================
# SIDEBAR NAVIGATION & CONTROLS
# =============================================================================

st.sidebar.markdown("## ✈️ PaperPilot")
st.sidebar.caption("Student Exam Revision Assistant")
st.sidebar.markdown("---")

NAV_OPTIONS = [
    "1. 📤 Upload Papers",
    "2. 🎯 Find Important Questions",
    "3. 📝 My Revision Plan",
    "4. 📊 Question Bank & Analytics",
    "5. ⚙️ Settings & Privacy",
]

if "nav_choice" not in st.session_state or st.session_state["nav_choice"] not in NAV_OPTIONS:
    st.session_state["nav_choice"] = NAV_OPTIONS[0]


def on_nav_change():
    st.session_state["nav_choice"] = st.session_state["sidebar_nav"]


nav_choice = st.sidebar.radio(
    "Navigation Steps",
    options=NAV_OPTIONS,
    index=NAV_OPTIONS.index(st.session_state["nav_choice"]),
    key="sidebar_nav",
    on_change=on_nav_change,
)

st.sidebar.markdown("---")

# Quick database summary in sidebar
db_stats = storage.get_stats()
st.sidebar.markdown(f"**Stored Papers:** `{db_stats['total_papers']}`")
st.sidebar.markdown(f"**Active Questions:** `{db_stats['active_questions']}`")
if db_stats["excluded_questions"] > 0:
    st.sidebar.caption(f"ℹ️ Excluded from analysis: {db_stats['excluded_questions']}")

st.sidebar.markdown("---")
st.sidebar.markdown("🔒 **100% Offline & Private**")
st.sidebar.caption("All PDFs, questions, and similarity computations run locally. No cloud APIs or tracking.")


# =============================================================================
# TOP HEADER & GUIDED 3-STEP PROGRESS BAR
# =============================================================================

all_active_questions = storage.get_questions(include_excluded=False)
stored_papers = storage.get_papers()
total_q_count = len(all_active_questions)
total_papers_count = len(stored_papers)

current_analysis = get_current_analysis()
repeated_cluster_count = len(current_analysis.repeated_clusters)

# Persistent Hero Banner
st.markdown(
    """
    <div class="hero-banner">
        <h2>✈️ PaperPilot</h2>
        <p>Turn previous year university question papers into a focused, priority-ranked exam revision plan.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Guided Step Progress Indicator
c_s1, c_s2, c_s3 = st.columns(3)
with c_s1:
    s1_badge = "✅" if total_q_count > 0 else "1️⃣"
    s1_sub = f"{total_papers_count} Papers ({total_q_count} Questions)" if total_q_count > 0 else "Upload PDF question papers"
    st.markdown(f"**{s1_badge} Step 1: Upload Papers**")
    st.caption(s1_sub)

with c_s2:
    s2_badge = "✅" if repeated_cluster_count > 0 else ("2️⃣" if total_q_count > 0 else "⚪")
    s2_sub = f"{repeated_cluster_count} Recurring Question Groups" if repeated_cluster_count > 0 else ("No repeats at current threshold" if total_q_count > 0 else "Discover recurring topics")
    st.markdown(f"**{s2_badge} Step 2: Important Questions**")
    st.caption(s2_sub)

with c_s3:
    s3_badge = "3️⃣" if total_q_count > 0 else "⚪"
    s3_sub = "Priority-ranked study plan" if total_q_count > 0 else "Generate study checklist"
    st.markdown(f"**{s3_badge} Step 3: My Revision Plan**")
    st.caption(s3_sub)

st.markdown("---")


# =============================================================================
# STEP 1: UPLOAD PAPERS & ONBOARDING
# =============================================================================
if nav_choice == "1. 📤 Upload Papers":
    st.title("📤 Step 1: Upload Question Papers")
    st.write(
        "Upload your past university question papers in text-based PDF format. "
        "PaperPilot will automatically extract individual questions while preserving numbers, marks, and examination years."
    )

    # High-level Metrics (Visible whenever papers are loaded)
    if total_q_count > 0:
        metrics = calculate_dataset_metrics(current_analysis, all_active_questions)
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Exam Papers", total_papers_count)
        col_m2.metric("Questions Extracted", total_q_count)
        col_m3.metric("Repeated Question Groups", repeated_cluster_count)
        col_m4.metric("Repetition Rate", f"{metrics['repetition_rate_pct']}%")

        col_next, _ = st.columns([1, 2])
        with col_next:
            if st.button("Proceed to Step 2: Find Important Questions ➔", type="primary", key="btn_to_step2_top"):
                st.session_state["nav_choice"] = "2. 🎯 Find Important Questions"
                st.rerun()
        st.markdown("---")

    # Welcome state for first-time students (Zero papers uploaded)
    if total_q_count == 0:
        st.info("👋 **Welcome to PaperPilot!** You have not uploaded any exam papers yet. Choose an option below to get started:")

        col_opt_upload, col_opt_sample = st.columns(2)
        with col_opt_upload:
            st.markdown("### 📥 Option A: Upload Your Own Papers")
            st.write("Drag and drop PDF examination papers from your university using the upload box below.")

        with col_opt_sample:
            st.markdown("### 🧪 Option B: Instant Sample Test")
            st.write("No PDFs handy? Try PaperPilot right now using 2 included Operating Systems papers (2022 & 2023).")
            if st.button("🚀 Load Sample Papers (2022 & 2023 OS)", type="secondary", key="btn_load_samples"):
                p22 = Path(__file__).resolve().parent / "data" / "sample_os_2022.pdf"
                p23 = Path(__file__).resolve().parent / "data" / "sample_os_2023.pdf"
                if not p22.exists() or not p23.exists():
                    from data.generate_samples import create_os_2022_pdf, create_os_2023_pdf
                    create_os_2022_pdf()
                    create_os_2023_pdf()

                doc22 = extract_text_from_pdf(p22.read_bytes(), filename="sample_os_2022.pdf", subject="Operating Systems", year=2022)
                doc23 = extract_text_from_pdf(p23.read_bytes(), filename="sample_os_2023.pdf", subject="Operating Systems", year=2023)
                q22 = parse_questions(doc22)
                q23 = parse_questions(doc23)

                storage.save_paper("sample_os_2022.pdf", "Operating Systems", 2022, q22.questions, overwrite=True)
                storage.save_paper("sample_os_2023.pdf", "Operating Systems", 2023, q23.questions, overwrite=True)
                mark_data_dirty()
                st.success("✅ Successfully loaded sample papers (Operating Systems 2022 & 2023) with 14 questions!")
                st.rerun()

        st.markdown("---")

    # Upload Container
    st.subheader("Add Question Papers")
    col_u1, col_u2 = st.columns([1, 1])
    with col_u1:
        default_subject = st.text_input("Course / Subject Name", value="Operating Systems", help="e.g. Operating Systems, Data Structures, Computer Networks")
    with col_u2:
        year_input = st.text_input("Default Exam Year (Optional)", placeholder="e.g. 2023", help="Auto-detected from filename if omitted")
        default_year: Optional[int] = None
        if year_input.strip():
            try:
                default_year = int(year_input.strip())
            except ValueError:
                st.warning("Year must be a valid 4-digit number (e.g. 2023).")

    uploaded_files = st.file_uploader(
        "Select Text-based PDF Question Papers",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload PDF question papers. Note: scanned image PDFs require OCR which is outside this MVP.",
    )

    col_chk, col_btn = st.columns([2, 1])
    with col_chk:
        overwrite_existing = st.checkbox(
            "Overwrite paper if already uploaded with the same filename",
            value=True,
            help="If checked, re-uploading a file replaces its questions with the freshly extracted set.",
        )
    with col_btn:
        extract_clicked = st.button("🚀 Extract & Store Questions", type="primary")

    if uploaded_files and extract_clicked:
        total_extracted = 0
        papers_processed = 0

        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            filename = uploaded_file.name

            paper_year = default_year
            if paper_year is None:
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", filename)
                if year_match:
                    paper_year = int(year_match.group(0))

            try:
                extracted_doc = extract_text_from_pdf(
                    file_bytes,
                    filename=filename,
                    subject=default_subject,
                    year=paper_year,
                )

                # Check if document yielded zero usable text (e.g. blank scan or missing Tesseract)
                if extracted_doc.total_chars == 0:
                    if not is_tesseract_available():
                        st.warning(
                            f"⚠️ **Scanned PDF Detected in `{filename}`!**\n\n"
                            f"This document contains image-only pages and requires Optical Character Recognition (OCR), "
                            f"but Tesseract-OCR is not installed or detected on this machine.\n\n"
                            f"Text-based PDFs work immediately. To enable scanned PDF support, set up local OCR below."
                        )
                        col_auto, col_man = st.columns([1, 1])
                        with col_auto:
                            if st.button("⚡ Set Up OCR Automatically", type="primary", key=f"auto_ocr_btn_{filename}"):
                                with st.status("Setting up local OCR engine...", expanded=True) as status:
                                    def ui_progress(msg: str, pct: float):
                                        st.write(f"• {msg}")
                                    res = run_ocr_setup(progress_callback=ui_progress)
                                    if res.success:
                                        if res.status == "installed_successfully":
                                            status.update(label="✅ Tesseract-OCR installed successfully!", state="complete", expanded=False)
                                            st.success(res.message)
                                            st.rerun()
                                        elif res.status == "installer_launched":
                                            status.update(label="ℹ️ Installer launched — setup wizard open", state="complete", expanded=True)
                                            st.info(res.message)
                                        else:
                                            status.update(label="✅ Tesseract-OCR is ready!", state="complete", expanded=False)
                                            st.success(res.message)
                                            st.rerun()
                                    else:
                                        status.update(label="❌ OCR Setup Failed", state="error", expanded=True)
                                        st.error(res.message)
                        with col_man:
                            with st.expander("📥 Manual Installation Instructions", expanded=False):
                                st.markdown(INSTALL_GUIDANCE_MESSAGE)
                    else:
                        st.warning(
                            f"⚠️ No usable question text could be extracted from `{filename}`. "
                            f"The document may be blank, corrupted, or have low image resolution."
                        )
                    continue

                parse_res = parse_questions(extracted_doc)

                saved = storage.save_paper(
                    filename=filename,
                    subject=default_subject,
                    year=paper_year,
                    questions=parse_res.questions,
                    overwrite=overwrite_existing,
                )

                if saved:
                    # Provide informative success feedback with OCR badges if applicable
                    doc_type = "Digital Text"
                    if extracted_doc.ocr_page_count > 0 and (extracted_doc.total_pages - extracted_doc.ocr_page_count) > 0:
                        doc_type = f"Mixed ({extracted_doc.total_pages - extracted_doc.ocr_page_count} Digital + {extracted_doc.ocr_page_count} Scanned OCR)"
                    elif extracted_doc.ocr_page_count > 0:
                        doc_type = f"Scanned ({extracted_doc.ocr_page_count} OCR Pages)"

                    st.success(
                        f"✅ Successfully processed `{filename}` [{doc_type}]: "
                        f"**{len(parse_res.questions)}** questions extracted "
                        f"(Year: {paper_year if paper_year else 'Unknown'})."
                    )

                    if extracted_doc.ocr_page_count > 0 and extracted_doc.avg_ocr_confidence:
                        st.caption(
                            f"🔍 OCR Scan Clarity: **~{int(extracted_doc.avg_ocr_confidence)}%**. "
                            f"*Note: OCR confidence reflects scan clarity, not question accuracy. You can review and edit text in the drawer below.*"
                        )

                    total_extracted += len(parse_res.questions)
                    papers_processed += 1
                else:
                    st.info(f"Skipped `{filename}` because it already exists and overwrite was unchecked.")

                # If there were unreadable pages or warnings, report them
                if extracted_doc.failed_page_count > 0 or extracted_doc.ocr_warnings:
                    with st.expander(f"⚠️ Page Extraction Warnings for `{filename}` ({len(extracted_doc.ocr_warnings)})", expanded=False):
                        for warn in extracted_doc.ocr_warnings:
                            st.caption(f"• {warn}")

                if parse_res.unparsed_segments:
                    with st.expander(f"ℹ️ Unparsed Headers/Instructions in `{filename}` ({len(parse_res.unparsed_segments)})", expanded=False):
                        for seg in parse_res.unparsed_segments[:5]:
                            st.caption(f"• {seg}")

            except PDFExtractionError as e:
                st.error(f"Failed to read `{filename}`: {e}")
            except StorageError as e:
                st.error(f"Database error while saving `{filename}`: {e}")

        if papers_processed > 0:
            mark_data_dirty()
            st.rerun()

    # Expandable Review Drawer (Keep review accessible without cluttering)
    if total_q_count > 0:
        st.markdown("---")
        with st.expander(f"📑 Review & Edit Extracted Questions ({total_q_count} Total)", expanded=False):
            st.write("Review, edit question text, fix marks, or exclude instructions from similarity clustering.")
            all_raw_questions = storage.get_questions(include_excluded=True)

            paper_options = ["All Papers"] + [p["filename"] for p in storage.get_papers()]
            selected_paper = st.selectbox("Filter by Question Paper", options=paper_options, key="select_review_paper")

            filtered_for_review = [
                q for q in all_raw_questions
                if selected_paper == "All Papers" or q.source_file == selected_paper
            ]

            st.caption(f"Showing {len(filtered_for_review)} questions for `{selected_paper}`")

            active_q_ids = {q.id for q in all_active_questions}
            # Display table
            review_table_data = []
            for q in filtered_for_review:
                review_table_data.append({
                    "ID": q.id,
                    "Paper": q.source_file,
                    "Page": q.source_page,
                    "Q#": q.question_number,
                    "Question Text": q.text,
                    "Year": q.year if q.year is not None else "N/A",
                    "Marks": q.marks or "N/A",
                    "Status": "❌ Excluded" if q.id not in active_q_ids else "✅ Active",
                })
            st.dataframe(pd.DataFrame(review_table_data), use_container_width=True, hide_index=True)

            # Edit Single Question Sub-form
            st.markdown("#### ✏️ Edit or Exclude a Question")
            q_ids = [q.id for q in filtered_for_review]
            if q_ids:
                selected_qid = st.selectbox("Select Question to Edit", options=q_ids, format_func=lambda x: f"[{x}] {next(q.text[:60] for q in filtered_for_review if q.id == x)}...")
                target_q = next(q for q in filtered_for_review if q.id == selected_qid)

                col_e1, col_e2 = st.columns([3, 1])
                with col_e1:
                    updated_text = st.text_area("Question Text", value=target_q.text, height=80)
                with col_e2:
                    updated_qnum = st.text_input("Question Number", value=target_q.question_number)
                    updated_marks = st.text_input("Marks", value=target_q.marks or "")
                    updated_excluded = st.checkbox("Exclude from Analysis", value=(target_q.id not in active_q_ids))

                if st.button("💾 Save Question Edits"):
                    storage.update_question(
                        question_id=target_q.id,
                        text=updated_text,
                        question_number=updated_qnum,
                        marks=updated_marks,
                        is_excluded=updated_excluded,
                    )
                    mark_data_dirty()
                    st.success("Question updated successfully!")
                    st.rerun()

            # Delete entire paper option
            if selected_paper != "All Papers":
                st.markdown("---")
                if st.button(f"🗑️ Delete `{selected_paper}` and its questions", type="secondary"):
                    storage.delete_paper(selected_paper)
                    mark_data_dirty()
                    st.success(f"Deleted `{selected_paper}` from database.")
                    st.rerun()

        # Bottom Call-To-Action
        col_next_bot, _ = st.columns([1, 2])
        with col_next_bot:
            if st.button("Proceed to Step 2: Find Important Questions ➔", type="primary", key="btn_to_step2_bot"):
                st.session_state["nav_choice"] = "2. 🎯 Find Important Questions"
                st.rerun()


# =============================================================================
# STEP 2: FIND IMPORTANT QUESTIONS
# =============================================================================
elif nav_choice == "2. 🎯 Find Important Questions":
    st.title("🎯 Step 2: Important & Recurring Questions")
    st.write(
        "These questions appeared across multiple examination papers or years. "
        "Questions asking about the same core concepts are grouped together so you can focus on high-yield exam topics."
    )

    if total_q_count == 0:
        st.warning("⚠️ No questions found. Please complete **Step 1: Upload Papers** first.")
        if st.button("Go to Step 1: Upload Papers ➔", type="primary"):
            st.session_state["nav_choice"] = "1. 📤 Upload Papers"
            st.rerun()
    else:
        current_threshold = st.session_state["similarity_threshold"]
        analysis = get_current_analysis()

        # Student-Friendly Summary Bar
        col_sm1, col_sm2, col_sm3 = st.columns(3)
        col_sm1.metric("Recurring Question Groups", len(analysis.repeated_clusters))
        col_sm2.metric("Past Papers Analyzed", total_papers_count)
        rep_rate = round((sum(c.occurrence_count for c in analysis.repeated_clusters) / total_q_count * 100), 1) if total_q_count > 0 else 0.0
        col_sm3.metric("Repetition Rate", f"{rep_rate}%")

        st.markdown("---")

        if not analysis.repeated_clusters:
            st.info(
                f"ℹ️ **No recurring questions found at similarity threshold `{current_threshold:.2f}`.**\n\n"
                f"Try slightly lowering the threshold slider in **Settings & Privacy** (e.g. to `0.55`) to cluster broader topic variants."
            )
        else:
            # AI Topic Labeling Controls
            col_ai_btn, col_ai_info = st.columns([1, 2])
            with col_ai_btn:
                gen_ai_clicked = st.button("🏷️ Label All Topics with Local AI", help="Uses local Ollama (qwen2.5-coder:1.5b-base) to generate concise topic tags")
            with col_ai_info:
                has_ai_labels = bool(st.session_state.get("ai_cluster_labels"))
                if has_ai_labels:
                    st.caption("✅ AI topic labels loaded in memory.")
                else:
                    st.caption("ℹ️ Optional: Click to label clusters with local AI (requires Ollama).")

            if gen_ai_clicked:
                ai_client = LocalAIClient()
                if not ai_client.check_health():
                    st.warning("⚠️ Local Ollama service is not running or unreachable at http://localhost:11434. Existing questions and analysis remain fully functional.")
                elif not ai_client.is_model_available():
                    st.warning(f"⚠️ Configured model '{ai_client.default_model}' is not installed in local Ollama. Existing questions and analysis remain fully functional.")
                else:
                    labeler = ClusterTopicLabeler(ai_client=ai_client)
                    labeled_count = 0
                    error_count = 0
                    for cluster in analysis.repeated_clusters:
                        label, err = labeler.label_cluster(cluster)
                        if label:
                            st.session_state["ai_cluster_labels"][cluster.cluster_id] = label
                            labeled_count += 1
                        elif err:
                            st.session_state["ai_cluster_errors"][cluster.cluster_id] = err.message
                            error_count += 1
                    if labeled_count > 0:
                        st.success(f"Generated AI topic labels for {labeled_count} repeated question groups!")
                    elif error_count > 0:
                        st.warning("AI labeling encountered errors. Existing clusters remain unchanged.")
                    st.rerun()

            # Render Question Cards
            for idx, cluster in enumerate(analysis.repeated_clusters, 1):
                years_badge = ", ".join(str(y) for y in cluster.years) if cluster.years else "N/A"
                match_badge = "Exact Match" if cluster.is_exact else f"Similar (~{int(cluster.avg_similarity * 100)}%)"

                ai_label = st.session_state.get("ai_cluster_labels", {}).get(cluster.cluster_id)
                if ai_label:
                    cluster_sub = cluster.questions[0].subject if cluster.questions else "Computer Science"
                    member_texts = [q.text for q in cluster.questions if q.text.strip() != cluster.representative_text.strip()]
                    expected_key = compute_cluster_cache_key(
                        model_name=ai_label.model,
                        prompt_version=PROMPT_VERSION,
                        subject=cluster_sub,
                        representative_text=cluster.representative_text,
                        member_texts=member_texts,
                    )
                    if ai_label.cache_key != expected_key:
                        ai_label = None

                title_prefix = f"🏷️ [{ai_label.topic}] " if ai_label else ""

                with st.expander(
                    f"📌 #{idx}: {title_prefix}\"{cluster.representative_text[:70]}...\" "
                    f"({cluster.paper_count} Papers, {cluster.occurrence_count} Times Asked)",
                    expanded=True,
                ):
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    col_m1.metric("Distinct Papers", cluster.paper_count)
                    col_m2.metric("Total Occurrences", cluster.occurrence_count)
                    col_m3.metric("Match Type", match_badge)
                    col_m4.metric("Exam Years", years_badge)

                    # Display AI Topic Badge if generated
                    if ai_label:
                        conf_icon = "🟢" if ai_label.confidence == "high" else ("🟡" if ai_label.confidence == "medium" else "⚪")
                        st.markdown(
                            f"**🏷️ AI Suggested Topic:** `{ai_label.topic}` "
                            f"({conf_icon} Confidence: *{ai_label.confidence.capitalize()}*)"
                        )
                        if ai_label.reasoning:
                            st.caption(
                                f"💡 *Reasoning:* {ai_label.reasoning} | "
                                f"Latency: `{ai_label.latency_ms:.0f} ms` | Model: `{ai_label.model}`"
                            )
                        st.markdown("---")
                    elif cluster.cluster_id in st.session_state.get("ai_cluster_errors", {}):
                        err_text = st.session_state["ai_cluster_errors"][cluster.cluster_id]
                        st.caption(f"⚠️ *AI Topic Label unavailable: {err_text}*")
                        st.markdown("---")

                    # Grounded AI Revision Notes Section
                    rev_notes = st.session_state.get("ai_cluster_revision_notes", {}).get(cluster.cluster_id)
                    if rev_notes:
                        cluster_sub = cluster.questions[0].subject if cluster.questions else "Computer Science"
                        member_texts = [q.text for q in cluster.questions if q.text.strip() != cluster.representative_text.strip()]
                        expected_rev_key = compute_revision_notes_cache_key(
                            model_name=rev_notes.model,
                            prompt_version=REVISION_PROMPT_VERSION,
                            subject=cluster_sub,
                            representative_text=cluster.representative_text,
                            member_texts=member_texts,
                        )
                        if rev_notes.cache_key != expected_rev_key:
                            rev_notes = None

                    col_rev_btn, col_rev_info = st.columns([1, 2])
                    with col_rev_btn:
                        btn_rev_label = "🔄 Refresh Revision Notes" if rev_notes else "📝 Generate Revision Notes"
                        rev_btn_clicked = st.button(
                            btn_rev_label,
                            key=f"btn_rev_{cluster.cluster_id}",
                            help="Generates grounded revision notes based strictly on this cluster's questions using local Ollama",
                        )

                    if rev_btn_clicked:
                        ai_client = LocalAIClient()
                        if not ai_client.check_health():
                            st.warning("⚠️ Local Ollama service is not running or unreachable at http://localhost:11434. Existing questions and analysis remain fully functional.")
                        elif not ai_client.is_model_available():
                            st.warning(f"⚠️ Configured model '{ai_client.default_model}' is not installed in local Ollama. Existing questions and analysis remain fully functional.")
                        else:
                            rev_gen = ClusterRevisionNotesGenerator(ai_client=ai_client)
                            notes_res, notes_err = rev_gen.generate_notes_for_cluster(cluster, force_refresh=(rev_notes is not None))
                            if notes_res:
                                st.session_state["ai_cluster_revision_notes"][cluster.cluster_id] = notes_res
                                st.session_state["ai_cluster_revision_errors"].pop(cluster.cluster_id, None)
                                st.success(f"Generated grounded revision notes for [{cluster.cluster_id.upper()}]!")
                            elif notes_err:
                                st.session_state["ai_cluster_revision_errors"][cluster.cluster_id] = notes_err.message
                                st.warning(f"Revision notes generation failed: {notes_err.message}")
                            st.rerun()

                    if rev_notes:
                        conf_badge = "🟢 High Confidence" if rev_notes.confidence == "high" else ("🟡 Medium Confidence" if rev_notes.confidence == "medium" else "⚪ Uncertain Scope")
                        st.markdown(f"**📝 AI Revision Notes** `({conf_badge})`")
                        st.caption("ℹ️ *AI-generated revision assistance grounded strictly in the questions below. Not verified ground truth.*")

                        st.markdown(f"**🎯 Revision Focus:** {rev_notes.focus}")

                        st.markdown("**📌 Key Revision Points:**")
                        for b in rev_notes.revision_bullets:
                            st.markdown(f"- {b}")

                        st.markdown(f"**🏷️ Key Concepts:** " + " • ".join(f"`{c}`" for c in rev_notes.key_concepts))

                        with st.expander(f"📚 Grounded Source Questions ({len(rev_notes.sources)} Evidence Items)", expanded=False):
                            for src in rev_notes.sources:
                                yr_str = f"Year: {src.year}" if src.year is not None else "Year: N/A"
                                mk_str = f"Marks: {src.marks}" if src.marks is not None else "Marks: N/A"
                                lead_tag = "👑 [Leader Anchor]" if src.is_leader else f"Similarity: {src.similarity_to_representative:.3f}"
                                st.markdown(
                                    f"- **{src.source_file}** (Page {src.source_page}, {src.question_number}, {yr_str}, {mk_str}) — `{lead_tag}`\n"
                                    f"  > *\"{src.text}\"*"
                                )

                        if rev_notes.reasoning:
                            st.caption(f"💡 *Scope Rationale:* {rev_notes.reasoning} | Latency: `{rev_notes.latency_ms:.0f} ms` | Model: `{rev_notes.model}`")
                        st.markdown("---")
                    elif cluster.cluster_id in st.session_state.get("ai_cluster_revision_errors", {}):
                        rev_err_msg = st.session_state["ai_cluster_revision_errors"][cluster.cluster_id]
                        st.caption(f"⚠️ *Revision notes unavailable: {rev_err_msg}*")
                        st.markdown("---")

                    st.markdown("**Representative Question:**")
                    st.info(f"**\"{cluster.representative_text}\"**")

                    # Source questions list
                    with st.expander(f"📚 Where did this question appear? ({len(cluster.questions)} occurrences across {cluster.paper_count} papers)", expanded=True):
                        for member in cluster.questions:
                            sim_score = cluster.similarity_to_representative.get(member.id, 1.0)
                            is_leader = (member.id == cluster.representative_id)
                            tag = "👑 [Leader Anchor]" if is_leader else f"Match: ~{int(sim_score * 100)}%"

                            st.markdown(
                                f"- **{member.source_file}** (Page {member.source_page}, Q{member.question_number}, "
                                f"Year {member.year if member.year else 'N/A'}) — `{tag}`\n"
                                f"  > *\"{member.text}\"*"
                            )

                    # Optional technical details expander
                    with st.expander("🔬 Technical Similarity Details", expanded=False):
                        st.caption(f"Cluster Identifier: `{cluster.cluster_id}`")
                        st.caption(f"Average Group Similarity: `{cluster.avg_similarity:.3f}`")
                        st.caption("Individual Cosine Similarity to Representative Leader:")
                        for qid, score in cluster.similarity_to_representative.items():
                            st.caption(f"• Question ID `{qid}`: `{score:.3f}`")

            # Export Button
            rep_df = get_repeated_clusters_df(analysis)
            st.markdown("---")
            csv_rep = rep_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Repeated Questions Analysis (CSV)",
                data=csv_rep,
                file_name="paperpilot_repeated_questions.csv",
                mime="text/csv",
                key="btn_download_repeated_csv",
            )

        # Call-To-Action to Step 3
        st.markdown("---")
        col_next_step3, _ = st.columns([1, 2])
        with col_next_step3:
            if st.button("Proceed to Step 3: My Revision Plan ➔", type="primary", key="btn_to_step3"):
                st.session_state["nav_choice"] = "3. 📝 My Revision Plan"
                st.rerun()


# =============================================================================
# STEP 3: MY REVISION PLAN
# =============================================================================
elif nav_choice == "3. 📝 My Revision Plan":
    st.title("📝 Step 3: My Revision Plan")
    st.write(
        "Questions ranked by exam recurrence so you know what to revise first. "
        "Questions asked in multiple years are prioritized as **High Priority**."
    )

    if total_q_count == 0:
        st.warning("⚠️ No questions found. Please complete **Step 1: Upload Papers** first.")
        if st.button("Go to Step 1: Upload Papers ➔", type="primary"):
            st.session_state["nav_choice"] = "1. 📤 Upload Papers"
            st.rerun()
    else:
        analysis = get_current_analysis()
        checklist_df = get_revision_checklist_df(analysis)

        # Priority Counts Metrics
        high_count = len(checklist_df[checklist_df["Priority"].str.contains("High", case=False, na=False)])
        medium_count = len(checklist_df[checklist_df["Priority"].str.contains("Medium", case=False, na=False)])
        standard_count = len(checklist_df[checklist_df["Priority"].str.contains("Standard", case=False, na=False)])

        col_pr1, col_pr2, col_pr3 = st.columns(3)
        col_pr1.metric("🔥 High Priority", high_count, help="Appeared in 2+ separate exam papers across years")
        col_pr2.metric("⚡ Medium Priority", medium_count, help="Repeated multiple times within paper or borderline similarity")
        col_pr3.metric("📘 Standard Priority", standard_count, help="Appeared in a single exam paper so far")

        st.markdown("---")

        # Priority Filter
        filter_priority = st.radio(
            "Filter Questions by Priority Tier",
            options=["All Questions", "🔥 High Priority Only", "⚡ Medium Priority Only", "📘 Standard Priority Only"],
            horizontal=True,
        )

        filtered_checklist = checklist_df
        if "High Priority" in filter_priority:
            filtered_checklist = checklist_df[checklist_df["Priority"].str.contains("High", case=False, na=False)]
        elif "Medium Priority" in filter_priority:
            filtered_checklist = checklist_df[checklist_df["Priority"].str.contains("Medium", case=False, na=False)]
        elif "Standard Priority" in filter_priority:
            filtered_checklist = checklist_df[checklist_df["Priority"].str.contains("Standard", case=False, na=False)]

        st.dataframe(filtered_checklist, use_container_width=True, hide_index=True)

        # Download Checklist CSV
        csv_checklist = checklist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Complete Revision Checklist (CSV)",
            data=csv_checklist,
            file_name="paperpilot_revision_checklist.csv",
            mime="text/csv",
            key="btn_download_checklist_csv",
        )

        # Visual Exam Distribution
        with st.expander("📊 Visual Exam Distribution Charts", expanded=False):
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.subheader("Questions per Exam Paper")
                papers_summary = get_papers_summary_df(all_active_questions)
                if not papers_summary.empty:
                    st.bar_chart(papers_summary.set_index("Filename")["Questions Extracted"])
            with col_v2:
                st.subheader("Questions per Exam Year")
                year_counts = {}
                for q in all_active_questions:
                    y_label = str(q.year) if q.year is not None else "Unknown"
                    year_counts[y_label] = year_counts.get(y_label, 0) + 1
                year_df = pd.DataFrame(list(year_counts.items()), columns=["Year", "Questions"]).sort_values(by="Year")
                if not year_df.empty:
                    st.bar_chart(year_df.set_index("Year")["Questions"])


# =============================================================================
# STEP 4: QUESTION BANK & ANALYTICS
# =============================================================================
elif nav_choice == "4. 📊 Question Bank & Analytics":
    st.title("📊 Question Bank & Analytics")
    st.write("Browse, search, and inspect the complete database of extracted exam questions and topic distributions.")

    if total_q_count == 0:
        st.info("No questions stored yet. Please upload papers in **Step 1: Upload Papers**.")
    else:
        tab_qbank, tab_analytics = st.tabs(["📚 All Questions", "📈 Exam Distribution & Clusters"])

        with tab_qbank:
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                search_query = st.text_input("🔍 Search question text", placeholder="Type keywords like 'deadlock', 'scheduling'...")
            with col_f2:
                paper_filter = st.selectbox("Filter by Paper", options=["All Papers"] + [p["filename"] for p in storage.get_papers()], key="qb_paper_select")

            show_excluded = st.checkbox("Show excluded questions", value=False)
            filtered_qb = storage.get_questions(
                source_file=None if paper_filter == "All Papers" else paper_filter,
                include_excluded=show_excluded,
            )
            if search_query.strip():
                q_lower = search_query.strip().lower()
                filtered_qb = [q for q in filtered_qb if q_lower in q.text.lower()]

            st.caption(f"Displaying **{len(filtered_qb)}** matching questions.")
            df_qb = get_all_questions_df(filtered_qb)
            st.dataframe(df_qb, use_container_width=True, hide_index=True)

            csv_all = df_qb.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Filtered Question Bank (CSV)",
                data=csv_all,
                file_name="paperpilot_all_questions.csv",
                mime="text/csv",
                key="btn_download_qb_csv",
            )

        with tab_analytics:
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                st.subheader("Questions per Exam Paper")
                papers_summary = get_papers_summary_df(all_active_questions)
                if not papers_summary.empty:
                    st.bar_chart(papers_summary.set_index("Filename")["Questions Extracted"])

            with col_ch2:
                st.subheader("Questions per Exam Year")
                year_counts = {}
                for q in all_active_questions:
                    y_label = str(q.year) if q.year is not None else "Unknown"
                    year_counts[y_label] = year_counts.get(y_label, 0) + 1
                year_df = pd.DataFrame(list(year_counts.items()), columns=["Year", "Questions"]).sort_values(by="Year")
                if not year_df.empty:
                    st.bar_chart(year_df.set_index("Year")["Questions"])

            st.markdown("---")
            st.subheader("Complete Cluster Breakdown Table")
            analysis = get_current_analysis()
            all_cluster_data = []
            for c in analysis.clusters:
                ai_lbl = st.session_state.get("ai_cluster_labels", {}).get(c.cluster_id)
                if ai_lbl:
                    c_sub = c.questions[0].subject if c.questions else "Computer Science"
                    m_texts = [q.text for q in c.questions if q.text.strip() != c.representative_text.strip()]
                    exp_key = compute_cluster_cache_key(
                        model_name=ai_lbl.model,
                        prompt_version=PROMPT_VERSION,
                        subject=c_sub,
                        representative_text=c.representative_text,
                        member_texts=m_texts,
                    )
                    if ai_lbl.cache_key != exp_key:
                        ai_lbl = None

                all_cluster_data.append({
                    "Cluster ID": c.cluster_id,
                    "AI Topic": ai_lbl.topic if ai_lbl else "N/A",
                    "Topic / Representative": c.representative_text,
                    "Distinct Papers": c.paper_count,
                    "Occurrences": c.occurrence_count,
                    "Repeated": "Yes" if c.occurrence_count > 1 else "No",
                    "Exam Years": ", ".join(str(y) for y in c.years) if c.years else "N/A",
                })

            st.dataframe(pd.DataFrame(all_cluster_data), use_container_width=True, hide_index=True)


# =============================================================================
# STEP 5: SETTINGS & PRIVACY
# =============================================================================
elif nav_choice == "5. ⚙️ Settings & Privacy":
    st.title("⚙️ Settings & Privacy")
    st.write("Configure similarity sensitivity, view privacy details, and manage local data.")

    st.subheader("🎚️ Similarity Sensitivity")
    st.write(
        "PaperPilot clusters questions using TF-IDF cosine similarity. "
        "The similarity threshold dictates how closely questions must match to be considered recurring."
    )

    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        new_th = st.slider(
            "Cosine Similarity Threshold",
            min_value=0.40,
            max_value=0.95,
            value=float(st.session_state["similarity_threshold"]),
            step=0.05,
            help="Higher values require closer word matching. Lower values cluster broader topic variants.",
        )
        if new_th != st.session_state["similarity_threshold"]:
            st.session_state["similarity_threshold"] = new_th
            mark_data_dirty()
            st.success(f"Threshold updated to {new_th:.2f} and clusters recalculated.")
            st.rerun()

    with col_s2:
        st.markdown(
            """
            **Guidance:**
            - **0.50 - 0.60:** Catches conceptual topic overlap (recommended for broad questions).
            - **0.65:** Default balanced threshold.
            - **0.75 - 0.90:** Identifies near-exact wording duplicates.
            """
        )

    st.markdown("---")
    st.subheader("🔒 Privacy & Storage Guarantee")
    st.markdown(
        """
        - **Local Storage:** All questions and paper metadata are saved in `<project>/paperpilot.db`.
        - **Zero Cloud Leakage:** PDFs are parsed locally. No data is sent to external cloud APIs or third parties.
        - **Local AI:** Optional AI features strictly communicate with local Ollama on loopback `localhost:11434`.
        - **Git Safety:** Your database and uploaded PDFs are excluded from version control via `.gitignore`.
        """
    )

    st.markdown("---")
    st.subheader("🔍 Local OCR Engine Status")
    tess_available = is_tesseract_available()
    if tess_available:
        tess_ver = get_tesseract_version() or "Detected"
        tess_path = get_tesseract_cmd() or "System PATH"
        st.success(f"✅ **Tesseract-OCR is installed and active** ({tess_ver})")
        st.caption(f"Binary path: `{tess_path}`. Scanned and image-only PDF pages are automatically converted to text.")
    else:
        st.info("ℹ️ **Tesseract-OCR is not installed or not detected on PATH.**")
        st.caption("Standard digital text PDFs work 100% offline. To support scanned exam paper photos and image PDFs, set up Tesseract-OCR.")
        col_set_auto, col_set_man = st.columns([1, 1])
        with col_set_auto:
            if st.button("⚡ Set Up OCR Automatically", type="primary", key="settings_setup_ocr_btn"):
                with st.status("Setting up local OCR engine...", expanded=True) as status:
                    def settings_progress(msg: str, pct: float):
                        st.write(f"• {msg}")
                    res = run_ocr_setup(progress_callback=settings_progress)
                    if res.success:
                        if res.status == "installed_successfully":
                            status.update(label="✅ Tesseract-OCR installed successfully!", state="complete", expanded=False)
                            st.success(res.message)
                            st.rerun()
                        elif res.status == "installer_launched":
                            status.update(label="ℹ️ Installer launched — setup wizard open", state="complete", expanded=True)
                            st.info(res.message)
                        else:
                            status.update(label="✅ Tesseract-OCR is ready!", state="complete", expanded=False)
                            st.success(res.message)
                            st.rerun()
                    else:
                        status.update(label="❌ OCR Setup Failed", state="error", expanded=True)
                        st.error(res.message)
        with col_set_man:
            with st.expander("📥 Manual Installation Instructions", expanded=False):
                st.markdown(INSTALL_GUIDANCE_MESSAGE)

    st.markdown("---")
    st.subheader("⚠️ Reset Database")
    st.write("Need to start fresh? Resetting deletes all stored papers and questions from your local SQLite database.")

    confirm_reset = st.checkbox("I understand this will permanently delete all stored questions and papers.")
    if st.button("🗑️ Reset Database & Clear All Data", disabled=not confirm_reset, type="primary"):
        storage.clear_all()
        mark_data_dirty()
        st.success("Database reset successfully! All questions and papers have been removed.")
        st.rerun()
