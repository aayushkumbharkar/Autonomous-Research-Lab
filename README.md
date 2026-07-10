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
Running and testing Veritas requires the following environment setup:
- **Docker and Docker Compose:** (Recommended path) Required for starting the complete project stack containerized. Running via Docker ensures the correct Python runtime environment is used.
- **Python 3.11 or 3.12:** Python version 3.11 or 3.12 is required to run the backend locally. Note that Python 3.13 and higher are **not supported** due to the lack of precompiled PyTorch (torch) wheel availability for newer Python versions.
- **Java 17+:** Required on the host machine only if you intend to run the Specmatic CLI directly outside of the containerized Docker environment.
- **Specmatic license.txt:** A valid Specmatic license file must be present at the root directory of the project for Specmatic commands to execute without license errors.

## 3. Specmatic License Setup
Specmatic requires a valid license to run contract and resiliency tests.
1. Generate your Specmatic trial license at [https://academy.specmatic.io](https://academy.specmatic.io) using your signed-in email address.
2. Save the license content as a file named `license.txt` in the project root directory.
3. Note: The `license.txt` file is excluded in `.gitignore` and must never be committed to the repository.

## 4. Running the Project

### Option A: Docker Compose (Recommended)
This approach automatically manages all dependencies, including pinning the backend runtime to Python 3.12.
1. Ensure your `license.txt` file is set up at the project root.
2. Run the following command from the root directory to build and start both the backend and frontend services:
   ```bash
   docker compose up -d --build
   ```
3. The backend will start on [http://localhost:8000](http://localhost:8000) and the frontend will start on [http://localhost:80](http://localhost:80).

### Option B: Local Python Setup
To run the backend locally on your host environment:
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment using Python 3.11 or 3.12:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   - **Windows PowerShell:**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Linux/macOS:**
     ```bash
     source .venv/bin/activate
     ```
4. Install all python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Copy the sample environment file and configure any necessary variables:
   ```bash
   cp .env.example .env
   ```
6. Start the development server:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## 5. Running Contract and Resiliency Tests

Specmatic contract and resiliency tests are unified into a **single script and a single CI job**. `schemaResiliencyTests: all` is set in [specmatic.yaml](specmatic.yaml), so both test types run in one Specmatic invocation — no separate resiliency script or job is needed.

- **Prerequisites:** The Veritas backend must be running on `http://localhost:8000`. Start it with `docker compose up -d --build` or the local Python setup above. No special mode flags are required — the backend runs in its normal production mode so that Specmatic exercises real business logic.
- **Execution Command:**
  ```bash
  bash run_contract_tests.sh
  ```
- **What it does:**
  1. Checks the backend is healthy at `/health`.
  2. Verifies the `/actuator/mappings` endpoint (used by Specmatic to discover all routes and calculate true API coverage).
  3. Runs the Specmatic JAR with `schemaResiliencyTests: positiveOnly` from [specmatic.yaml](specmatic.yaml), exercising all 8 spec endpoints with both example-based contract tests and generative resiliency tests (positive boundary variations) in one pass.
- **Results:** HTML report → `build/reports/specmatic/test/html/index.html`. CTRF JSON → `build/reports/specmatic/test/ctrf/ctrf-report.json`.

### 5.1 Schema Resiliency Levels and the 600-Invocation Limit
You can configure the strictness of generative tests under `specmatic.settings.test.schemaResiliencyTests` in [specmatic.yaml](specmatic.yaml):
- **`none`:** Disables schema resiliency validation. Only runs standard example-based tests.
- **`positiveOnly`:** Generates variations that represent valid bounds, types, enum values, and nullable constraints to verify successful (`200 OK`) handling. **This is the setting used in CI.**
- **`all`:** Generates both positive variations and negative boundary violations (e.g. invalid data types, missing required fields, boundary violations) to ensure the API returns appropriate 4xx errors.

**Why `positiveOnly` and not `all`?**
Specmatic's `all` mode generates a Cartesian product of mutations across every field, nested object, and array in both request and response schemas. For 8 endpoints with deeply nested schemas (e.g. `/api/research/query` has `confidence`, `citations`, `claim_verifications` arrays, each with multiple properties), this quickly exceeds the **600-invocation limit** of the Specmatic Enterprise trial license. `positiveOnly` runs only valid boundary variations — still meaningful resiliency testing — while keeping total invocations safely under the threshold.


## 6. Key Learnings: Enabling the Actuator for True Coverage

A critical lesson from this project is the difference between **tests passing** and **tests actually covering your endpoints**.

### The Problem: 0% Coverage on 7 of 8 Endpoints in CI

The CI report showed `0% — not tested*!` for 7 of 8 endpoints even though every test scenario in `openapi.yaml` had a matching example and passed locally. The `*` meant "not eligible for coverage" and `!` meant "excluded by a filter" — but there were no filters. The real cause was that Specmatic could not calculate coverage because the `actuatorUrl` configured in `specmatic.yaml` was **unreachable inside the Specmatic Docker container** during the older Docker-based CI run. Without a successful actuator call, Specmatic does not know which routes the server actually implements, so it cannot match test runs to endpoints — resulting in 0% coverage for everything except the single endpoint tested by an inline example in the spec.

### The Fix: Make the Actuator Reachable

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

Once the actuator was reachable (CI switched from Docker-in-Docker to running Specmatic as a JAR with `--network host`), the coverage table immediately filled from `0%` to `100%` for all 8 endpoints.

### The Second Problem: CONTRACT_TEST_MODE Bypassing Real Logic

A `CONTRACT_TEST_MODE=true` environment variable had been added to CI to avoid needing external services (ChromaDB, embedding model) during tests. Every endpoint had bypass logic that returned hardcoded stub responses when this flag was set. This made contract tests pass but left the actual business logic entirely untested. Specmatic was validating stub data against the schema, not the real implementation.

**The fix:** Remove `CONTRACT_TEST_MODE=true` from CI entirely. FastAPI's SQLite database initialises cleanly without any external services, so the backend starts normally in CI. Endpoints that previously required ChromaDB or the embedding model now run against a freshly-initialised empty database, which is correct contract testing behaviour — Specmatic provides the request data and validates the response shape, not the content.

### The Third Problem: Separate Jobs for Contract and Resiliency Tests

The original CI had two separate steps: one calling `run_contract_tests.sh` and one calling `run_resiliency_tests.sh`. The resiliency script used a `--filter` flag to restrict generative tests to a single endpoint, and it ran Specmatic via Docker with separate volume mounts. This was unnecessary complexity.

**The fix:** Set `schemaResiliencyTests: all` in `specmatic.yaml` and delete `run_resiliency_tests.sh`. A single `run_contract_tests.sh` invocation runs both contract and resiliency tests in one Specmatic pass. CI is simplified to a single job with a single artifact upload.

## 7. Running the AI Uncertainty Demo
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

## 8. CI Pipeline
The project is configured with a GitHub Actions workflow in [.github/workflows/specmatic-contract-tests.yml](.github/workflows/specmatic-contract-tests.yml). The CI pipeline runs a **single job** that:
1. Starts the Veritas backend via `docker compose up -d --build` (no `CONTRACT_TEST_MODE` — real backend).
2. Verifies the `/actuator/mappings` endpoint is reachable (prerequisite for accurate coverage calculation).
3. Executes `run_contract_tests.sh`, which runs the Specmatic JAR once with `schemaResiliencyTests: all` set in [specmatic.yaml](specmatic.yaml) — covering both contract and resiliency tests in a single invocation.
4. Uploads the HTML and CTRF reports as a single CI artifact named `specmatic-report`.

This ensures that every push to `main` and `develop` branches undergoes rigorous API contract compliance and input resiliency validation, with accurate coverage reporting across all 8 endpoints.
