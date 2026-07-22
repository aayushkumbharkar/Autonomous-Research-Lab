"""
Ingestion Service.

Accepts raw transcripts (text or audio), chunks them,
generates embeddings, and stores in both SQLite and ChromaDB.
"""

import asyncio
import uuid
from typing import Optional

import chromadb
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.transcript import Transcript, Chunk
from app.services.embeddings import embed_texts
from app.utils.chunking import chunk_text, ChunkResult
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level ChromaDB client and collection
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


def init_chroma():
    """Initialize ChromaDB client and collection. Called at startup."""
    global _chroma_client, _collection
    settings = get_settings()
    _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    _collection = _chroma_client.get_or_create_collection(
        name="research_chunks",
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("chroma_initialized",
                persist_dir=settings.chroma_persist_dir,
                doc_count=_collection.count())


def get_collection() -> chromadb.Collection:
    """Get the ChromaDB collection."""
    if _collection is None:
        init_chroma()
    return _collection


async def ingest_text(
    db: AsyncSession,
    text: str,
    filename: str,
    metadata: Optional[dict] = None,
) -> tuple[Transcript, list[Chunk]]:
    """
    Ingest a text transcript: chunk, embed, and store.

    Args:
        db: Database session
        text: Raw transcript text
        filename: Source filename
        metadata: Optional metadata dict

    Returns:
        Tuple of (Transcript, list of Chunks)
    """
    settings = get_settings()
    logger.info("ingesting_text", filename=filename, text_length=len(text))

    # Create transcript record
    transcript = Transcript(
        filename=filename,
        source_type="text",
        raw_text=text,
        metadata_json=metadata,
        status="processing",
    )
    db.add(transcript)
    await db.flush()  # Get the ID

    try:
        # Chunk the text
        chunk_results = chunk_text(
            text,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        if not chunk_results:
            transcript.status = "failed"
            transcript.error_message = "No chunks produced from text"
            logger.warning("no_chunks_produced", filename=filename)
            return transcript, []

        # Generate embeddings
        contents = [c.content for c in chunk_results]
        embeddings = embed_texts(contents)

        # Store in ChromaDB and SQLite
        collection = get_collection()
        chunks = []

        chroma_ids = []
        chroma_embeddings = []
        chroma_documents = []
        chroma_metadatas = []

        for i, (cr, emb) in enumerate(zip(chunk_results, embeddings)):
            embedding_id = str(uuid.uuid4())

            chunk = Chunk(
                transcript_id=transcript.id,
                content=cr.content,
                chunk_index=cr.chunk_index,
                speaker=cr.speaker,
                timestamp_start=cr.timestamp_start,
                timestamp_end=cr.timestamp_end,
                embedding_id=embedding_id,
            )
            db.add(chunk)
            chunks.append(chunk)

            chroma_ids.append(embedding_id)
            chroma_embeddings.append(emb.tolist())
            chroma_documents.append(cr.content)
            chroma_metadatas.append({
                "transcript_id": transcript.id,
                "chunk_index": cr.chunk_index,
                "speaker": cr.speaker or "",
                "timestamp_start": cr.timestamp_start or 0.0,
            })

        # Batch add to ChromaDB
        collection.add(
            ids=chroma_ids,
            embeddings=chroma_embeddings,
            documents=chroma_documents,
            metadatas=chroma_metadatas,
        )

        transcript.status = "processed"
        await db.flush()

        logger.info("ingestion_complete",
                     transcript_id=transcript.id,
                     chunk_count=len(chunks))

        return transcript, chunks

    except Exception as e:
        transcript.status = "failed"
        transcript.error_message = str(e)
        logger.error("ingestion_failed", filename=filename, error=str(e))
        raise


async def ingest_audio(
    db: AsyncSession,
    audio_bytes: bytes,
    filename: str,
    metadata: Optional[dict] = None,
) -> tuple[Transcript, list[Chunk]]:
    """
    Ingest an audio file: transcribe via Groq Whisper, then ingest as text.

    Args:
        db: Database session
        audio_bytes: Raw audio file bytes
        filename: Source filename
        metadata: Optional metadata dict

    Returns:
        Tuple of (Transcript, list of Chunks)
    """
    import openai

    settings = get_settings()
    logger.info("transcribing_audio", filename=filename, size_bytes=len(audio_bytes))

    try:
        client = openai.OpenAI(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key or "mock-key",
            timeout=settings.request_timeout,
        )
        loop = asyncio.get_event_loop()
        transcription = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=settings.whisper_model,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            ),
        )

        # Extract text and build timestamp-enriched transcript
        if hasattr(transcription, 'segments') and transcription.segments:
            lines = []
            for seg in transcription.segments:
                timestamp = f"[{int(seg.get('start', 0) // 60):02d}:{int(seg.get('start', 0) % 60):02d}]"
                lines.append(f"{timestamp} {seg.get('text', '').strip()}")
            text = "\n".join(lines)
        else:
            text = transcription.text if hasattr(transcription, 'text') else str(transcription)

        if metadata is None:
            metadata = {}
        metadata["source_type"] = "audio"
        metadata["original_filename"] = filename

        transcript, chunks = await ingest_text(db, text, filename, metadata)
        transcript.source_type = "audio"
        return transcript, chunks

    except Exception as e:
        # Create failed transcript record
        transcript = Transcript(
            filename=filename,
            source_type="audio",
            raw_text="",
            metadata_json=metadata,
            status="failed",
            error_message=f"Audio transcription failed: {str(e)}",
        )
        db.add(transcript)
        logger.error("audio_transcription_failed", filename=filename, error=str(e))
        return transcript, []


def get_all_chunk_documents() -> list[dict]:
    """Get all documents from ChromaDB for BM25 index building."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    results = collection.get(include=["documents"])
    documents = []
    for doc_id, content in zip(results["ids"], results["documents"]):
        documents.append({"id": doc_id, "content": content})
    return documents
