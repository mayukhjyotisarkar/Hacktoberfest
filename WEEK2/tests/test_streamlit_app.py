"""
test_streamlit_app.py - Automated UI tests using Streamlit's official AppTest framework.

Verifies that app.py executes cleanly across the redesigned guided 3-step workflow:
  1. 📤 Upload Papers
  2. 🎯 Find Important Questions
  3. 📝 My Revision Plan
  4. 📊 Question Bank & Analytics
  5. ⚙️ Settings & Privacy
"""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from paperpilot.storage import PaperPilotStorage
from paperpilot.question_parser import QuestionItem


APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Initializes isolated test database with sample questions for AppTest."""
    test_db = tmp_path / "ui_test_paperpilot.db"
    monkeypatch.setenv("PAPERPILOT_DB_PATH", str(test_db))
    storage = PaperPilotStorage(db_path=test_db)

    # Insert sample questions
    q1 = QuestionItem("q1", "1.", "Explain Deadlock four conditions.", "1. Explain Deadlock four conditions.", "os_2022.pdf", 1, "OS", 2022, "[10 Marks]")
    q2 = QuestionItem("q2", "2.", "Explain Deadlock necessary conditions.", "2. Explain Deadlock necessary conditions.", "os_2023.pdf", 1, "OS", 2023, "[10 Marks]")
    storage.save_paper("os_2022.pdf", "OS", 2022, [q1])
    storage.save_paper("os_2023.pdf", "OS", 2023, [q2])

    # Point app.py DB_PATH to this temporary database
    import app
    monkeypatch.setattr(app, "DB_PATH", test_db)
    monkeypatch.setattr(app, "storage", storage)
    yield storage


def test_dashboard_renders_metrics():
    """Verifies that Step 1 view loads overview metrics and tables without exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()
    assert not at.exception
    assert len(at.metric) >= 4
    metric_labels = [m.label for m in at.metric]
    assert "Exam Papers" in metric_labels
    assert "Questions Extracted" in metric_labels


def test_question_bank_renders_and_filters():
    """Verifies Question Bank tab in Step 4 loads, filters, and generates CSV data."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Question Bank & Analytics (Option 4)
    at.sidebar.radio[0].set_value("4. 📊 Question Bank & Analytics").run()
    assert not at.exception
    assert len(at.dataframe) >= 1
    assert len(at.download_button) >= 1


def test_repeated_questions_renders_clusters():
    """Verifies Step 2 clusters items and displays match types."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 2: Find Important Questions
    at.sidebar.radio[0].set_value("2. 🎯 Find Important Questions").run()
    assert not at.exception
    assert len(at.download_button) >= 1


def test_topic_analysis_charts_render():
    """Verifies charts and cluster tables render without exceptions in Step 4."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 4: Question Bank & Analytics
    at.sidebar.radio[0].set_value("4. 📊 Question Bank & Analytics").run()
    assert not at.exception


def test_revision_checklist_renders():
    """Verifies Step 3 ranks priorities and provides CSV download."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 3: My Revision Plan
    at.sidebar.radio[0].set_value("3. 📝 My Revision Plan").run()
    assert not at.exception
    assert len(at.metric) >= 3
    assert len(at.download_button) >= 1


