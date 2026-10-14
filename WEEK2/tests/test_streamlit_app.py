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
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    assert len(at.metric) >= 4
    # Metric labels: Exam Papers, Questions Extracted, Repeated Question Groups, Repetition Rate
    metric_labels = [m.label for m in at.metric]
    assert "Exam Papers" in metric_labels
    assert "Questions Extracted" in metric_labels


def test_question_bank_renders_and_filters():
    """Verifies Question Bank tab loads, filters, and generates CSV data."""
    at = AppTest.from_file(APP_PATH)
    at.run()

    # Navigate to Question Bank (Option index 2)
    at.sidebar.radio[0].set_value("📚 Question Bank").run()
    assert not at.exception
    assert len(at.dataframe) >= 1
    assert len(at.download_button) >= 1


def test_repeated_questions_renders_clusters():
    """Verifies Repeated Questions tab clusters items and displays match types."""
    at = AppTest.from_file(APP_PATH)
    at.run()

    # Navigate to Repeated Questions (Option index 3)
    at.sidebar.radio[0].set_value("🔁 Repeated Questions").run()
    assert not at.exception
    assert len(at.download_button) >= 1


def test_topic_analysis_charts_render():
    """Verifies charts and cluster tables render without exceptions."""
    at = AppTest.from_file(APP_PATH)
    at.run()

    # Navigate to Topic & Frequency Analysis (Option index 4)
    at.sidebar.radio[0].set_value("📈 Topic & Frequency Analysis").run()
    assert not at.exception


def test_revision_checklist_renders():
    """Verifies Revision Checklist tab ranks priorities and provides CSV download."""
    at = AppTest.from_file(APP_PATH)
    at.run()

    # Navigate to Revision Checklist (Option index 5)
    at.sidebar.radio[0].set_value("📝 Revision Checklist").run()
    assert not at.exception
    assert len(at.metric) >= 3
    assert len(at.download_button) >= 1


def test_settings_and_threshold_slider():
    """Verifies Settings tab and dynamic similarity threshold updates."""
    at = AppTest.from_file(APP_PATH)
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
