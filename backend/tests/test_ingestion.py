"""Tests for the chunking and ingestion utilities."""

from app.utils.chunking import chunk_text, ChunkResult


class TestChunking:
    """Test text chunking functionality."""

    def test_basic_chunking(self):
        text = "This is sentence one. This is sentence two. This is sentence three. " * 20
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=30)
        assert len(chunks) > 1
        assert all(isinstance(c, ChunkResult) for c in chunks)
        assert all(c.chunk_index == i for i, c in enumerate(chunks))

    def test_speaker_extraction(self):
        text = """John: I think the project went well overall.
Jane: I agree, but there were some challenges.
John: Can you elaborate on those challenges?
Jane: Sure, the main issue was communication."""
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) >= 1
        # Should detect speakers
        has_speaker = any(c.speaker is not None for c in chunks)
        assert has_speaker

    def test_timestamp_extraction(self):
        text = """[00:01] Hello everyone, welcome to the meeting.
[00:15] Let's start with the project update.
[01:30] Moving on to the next topic."""
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) >= 1
        # Should extract timestamps
        has_timestamp = any(c.timestamp_start is not None for c in chunks)
        assert has_timestamp

    def test_empty_text(self):
        chunks = chunk_text("")
        assert chunks == []

    def test_single_sentence(self):
        chunks = chunk_text("This is a single sentence.")
        assert len(chunks) == 1
        assert chunks[0].content == "This is a single sentence."

    def test_chunk_size_respected(self):
        text = "Word " * 500
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            # Allow some overflow for sentence boundary
            assert len(chunk.content) < 200


class TestBM25:
    """Test BM25 keyword search."""

    def test_build_and_search(self):
        from app.utils.bm25 import BM25Index

        index = BM25Index()
        docs = [
            {"id": "1", "content": "The quick brown fox jumps over the lazy dog"},
            {"id": "2", "content": "Python is a great programming language"},
            {"id": "3", "content": "Machine learning uses algorithms to learn from data"},
        ]
        index.build(docs)
        assert index.doc_count == 3

        results = index.search("python programming", top_k=2)
        assert len(results) > 0
        assert results[0].doc_id == "2"  # Python doc should be first

    def test_empty_search(self):
        from app.utils.bm25 import BM25Index

        index = BM25Index()
        results = index.search("anything")
        assert results == []


class TestClaimVerifier:
    """Test claim verification logic."""

    def test_supported_claim(self):
        from app.services.claim_verifier import verify_claims

        answer = "The project had 15 team members and was completed in 6 months."
        chunks = [
            {"id": "1", "content": "The project team consisted of 15 members and the project was completed in 6 months."},
        ]
        verified, ratio = verify_claims(answer, chunks)
        assert len(verified) >= 1
        assert ratio > 0.5

    def test_unsupported_claim(self):
        from app.services.claim_verifier import verify_claims

        answer = "The company was founded in 1999 and has offices in Tokyo."
        chunks = [
            {"id": "1", "content": "The weather today is sunny and warm."},
        ]
        verified, ratio = verify_claims(answer, chunks)
        assert len(verified) >= 1
        # Should have lower support ratio
        supported = [v for v in verified if v.status == "supported"]
        # Most claims should be unsupported
        assert ratio < 0.8

    def test_no_context(self):
        from app.services.claim_verifier import verify_claims

        answer = "Some important finding."
        verified, ratio = verify_claims(answer, [])
        assert ratio == 0.0

    def test_no_claims(self):
        from app.services.claim_verifier import verify_claims

        answer = "OK."
        verified, ratio = verify_claims(answer, [{"id": "1", "content": "data"}])
        assert ratio == 1.0  # No claims = vacuously true