def test_settings_and_threshold_slider():
    """Verifies Settings tab and dynamic similarity threshold updates."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 5: Settings & Privacy
    at.sidebar.radio[0].set_value("5. ⚙️ Settings & Privacy").run()
    assert not at.exception

    # Change slider to 0.85
    # The slider on the settings page is at.slider[0]
    if at.slider:
        at.slider[0].set_value(0.85).run()
        assert not at.exception
        assert at.session_state["similarity_threshold"] == 0.85

    # Reset button is disabled until checkbox is checked
    reset_btn = None
    for b in at.button:
        if "Reset Database" in b.label:
            reset_btn = b
            break
    if reset_btn:
        assert reset_btn.disabled is True


def test_repeated_questions_when_ai_is_unavailable():
    """Verifies that Step 2 gracefully handles Ollama being offline."""
    from unittest.mock import patch

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 2
    at.sidebar.radio[0].set_value("2. 🎯 Find Important Questions").run()
    assert not at.exception

    # Find the AI button
    ai_btn = None
    for b in at.button:
        if "Label All Topics with Local AI" in b.label:
            ai_btn = b
            break
    assert ai_btn is not None

    # Click the AI button while Ollama check_health returns False
    with patch("paperpilot.local_ai.LocalAIClient.check_health", return_value=False):
        ai_btn.click().run()
        assert not at.exception
        warnings = [w.value for w in at.warning]
        assert any("not running or unreachable" in w for w in warnings)


def test_repeated_questions_displays_cached_ai_label():
    """Verifies that an existing cached AI label is rendered inside the cluster expander."""
    from paperpilot.topic_labeler import CachedTopicLabel

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Set cached AI label for cluster_1
    at.session_state["ai_cluster_labels"]["cluster_1"] = CachedTopicLabel(
        topic="Deadlock Conditions",
        confidence="high",
        reasoning="Four conditions required for deadlock",
        model="qwen2.5-coder:1.5b-base",
        latency_ms=115.0,
        created_at=1000.0,
        cache_key="mock_hash",
    )

    at.sidebar.radio[0].set_value("2. 🎯 Find Important Questions").run()
    assert not at.exception

    captions = [c.value for c in at.caption]
    assert any("AI topic labels loaded" in c for c in captions)


def test_repeated_questions_revision_notes_offline_handling():
    """Verifies that clicking 'Generate Revision Notes' when Ollama is offline displays a clean warning."""
    from unittest.mock import patch

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    at.sidebar.radio[0].set_value("2. 🎯 Find Important Questions").run()
    assert not at.exception

    # Locate the per-cluster 'Generate Revision Notes' button
    rev_btn = None
    for b in at.button:
        if "Generate Revision Notes" in b.label:
            rev_btn = b
            break
    assert rev_btn is not None

    with patch("paperpilot.local_ai.LocalAIClient.check_health", return_value=False):
        rev_btn.click().run()
        assert not at.exception
        warnings = [w.value for w in at.warning]
        assert any("not running or unreachable" in w for w in warnings)


def test_repeated_questions_renders_revision_notes_without_unsolicited_inference():
    """Verifies that existing revision notes render cleanly and reruns trigger zero inference."""
    from unittest.mock import patch
    from paperpilot.revision_notes import GroundedRevisionNotes, SourceQuestionCitation, compute_revision_notes_cache_key, REVISION_PROMPT_VERSION

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    at.sidebar.radio[0].set_value("2. 🎯 Find Important Questions").run()
    assert not at.exception

    # Fetch current analysis to obtain exact representative and member texts
    analysis = at.session_state.get("analysis_cache")
    if analysis and analysis.repeated_clusters:
        target_cluster = analysis.repeated_clusters[0]
        cid = target_cluster.cluster_id
        cluster_sub = target_cluster.questions[0].subject if target_cluster.questions else "Computer Science"
        member_texts = [q.text for q in target_cluster.questions if q.text.strip() != target_cluster.representative_text.strip()]
        expected_key = compute_revision_notes_cache_key(
            model_name="qwen2.5-coder:1.5b-base",
            prompt_version=REVISION_PROMPT_VERSION,
            subject=cluster_sub,
            representative_text=target_cluster.representative_text,
            member_texts=member_texts,
        )

        sample_src = SourceQuestionCitation(
            question_id="q_sample",
            source_file="sample.pdf",
            source_page=1,
            question_number="1",
            year=2022,
            marks="10",
            text="Explain deadlock avoidance.",
            similarity_to_representative=1.0,
            is_leader=True,
        )

        at.session_state["ai_cluster_revision_notes"][cid] = GroundedRevisionNotes(
            focus="Deadlock avoidance safety criteria",
            revision_bullets=["Understand safety state matrices", "Review resource-request steps"],
            key_concepts=["Deadlock Avoidance", "Safe State"],
            confidence="high",
            reasoning="Grounded in exam questions",
            sources=[sample_src],
            model="qwen2.5-coder:1.5b-base",
            latency_ms=130.0,
            created_at=1000.0,
            cache_key=expected_key,
        )

        with patch("paperpilot.local_ai.LocalAIClient.send_generate_prompt") as mock_send:
            at.run()
            assert not at.exception
            mock_send.assert_not_called()

            md_texts = [m.value for m in at.markdown]
            assert any("Deadlock avoidance safety criteria" in m for m in md_texts)
            assert any("Understand safety state matrices" in m for m in md_texts)


def test_welcome_state_when_database_is_empty(tmp_path, monkeypatch):
    """Verifies that an empty database presents the welcome screen with sample load option."""
    empty_db = tmp_path / "empty_paperpilot.db"
    monkeypatch.setenv("PAPERPILOT_DB_PATH", str(empty_db))
    empty_storage = PaperPilotStorage(db_path=empty_db)

    import app
    monkeypatch.setattr(app, "DB_PATH", empty_db)
    monkeypatch.setattr(app, "storage", empty_storage)

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()
    assert not at.exception

    # Check for Welcome banner text
    info_texts = [i.value for i in at.info]
    assert any("Welcome to PaperPilot" in t for t in info_texts)

    # Check that 'Load Sample Papers' button is present
    sample_btn = None
    for b in at.button:
        if "Load Sample Papers" in b.label:
            sample_btn = b
            break
    assert sample_btn is not None


def test_settings_displays_ocr_engine_status():
    """Verifies that Step 5 Settings displays local OCR engine status and guidance."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Step 5: Settings & Privacy
    at.sidebar.radio[0].set_value("5. ⚙️ Settings & Privacy").run()
    assert not at.exception

    # Check for OCR Engine Status subheader
    subheaders = [s.value for s in at.subheader]
    assert any("OCR Engine Status" in s for s in subheaders)


