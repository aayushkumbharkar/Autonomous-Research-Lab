"""
Text Chunking Utilities.

Sentence-aware chunking that:
- Never splits mid-sentence
- Preserves speaker attribution per chunk
- Supports configurable chunk_size and overlap
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChunkResult:
    """Result of chunking a document."""
    content: str
    chunk_index: int
    speaker: Optional[str] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    metadata: dict = field(default_factory=dict)


# Pattern to detect speaker turns: "Speaker Name:" or "[Speaker Name]"
SPEAKER_PATTERN = re.compile(
    r'^(?:\[([^\]]+)\]|([A-Za-z][A-Za-z\s.]+?)):\s*',
    re.MULTILINE,
)

# Pattern to detect timestamps: [00:01:23] or (00:01:23) or 00:01:23
TIMESTAMP_PATTERN = re.compile(
    r'[\[\(]?(\d{1,2}):(\d{2})(?::(\d{2}))?[\]\)]?\s*'
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling common abbreviations."""
    # Split on sentence-ending punctuation followed by space + capital letter
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


def _parse_timestamp(match: re.Match) -> float:
    """Parse a timestamp match into seconds."""
    hours_or_minutes = int(match.group(1))
    minutes_or_seconds = int(match.group(2))
    seconds = int(match.group(3)) if match.group(3) else 0

    if match.group(3):  # HH:MM:SS format
        return hours_or_minutes * 3600 + minutes_or_seconds * 60 + seconds
    else:  # MM:SS format
        return hours_or_minutes * 60 + minutes_or_seconds


def _extract_speaker_and_content(line: str) -> tuple[Optional[str], str]:
    """Extract speaker name and content from a line."""
    match = SPEAKER_PATTERN.match(line)
    if match:
        speaker = match.group(1) or match.group(2)
        content = line[match.end():].strip()
        return speaker.strip(), content
    return None, line.strip()


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[ChunkResult]:
    """
    Chunk text into sentence-aware segments with speaker attribution.

    Args:
        text: Raw transcript text
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between consecutive chunks in characters

    Returns:
        List of ChunkResult with content, speaker, and metadata
    """
    if not text or not text.strip():
        return []

    lines = text.strip().split('\n')
    segments: list[dict] = []

    current_speaker = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for timestamp
        ts_match = TIMESTAMP_PATTERN.match(line)
        timestamp = None
        if ts_match:
            timestamp = _parse_timestamp(ts_match)
            line = line[ts_match.end():].strip()

        # Check for speaker
        speaker, content = _extract_speaker_and_content(line)
        if speaker:
            current_speaker = speaker
        if not content:
            continue

        segments.append({
            "content": content,
            "speaker": current_speaker,
            "timestamp": timestamp,
        })

    # Now build chunks from segments using sentence-aware boundaries
    chunks: list[ChunkResult] = []
    current_content = ""
    current_speaker = None
    current_ts_start = None
    current_ts_end = None
    chunk_index = 0

    for seg in segments:
        seg_content = seg["content"]
        seg_speaker = seg["speaker"]
        seg_ts = seg["timestamp"]

        # If adding this segment would exceed chunk_size, finalize current chunk
        if current_content and (len(current_content) + len(seg_content) + 1) > chunk_size:
            chunks.append(ChunkResult(
                content=current_content.strip(),
                chunk_index=chunk_index,
                speaker=current_speaker,
                timestamp_start=current_ts_start,
                timestamp_end=current_ts_end,
            ))
            chunk_index += 1

            # Overlap: keep the last portion of current_content
            if chunk_overlap > 0 and len(current_content) > chunk_overlap:
                # Find sentence boundary near overlap point
                overlap_text = current_content[-chunk_overlap:]
                sentence_start = overlap_text.find('. ')
                if sentence_start >= 0:
                    overlap_text = overlap_text[sentence_start + 2:]
                current_content = overlap_text
            else:
                current_content = ""

            current_ts_start = seg_ts

        if not current_content:
            current_ts_start = seg_ts

        # Append segment
        if current_content:
            current_content += " " + seg_content
        else:
            current_content = seg_content

        current_speaker = seg_speaker
        if seg_ts is not None:
            current_ts_end = seg_ts

    # Finalize last chunk
    if current_content.strip():
        chunks.append(ChunkResult(
            content=current_content.strip(),
            chunk_index=chunk_index,
            speaker=current_speaker,
            timestamp_start=current_ts_start,
            timestamp_end=current_ts_end,
        ))

    # Validate: no degenerate chunks (< 20 chars unless it's the only chunk)
    if len(chunks) > 1:
        chunks = [c for c in chunks if len(c.content) >= 20]
        # Re-index
        for i, c in enumerate(chunks):
            c.chunk_index = i

    return chunks
