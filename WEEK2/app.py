"""
app.py - Streamlit Web Interface for PaperPilot.

Local-first, privacy-focused Previous Year Question Paper (PYQ) analyzer.
Extracts questions from text PDFs, clusters recurring questions using TF-IDF
and leader-clustering, calculates recurrence analytics, and creates revision checklists.
"""

from pathlib import Path
import re
from typing import List, Optional
import pandas as pd
import streamlit as st

from paperpilot.pdf_extractor import extract_text_from_pdf, PDFExtractionError
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

# Set Streamlit page layout and title
st.set_page_config(
    page_title="PaperPilot — Exam Paper Analyzer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize SQLite Storage
DB_PATH = Path(__file__).resolve().parent / "paperpilot.db"


@st.cache_resource
def get_storage() -> PaperPilotStorage:
    """Returns a singleton instance of PaperPilotStorage."""
    return PaperPilotStorage(db_path=DB_PATH)


storage = get_storage()

# Initialize session state keys
if "similarity_threshold" not in st.session_state:
    st.session_state["similarity_threshold"] = 0.65

if "analysis_cache" not in st.session_state:
    st.session_state["analysis_cache"] = None

if "cache_dirty" not in st.session_state:
    st.session_state["cache_dirty"] = True

if "review_file_filter" not in st.session_state:
    st.session_state["review_file_filter"] = "All Papers"


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


# =============================================================================
# SIDEBAR NAVIGATION & CONTROLS
# =============================================================================

st.sidebar.markdown("## ✈️ PaperPilot")
st.sidebar.caption("Local-First Exam Paper Analyzer")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "Navigation",
    options=[
        "📊 Dashboard",
        "📤 Upload & Review",
        "📚 Question Bank",
        "🔁 Repeated Questions",
        "📈 Topic & Frequency Analysis",
        "📝 Revision Checklist",
        "⚙️ Settings & Privacy",
    ],
    index=0,
)

st.sidebar.markdown("---")

# Global threshold quick-slider in sidebar
st.sidebar.markdown("### 🎚️ Similarity Threshold")
new_threshold = st.sidebar.slider(
    "Cosine Similarity Threshold",
    min_value=0.40,
    max_value=0.95,
    value=float(st.session_state["similarity_threshold"]),
    step=0.05,
    help="Higher values require closer word matching. Lower values cluster broader topic variants.",
)
if new_threshold != st.session_state["similarity_threshold"]:
    st.session_state["similarity_threshold"] = new_threshold
    mark_data_dirty()
    st.sidebar.info(f"Threshold set to {new_threshold:.2f}. Recalculating...")
    st.rerun()

st.sidebar.markdown("---")
# Quick database counters
db_stats = storage.get_stats()
st.sidebar.markdown(f"**Stored Papers:** `{db_stats['total_papers']}`")
st.sidebar.markdown(f"**Active Questions:** `{db_stats['active_questions']}`")
if db_stats["excluded_questions"] > 0:
    st.sidebar.caption(f"ℹ️ Excluded from analysis: {db_stats['excluded_questions']}")

st.sidebar.markdown("---")
st.sidebar.markdown("🔒 **100% Offline & Private**")
st.sidebar.caption("All PDFs, questions, and similarity computations run locally. No external APIs used.")


