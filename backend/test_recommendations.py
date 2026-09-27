"""Run with: python -m unittest -v. These tests never call the real OpenAI API."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from openai import APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import ValidationError

from main import app
from models import Candidate, CandidateBatch
from ranking import rank_candidates


def sample_candidates():
    # Deliberately unordered to catch accidental use of LLM order.
    return [
        Candidate(word=word, context_score=score, style_score=score,
                  grammar_score=score, explanation="A test explanation.")
        for word, score in [
            ("weak", 10), ("zebra", 90), ("best", 100), ("alpha", 90),
            ("middle", 70), ("good", 80), ("poor", 20), ("fair", 50),
        ]
    ]


class RankingTests(unittest.TestCase):
    def test_weighted_formula(self):
        candidate = Candidate(word="useful", context_score=90, style_score=80,
                              grammar_score=70, explanation="Fits the sentence.")
        self.assertEqual(rank_candidates([candidate])[0].fit_score, 82)

    def test_half_rounds_up(self):
        candidate = Candidate(word="useful", context_score=50, style_score=50,
                              grammar_score=52, explanation="Fits the sentence.")
        self.assertEqual(rank_candidates([candidate])[0].fit_score, 51)

    def test_all_ranks_and_order_independence(self):
        candidates = sample_candidates()
        ranked = rank_candidates(candidates)
        self.assertEqual([item.word for item in ranked], ["best", "alpha", "zebra", "good", "middle", "fair", "poor", "weak"])
        self.assertEqual(ranked, rank_candidates(list(reversed(candidates))))
        self.assertEqual([item.fit_score for item in ranked], [100, 90, 90, 80, 70, 50, 20, 10])

    def test_scores_require_integers_in_range(self):
        for bad_score in [-1, 101, 80.5, "80", True]:
            with self.subTest(score=bad_score), self.assertRaises(ValidationError):
                Candidate(word="test", context_score=bad_score, style_score=50,
                          grammar_score=50, explanation="A test.")

    def test_exactly_eight_distinct_words(self):
        for count in [7, 9]:
            with self.subTest(count=count), self.assertRaises(ValidationError):
                CandidateBatch(candidates=(sample_candidates() * 2)[:count])
        candidates = sample_candidates()
        candidates[-1] = candidates[0].model_copy(update={"word": "WEAK"})
        with self.assertRaises(ValidationError):
            CandidateBatch(candidates=candidates)

    def test_model_cannot_supply_fit_score(self):
        data = sample_candidates()[0].model_dump()
        data["fit_score"] = 100
        with self.assertRaises(ValidationError):
            Candidate.model_validate(data)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database_path = patch("database.DB_PATH", Path(directory.name) / "test.db")
        database_path.start()
        self.addCleanup(database_path.stop)
        self.client = TestClient(app)
        self.payload = {"sentence": "The idea was ____.", "mode": "Creative"}

    def test_sdk_parsing_through_endpoint_to_ranked_response(self):
        # Real SDK parser with fake HTTP transport; no paid request.
        def fake_openai(request):
            body = json.loads(request.content)
            self.assertEqual(json.loads(body["input"][1]["content"]), self.payload)
            schema = body["text"]["format"]["schema"]
            self.assertEqual(schema["properties"]["candidates"]["minItems"], 8)
            self.assertNotIn("fit_score", schema["$defs"]["Candidate"]["properties"])
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 0,
                "status": "completed", "model": "gpt-4.1-mini", "error": None,
                "incomplete_details": None,
                "output": [{"id": "msg_test", "type": "message", "role": "assistant",
                            "status": "completed", "content": [{
                                "type": "output_text", "annotations": [],
                                "text": CandidateBatch(candidates=sample_candidates()).model_dump_json(),
                            }]}],
            })

        sdk = OpenAI(api_key="test-only", http_client=httpx.Client(transport=httpx.MockTransport(fake_openai)))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), patch("llm.OpenAI", return_value=sdk):
            response = self.client.post("/recommend", json=self.payload)
        self.assertEqual(response.status_code, 200)
        results = response.json()["recommendations"]
        self.assertEqual([item["word"] for item in results], ["best", "alpha", "zebra", "good", "middle"])
        self.assertEqual(set(results[0]), {"word", "fit_score", "explanation"})

    def test_bad_input_does_not_call_openai(self):
        with patch("llm.OpenAI") as sdk:
            for payload in [{"sentence": "No blank", "mode": "Creative"},
                            {"sentence": "An ____ idea", "mode": "Unknown"}]:
                self.assertEqual(self.client.post("/recommend", json=payload).status_code, 422)
            sdk.assert_not_called()

    def test_missing_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), patch("llm.OpenAI") as sdk:
            self.assertEqual(self.client.post("/recommend", json=self.payload).status_code, 503)
            sdk.assert_not_called()

    def test_refused_or_incomplete_response(self):
        for status in ["completed", "incomplete"]:
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), patch("llm.OpenAI") as sdk:
                sdk.return_value.__enter__.return_value.responses.parse.return_value = SimpleNamespace(status=status, output_parsed=None)
                self.assertEqual(self.client.post("/recommend", json=self.payload).status_code, 502)

    def test_provider_errors_are_safe_and_actionable(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        errors = [
            (AuthenticationError("secret detail", response=httpx.Response(401, request=request), body=None), 503),
            (RateLimitError("secret detail", response=httpx.Response(429, request=request), body=None), 503),
            (APITimeoutError(request=request), 504),
            (ValueError("secret detail"), 502),
        ]
        for error, status in errors:
            with self.subTest(error=type(error).__name__), patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), patch("llm.OpenAI") as sdk:
                sdk.return_value.__enter__.return_value.responses.parse.side_effect = error
                response = self.client.post("/recommend", json=self.payload)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("secret detail", response.text)
                self.assertNotIn("test-only", response.text)

    def test_cors(self):
        response = self.client.options("/recommend", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")


if __name__ == "__main__":
    unittest.main()
