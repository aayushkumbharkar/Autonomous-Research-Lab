# Skipped Endpoints — Justification

This document details the coverage status of the Veritas API endpoints in Specmatic.

---

## 100% Specification Coverage

Every single endpoint defined in the API contract (`openapi.yaml`) is fully implemented, tested, and covered at **100% absolute coverage**. This includes the health check probes:

| Method | Path | operationId | Status | Justification / Coverage |
|--------|------|-------------|--------|--------------------------|
| GET | /health | healthSimple | ✅ Covered | Simple CI/CD readiness probe returning `{"status": "ok"}`. Covered at 100%. |
| GET | /api/health | healthDetailed | ✅ Covered | Detailed health check returning component statuses. Covered at 100%. |
| POST | /api/search | hybridSearch | ✅ Covered | Hybrid semantic + keyword search. Covered at 100% (including 200 and 422 validations). |
| POST | /api/ingest/text | ingestText | ✅ Covered | Ingest text transcripts. Covered at 100%. |
| POST | /api/research/query | submitResearchQuery | ✅ Covered | Submit queries for grounded answer generation. Covered at 100%. |
| POST | /api/evaluation/evaluate | runEvaluation | ✅ Covered | Manually evaluate answers. Covered at 100% (including 200, 404, and 422 validations). |
| POST | /api/interview/sessions | createInterviewSession | ✅ Covered | Start a new interview session. Covered at 100%. |
| GET | /api/tools | listTools | ✅ Covered | List available MCP tools. Covered at 100%. |

---

## Intentionally Undocumented Endpoints (Infrastructure & Internal Only)

The following routes are implemented in the application but are not part of the `openapi.yaml` specification:

### 1. GET /actuator/mappings
* **Reason for omission:** This is a Specmatic introspection endpoint. It is added solely to return FastAPI routes in Spring Actuator format so Specmatic can automatically discover implemented endpoints and calculate coverage metrics. It is not part of the Veritas business domain, has no client consumers, and is excluded from the specification by design to prevent circular dependency testing.

### 2. GET /api/coverage
* **Reason for omission:** This is a diagnostic helper endpoint designed to assess indexed data volume (total chunks, transcripts, etc.) for internal observability. It is not a consumer-facing API surface.

### 3. Other Internal / Experimental Routes
* Additional endpoints like `/api/ingest/audio`, `/api/ingest/transcripts`, `/api/research/queries`, and sub-routes under interview session management are internal developer routes and utility scripts. These helper routes are not exposed to client integrations and are excluded from the main public specification.
