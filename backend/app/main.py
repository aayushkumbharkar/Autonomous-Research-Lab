"""
Autonomous Research Lab — Main Application Entry Point.

FastAPI application with:
- Lifespan handler (init DB, ChromaDB, embeddings, BM25, tools)
- CORS middleware
- All API routers
- Health check endpoint
- Global error handling
"""

import os
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure data directory exists
data_dir = Path("./data")
data_dir.mkdir(exist_ok=True)
(data_dir / "chroma").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    from app.config import get_settings
    from app.utils.logging import setup_logging, get_logger
    from app.database import init_db, close_db
    from app.services.embeddings import init_embeddings
    from app.services.ingestion import init_chroma
    from app.services.retrieval import init_bm25
    from app.tools.registry import get_registry
    from app.tools.search_tool import SearchTool
    from app.tools.summarize_tool import SummarizeTool
    from app.tools.cluster_tool import ClusterTool
    from app.tools.evaluate_tool import EvaluateTool

    settings = get_settings()
    setup_logging()
    logger = get_logger("main")

    logger.info("startup_begin", log_level=settings.log_level)

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    # Initialize ChromaDB
    init_chroma()

    # Load embedding model (this downloads on first run)
    init_embeddings()

    # Build BM25 index from existing documents
    init_bm25()

    # Register MCP tools
    registry = get_registry()
    registry.register(SearchTool())
    registry.register(SummarizeTool())
    registry.register(ClusterTool())
    registry.register(EvaluateTool())
    logger.info("tools_registered", count=len(registry.list_tools()))

    logger.info("startup_complete")

    yield  # Application runs here

    # Shutdown
    await close_db()
    logger.info("shutdown_complete")


# Create application
app = FastAPI(
    title="Autonomous Research Lab",
    description=(
        "A self-evaluating, self-improving AI research platform. "
        "Conducts interviews, processes transcripts, retrieves insights, "
        "generates grounded answers with citations, verifies claims, "
        "and learns from failures."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from app.utils.logging import get_logger
    logger = get_logger("error_handler")
    logger.error("unhandled_exception",
                 path=request.url.path,
                 method=request.method,
                 error=str(exc),
                 exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "type": type(exc).__name__,
        },
    )


# Health check
@app.get("/api/health")
async def health_check():
    """System health check with component status."""
    from app.services.ingestion import get_collection
    from app.services.retrieval import _bm25_index

    collection = get_collection()

    return {
        "status": "healthy",
        "components": {
            "database": "connected",
            "chromadb": {
                "status": "connected",
                "document_count": collection.count(),
            },
            "bm25_index": {
                "status": "ready",
                "document_count": _bm25_index.doc_count,
            },
            "embedding_model": "loaded",
        },
        "version": "1.0.0",
    }


# Data coverage endpoint (new — addresses "data coverage awareness" feedback)
@app.get("/api/coverage")
async def data_coverage():
    """
    Data coverage awareness: how much data does the system have?
    Helps users understand if there's enough data for reliable answers.
    """
    from sqlalchemy import select, func
    from app.database import get_session_factory
    from app.models.transcript import Transcript, Chunk
    from app.services.ingestion import get_collection

    factory = get_session_factory()
    async with factory() as session:
        # Count transcripts
        result = await session.execute(select(func.count(Transcript.id)))
        transcript_count = result.scalar() or 0

        # Count chunks
        result = await session.execute(select(func.count(Chunk.id)))
        chunk_count = result.scalar() or 0

        # Distinct speakers
        result = await session.execute(
            select(func.count(func.distinct(Chunk.speaker))).where(Chunk.speaker.isnot(None))
        )
        speaker_count = result.scalar() or 0

    collection = get_collection()

    return {
        "total_transcripts": transcript_count,
        "total_chunks": chunk_count,
        "indexed_documents": collection.count(),
        "distinct_speakers": speaker_count,
        "coverage_assessment": (
            "good" if chunk_count >= 50
            else "moderate" if chunk_count >= 10
            else "limited" if chunk_count > 0
            else "empty"
        ),
    }


# Include routers
from app.api.ingestion import router as ingestion_router
from app.api.retrieval import router as retrieval_router
from app.api.research import router as research_router
from app.api.interview import router as interview_router
from app.api.evaluation import router as evaluation_router
from app.api.tools import router as tools_router

app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(research_router)
app.include_router(interview_router)
app.include_router(evaluation_router)
app.include_router(tools_router)