# =============================================================================
# 1. DASHBOARD
# =============================================================================
if nav_choice == "📊 Dashboard":
    st.title("📊 PaperPilot Dashboard")
    st.write(
        "Welcome to **PaperPilot**! An offline, privacy-first analyzer for previous-year exam papers. "
        "Upload your text-based PDF question papers to discover recurring topics, examine question frequency, "
        "and generate a targeted study checklist."
    )

    questions = storage.get_questions(include_excluded=False)
    papers = storage.get_papers()

    if not questions or not papers:
        st.info(
            "👋 **No exam papers analyzed yet!**\n\n"
            "Get started in 3 easy steps:\n"
            "1. Navigate to **Upload & Review** in the sidebar.\n"
            "2. Upload your course question paper PDFs (or test with the sample papers in `data/`).\n"
            "3. Review the extracted questions and return here for instant analytics!"
        )

        col_demo1, col_demo2 = st.columns(2)
        with col_demo1:
            st.markdown("### 📁 Synthetic Test Papers Available")
            st.markdown(
                "You can test immediately using the included synthetic Operating Systems papers:\n"
                "- `data/sample_os_2022.pdf` (Year 2022)\n"
                "- `data/sample_os_2023.pdf` (Year 2023)"
            )
        with col_demo2:
            st.markdown("### 🔒 Privacy Guarantee")
            st.markdown(
                "- **Zero Cloud APIs:** No OpenAI, Claude, or third-party connections.\n"
                "- **Local Storage:** All questions are stored in a local SQLite file (`paperpilot.db`).\n"
                "- **Deterministic ML:** Powered by TF-IDF & Cosine Similarity via Scikit-Learn."
            )
    else:
        analysis = get_current_analysis()
        metrics = calculate_dataset_metrics(analysis, questions)

        # 4 High-Level Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Exam Papers", metrics["distinct_papers"])
        col2.metric("Questions Extracted", metrics["total_questions"])
        col3.metric("Repeated Question Groups", metrics["repeated_clusters_count"])
        col4.metric("Repetition Rate", f"{metrics['repetition_rate_pct']:.1f}%")

        st.markdown("---")

        # Papers Table & Quick Repeated Snippet
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("📑 Uploaded Papers")
            papers_df = get_papers_summary_df(questions)
            st.dataframe(papers_df, width="stretch", hide_index=True)

        with col_right:
            st.subheader("🔁 Top Repeated Questions")
            if analysis.repeated_clusters:
                rep_df = get_repeated_clusters_df(analysis)
                st.dataframe(
                    rep_df[["Representative Question", "Distinct Papers", "Total Occurrences", "Exam Years"]].head(5),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.write("No questions met the repetition threshold yet. Try lowering the threshold in the sidebar.")

        # Re-analysis Notice if dirty
        if st.session_state.get("cache_dirty", False):
            st.warning("⚠️ Questions have been edited. Results will refresh on your next view.")


# =============================================================================
# 2. UPLOAD & REVIEW
# =============================================================================
elif nav_choice == "📤 Upload & Review":
    st.title("📤 Upload & Review Exam Papers")
    st.write(
        "Upload text-based PDF question papers, assign course metadata, and review "
        "the extracted questions to ensure clean data before similarity clustering."
    )

    tab_upload, tab_review, tab_manage = st.tabs(["1. Upload PDFs", "2. Review & Edit Questions", "3. Manage Papers"])

    # --- SUB-TAB 1: UPLOAD ---
    with tab_upload:
        st.subheader("Upload PDF Question Papers")

        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            default_subject = st.text_input("Course / Subject Name", value="Operating Systems")
        with col_meta2:
            default_year_str = st.text_input("Default Exam Year (Optional, e.g. 2023)", value="")

        default_year: Optional[int] = None
        if default_year_str.strip().isdigit():
            default_year = int(default_year_str.strip())

        uploaded_files = st.file_uploader(
            "Select Text-based PDF Question Papers",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload PDF question papers. Note: scanned image PDFs require OCR which is outside the MVP.",
        )

        overwrite_existing = st.checkbox(
            "Overwrite paper if already uploaded with the same filename",
            value=True,
            help="If checked, re-uploading a file with the same name replaces its questions with the freshly extracted set.",
        )

        if uploaded_files:
            if st.button("🚀 Extract & Store Questions", type="primary"):
                total_extracted = 0
                papers_processed = 0

                for uploaded_file in uploaded_files:
                    file_bytes = uploaded_file.read()
                    filename = uploaded_file.name

                    # Attempt to extract year from filename if not explicitly provided (e.g. sample_os_2022.pdf)
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

                        # Check if document is scanned image
                        if extracted_doc.is_scanned:
                            st.warning(
                                f"⚠️ **Scanned PDF Detected in `{filename}`!**\n\n"
                                f"This file contains image-only pages with no selectable text. "
                                f"Scanned PDFs require an Optical Character Recognition (OCR) engine, "
                                f"which is not part of this offline MVP. Please upload text-based PDFs."
                            )
                            continue

                        # Parse questions with page tracking preserved
                        parse_res = parse_questions(extracted_doc)

                        # Save to SQLite database
                        saved = storage.save_paper(
                            filename=filename,
                            subject=default_subject,
                            year=paper_year,
                            questions=parse_res.questions,
                            overwrite=overwrite_existing,
                        )

                        if saved:
                            st.success(
                                f"✅ Successfully processed `{filename}`: "
                                f"**{len(parse_res.questions)}** questions extracted "
                                f"(Year: {paper_year if paper_year else 'Unknown'})."
                            )
                            total_extracted += len(parse_res.questions)
                            papers_processed += 1
                        else:
                            st.info(f"Skipped `{filename}` because it already exists and overwrite was unchecked.")

                        # Show unparsed warnings if any headers were dropped
                        if parse_res.unparsed_segments:
                            with st.expander(f"ℹ️ Unparsed Headers/Instructions in `{filename}` ({len(parse_res.unparsed_segments)})"):
                                for seg in parse_res.unparsed_segments[:5]:
                                    st.caption(f"• {seg}")

                    except PDFExtractionError as e:
                        st.error(f"Failed to read `{filename}`: {e}")
                    except StorageError as e:
                        st.error(f"Database error while saving `{filename}`: {e}")

                if papers_processed > 0:
                    mark_data_dirty()
                    st.balloons()
                    st.info("Head to the **'Review & Edit Questions'** tab to inspect and correct extracted items!")

    # --- SUB-TAB 2: REVIEW & EDIT ---
    with tab_review:
        st.subheader("Review Extracted Questions")
        st.write(
            "Review parsed questions. You can fix typos, adjust question numbers, "
            "or exclude non-question lines before running similarity analysis."
        )

        stored_papers = storage.get_papers()
        if not stored_papers:
            st.info("No papers available to review. Upload a PDF first.")
        else:
            paper_options = ["All Papers"] + [p["filename"] for p in stored_papers]
            selected_paper = st.selectbox(
                "Filter questions by paper:",
                options=paper_options,
                key="review_paper_select",
            )

            filter_filename = None if selected_paper == "All Papers" else selected_paper
            review_questions = storage.get_questions(
                source_file=filter_filename,
                include_excluded=True,
            )

            if not review_questions:
                st.write("No questions found for the selected filter.")
            else:
                # Prepare data for st.data_editor
                editor_data = []
                for q in review_questions:
                    editor_data.append({
                        "ID": q.id,
                        "Paper": q.source_file,
                        "Page": q.source_page,
                        "No": q.question_number,
                        "Question Text": q.text,
                        "Marks": q.marks or "",
                        "Year": str(q.year) if q.year is not None else "Unknown",
                    })

                review_df = pd.DataFrame(editor_data)

                st.markdown(
                    "💡 **Tip:** Edit question text or numbering directly in the table below, "
                    "then click **Save Corrections to Database**."
                )

                edited_df = st.data_editor(
                    review_df,
                    key="review_editor",
                    disabled=["ID", "Paper", "Page"],
                    width="stretch",
                    num_rows="fixed",
                    column_config={
                        "ID": st.column_config.TextColumn("ID", width="small"),
                        "Question Text": st.column_config.TextColumn("Question Text", width="large"),
                        "No": st.column_config.TextColumn("No", width="small"),
                        "Marks": st.column_config.TextColumn("Marks", width="small"),
                        "Year": st.column_config.TextColumn("Year", width="small"),
                    },
                )

                col_save, col_exclude = st.columns([1, 1])

                with col_save:
                    if st.button("💾 Save Corrections to Database", type="primary"):
                        updates_count = 0
                        for _, row in edited_df.iterrows():
                            qid = row["ID"]
                            new_text = str(row["Question Text"]).strip()
                            new_num = str(row["No"]).strip()
                            new_marks = str(row["Marks"]).strip() or None
                            new_year = int(row["Year"]) if str(row["Year"]).isdigit() else None

                            storage.update_question(
                                question_id=qid,
                                text=new_text,
                                question_number=new_num,
                                marks=new_marks,
                                year=new_year,
                            )
                            updates_count += 1

                        mark_data_dirty()
                        st.success(f"Successfully saved changes for {updates_count} questions!")
                        st.rerun()

                with col_exclude:
                    # Individual question exclusion / deletion tool
                    with st.expander("🗑️ Exclude or Delete a Specific Question"):
                        del_q_options = {f"[{q.source_file} p.{q.source_page}] {q.question_number} {q.text[:60]}...": q.id for q in review_questions}
                        selected_del_label = st.selectbox("Select question to exclude/delete:", list(del_q_options.keys()))
                        if selected_del_label:
                            target_qid = del_q_options[selected_del_label]
                            col_ex, col_del = st.columns(2)
                            with col_ex:
                                if st.button("🚫 Exclude from Analysis"):
                                    storage.update_question(target_qid, is_excluded=True)
                                    mark_data_dirty()
                                    st.warning("Question excluded from future similarity clustering.")
                                    st.rerun()
                            with col_del:
                                if st.button("❌ Delete Permanently"):
                                    storage.delete_question(target_qid)
                                    mark_data_dirty()
                                    st.error("Question permanently deleted.")
                                    st.rerun()

    # --- SUB-TAB 3: MANAGE PAPERS ---
    with tab_manage:
        st.subheader("Manage Stored Papers")
        stored_papers = storage.get_papers()

        if not stored_papers:
            st.write("No papers stored yet.")
        else:
            for p in stored_papers:
                col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
                with col_p1:
                    st.markdown(
                        f"**{p['filename']}** — Subject: *{p['subject']}* | "
                        f"Year: *{p['year'] if p['year'] else 'N/A'}* | "
                        f"Questions: `{p['question_count']}`"
                    )
                with col_p2:
                    st.caption(f"Uploaded: {p['uploaded_at'][:10]}")
                with col_p3:
                    if st.button("🗑️ Delete Paper", key=f"del_{p['filename']}"):
                        storage.delete_paper(p["filename"])
                        mark_data_dirty()
                        st.success(f"Deleted `{p['filename']}` and its questions.")
                        st.rerun()


# =============================================================================
# 3. QUESTION BANK
# =============================================================================
elif nav_choice == "📚 Question Bank":
    st.title("📚 Searchable Question Bank")
    st.write("Browse, search, and filter all reviewed questions across examination years.")

    questions = storage.get_questions(include_excluded=False)

    if not questions:
        st.info("The Question Bank is empty. Please upload exam papers in the **Upload & Review** section.")
    else:
        # Search & Filter Controls
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        with col_s1:
            search_query = st.text_input("🔍 Search question text (case-insensitive)", placeholder="e.g. deadlock, scheduling, page fault")
        with col_s2:
            subjects = ["All Subjects"] + sorted(list(set(q.subject for q in questions)))
            sel_subject = st.selectbox("Subject", subjects)
        with col_s3:
            years = ["All Years"] + sorted(list(set(str(q.year) for q in questions if q.year is not None)))
            sel_year = st.selectbox("Year", years)

        # Apply Filters
        filtered_q = questions
        if search_query.strip():
            q_lower = search_query.strip().lower()
            filtered_q = [q for q in filtered_q if q_lower in q.text.lower()]
        if sel_subject != "All Subjects":
            filtered_q = [q for q in filtered_q if q.subject == sel_subject]
        if sel_year != "All Years":
            filtered_q = [q for q in filtered_q if str(q.year) == sel_year]

        st.markdown(f"**Showing {len(filtered_q)} of {len(questions)} total questions**")

        q_df = get_all_questions_df(filtered_q)
        st.dataframe(q_df, width="stretch", hide_index=True)

        # CSV Download Button
        csv_data = q_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Question Bank (CSV)",
            data=csv_data,
            file_name="paperpilot_question_bank.csv",
            mime="text/csv",
        )


