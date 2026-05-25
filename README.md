# Autonomous Research Lab

A self-evaluating, self-improving AI research platform that conducts interviews, processes messy human data, retrieves relevant insights, generates grounded answers with citations, verifies claims, and learns from failures.

> **"I built an AI research system that doesn't just generate answers — it verifies its claims, measures its confidence, learns from past failures, and improves over time."**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Interview    │  │ Research     │  │ Evaluation           │  │
│  │ View (Chat)  │  │ View (Q&A)  │  │ View (Failure Replay)│  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API
┌─────────────────────────────┴───────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Ingestion   │  │ Hybrid       │  │ Research Agent         │ │
│  │ (STT+Chunk) │  │ Retrieval    │  │ (Generate + Cite)      │ │
│  └─────────────┘  │ (RRF Fusion) │  └───────────┬────────────┘ │
│                   └──────────────┘              │              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────▼────────────┐ │
│  │ Moderator   │  │ MCP Tool     │  │ Claim Verifier         │ │
│  │ Agent       │  │ Layer        │  │ (Truth Enforcement)    │ │
│  └─────────────┘  └──────────────┘  └───────────┬────────────┘ │
│                                                 │              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────▼────────────┐ │
│  │ Confidence  │  │ Feedback     │  │ Hybrid Evaluation      │ │
│  │ System      │  │ Loop (+      │  │ (LLM + Deterministic)  │ │
│  │ (Dual-Run)  │  │ Failure Mem) │  │                        │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ ChromaDB         │  │ SQLite           │                    │
│  │ (Vector Store)   │  │ (Structured Data)│                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## System Modules

### 1. Ingestion
- **Text**: Upload transcripts with speaker diarization and timestamp extraction
- **Audio**: Groq Whisper STT with automatic chunking
- **Chunking**: Sentence-aware splitting with configurable size/overlap
- **Storage**: Dual storage in SQLite (structured) + ChromaDB (vectors)

### 2. Hybrid Retrieval
- **Semantic Search**: ChromaDB cosine similarity via `all-MiniLM-L6-v2` embeddings
- **Keyword Search**: BM25Okapi for lexical matching
- **Fusion**: Reciprocal Rank Fusion (RRF) with configurable weights
- **Caching**: TTL-based retrieval cache, LRU embedding cache

### 3. Research Agent
- Retrieves context → generates grounded answer with `[N]` citations
- **Refusal mode**: Refuses to answer when confidence < 30%
- **Reasoning trace**: Logs full retrieval metadata for traceability

### 4. Claim Verification Layer ⭐
- **Two-stage verification**: Token overlap (fast) + semantic similarity (fallback)
- Classifies claims as `supported` / `partially_supported` / `unsupported`
- Hard-penalizes faithfulness score for unsupported claims
- This is the truth alignment enforcement layer

### 5. Confidence System ⭐
- **Dual-run disagreement**: Generates 2 answers at different temperatures
- Computes agreement score to measure output stability
- Multi-signal aggregation: eval score + claim support + context coverage + agreement
- Exposes `confidence` (0-1), `risk_level` (low/medium/high), and explanation

### 6. Hybrid Evaluation Engine ⭐
- **Deterministic signals**: Citation coverage (%), retrieval token overlap, claim support ratio
- **LLM-as-judge**: Faithfulness, coverage, specificity, retrieval quality (with rubrics)
- Composite score blends both signal types
- Faithfulness is hard-penalized by claim support ratio

### 7. Feedback Loop + Failure Memory ⭐
- **Failure Memory**: Stores `{failure_type, best_fix, success_count}` patterns
- On new query: checks memory for learned fixes → applies best fix first
- Falls back to escalation: prompt rewrite → retrieval expansion → weight adjustment
- Records improvements for future learning

### 8. Moderator Agent
- Adaptive AI interviewer with topic tracking
- Sliding context window to handle long conversations
- Session summarization on completion

### 9. MCP Tool Layer
- Tool registry with 4 tools: `search`, `summarize`, `cluster`, `evaluate`
- **LLM-driven tool selection**: Agent classifies query intent and picks the best tool
- Structured inputs/outputs for composability

---

## Frontend Views

### 1. Research View
- Query input → answer with inline citations
- **Trust Panel**: Confidence meter, risk badge, claim verification breakdown
- Evaluation score cards (4 dimensions)
- Data ingestion panel
- Reasoning trace (collapsible)

### 2. Interview View
- Chat UI with moderator/participant message bubbles
- Session management (start/end/list)
- Session summarization

### 3. Evaluation View
- Data coverage dashboard (transcripts, chunks, assessment)
- Recent evaluations table
- **Failure Replay**: Side-by-side retry comparison showing old→new answers and improvement

---

## Design Decisions & Tradeoffs

| Decision | Rationale | Tradeoff |
|----------|-----------|----------|
| Local embeddings (sentence-transformers) | No external API dependency, data stays local | ~300MB RAM, CPU-only speed |
| ChromaDB over FAISS | Simpler API, built-in persistence, metadata filtering | Less index tuning control |
| SQLite over PostgreSQL | Zero-config, sufficient for single-user | No concurrent writes |
| Hybrid eval (LLM + deterministic) | More robust than LLM-only judging | Added complexity |
| Claim verification via token overlap | Fast, deterministic, no API calls | May miss paraphrases (mitigated by semantic fallback) |
| RRF fusion over learned fusion | No training data needed | Fixed fusion, can't adapt to query type |
| Failure memory via SQLite | Simple, persistent, queryable | No semantic pattern matching (uses type-based lookup) |

---

## Known Limitations

1. **No auth**: Assumes internal deployment. Add API key auth for exposure.
2. **Single-user**: SQLite + in-memory BM25. Not horizontally scalable.
3. **No streaming**: Groq responses are awaited in full.
4. **Eval calibration**: LLM-as-judge scores should be calibrated against human judgments.
5. **Failure memory matching**: Uses failure-type matching, not semantic similarity on query patterns.
6. **No temporal weighting**: Doesn't prioritize recent data over older data.

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key ([console.groq.com](https://console.groq.com))

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Quick Test
```bash
# Health check
curl http://localhost:8000/api/health

# Ingest a transcript
curl -X POST http://localhost:8000/api/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"text": "John: The project went really well. We delivered on time.\nJane: I agree, the team collaboration was excellent.", "filename": "test.txt"}'

# Research query
curl -X POST http://localhost:8000/api/research/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How did the project go?"}'
```

---

## Where This System Can Fail

1. **Insufficient data**: With < 10 chunks, retrieval quality degrades. The system now shows data coverage warnings.
2. **Adversarial inputs**: Carefully crafted prompts could still trick the LLM judge. The deterministic signals provide a safety net.
3. **Score drift**: LLM judge scores may drift over time as the model is updated. Monitor calibration.
4. **Cold start**: Failure memory is empty at first. The system gets smarter after 10-20 queries.
5. **Context window limits**: Very long transcripts may lose information during chunking. Adjust `chunk_size` and `overlap`.

---

## License

MIT
