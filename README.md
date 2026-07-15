---
title: Autonomous Research Lab Backend
emoji: 🌖
colorFrom: red
colorTo: purple
sdk: docker
pinned: false
---

# Veritas (Autonomous Research Lab)

## 1. Project Overview
Veritas is a closed-loop AI research platform built for systematic data ingestion, hybrid retrieval, granular claim verification, and continuous self-improvement. It shifts the paradigm from a simple generative AI wrapper to a verified system by validating LLM outputs against source material to prevent unchecked hallucinations. By combining dense semantic and sparse lexical hybrid retrieval, token-level claim verification, dual-run disagreement modeling, and a closed-loop feedback loop with persistent failure memory, the lab ensures that every response is verifiable, calibrated for risk, and capable of learning from its own errors.

## 2. Prerequisites
Running and testing Veritas requires the following:
- **Docker and Docker Compose:** (Recommended path) Required for starting the complete project stack containerized. Running via Docker ensures the correct Python runtime environment is used.
- **Java 17 or higher:** Required to run the Specmatic test JAR.
- **Python 3.11 or 3.12:** Python version 3.11 or 3.12 is required if running the backend locally. Note that Python 3.13 and higher are **not supported** due to the lack of precompiled PyTorch (torch) wheel availability for newer Python versions.

## 3. Specmatic License Setup
Specmatic runs on the built-in Open Source license. No license configuration is required.

## 4. Environment Setup
Before running anything, create a `.env` file in the project root. A template is provided:

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

```env
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # if used
DATABASE_URL=sqlite:///./veritas.db
CHROMA_HOST=localhost
CHROMA_PORT=8001
```

The `.env` file is gitignored and must never be committed. Without it, docker-compose will fail to start.

## 5. Specmatic JAR
The test runner downloads Specmatic automatically on first run and saves it to `~/.specmatic/specmatic.jar`.

To download manually:

```bash
mkdir -p ~/.specmatic
curl -L -o ~/.specmatic/specmatic.jar \
  https://github.com/specmatic/specmatic/releases/download/2.50.0/specmatic.jar
```

Java 17 or higher is required to run the JAR.

## 6. Running the Project
This approach automatically manages all dependencies, including pinning the backend runtime to Python 3.12.

1. Ensure your `.env` file is set up at the project root with the required keys.
2. Run the following command from the root directory to build and start both the backend and frontend services:
   ```bash
   docker-compose up -d --build
   ```
