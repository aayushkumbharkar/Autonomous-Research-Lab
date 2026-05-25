"""
BM25 Keyword Search Implementation.

In-memory BM25 index that is rebuilt on ingest.
Compatible with the RRF fusion in the HybridRetriever.
"""

import re
from rank_bm25 import BM25Okapi
from dataclasses import dataclass

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BM25Result:
    """Result from BM25 keyword search."""
    doc_id: str
    score: float
    rank: int


class BM25Index:
    """
    BM25 keyword search index.

    Maintains an in-memory index of all chunks.
    Must be rebuilt when new documents are ingested.
    """

    def __init__(self):
        self._corpus: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._index: BM25Okapi | None = None

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + punctuation tokenizer."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        return tokens

    def build(self, documents: list[dict]):
        """
        Build the BM25 index from documents.

        Args:
            documents: List of {"id": str, "content": str}
        """
        self._doc_ids = [doc["id"] for doc in documents]
        self._corpus = [self._tokenize(doc["content"]) for doc in documents]

        if self._corpus:
            self._index = BM25Okapi(self._corpus)
            logger.info("bm25_index_built", doc_count=len(self._corpus))
        else:
            self._index = None
            logger.warning("bm25_index_empty")

    def add_documents(self, documents: list[dict]):
        """
        Add documents to the existing index.
        Note: BM25Okapi doesn't support incremental adds, so we rebuild.
        """
        for doc in documents:
            self._doc_ids.append(doc["id"])
            self._corpus.append(self._tokenize(doc["content"]))

        if self._corpus:
            self._index = BM25Okapi(self._corpus)

    def search(self, query: str, top_k: int = 10) -> list[BM25Result]:
        """
        Search the index with a query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            Ranked list of BM25Results
        """
        if self._index is None or not self._corpus:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        scores = self._index.get_scores(tokens)

        # Get top-k indices
        scored_indices = [(i, float(s)) for i, s in enumerate(scores) if s > 0]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = scored_indices[:top_k]

        results = []
        for rank, (idx, score) in enumerate(top_indices):
            results.append(BM25Result(
                doc_id=self._doc_ids[idx],
                score=score,
                rank=rank + 1,
            ))

        return results

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)
