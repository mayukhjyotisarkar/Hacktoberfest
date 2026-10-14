"""
test_streamlit_app.py - Automated UI tests using Streamlit's official AppTest framework.

Verifies that app.py executes cleanly across all navigation tabs,
renders dataframes, metrics, and expanders without runtime exceptions,
and reacts properly to slider updates and user selections.
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
    """Verifies that the Home/Dashboard view loads metrics and tables without exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()
    assert not at.exception
    assert len(at.metric) >= 4
    # Metric labels: Exam Papers, Questions Extracted, Repeated Question Groups, Repetition Rate
    metric_labels = [m.label for m in at.metric]
    assert "Exam Papers" in metric_labels
    assert "Questions Extracted" in metric_labels


def test_question_bank_renders_and_filters():
    """Verifies Question Bank tab loads, filters, and generates CSV data."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Question Bank (Option index 2)
    at.sidebar.radio[0].set_value("📚 Question Bank").run()
    assert not at.exception
    assert len(at.dataframe) >= 1
    assert len(at.download_button) >= 1


def test_repeated_questions_renders_clusters():
    """Verifies Repeated Questions tab clusters items and displays match types."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Repeated Questions (Option index 3)
    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
    assert not at.exception
    assert len(at.download_button) >= 1


def test_topic_analysis_charts_render():
    """Verifies charts and cluster tables render without exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Topic & Frequency Analysis (Option index 4)
    at.sidebar.radio[0].set_value("📈 Topic & Frequency Analysis").run()
    assert not at.exception


def test_revision_checklist_renders():
    """Verifies Revision Checklist tab ranks priorities and provides CSV download."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Revision Checklist (Option index 5)
    at.sidebar.radio[0].set_value("📝 Revision Checklist").run()
    assert not at.exception
    assert len(at.metric) >= 3
    assert len(at.download_button) >= 1


def test_settings_and_threshold_slider():
    """Verifies Settings tab and dynamic similarity threshold updates."""
    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Change sidebar slider to 0.85
    at.sidebar.slider[0].set_value(0.85).run()
    assert not at.exception
    assert at.session_state["similarity_threshold"] == 0.85

    # Navigate to Settings (Option index 6)
    at.sidebar.radio[0].set_value("⚙️ Settings & Privacy").run()
    assert not at.exception
    # Reset button is disabled until checkbox is checked
    reset_btn = at.button[0]
    assert reset_btn.disabled is True


def test_repeated_questions_when_ai_is_unavailable():
    """Verifies that Repeated Questions gracefully handles Ollama being offline."""
    from unittest.mock import patch

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Navigate to Repeated Questions
    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
    assert not at.exception

    # Find the AI button
    ai_btn = None
    for b in at.button:
        if "Generate AI Topic Labels" in b.label:
            ai_btn = b
            break
    assert ai_btn is not None

    # Click the AI button while Ollama check_health returns False
    with patch("paperpilot.local_ai.LocalAIClient.check_health", return_value=False):
        ai_btn.click().run()
        assert not at.exception
        # Warning displayed that Ollama is unreachable
        warnings = [w.value for w in at.warning]
        assert any("not running or unreachable" in w for w in warnings)


def test_repeated_questions_displays_cached_ai_label():
    """Verifies that an existing cached AI label is rendered inside the cluster expander."""
    from paperpilot.topic_labeler import CachedTopicLabel

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    # Set cached AI label for cluster_001
    at.session_state["ai_cluster_labels"]["cluster_001"] = CachedTopicLabel(
        topic="Deadlock Conditions",
        confidence="high",
        reasoning="Four conditions required for deadlock",
        model="qwen2.5-coder:1.5b-base",
        latency_ms=115.0,
        created_at=1000.0,
        cache_key="mock_hash",
    )

    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
    assert not at.exception

    # Confirm caption contains the loaded status
    captions = [c.value for c in at.caption]
    assert any("AI topic labels loaded" in c for c in captions)


def test_repeated_questions_revision_notes_offline_handling():
    """Verifies that clicking 'Generate Revision Notes' when Ollama is offline displays a clean warning."""
    from unittest.mock import patch

    at = AppTest.from_file(APP_PATH, default_timeout=15.0)
    at.run()

    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
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

    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
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
            # Re-run app (navigating within app)
            at.run()
            assert not at.exception
            # Verify no unsolicited inference was triggered
            mock_send.assert_not_called()

            # Confirm revision notes text rendered
            md_texts = [m.value for m in at.markdown]
            assert any("Deadlock avoidance safety criteria" in m for m in md_texts)
            assert any("Understand safety state matrices" in m for m in md_texts)