# =============================================================================
# 4. REPEATED QUESTIONS
# =============================================================================
elif nav_choice == "🔁 Repeated Questions":
    st.title("🔁 Repeated & Similar Questions")
    st.write(
        "Identifies exact and semantically similar questions using **TF-IDF + Cosine Similarity** "
        "and **Representative-Based (Leader) Clustering**. "
        "Questions are matched against a cluster anchor to avoid false chain-merging."
    )

    questions = storage.get_questions(include_excluded=False)

    if not questions:
        st.info("No questions to analyze. Upload papers in **Upload & Review**.")
    else:
        current_threshold = st.session_state["similarity_threshold"]
        analysis = get_current_analysis()

        # Explanation Alert for Students
        with st.expander("ℹ️ How Clustering Works & Metric Definitions"):
            st.markdown(
                """
                - **Leader / Representative-Based Clustering:** Questions are anchored to the most comprehensive question. 
                  Every candidate must meet the similarity threshold against that specific leader, preventing transitive chaining 
                  (where A matches B and B matches C, but A and C are unrelated).
                - **Total Occurrences:** Total times this question was asked across all papers.
                - **Distinct Papers:** How many separate exam question papers featured this question.
                - **Individual Similarity Score:** Every member's exact cosine similarity against the representative anchor.
                """
            )

        st.markdown(
            f"**Current Threshold:** `{current_threshold:.2f}` | "
            f"**Repeated Clusters Found:** `{len(analysis.repeated_clusters)}` | "
            f"**Questions Involved:** `{sum(c.occurrence_count for c in analysis.repeated_clusters)}`"
        )

        if not analysis.repeated_clusters:
            st.warning(
                f"No questions met the similarity threshold of `{current_threshold:.2f}`. "
                f"Try lowering the threshold in the sidebar slider (e.g. to 0.50 or 0.60)."
            )
        else:
            for cluster in analysis.repeated_clusters:
                years_badge = ", ".join(str(y) for y in cluster.years) if cluster.years else "N/A"
                match_badge = "Exact Duplicate" if cluster.is_exact else f"Similar (~{int(cluster.avg_similarity * 100)}%)"

                with st.expander(
                    f"📌 [{cluster.cluster_id.upper()}] {cluster.representative_text[:75]}... "
                    f"({cluster.paper_count} Papers, {cluster.occurrence_count} Occurrences)",
                    expanded=True,
                ):
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    col_m1.metric("Distinct Papers", cluster.paper_count)
                    col_m2.metric("Total Occurrences", cluster.occurrence_count)
                    col_m3.metric("Match Type", match_badge)
                    col_m4.metric("Exam Years", years_badge)

                    st.markdown("**Representative Anchor Question:**")
                    st.info(f"**\"{cluster.representative_text}\"**")

                    st.markdown("**Member Questions & Individual Similarity to Anchor:**")
                    for member in cluster.questions:
                        sim_score = cluster.similarity_to_representative.get(member.id, 1.0)
                        is_leader = (member.id == cluster.representative_id)
                        tag = "👑 [Leader Anchor]" if is_leader else f"Similarity: {sim_score:.3f}"

                        st.markdown(
                            f"- **{member.source_file}** (Page {member.source_page}, {member.question_number}, "
                            f"Year {member.year if member.year else 'N/A'}) — `{tag}`\n"
                            f"  > *\"{member.text}\"*"
                        )

            # Export Repeated Clusters
            rep_df = get_repeated_clusters_df(analysis)
            st.markdown("---")
            csv_rep = rep_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Repeated Questions Analysis (CSV)",
                data=csv_rep,
                file_name="paperpilot_repeated_questions.csv",
                mime="text/csv",
            )