3. The backend will start on [http://localhost:8000](http://localhost:8000) and the frontend will start on [http://localhost:80](http://localhost:80).

To stop the services:
```bash
docker-compose down -v
```

## 7. Running Contract Tests
Specmatic contract and resiliency tests are unified into a single script. `schemaResiliencyTests: all` is set in [specmatic.yaml](specmatic.yaml), so both test types run in one Specmatic invocation.

- **Prerequisites:** The Veritas backend must be running on `http://localhost:8000`. Start it with `docker-compose up -d --build`.
- **Execution Command:**
  ```bash
  bash run_contract_tests.sh
  ```
- **What it does:**
  1. Automatically downloads the Specmatic JAR (v2.50.0) to `~/.specmatic/specmatic.jar` if not present.
  2. Configures the backend environment dynamically to enable mock LLM generation and disable API rate limiting during tests.
  3. Waits robustly for the Veritas backend to be healthy at `/health` (up to 120 seconds).
  4. Verifies the `/actuator/mappings` endpoint is ready.
  5. Runs the Specmatic JAR with `schemaResiliencyTests: all` as configured in [specmatic.yaml](specmatic.yaml), exercising all 8 spec endpoints with both example-based contract tests and generative resiliency tests.
  6. Restores the backend environment to standard mode upon completion.
- **Results:** HTML report → `build/reports/specmatic/test/html/index.html`. CTRF JSON → `build/reports/specmatic/test/ctrf/ctrf-report.json`.

### 7.1 Key Learnings: Enabling the Actuator for True Coverage
A critical lesson from this project is the difference between **tests passing** and **tests actually covering your endpoints**.

#### The Problem: 0% Coverage on 7 of 8 Endpoints in CI
The CI report showed `0% — not tested*!` for 7 of 8 endpoints even though every test scenario in `openapi.yaml` had a matching example and passed locally. The `*` meant "not eligible for coverage" and `!` meant "excluded by a filter" — but there were no filters. The real cause was that Specmatic could not calculate coverage because the `actuatorUrl` configured in `specmatic.yaml` was **unreachable inside the Specmatic Docker container** during the older Docker-based CI run. Without a successful actuator call, Specmatic does not know which routes the server actually implements, so it cannot match test runs to endpoints — resulting in 0% coverage for everything except the single endpoint tested by an inline example in the spec.

#### The Fix: Make the Actuator Reachable
Specmatic uses a [Spring Boot-compatible Actuator endpoint](https://docs.spring.io/spring-boot/docs/current/actuator-api/htmlsingle/#mappings) at `/actuator/mappings` to discover every route registered in the server. Without this, it falls back to spec-only coverage tracking, which is far less accurate.

Veritas is a FastAPI application, not Spring Boot. The fix was to implement a custom `/actuator/mappings` endpoint that returns all FastAPI routes in the exact JSON shape Specmatic expects:

```python
@app.get("/actuator/mappings", include_in_schema=False)
async def actuator_mappings():
    from fastapi.routing import APIRoute

    def collect_routes(route_list, prefix=""):
        result = []
        for route in route_list:
            if isinstance(route, APIRoute):
                full_path = prefix + route.path
                for method in route.methods:
                    result.append({
                        "handler": route.name or full_path,
                        "predicate": f"{method} {full_path}, produces [application/json]",
                    })
            elif hasattr(route, "routes"):
                route_prefix = getattr(route, "path", "") or ""
                result.extend(collect_routes(route.routes, prefix + route_prefix))
        return result

    return {
        "contexts": {
            "application": {
                "mappings": {
                    "dispatcherServlets": {
                        "dispatcherServlet": collect_routes(app.routes)
                    }
                }
            }
        }
    }
```

Once the actuator was reachable, the coverage table immediately filled from `0%` to `100%` for all 8 endpoints.

#### The Second Problem: CONTRACT_TEST_MODE Bypassing Real Logic
A `CONTRACT_TEST_MODE=true` environment variable had been added to CI to avoid needing external services (ChromaDB, embedding model) during tests. Every endpoint had bypass logic that returned hardcoded stub responses when this flag was set. This made contract tests pass but left the actual business logic entirely untested. Specmatic was validating stub data against the schema, not the real implementation.

**The fix:** Remove `CONTRACT_TEST_MODE=true` from CI entirely. FastAPI's SQLite database initialises cleanly without any external services, so the backend starts normally in CI. Endpoints that previously required ChromaDB or the embedding model now run against a freshly-initialised empty database, which is correct contract testing behaviour — Specmatic provides the request data and validates the response shape, not the content.

#### The Third Problem: Separate Jobs for Contract and Resiliency Tests
The original CI had two separate steps: one calling `run_contract_tests.sh` and one calling `run_resiliency_tests.sh`. The resiliency script used a `--filter` flag to restrict generative tests to a single endpoint, and it ran Specmatic via Docker with separate volume mounts. This was unnecessary complexity.

**The fix:** Set `schemaResiliencyTests: all` in `specmatic.yaml` and delete `run_resiliency_tests.sh`. A single `run_contract_tests.sh` invocation runs both contract and resiliency tests in one Specmatic pass. CI is simplified to a single job with a single artifact upload.

## 8. Running the AI Uncertainty Demo
Veritas includes a demo script to showcase how the system handles queries with high model uncertainty and self-corrects via the closed feedback loop.

- **Execution Command:**
  ```bash
  bash ai_uncertainty_demo/run_ai_uncertainty_demo.sh
  ```
- **Explanation of the 4-Step Flow:**
  1. **Topic Ingestion:** Ingests research transcripts into the SQLite database and ChromaDB vector store.
  2. **Baseline Search & Q&A:** Executes a standard search query and LLM answer generation.
  3. **Simulating Disagreement/Uncertainty:** Executes a dual-run generation check to detect disagreement and compute uncertainty.
  4. **Closed-Loop Self-Correction:** Logs the failure, performs retrieval expansion and query rewriting, and executes a successful retry run.

## 9. CI Pipeline
The project is configured with a GitHub Actions workflow in [.github/workflows/specmatic-contract-tests.yml](.github/workflows/specmatic-contract-tests.yml). The CI pipeline runs a **single job** that:
1. Starts the Veritas backend via `docker compose up -d --build` (no `CONTRACT_TEST_MODE` — real backend).
2. Verifies the `/actuator/mappings` endpoint is reachable (prerequisite for accurate coverage calculation).
3. Executes `run_contract_tests.sh`, which runs the Specmatic JAR once with `schemaResiliencyTests: all` set in [specmatic.yaml](specmatic.yaml) — covering both contract and resiliency tests in a single invocation.
4. Uploads the HTML and CTRF reports as a single CI artifact named `specmatic-report`.

This ensures that every push to `main` and `develop` branches undergoes rigorous API contract compliance and input resiliency validation, with accurate coverage reporting across all 8 endpoints.
