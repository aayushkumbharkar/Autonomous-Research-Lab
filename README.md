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

## 5. Running Contract Tests
Specmatic contract tests ensure that the API's implementation strictly adheres to the OpenAPI specification contract defined in [openapi.yaml](file:///openapi.yaml).
- **Prerequisites:** The Veritas backend must be active, running on `http://localhost:8000`, and running in **Contract Test Mode** (add `CONTRACT_TEST_MODE=true` and `RATE_LIMIT_ENABLED=false` to [backend/.env](file:///backend/.env) and run `docker compose up -d`). The scripts have built-in checks to ensure this.
- **Execution Command:**
  ```bash
  bash run_contract_tests.sh
  ```
- **What it does:** This runs contract verification tests inside a Docker container using the Specmatic test runner against the live backend endpoints. It uses [specmatic-contract.yaml](file:///specmatic-contract.yaml) as the configuration, which bypasses resiliency test generation to keep Example tests under developer API limits.
- **Results:** The CLI output reports passing/failing tests, and the final test results are saved as a JSON report to `contract_test_results.json` in the project root.

## 6. Running Resiliency Tests
Specmatic resiliency testing verifies that the API handles unexpected and malformed inputs gracefully. It generates contract-invalid inputs (wrong types, missing required fields, boundary violations) to ensure the backend rejects them with appropriate 400-series client errors instead of crashing or returning 500 Internal Server Errors.
- **Prerequisites:** The Veritas backend must be active, running on `http://localhost:8000`, and running in **Contract Test Mode** (add `CONTRACT_TEST_MODE=true` and `RATE_LIMIT_ENABLED=false` to [backend/.env](file:///backend/.env) and run `docker compose up -d`). The scripts have built-in checks to ensure this.
- **Execution Command:**
  ```bash
  bash run_resiliency_tests.sh
  ```
- **What it does:** It invokes the Specmatic test runner with the generative testing environment variable enabled (`SPECMATIC_GENERATIVE_TESTS=true`), mounting the default [specmatic.yaml](file:///specmatic.yaml) (which contains `schemaResiliencyTests: all`) and [openapi.yaml](file:///openapi.yaml) to execute negative validation testing against the live server.

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
The project is configured with a GitHub Actions workflow in [.github/workflows/specmatic-contract-tests.yml](file:///.github/workflows/specmatic-contract-tests.yml). The CI pipeline automatically spins up the Veritas backend service and executes:
1. Standard Specmatic contract tests using `run_contract_tests.sh`.
2. Specmatic resiliency tests using `run_resiliency_tests.sh`.

This ensures that every push to the `main` and `develop` branches undergoes rigorous API contract compliance and input resiliency validation.
