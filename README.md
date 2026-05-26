# Autonomous Research Lab

A closed-loop AI research platform built for systematic data ingestion, hybrid retrieval, granular claim verification, and continuous self-improvement.

---

## 1. Problem Statement

Modern enterprise environments struggle to deploy Large Language Models (LLMs) for high-stakes research and analysis due to four architectural failure modes:
1. **Unchecked Hallucinations:** Generative models synthesize facts that look convincing but lack any grounding in the source material.
2. **Implicit Trust:** Standard RAG pipelines present outputs as infallible truth without measuring model uncertainty or indexing source material alignment.
3. **Opaque Reasoning:** Users cannot verify which specific parts of a source document supported which assertion in a generated answer.
4. **Static Performance:** Systems remain static. If a query retrieves poor context or generates an incorrect answer today, it will fail exactly the same way tomorrow.

---

## 2. Solution Overview

The **Autonomous Research Lab** shifts the paradigm from a *generative wrapper* to a *verified system*. 

Rather than assuming model correctness, the platform treats LLM outputs as hypotheses that must undergo rigorous, automated validation before they are presented to the user. By combining **dense and sparse hybrid retrieval**, **token-level claim verification**, **dual-run disagreement modeling**, and a **closed-loop feedback system with persistent failure memory**, the lab ensures that every response is verifiable, calibrated for risk, and capable of learning from its own mistakes.

---

## 3. Core Capabilities

*   **Adaptive Interviewing:** Conducts structured participant interviews via an autonomous moderator agent, tracking covered vs. remaining topics in real time, and auto-ingesting transcripts.
*   **Hybrid Retrieval:** Merges dense vector search (semantic similarity) and sparse lexical search (BM25) using Reciprocal Rank Fusion (RRF) to capture both concept-level intent and exact keyword matches.
*   **Research & Citation:** Evaluates user queries against ingested corpora and synthesizes answers backed by precise, inline source citations.
*   **Granular Claim Verification:** Dissects generated answers into atomic assertions and verifies the truth of each assertion against the text of cited source chunks.
*   **Calibrated Confidence Modeling:** Employs a dual-run generation check to detect model instability and computes risk metrics (low, medium, high), refusing to answer when uncertainty is too high.
*   **Closed-Loop Self-Improvement:** Evaluates answers against deterministic and LLM-based quality rubrics. If an answer fails, the system logs the failure, applies corrective strategies (e.g., query rewriting, retrieval expansion), and retries.

---

## 4. Architectural Overview

The system is split into a **FastAPI backend** managing databases, retrieval, and agent logic, and a **React+TypeScript frontend** for interactive querying, interviewing, and evaluation replays.

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Interview    │  │ Research     │  │ Evaluation           │  │
│  │ View (Chat)  │  │ View (Q&A)   │  │ View (Failure Replay)│  │
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
│  │             │  │              │  │                        │ │
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

### Data Flow & Component Mapping:
1. **Ingestion Layer:** Raw transcripts are split using a sentence-aware chunker, ensuring no sentence is cut in half. Speaker names and timestamps are parsed and prepended to each chunk.
2. **Persistence Layer:** Structured metadata, sessions, and logs are kept in **SQLite**, while high-dimensional chunk embeddings (generated using a local `all-MiniLM-L6-v2` transformer) are indexed in **ChromaDB**.
3. **Retrieval Layer:** The system queries both ChromaDB (cosine similarity) and BM25Okapi, merging the results using RRF.
4. **Agent & Verification Layer:** The core research agent generates a draft response. The verification engine analyzes the draft, computes confidence metrics, and evaluates it.
5. **Feedback Loop Layer:** If the evaluation score is below 70%, the feedback loop triggers an escalation process, logs the failure type and fix in SQLite, and retries.

---

## 5. Key Engineering Differentiators

