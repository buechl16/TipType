"""Logging tests use a temporary database and never call OpenAI."""

import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from database import save_session
from main import app
from ranking import rank_candidates
from test_recommendations import sample_candidates


class LoggingTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / "test.db"
        database_path = patch("database.DB_PATH", self.db_path)
        database_path.start()
        self.addCleanup(database_path.stop)
        generator = patch("main.generate_candidates", side_effect=lambda request: sample_candidates())
        generator.start()
        self.addCleanup(generator.stop)
        self.client = TestClient(app)

    def new_session(self):
        response = self.client.post("/recommend", json={
            "sentence": "Private source sentence with ____.", "mode": "Academic",
        })
        self.assertEqual(response.status_code, 200)
        return response.json()

    def rows(self, session_id):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM recommendation_candidates WHERE session_id = ? ORDER BY final_rank",
                (session_id,),
            )]
        finally:
            connection.close()

    def accept(self, session_id, word):
        return self.client.post(f"/sessions/{session_id}/accept", json={"word": word})

    def test_success_logs_all_eight_and_returns_five(self):
        result = self.new_session()
        session_id = result["session_id"]
        self.assertEqual(str(UUID(session_id)), session_id)
        rows = self.rows(session_id)
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(result["recommendations"]), 5)
        self.assertEqual([row["final_rank"] for row in rows], list(range(1, 9)))
        self.assertEqual([row["candidate_word"] for row in rows[:5]],
                         [item["word"] for item in result["recommendations"]])
        candidates = {candidate.word: candidate for candidate in sample_candidates()}
        for row in rows:
            candidate = candidates[row["candidate_word"]]
            self.assertEqual(row["writing_mode"], "Academic")
            self.assertEqual(row["context_score"], candidate.context_score)
            self.assertEqual(row["style_score"], candidate.style_score)
            self.assertEqual(row["grammar_score"], candidate.grammar_score)
            self.assertEqual(row["fit_score"], rank_candidates([candidate])[0].fit_score)
            self.assertEqual(row["accepted"], 0)
            self.assertIsNotNone(datetime.fromisoformat(row["timestamp"]).tzinfo)
        self.assertEqual(len({row["timestamp"] for row in rows}), 1)
        self.assertEqual(set(rows[0]), {
            "session_id", "writing_mode", "candidate_word", "context_score",
            "style_score", "grammar_score", "fit_score", "final_rank", "accepted", "timestamp",
        })
        self.assertNotIn(b"Private source sentence", self.db_path.read_bytes())

    def test_latest_selection_wins_and_repeated_click_is_safe(self):
        session_id = self.new_session()["session_id"]
        for word in ["best", "alpha", "alpha", "good"]:
            response = self.accept(session_id, word)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"session_id": session_id, "word": word, "accepted": True})
            self.assertEqual([row["candidate_word"] for row in self.rows(session_id) if row["accepted"]], [word])

    def test_sessions_are_unique_and_selections_are_isolated(self):
        first = self.new_session()["session_id"]
        second = self.new_session()["session_id"]
        self.assertNotEqual(first, second)
        self.accept(first, "best")
        self.accept(second, "good")
        self.assertEqual([row["candidate_word"] for row in self.rows(first) if row["accepted"]], ["best"])
        self.assertEqual([row["candidate_word"] for row in self.rows(second) if row["accepted"]], ["good"])

    def test_invalid_selection_does_not_clear_existing_choice(self):
        session_id = self.new_session()["session_id"]
        self.accept(session_id, "best")
        for word in ["missing", "weak", "' OR 1=1 --"]:
            self.assertEqual(self.accept(session_id, word).status_code, 404)
        self.assertEqual(self.accept(str(uuid4()), "best").status_code, 404)
        self.assertEqual(self.accept("not-a-uuid", "best").status_code, 422)
        self.assertEqual([row["candidate_word"] for row in self.rows(session_id) if row["accepted"]], ["best"])

    def test_database_enforces_only_one_accepted_row(self):
        session_id = self.new_session()["session_id"]
        self.accept(session_id, "best")
        connection = sqlite3.connect(self.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError), connection:
                connection.execute(
                    "UPDATE recommendation_candidates SET accepted = 1 WHERE session_id = ? AND candidate_word = ?",
                    (session_id, "alpha"),
                )
        finally:
            connection.close()

    def test_partial_session_insert_is_rolled_back(self):
        session_id = self.new_session()["session_id"]
        candidates = sample_candidates()
        ranked = rank_candidates(candidates)
        # Force a duplicate primary key after some inserts have succeeded.
        ranked[-1] = ranked[0]
        with self.assertRaises(sqlite3.IntegrityError):
            save_session("Creative", candidates, ranked)
        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM recommendation_candidates").fetchone()[0], 8)
        finally:
            connection.close()
        self.assertEqual(len(self.rows(session_id)), 8)

    def test_failed_generation_creates_no_session(self):
        from fastapi import HTTPException

        with patch("main.generate_candidates", side_effect=HTTPException(status_code=502, detail="Failed")):
            response = self.client.post("/recommend", json={"sentence": "An ____ idea.", "mode": "Creative"})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(self.db_path.exists())

    def test_database_failure_returns_error(self):
        session_id = self.new_session()["session_id"]
        with patch("main.accept_candidate", side_effect=sqlite3.OperationalError("private detail")):
            response = self.accept(session_id, "best")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private detail", response.text)
        with patch("main.save_session", side_effect=sqlite3.OperationalError("private detail")):
            response = self.client.post("/recommend", json={"sentence": "An ____ idea.", "mode": "Creative"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(self.rows(session_id)), 8)


if __name__ == "__main__":
    unittest.main()
