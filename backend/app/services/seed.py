"""
Automatic Seeder Service.

Populates the database and ChromaDB with initial seed transcripts if the system is empty.
"""

import json
from pathlib import Path
from sqlalchemy import select, func

from app.database import get_session_factory
from app.models.transcript import Transcript
from app.utils.logging import get_logger

logger = get_logger("seeder")

SEED_FILE_PATH = Path(__file__).parent.parent / "seed_transcripts.json"


async def seed_database_if_empty(force: bool = False) -> dict:
    """Seeds default transcripts if no transcripts exist in the database."""
    if not SEED_FILE_PATH.exists():
        logger.info("seed_file_not_found", path=str(SEED_FILE_PATH))
        return {"status": "error", "reason": f"Seed file not found at {SEED_FILE_PATH}"}

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(func.count(Transcript.id)))
        count = result.scalar() or 0

    if count > 0 and not force:
        logger.info("database_not_empty_skipping_seed", existing_count=count)
        return {"status": "skipped", "existing_count": count}

    logger.info("database_seeding_started", path=str(SEED_FILE_PATH), force=force)

    try:
        with open(SEED_FILE_PATH, "r", encoding="utf-8") as f:
            seed_data = json.load(f)

        from app.services.ingestion import ingest_text

        seeded_count = 0
        async with factory() as session:
            for item in seed_data:
                filename = item.get("filename", "seed_transcript.txt")
                text = item.get("text", "")
                metadata = item.get("metadata", {})

                if not text or not text.strip():
                    continue

                await ingest_text(db=session, text=text, filename=filename, metadata=metadata)
                seeded_count += 1
            
            await session.commit()

        # Re-build BM25 index after seeding
        from app.services.retrieval import init_bm25
        init_bm25()

        logger.info("seeding_completed_successfully", count=seeded_count)
        return {"status": "success", "seeded_count": seeded_count}
    except Exception as e:
        logger.error("seeding_failed", error=str(e), exc_type=type(e).__name__)
        return {"status": "error", "error": str(e)}
