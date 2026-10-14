"""
storage.py - SQLite storage engine for PaperPilot.

Manages persistent local storage for uploaded question papers and extracted
questions. Provides ACID transactions, parameterized queries, and safe handling
of missing values, duplicate uploads, and user edits.
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import List, Dict, Any, Optional, Union, Generator
from datetime import datetime

from paperpilot.question_parser import QuestionItem

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "paperpilot.db"


class StorageError(Exception):
    """Custom exception raised when a database operation fails."""
    pass


class PaperPilotStorage:
    """
    SQLite persistence layer for papers and parsed/reviewed questions.

    Schema:
    -------
    papers:
      - filename (TEXT PRIMARY KEY): Unique PDF file name.
      - subject (TEXT NOT NULL): Academic course/subject name.
      - year (INTEGER): Examination year (nullable).
      - uploaded_at (TEXT): ISO timestamp when the paper was stored.
      - question_count (INTEGER): Number of active questions extracted.

    questions:
      - id (TEXT PRIMARY KEY): Unique UUID string.
      - question_number (TEXT): Delimiter label (e.g. '1.', 'Q2', '1(a)').
      - text (TEXT NOT NULL): Cleaned question text for similarity & revision.
      - raw_text (TEXT): Original raw text as extracted from PDF.
      - source_file (TEXT NOT NULL): References papers(filename).
      - source_page (INTEGER NOT NULL): 1-indexed page number in the PDF.
      - subject (TEXT NOT NULL): Subject name.
      - year (INTEGER): Examination year (nullable).
      - marks (TEXT): Marks string (e.g. '[10 Marks]', nullable).
      - is_excluded (INTEGER DEFAULT 0): 1 if student excluded this item from analysis.
    """

    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Yields an SQLite connection configured with Row factory, WAL mode, and foreign keys.
        Manages transactions and guarantees connection closure in finally block.
        Uses check_same_thread=False for thread safety across Streamlit execution threads.
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Creates the required tables and indexes if they do not exist."""
        try:
            with self._get_connection() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS papers (
                        filename TEXT PRIMARY KEY,
                        subject TEXT NOT NULL,
                        year INTEGER,
                        uploaded_at TEXT NOT NULL,
                        question_count INTEGER DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS questions (
                        id TEXT PRIMARY KEY,
                        question_number TEXT,
                        text TEXT NOT NULL,
                        raw_text TEXT,
                        source_file TEXT NOT NULL,
                        source_page INTEGER NOT NULL,
                        subject TEXT NOT NULL,
                        year INTEGER,
                        marks TEXT,
                        is_excluded INTEGER DEFAULT 0,
                        FOREIGN KEY (source_file) REFERENCES papers(filename) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_questions_source_file ON questions(source_file);
                    CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);
                    CREATE INDEX IF NOT EXISTS idx_questions_year ON questions(year);
                    CREATE INDEX IF NOT EXISTS idx_questions_excluded ON questions(is_excluded);
                """)
        except sqlite3.Error as e:
            raise StorageError(f"Database initialization failed: {e}") from e

    # -------------------------------------------------------------------------
    # Paper Operations
    # -------------------------------------------------------------------------

    def save_paper(
        self,
        filename: str,
        subject: str,
        year: Optional[int] = None,
        questions: Optional[List[QuestionItem]] = None,
        overwrite: bool = True,
    ) -> bool:
        """
        Saves a paper and its associated questions.

        If overwrite=False and the paper already exists, returns False to prevent
        duplicate paper records. If overwrite=True, replaces existing questions for
        that paper in an atomic transaction.
        """
        questions = questions or []
        now_iso = datetime.now().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if paper already exists
                cursor.execute("SELECT filename FROM papers WHERE filename = ?", (filename,))
                existing = cursor.fetchone()

                if existing and not overwrite:
                    return False

                if existing:
                    # Update paper record and clear old questions for this file
                    cursor.execute(
                        """
                        UPDATE papers
                        SET subject = ?, year = ?, uploaded_at = ?, question_count = ?
                        WHERE filename = ?
                        """,
                        (subject, year, now_iso, len(questions), filename),
                    )
                    cursor.execute("DELETE FROM questions WHERE source_file = ?", (filename,))
                else:
                    cursor.execute(
                        """
                        INSERT INTO papers (filename, subject, year, uploaded_at, question_count)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (filename, subject, year, now_iso, len(questions)),
                    )

                # Insert questions
                if questions:
                    q_rows = [
                        (
                            q.id,
                            q.question_number,
                            q.text,
                            q.raw_text,
                            filename,
                            q.source_page,
                            subject,
                            year if q.year is None else q.year,
                            q.marks,
                            0,
                        )
                        for q in questions
                    ]
                    cursor.executemany(
                        """
                        INSERT INTO questions (
                            id, question_number, text, raw_text, source_file,
                            source_page, subject, year, marks, is_excluded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        q_rows,
                    )
                return True
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save paper '{filename}': {e}") from e

    def get_papers(self) -> List[Dict[str, Any]]:
        """Retrieves all stored papers ordered by upload timestamp descending."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT filename, subject, year, uploaded_at, question_count FROM papers ORDER BY uploaded_at DESC"
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to fetch papers: {e}") from e

    def delete_paper(self, filename: str) -> bool:
        """Deletes a paper and all its associated questions via cascading foreign key."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM papers WHERE filename = ?", (filename,))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete paper '{filename}': {e}") from e

    # -------------------------------------------------------------------------
    # Question Operations
    # -------------------------------------------------------------------------

    def get_questions(
        self,
        source_file: Optional[str] = None,
        subject: Optional[str] = None,
        year: Optional[int] = None,
        include_excluded: bool = False,
    ) -> List[QuestionItem]:
        """
        Retrieves QuestionItem objects filtered by criteria.
        Excludes questions marked is_excluded=1 unless include_excluded=True.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id, question_number, text, raw_text, source_file, source_page, subject, year, marks FROM questions WHERE 1=1"
                params: List[Any] = []

                if not include_excluded:
                    query += " AND is_excluded = 0"
                if source_file:
                    query += " AND source_file = ?"
                    params.append(source_file)
                if subject:
                    query += " AND subject = ?"
                    params.append(subject)
                if year is not None:
                    query += " AND year = ?"
                    params.append(year)

                query += " ORDER BY source_file ASC, source_page ASC, id ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [
                    QuestionItem(
                        id=row["id"],
                        question_number=row["question_number"],
                        text=row["text"],
                        raw_text=row["raw_text"],
                        source_file=row["source_file"],
                        source_page=row["source_page"],
                        subject=row["subject"],
                        year=row["year"],
                        marks=row["marks"],
                    )
                    for row in rows
                ]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to retrieve questions: {e}") from e

    def get_question_by_id(self, question_id: str) -> Optional[QuestionItem]:
        """Retrieves a single question by its unique ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, question_number, text, raw_text, source_file, source_page, subject, year, marks
                    FROM questions WHERE id = ?
                    """,
                    (question_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return QuestionItem(
                    id=row["id"],
                    question_number=row["question_number"],
                    text=row["text"],
                    raw_text=row["raw_text"],
                    source_file=row["source_file"],
                    source_page=row["source_page"],
                    subject=row["subject"],
                    year=row["year"],
                    marks=row["marks"],
                )
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get question '{question_id}': {e}") from e

    def update_question(
        self,
        question_id: str,
        text: Optional[str] = None,
        question_number: Optional[str] = None,
        marks: Optional[str] = None,
        subject: Optional[str] = None,
        year: Optional[int] = None,
        is_excluded: Optional[bool] = None,
    ) -> bool:
        """
        Updates fields of a reviewed question.
        Returns True if a record was updated, False if question_id was not found.
        """
        fields = []
        params: List[Any] = []

        if text is not None:
            fields.append("text = ?")
            params.append(text)
        if question_number is not None:
            fields.append("question_number = ?")
            params.append(question_number)
        if marks is not None:
            fields.append("marks = ?")
            params.append(marks)
        if subject is not None:
            fields.append("subject = ?")
            params.append(subject)
        if year is not None:
            fields.append("year = ?")
            params.append(year)
        if is_excluded is not None:
            fields.append("is_excluded = ?")
            params.append(1 if is_excluded else 0)

        if not fields:
            return False

        params.append(question_id)
        sql = f"UPDATE questions SET {', '.join(fields)} WHERE id = ?"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                updated = cursor.rowcount > 0

                # Refresh question_count in papers table
                if updated:
                    cursor.execute("""
                        UPDATE papers
                        SET question_count = (
                            SELECT COUNT(*) FROM questions
                            WHERE source_file = papers.filename AND is_excluded = 0
                        )
                    """)
                return updated
        except sqlite3.Error as e:
            raise StorageError(f"Failed to update question '{question_id}': {e}") from e

    def delete_question(self, question_id: str) -> bool:
        """Deletes a question permanently by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Find the source file first to update paper count
                cursor.execute("SELECT source_file FROM questions WHERE id = ?", (question_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                source_file = row["source_file"]

                cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
                cursor.execute(
                    """
                    UPDATE papers
                    SET question_count = (
                        SELECT COUNT(*) FROM questions
                        WHERE source_file = ? AND is_excluded = 0
                    )
                    WHERE filename = ?
                    """,
                    (source_file, source_file),
                )
                return True
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete question '{question_id}': {e}") from e

    # -------------------------------------------------------------------------
    # Maintenance & Diagnostics
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, int]:
        """Returns high-level storage counts."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM papers")
                paper_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM questions WHERE is_excluded = 0")
                active_q_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM questions WHERE is_excluded = 1")
                excluded_q_count = cursor.fetchone()[0]

                return {
                    "total_papers": paper_count,
                    "active_questions": active_q_count,
                    "excluded_questions": excluded_q_count,
                }
        except sqlite3.Error as e:
            raise StorageError(f"Failed to retrieve stats: {e}") from e

    def clear_all(self) -> None:
        """Wipes all records from the database (for explicit project reset)."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM questions;")
                conn.execute("DELETE FROM papers;")
        except sqlite3.Error as e:
            raise StorageError(f"Failed to clear database: {e}") from e

