"""
Ingestion API Router.

Endpoints for uploading transcripts (text and audio)
and listing ingested data.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.transcript import Transcript, Chunk
from app.schemas.ingestion import (
    IngestTextRequest,
    IngestResponse,
    TranscriptResponse,
    ChunkResponse,
)
from app.services.ingestion import ingest_text, ingest_audio
from app.services.retrieval import rebuild_bm25

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/text", response_model=IngestResponse)
async def ingest_text_endpoint(
    request: IngestTextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a text transcript: chunk, embed, and index."""
    if get_settings().contract_test_mode:
        return IngestResponse(
            transcript_id="tx-001",
            filename=request.filename,
            source_type="text",
            chunk_count=12,
            status="processed",
            message=f"Ingested 12 chunks from '{request.filename}'",
        )

    transcript, chunks = await ingest_text(
        db, request.text, request.filename, request.metadata,
    )

    # Rebuild BM25 index after ingestion
    if chunks:
        rebuild_bm25()

    return IngestResponse(
        transcript_id=transcript.id,
        filename=transcript.filename,
        source_type=transcript.source_type,
        chunk_count=len(chunks),
        status=transcript.status,
        message=f"Ingested {len(chunks)} chunks from '{transcript.filename}'",
    )


@router.post("/audio", response_model=IngestResponse)
async def ingest_audio_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest an audio file: transcribe via Whisper, then chunk and index."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    audio_bytes = await file.read()
    if len(audio_bytes) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    transcript, chunks = await ingest_audio(
        db, audio_bytes, file.filename,
    )

    if chunks:
        rebuild_bm25()

    return IngestResponse(
        transcript_id=transcript.id,
        filename=transcript.filename,
        source_type=transcript.source_type,
        chunk_count=len(chunks),
        status=transcript.status,
        message=(
            f"Transcribed and ingested {len(chunks)} chunks"
            if transcript.status == "processed"
            else f"Ingestion failed: {transcript.error_message}"
        ),
    )


@router.get("/transcripts", response_model=list[TranscriptResponse])
async def list_transcripts(db: AsyncSession = Depends(get_db)):
    """List all ingested transcripts."""
    stmt = select(Transcript).order_by(Transcript.created_at.desc())
    result = await db.execute(stmt)
    transcripts = result.scalars().all()

    responses = []
    for t in transcripts:
        # Count chunks
        count_stmt = select(func.count()).where(Chunk.transcript_id == t.id)
        count_result = await db.execute(count_stmt)
        chunk_count = count_result.scalar() or 0

        responses.append(TranscriptResponse(
            id=t.id,
            filename=t.filename,
            source_type=t.source_type,
            status=t.status,
            error_message=t.error_message,
            metadata_json=t.metadata_json,
            created_at=t.created_at,
            chunk_count=chunk_count,
        ))

    return responses


@router.get("/transcripts/{transcript_id}/chunks", response_model=list[ChunkResponse])
async def list_chunks(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all chunks for a transcript."""
    stmt = (
        select(Chunk)
        .where(Chunk.transcript_id == transcript_id)
        .order_by(Chunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    return [ChunkResponse.model_validate(c) for c in chunks]
