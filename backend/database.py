"""Small SQLite helpers. Source sentences and explanations are never stored."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import Candidate, Recommendation

DB_PATH = Path(__file__).with_name("tiptype.db")


@contextmanager
def connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_candidates (
                session_id TEXT NOT NULL,
                writing_mode TEXT NOT NULL,
                candidate_word TEXT NOT NULL,
                context_score INTEGER NOT NULL CHECK (context_score BETWEEN 0 AND 100),
                style_score INTEGER NOT NULL CHECK (style_score BETWEEN 0 AND 100),
                grammar_score INTEGER NOT NULL CHECK (grammar_score BETWEEN 0 AND 100),
                fit_score INTEGER NOT NULL CHECK (fit_score BETWEEN 0 AND 100),
                final_rank INTEGER NOT NULL CHECK (final_rank BETWEEN 1 AND 8),
                accepted INTEGER NOT NULL DEFAULT 0 CHECK (accepted IN (0, 1)),
                timestamp TEXT NOT NULL,
                PRIMARY KEY (session_id, candidate_word),
                UNIQUE (session_id, final_rank)
            )
        """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS one_accepted_per_session
            ON recommendation_candidates (session_id) WHERE accepted = 1
        """)
        # Commit on success; roll back the whole transaction on an error.
        with connection:
            yield connection
    finally:
        connection.close()


def save_session(
    writing_mode: str,
    candidates: list[Candidate],
    ranked: list[Recommendation],
) -> str:
    session_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    candidates_by_word = {candidate.word: candidate for candidate in candidates}

    with connect() as connection:
        for final_rank, recommendation in enumerate(ranked, start=1):
            candidate = candidates_by_word[recommendation.word]
            connection.execute("""
                INSERT INTO recommendation_candidates (
                    session_id, writing_mode, candidate_word,
                    context_score, style_score, grammar_score,
                    fit_score, final_rank, accepted, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                session_id, writing_mode, candidate.word,
                candidate.context_score, candidate.style_score, candidate.grammar_score,
                recommendation.fit_score, final_rank, timestamp,
            ))
    return session_id


def accept_candidate(session_id: str, word: str) -> bool:
    """Select one displayed candidate atomically; return False if it doesn't exist."""
    with connect() as connection:
        # Acquire the write lock before checking/updating this selection.
        connection.execute("BEGIN IMMEDIATE")
        candidate = connection.execute("""
            SELECT 1 FROM recommendation_candidates
            WHERE session_id = ? AND candidate_word = ? AND final_rank <= 5
        """, (session_id, word)).fetchone()
        if candidate is None:
            return False

        connection.execute("""
            UPDATE recommendation_candidates SET accepted = 0 WHERE session_id = ?
        """, (session_id,))
        connection.execute("""
            UPDATE recommendation_candidates SET accepted = 1
            WHERE session_id = ? AND candidate_word = ?
        """, (session_id, word))
    return True
