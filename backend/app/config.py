"""
Autonomous Research Lab - Configuration Module

Centralized configuration using Pydantic BaseSettings.
All settings are validated at startup (fail-fast principle).
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- API Keys ---
    groq_api_key: str = Field(..., description="Groq API key for LLM and Whisper")

    # --- Model Configuration ---
    groq_model: str = Field("llama-3.3-70b-versatile", description="Groq LLM model ID")
    groq_fast_model: str = Field("llama-3.1-8b-instant", description="Groq fast/cheap LLM model ID")
    whisper_model: str = Field("whisper-large-v3-turbo", description="Groq Whisper model ID")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Sentence-transformers model")

    # --- Storage ---
    chroma_persist_dir: str = Field("./data/chroma", description="ChromaDB persistence directory")
    sqlite_url: str = Field(
        "sqlite+aiosqlite:///./data/research_lab.db",
        description="SQLAlchemy database URL",
    )

    # --- Evaluation ---
    eval_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum acceptable eval score")
    max_retry_attempts: int = Field(3, ge=1, le=10, description="Max feedback loop retries")

    # --- Performance ---
    embedding_cache_size: int = Field(1024, description="LRU cache size for embeddings")
    retrieval_cache_ttl: int = Field(300, description="Retrieval cache TTL in seconds")
    request_timeout: float = Field(30.0, description="Timeout for external API calls")

    # --- Chunking ---
    chunk_size: int = Field(512, ge=64, le=2048, description="Chunk size in characters")
    chunk_overlap: int = Field(64, ge=0, le=512, description="Chunk overlap in characters")

    # --- Search ---
    default_top_k: int = Field(10, ge=1, le=100, description="Default retrieval top-k")
    semantic_weight: float = Field(0.6, ge=0.0, le=1.0, description="Semantic search weight in hybrid")
    keyword_weight: float = Field(0.4, ge=0.0, le=1.0, description="Keyword search weight in hybrid")

    # --- Server ---
    frontend_url: str = Field("http://localhost:5173", description="Frontend URL for CORS")
    log_level: str = Field("INFO", description="Logging level")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton instance — imported by all modules
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the settings singleton. Fails fast if env vars are missing."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