def test_upload_scanned_pdf_without_tesseract_shows_guidance_without_crash():
    """
    Regression test for AttributeError: 'ExtractedDocument' object has no attribute 'ocr_available'.
    Verifies that uploading a scanned PDF (0 extractable chars) when Tesseract is not installed
    displays the actionable guidance warning banner without crashing.
    """
    from unittest.mock import patch
    from paperpilot.pdf_extractor import ExtractedDocument

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    at.file_uploader[0].upload("scanned_sample.pdf", b"%PDF-1.4 mock scanned file")
    extract_btn = [b for b in at.button if "Extract" in b.label][0]
    extract_btn.click()

    scanned_doc = ExtractedDocument(
        filename="scanned_sample.pdf",
        pages=[],
        total_pages=1,
        total_chars=0,
        is_scanned=True,
    )

    with patch("paperpilot.ocr.is_tesseract_available", return_value=False), \
         patch("paperpilot.pdf_extractor.extract_text_from_pdf", return_value=scanned_doc):
        at.run()
        assert not at.exception
        warnings = [w.value for w in at.warning]
        assert any("Scanned PDF Detected" in w for w in warnings)
        assert any("Tesseract-OCR" in w for w in warnings)


def test_upload_text_pdf_without_tesseract_succeeds(tmp_path, monkeypatch):
    """
    Verifies that uploading a text-based PDF when Tesseract is not installed
    succeeds completely without crashing or prompting for OCR.
    """
    from unittest.mock import patch
    from paperpilot.pdf_extractor import ExtractedDocument, ExtractedPage
    import app

    test_db = tmp_path / "test_upload_text.db"
    monkeypatch.setenv("PAPERPILOT_DB_PATH", str(test_db))
    monkeypatch.setattr(app, "DB_PATH", test_db)
    test_storage = PaperPilotStorage(db_path=test_db)
    monkeypatch.setattr(app, "storage", test_storage)

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    at.file_uploader[0].upload("os_2024.pdf", b"%PDF-1.4 mock text file")
    extract_btn = [b for b in at.button if "Extract" in b.label][0]
    extract_btn.click()

    text_doc = ExtractedDocument(
        filename="os_2024.pdf",
        subject="Operating Systems",
        year=2024,
        pages=[
            ExtractedPage(
                page_number=1,
                text="1. Explain the differences between preemptive and non-preemptive scheduling.\n2. Define thrashing in virtual memory.",
                char_count=100,
                extraction_method="text",
            )
        ],
        total_pages=1,
        total_chars=100,
        is_scanned=False,
    )

    with patch("paperpilot.ocr.is_tesseract_available", return_value=False), \
         patch("paperpilot.pdf_extractor.extract_text_from_pdf", return_value=text_doc):
        at.run()
        assert not at.exception
        # Verify papers and questions were saved to the database
        saved_papers = test_storage.get_papers()
        assert any(p["filename"] == "os_2024.pdf" for p in saved_papers)
        questions = test_storage.get_questions(source_file="os_2024.pdf")
        assert len(questions) >= 2