# =============================================================================
# 5. TOPIC & FREQUENCY ANALYSIS
# =============================================================================
elif nav_choice == "📈 Topic & Frequency Analysis":
    st.title("📈 Topic & Frequency Analysis")
    st.write("Visual breakdown of question distribution across papers, examination years, and recurrence clusters.")

    questions = storage.get_questions(include_excluded=False)

    if not questions:
        st.info("No questions to analyze. Upload papers in **Upload & Review**.")
    else:
        analysis = get_current_analysis()

        tab_charts, tab_tables = st.tabs(["📊 Visual Charts", "📑 Tabular Distribution"])

        with tab_charts:
            col_ch1, col_ch2 = st.columns(2)

            with col_ch1:
                st.subheader("Questions per Exam Paper")
                papers_summary = get_papers_summary_df(questions)
                if not papers_summary.empty:
                    chart_data = papers_summary.set_index("Filename")["Questions Extracted"]
                    st.bar_chart(chart_data)

            with col_ch2:
                st.subheader("Questions per Exam Year")
                year_counts = {}
                for q in questions:
                    y_label = str(q.year) if q.year is not None else "Unknown"
                    year_counts[y_label] = year_counts.get(y_label, 0) + 1

                year_df = pd.DataFrame(list(year_counts.items()), columns=["Year", "Questions"]).sort_values(by="Year")
                st.bar_chart(year_df.set_index("Year"))

            st.subheader("Recurrence Distribution")
            col_pie1, col_pie2 = st.columns([1, 2])
            with col_pie1:
                rep_count = sum(c.occurrence_count for c in analysis.repeated_clusters)
                single_count = len(analysis.single_question_clusters)
                dist_df = pd.DataFrame({
                    "Category": ["Repeated Questions", "Single-Appearance Questions"],
                    "Count": [rep_count, single_count],
                })
                st.dataframe(dist_df, width="stretch", hide_index=True)
            with col_pie2:
                st.bar_chart(dist_df.set_index("Category"))

        with tab_tables:
            st.subheader("Complete Cluster Breakdown")
            all_cluster_data = []
            for c in analysis.clusters:
                all_cluster_data.append({
                    "Cluster ID": c.cluster_id,
                    "Topic / Representative": c.representative_text,
                    "Distinct Papers": c.paper_count,
                    "Occurrences": c.occurrence_count,
                    "Years": ", ".join(str(y) for y in c.years) if c.years else "N/A",
                    "Is Repeated": "Yes" if c.occurrence_count > 1 else "No",
                })
            all_cluster_df = pd.DataFrame(all_cluster_data)
            st.dataframe(all_cluster_df, width="stretch", hide_index=True)