### A. The Claim Verification Layer
Instead of relying on an LLM to self-police its outputs, the platform runs a dedicated claim verification pipeline ([claim_verifier.py](file:///c:/Autonomous%20Research%20Lab/backend/app/services/claim_verifier.py)) immediately after generation:
1. **Extraction:** The generated answer is parsed into individual, atomic claims.
2. **Direct Mapping:** The system locates the source chunk cited for each claim.
3. **Two-Stage Validation:**
   - *Stage 1 (Token Overlap):* Computes direct n-gram overlap between the claim and the cited chunk (fast, deterministic).
   - *Stage 2 (Semantic Similarity):* If token overlap is low, the system falls back to semantic similarity using embeddings, classifying the claim as `supported`, `partially_supported`, or `unsupported`.
4. **Hard Penalty:** Any answer containing `unsupported` claims receives a severe penalty on its overall faithfulness score, halting execution and triggering the feedback loop.

### B. Confidence & Uncertainty Modeling
Generative models are prone to hallucinating under high-entropy conditions. To detect this, the confidence system ([confidence.py](file:///c:/Autonomous%20Research%20Lab/backend/app/services/confidence.py)) uses a **dual-run disagreement strategy**:
* **Stability Testing:** The system runs the generation prompt twice: once at temperature `0.2` (stable) and once at temperature `0.7` (creative).
* **Semantic Agreement Score:** The system measures the cosine similarity between the embeddings of the two outputs. High semantic disagreement indicates that the model is guesses and output is highly unstable.
* **Aggregated Confidence:** Disagreement is blended with the *claim support ratio* and *context coverage* into a final score (0.0 to 1.0).
* **Refusal Threshold:** If confidence drops below `30%`, the model enters **Refusal Mode**, choosing to declare uncertainty and request human review rather than risk presenting a false answer.

### C. Hybrid Evaluation Engine
The system grades answer quality through a hybrid formula ([evaluation.py](file:///c:/Autonomous%20Research%20Lab/backend/app/services/evaluation.py)) combining deterministic mathematics and LLM-as-a-judge rubrics:
$$\text{Composite Score} = (\text{LLM Faithfulness} \times 0.4) + (\text{Citation Coverage} \times 0.2) + (\text{Claim Support Ratio} \times 0.4)$$
* **Deterministic Signals:**
  - *Citation Coverage:* The percentage of generated sentences containing valid, active source citations.
  - *Retrieval Overlap:* The token-level overlap between the generated text and the retrieved context.
  - *Claim Support Ratio:* The percentage of atomic claims verified as `supported` or `partially_supported`.
* **LLM-as-a-Judge Signals:**
  - Standardized rubrics measuring *faithfulness*, *specificity*, and *retrieval quality*, preventing rating drift and bias.

### D. Self-Improving Feedback Loop & Failure Memory
When an answer fails to clear the evaluation threshold, the system does not fail silently. It learns and adapts ([feedback_loop.py](file:///c:/Autonomous%20Research%20Lab/backend/app/services/feedback_loop.py), [failure_memory.py](file:///c:/Autonomous%20Research%20Lab/backend/app/services/failure_memory.py)):
1. **Failure Classification:** The failure is classified (e.g., `low_faithfulness`, `low_citation_coverage`, `poor_retrieval`).
2. **Escalation Execution:** The feedback loop executes progressive retries (up to 3 attempts):
   - *Attempt 2:* Rewrites the query using an LLM query expansion prompt.
   - *Attempt 3:* Expands the retrieval count (e.g., top 10 chunks to top 15) and shifts the RRF fusion weight towards semantic search.
3. **Failure Memory SQLite Logging:** If a retry succeeds, the query pattern, failure type, and successful fix are written to SQLite.
4. **Proactive Fixes:** On future incoming queries, the system checks the failure memory. If a similar query pattern is found, the successful fix is applied proactively during the first run.

---

## 6. Product Walkthrough

### 1. Research View
The primary analytical workspace.
*   **Search Interface:** Query input with real-time response generation.
*   **Inline Citations:** Clicking on citations highlights the specific text chunk retrieved from the source document.
*   **Trust Panel:** A dedicated sidebar exposing the confidence meter, the claim verification breakdown (grounded vs. ungrounded claims), and a risk level badge (Low, Medium, High Risk).
*   **Reasoning Trace:** A collapsible section displaying the raw prompt context, retrieved chunks, and the step-by-step thinking trace.

### 2. Interview View
An interactive dialogue room for data gathering.
*   **Moderator Agent:** A dynamic interviewer guided by a sliding context window to maintain coherence across long sessions.
*   **Topic Tracker:** Renders a list of "Topics Covered" and "Suggested Topics Remaining," updating based on participant responses.
*   **Auto-Ingestion:** Clicking "End Session" automatically transcribes (if audio), summarizes, chunks, and indexes the transcript.

### 3. Evaluation View
The diagnostic control center.
*   **Data Coverage Dashboard:** Metrics highlighting the total transcripts, chunk count, and index health.
*   **Evaluation Logs:** A history of recent runs, their scores, confidence levels, and retry counts.
*   **Failure Replay Panel:** A side-by-side comparison interface showing the original failing answer, the applied correction strategy, and the final self-improved output.

---

## 7. Lifecycle of a Query: End-to-End Trace

The sequence diagram below details how a query traverses the system:

```
[ User ]        [ main.py ]     [ Retrieval ]     [ Research Agent ]   [ Claim Verifier ]  [ Evaluation ]   [ Failure Memory ]
   │                 │               │                   │                  │                │                 │
   │ ─── Query ────> │               │                   │                  │                │                 │
   │                 │ ── Check ───────────────────────────────────────────────────────────> │                 │
   │                 │ <─ Fix (e.g., Rewrite Query) ──────────────────────────────────────── │                 │
   │                 │ ─── Retrieve (Fused BM25 + Vector) ──>               │                │                 │
   │                 │ <── Top Chunks ───────────────────────               │                │                 │
   │                 │ ─── Generate Draft (w/ Citations) ───────────────>   │                │                 │
   │                 │ <── Draft Answer ─────────────────────────────────   │                │                 │
   │                 │ ─── Verify Claims & Disagreement ──────────────────> │                │                 │
   │                 │ <── Verified Claims & Confidence Score ──────────────│                │                 │
   │                 │ ─── Evaluate Answer ────────────────────────────────────────────────> │                 │
   │                 │ <── Composite Score (e.g., 62% - FAIL) ────────────────────────────── │                 │
   │                 │                                                                       │                 │
   │                 │ ─── Record Failure & Select Escalation Fix ───────────────────────────────────────────> │
   │                 │                                                                                         │
   │                 │ ─── Retry 2 (Expanded Search & Rewritten Query) ──>  │                │                 │
   │                 │ <── New Chunks & New Answer ───────────────────────  │                │                 │
   │                 │ ─── Verify New Answer ─────────────────────────────> │                │                 │
   │                 │ <── High Confidence ─────────────────────────────────                │                 │
   │                 │ ─── Re-Evaluate ────────────────────────────────────────────────────> │                 │
   │                 │ <── Composite Score (e.g., 88% - PASS) ────────────────────────────── │                 │
   │                 │                                                                                         │
   │                 │ ─── Log Successful Fix in SQLite ─────────────────────────────────────────────────────> │
   │ <── Return ───── │                                                                                         │
```

---

## 8. Technology Stack

*   **Backend Framework:** FastAPI (Asynchronous Python ASGI web framework)
*   **Vector Database:** ChromaDB (Local, persistent metadata-filtered vector index)
*   **Embedding Model:** `all-MiniLM-L6-v2` (Local transformer model via sentence-transformers)
*   **Database:** SQLite (SQLAlchemy + aiosqlite for async sessions)
*   **Inference API:** Groq SDK (Llama 3.3 70B & Whisper Large v3)
*   **Lexical Search:** `rank-bm25` (BM25Okapi python implementation)
*   **Frontend Library:** React (TypeScript, Vite, HTML5 semantic layout)
*   **Styling:** Custom Vanilla CSS (curated design tokens, glassmorphism, responsive grid)

---

## 9. Project Structure

```text
Autonomous-Research-Lab/
├── backend/
│   ├── app/
│   │   ├── api/             # API routes (ingestion, retrieval, research, interview, evaluation)
│   │   ├── models/          # SQLAlchemy Database models (research, transcript, interview)
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Core business logic (RAG, claims, confidence, feedback loop)
│   │   ├── tools/           # MCP tools registry and execution handlers
│   │   ├── utils/           # Helper libraries (logging configuration, text chunking)
│   │   ├── config.py        # Environment variables & runtime settings
│   │   ├── database.py      # SQLAlchemy engine initialization and session management
│   │   └── main.py          # Fast API application initialization and lifespan
│   ├── data/                # SQLite DB and Chroma vector data directory
│   ├── tests/               # Backend testing suite
│   ├── .env                 # Environment configuration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── assets/          # Fonts, icons, and static assets
│   │   ├── pages/           # Pages (ResearchView, InterviewView, EvaluationView)
│   │   ├── services/        # Frontend API client
│   │   ├── App.tsx          # Main application layout and router
│   │   └── main.tsx         # Application mount point
│   ├── index.html           # HTML5 entry template
│   ├── package.json         # Node.js dependencies and scripts
│   └── tsconfig.json        # TypeScript configuration
└── README.md                # System documentation
```

---

## 10. Getting Started

### Prerequisites
*   Python 3.11+
*   Node.js 18+
*   A Groq API key ([console.groq.com](https://console.groq.com))

### 1. Setup Backend
1. Navigate to the backend directory and create a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   - **macOS/Linux:** `source .venv/bin/activate`
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create your environment configuration file:
   ```bash
   cp .env.example .env
   ```
5. Open `.env` and fill in your `GROQ_API_KEY`.
6. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *Note: On first startup, the system will download the `all-MiniLM-L6-v2` embedding model (~90MB). The server is ready once the console prints `Application startup complete.`*

### 2. Setup Frontend
1. Open a new terminal window, navigate to the frontend directory, and install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Run the Vite development server:
   ```bash
   npm run dev
   ```
3. Open your browser and navigate to `http://localhost:5173`.

---

## 11. System Limitations

Every real-world engineering architecture has tradeoffs. Here is a breakdown of the platform's current design constraints:
1. **Single-Node DB Architecture:** SQLite and ChromaDB run locally. This setup simplifies development but cannot support multi-user write concurrency or horizontal scaling.
2. **Cold Start Failure Memory:** The failure memory system utilizes simple query-pattern matching. It does not perform semantic clustering on failure logs, meaning the system gets smarter only after 10-20 queries have established a history.
3. **Local Embedding Latency:** Generating embeddings on a CPU (via `sentence-transformers`) is slower than calling cloud APIs, adding 50–250ms of overhead per text chunking operation. This is mitigated by the LRU embedding cache.
4. **No Token Streaming:** Responses from the Groq API are awaited in full because claim verification and evaluation engines must process the entire text block before releasing the answer to the user.

---

## 12. Future Work

*   **Semantic Failure Memory:** Transition the failure memory system to a vector index to match and resolve queries based on semantic similarity.
*   **Streaming-First Verification:** Redesign the claim verifier to process chunks via token streams, showing verified sentences dynamically to lower perceived latency.
*   **Distributed Vector Storage:** Replace the embedded ChromaDB setup with a distributed database cluster (e.g., Qdrant or pgvector) to support production workloads.
*   **Temporal Grounding:** Introduce timestamp-aware weights during retrieval to prioritize recent documents and transcripts over older data.

---

## 13. System Philosophy

> **"Reliability is the only feature that matters."**

Most AI development focuses on making models *smarter*. The Autonomous Research Lab is built on the philosophy that **models will always fail**, and the real engineering challenge is building **systems** that detect, manage, and correct those failures before they reach the user.

By shifting trust away from prompt formatting and placing it in strict verification loops, we can build AI platforms that aren't just intelligent, but reliable.
