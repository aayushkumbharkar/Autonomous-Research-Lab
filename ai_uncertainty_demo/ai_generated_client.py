"""
AI-Generated API Client for Veritas Research Platform.

This file simulates what an AI coding agent (like Copilot, Cursor, or ChatGPT)
might generate when asked to "write a Python client for the Veritas search API."

The AI has read partial docs and inferred the API shape, but made several
realistic mistakes that would slip past mock-based unit tests.

MISTAKES INTENTIONALLY INCLUDED:
  1. Wrong field name:  sends "query_text" instead of "query"
  2. Wrong endpoint:    POSTs to "/api/query" instead of "/api/search"
  3. Missing header:    omits Content-Type: application/json header
"""

import requests
from typing import Optional


class VeritasSearchClient:
    """Client for the Veritas hybrid search API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    # ── FLAWED version (AI-generated) ──────────────────────────────────
    def search(
        self,
        query_text: str,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Search the Veritas knowledge base.

        BUG 1: Parameter is named "query_text" — the real API expects "query".
        BUG 2: Endpoint is "/api/query" — the real endpoint is "/api/search".
        BUG 3: No Content-Type header — the API requires application/json.
        """
        url = f"{self.base_url}/api/query"       # ← WRONG: should be /api/search

        payload = {
            "query_text": query_text,             # ← WRONG: should be "query"
            "top_k": top_k,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
        }

        if filters:
            payload["filters"] = filters

        # BUG 3: No Content-Type header — requests *does* set it
        # automatically for json=, but here we use data= which does NOT
        response = requests.post(url, data=str(payload))  # ← WRONG: should use json=

        response.raise_for_status()
        return response.json()

    # ── FIXED version ──────────────────────────────────────────────────
    def search_fixed(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Corrected search method — matches the OpenAPI contract exactly.

        FIX 1: Parameter is "query" (matches contract field name).
        FIX 2: Endpoint is "/api/search" (matches contract path).
        FIX 3: Uses json= so requests sets Content-Type: application/json.
        """
        url = f"{self.base_url}/api/search"       # ✓ CORRECT endpoint

        payload = {
            "query": query,                        # ✓ CORRECT field name
            "top_k": top_k,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
        }

        if filters:
            payload["filters"] = filters

        response = requests.post(
            url,
            json=payload,                          # ✓ CORRECT: sets Content-Type
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()
        return response.json()


# ── Convenience wrappers used by the demo script ───────────────────────

def run_flawed_search(base_url: str = "http://localhost:8000") -> dict:
    """Run a search using the flawed AI-generated client."""
    client = VeritasSearchClient(base_url=base_url)
    return client.search(query_text="What are the key findings?", top_k=5)


def run_fixed_search(base_url: str = "http://localhost:8000") -> dict:
    """Run a search using the corrected client."""
    client = VeritasSearchClient(base_url=base_url)
    return client.search_fixed(query="What are the key findings?", top_k=5)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "flawed"
    base = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

    print(f"Running {mode} client against {base} ...")
    try:
        if mode == "fixed":
            result = run_fixed_search(base_url=base)
        else:
            result = run_flawed_search(base_url=base)
        print("SUCCESS:")
        import json
        print(json.dumps(result, indent=2))
    except requests.exceptions.HTTPError as e:
        print(f"HTTP ERROR: {e}")
        print(f"Response body: {e.response.text if e.response else 'N/A'}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"CONNECTION ERROR: {e}")
        sys.exit(1)