# =============================================================================
# 6. REVISION CHECKLIST
# =============================================================================
elif nav_choice == "📝 Revision Checklist":
    st.title("📝 Student Revision Checklist & Study Guide")
    st.write(
        "A targeted, prioritized revision checklist derived **strictly from historical repetition evidence**. "
        "Questions are organized into high, medium, and standard priority tiers."
    )

    questions = storage.get_questions(include_excluded=False)

    if not questions:
        st.info("No questions to prioritize. Upload papers in **Upload & Review**.")
    else:
        analysis = get_current_analysis()
        checklist_df = get_revision_checklist_df(analysis)

        col_t1, col_t2, col_t3 = st.columns(3)
        high_count = len(checklist_df[checklist_df["Priority"].str.contains("High")])
        med_count = len(checklist_df[checklist_df["Priority"].str.contains("Medium")])
        std_count = len(checklist_df[checklist_df["Priority"].str.contains("Standard")])

        col_t1.metric("🔴 High Priority (Multi-Year)", high_count)
        col_t2.metric("🟡 Medium Priority (Repeated)", med_count)
        col_t3.metric("🟢 Standard Priority", std_count)

        st.markdown("---")

        # Interactive checklist table
        st.dataframe(
            checklist_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Priority": st.column_config.TextColumn("Priority Tier", width="medium"),
                "Topic / Question": st.column_config.TextColumn("Topic / Representative Question", width="large"),
                "Distinct Papers": st.column_config.NumberColumn("Distinct Papers", width="small"),
                "Total Occurrences": st.column_config.NumberColumn("Occurrences", width="small"),
                "Exam Years": st.column_config.TextColumn("Exam Years", width="small"),
                "Sample Source": st.column_config.TextColumn("Source Paper", width="medium"),
            },
        )

        csv_chk = checklist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Revision Checklist (CSV)",
            data=csv_chk,
            file_name="paperpilot_revision_checklist.csv",
            mime="text/csv",
        )


