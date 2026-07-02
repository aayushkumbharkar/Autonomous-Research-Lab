"""
Unit tests for the AI-generated Veritas search client.

These tests use hand-rolled mocks that PASS despite the client being flawed.
This demonstrates the fundamental weakness of mock-based testing:
mocks faithfully reproduce whatever assumptions the developer (or AI) baked in,
including wrong field names, wrong endpoints, and wrong Content-Types.

The mocks here:
  - Accept ANY URL (don't validate the endpoint path)
  - Accept ANY request body (don't validate field names)
  - Return canned success responses regardless of input

Result: All tests pass → false confidence that the client is correct.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from ai_generated_client import VeritasSearchClient


class TestVeritasSearchClient(unittest.TestCase):
    """Unit tests that give FALSE CONFIDENCE in the flawed client."""

    def setUp(self):
        """Create a client instance for testing."""
        self.client = VeritasSearchClient(base_url="http://localhost:8000")

    def _make_mock_response(self, status_code=200, json_data=None):
        """Create a mock response that looks like a successful API call."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = json_data or {
            "query": "What are the key findings?",
            "results": [
                {
                    "chunk_id": "abc-123",
                    "content": "User engagement increased by 40% after the new onboarding flow.",
                    "score": 0.92,
                    "semantic_score": 0.95,
                    "keyword_score": 0.87,
                    "speaker": "Participant A",
                    "transcript_id": "tx-001",
                    "chunk_index": 3,
                }
            ],
            "total_results": 1,
            "search_metadata": {"method": "hybrid", "duration_ms": 45},
        }
        return mock_resp

    @patch("ai_generated_client.requests.post")
    def test_search_returns_results(self, mock_post):
        """Test that search() returns results — PASSES with flawed client."""
        mock_post.return_value = self._make_mock_response()

        # The client sends "query_text" (wrong) to "/api/query" (wrong)
        # but the mock doesn't care — it accepts anything
        result = self.client.search(query_text="What are the key findings?")

        self.assertIn("results", result)
        self.assertEqual(result["total_results"], 1)
        self.assertEqual(len(result["results"]), 1)

    @patch("ai_generated_client.requests.post")
    def test_search_result_has_expected_fields(self, mock_post):
        """Test that results contain the expected fields — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response()

        result = self.client.search(query_text="machine learning")

        first_result = result["results"][0]
        self.assertIn("chunk_id", first_result)
        self.assertIn("content", first_result)
        self.assertIn("score", first_result)
        self.assertIn("semantic_score", first_result)
        self.assertIn("keyword_score", first_result)
        self.assertIn("transcript_id", first_result)

    @patch("ai_generated_client.requests.post")
    def test_search_with_custom_top_k(self, mock_post):
        """Test that top_k parameter is accepted — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response()

        result = self.client.search(query_text="user feedback", top_k=5)

        # Mock was called — but we don't validate WHAT was sent
        mock_post.assert_called_once()
        self.assertIn("results", result)

    @patch("ai_generated_client.requests.post")
    def test_search_with_filters(self, mock_post):
        """Test that filters are passed through — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response()

        result = self.client.search(
            query_text="onboarding",
            filters={"speaker": "Participant A"},
        )

        mock_post.assert_called_once()
        self.assertIn("results", result)

    @patch("ai_generated_client.requests.post")
    def test_search_with_custom_weights(self, mock_post):
        """Test custom semantic/keyword weights — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response()

        result = self.client.search(
            query_text="research methodology",
            semantic_weight=0.8,
            keyword_weight=0.2,
        )

        mock_post.assert_called_once()
        self.assertEqual(result["total_results"], 1)

    @patch("ai_generated_client.requests.post")
    def test_search_handles_empty_results(self, mock_post):
        """Test handling of empty result set — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response(
            json_data={
                "query": "nonexistent topic",
                "results": [],
                "total_results": 0,
                "search_metadata": {"method": "hybrid", "duration_ms": 12},
            }
        )

        result = self.client.search(query_text="nonexistent topic")

        self.assertEqual(result["total_results"], 0)
        self.assertEqual(len(result["results"]), 0)

    @patch("ai_generated_client.requests.post")
    def test_search_metadata_present(self, mock_post):
        """Test that search metadata is included — PASSES despite bugs."""
        mock_post.return_value = self._make_mock_response()

        result = self.client.search(query_text="engagement patterns")

        self.assertIn("search_metadata", result)
        self.assertIn("method", result["search_metadata"])


class TestClientConfiguration(unittest.TestCase):
    """Test client configuration — these legitimately pass."""

    def test_default_base_url(self):
        """Test default base URL configuration."""
        client = VeritasSearchClient()
        self.assertEqual(client.base_url, "http://localhost:8000")

    def test_custom_base_url(self):
        """Test custom base URL configuration."""
        client = VeritasSearchClient(base_url="http://api.example.com:9000")
        self.assertEqual(client.base_url, "http://api.example.com:9000")

    def test_trailing_slash_stripped(self):
        """Test that trailing slashes are stripped from base URL."""
        client = VeritasSearchClient(base_url="http://localhost:8000/")
        self.assertEqual(client.base_url, "http://localhost:8000")


if __name__ == "__main__":
    unittest.main()
