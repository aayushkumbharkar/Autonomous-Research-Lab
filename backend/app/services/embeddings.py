"""
Embedding Service.

Singleton wrapper around sentence-transformers with LRU caching.
Loaded once at startup, reused across all requests.
"""

import hashlib
from functools import lru_cache
from typing import Optional

import numpy as np

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton
_model = None
_cache: dict[str, np.ndarray] = {}
_cache_max_size: int = 1024


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        logger.info("loading_embedding_model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding_model_loaded", model=settings.embedding_model,
                     dimension=_model.get_sentence_embedding_dimension())
    return _model


def _cache_key(text: str) -> str:
    """Generate cache key for a text."""
    return hashlib.md5(text.encode()).hexdigest()


def init_embeddings():
    """Pre-load the model at startup. Call from lifespan."""
    _get_model()
    settings = get_settings()
    global _cache_max_size
    _cache_max_size = settings.embedding_cache_size


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Uses LRU cache to avoid re-embedding identical texts.

    Args:
        texts: List of strings to embed
        batch_size: Processing batch size

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    global _cache

    model = _get_model()
    results = []
    uncached_indices = []
    uncached_texts = []

    # Check cache
    for i, text in enumerate(texts):
        key = _cache_key(text)
        if key in _cache:
            results.append((i, _cache[key]))
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # Embed uncached texts
    if uncached_texts:
        embeddings = model.encode(
            uncached_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        for idx, text, emb in zip(uncached_indices, uncached_texts, embeddings):
            key = _cache_key(text)
            # Evict oldest if cache is full
            if len(_cache) >= _cache_max_size:
                oldest_key = next(iter(_cache))
                del _cache[oldest_key]
            _cache[key] = emb
            results.append((idx, emb))

    # Sort by original index and stack
    results.sort(key=lambda x: x[0])
    return np.array([r[1] for r in results])


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string. Returns 1D array."""
    return embed_texts([query])[0]


def get_embedding_dimension() -> int:
    """Get the dimensionality of embeddings."""
    model = _get_model()
    return model.get_sentence_embedding_dimension()


def clear_cache():
    """Clear the embedding cache."""
    global _cache
    _cache = {}
    logger.info("embedding_cache_cleared")