# =============================================================================
# 7. SETTINGS & PRIVACY
# =============================================================================
elif nav_choice == "⚙️ Settings & Privacy":
    st.title("⚙️ Settings & Offline Privacy")

    col_set1, col_set2 = st.columns(2)

    with col_set1:
        st.subheader("Clustering Configuration")
        st.write(
            "Configure the TF-IDF Cosine Similarity threshold used for detecting repeated questions. "
            "Higher thresholds require more exact wording; lower thresholds cluster broader variants."
        )

        cfg_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.40,
            max_value=0.95,
            value=float(st.session_state["similarity_threshold"]),
            step=0.05,
            key="settings_slider",
        )

        if cfg_threshold != st.session_state["similarity_threshold"]:
            st.session_state["similarity_threshold"] = cfg_threshold
            mark_data_dirty()
            st.success(f"Similarity threshold updated to {cfg_threshold:.2f}!")

        st.markdown(
            """
            **Guidance:**
            - `0.80 - 0.95`: Identifies near-verbatim repeated questions.
            - `0.60 - 0.75`: Recommended baseline for capturing paraphrased question variants.
            - `0.40 - 0.55`: Loose clustering; groups related topic concepts together.
            """
        )

    with col_set2:
        st.subheader("🔒 Privacy & Offline Assurance")
        st.info(
            "**No Cloud Telemetry or APIs**\n\n"
            "PaperPilot runs entirely on your local machine. "
            "No exam papers, extracted text, or analysis data are ever transmitted to any external server."
        )

        st.markdown(f"**Database Location:** `{DB_PATH}`")
        stats = storage.get_stats()
        st.markdown(f"**Total Papers in DB:** `{stats['total_papers']}`")
        st.markdown(f"**Active Questions in DB:** `{stats['active_questions']}`")
        st.markdown(f"**Excluded Questions:** `{stats['excluded_questions']}`")

    st.markdown("---")

    # Project Data Reset with Explicit Confirmation
    st.subheader("⚠️ Project Reset")
    st.write("Wipe all stored papers and extracted questions from your local database.")

    confirm_reset = st.checkbox("I confirm that I want to permanently wipe all stored papers and questions.")

    if st.button("🗑️ Reset All Project Data", type="primary", disabled=not confirm_reset):
        storage.clear_all()
        st.session_state["analysis_cache"] = None
        st.session_state["cache_dirty"] = True
        st.success("All project data has been wiped successfully.")
        st.rerun()
