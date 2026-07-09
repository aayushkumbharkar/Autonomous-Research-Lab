# Skipped Endpoints — Justification

This document lists endpoints that are **intentionally excluded** from the
`openapi.yaml` specification and therefore from Specmatic contract coverage
enforcement. All endpoints defined in `openapi.yaml` are tested at 100%
absolute coverage and do **not** belong in this document.

---

## GET /actuator/mappings

**Why excluded from spec:**
This endpoint exists solely so Specmatic can discover all FastAPI routes and
calculate accurate coverage metrics. It mirrors the Spring Boot Actuator
`/actuator/mappings` response shape. It has no Veritas business logic, no
consumer contracts, and no client callers — including it in the spec would
create a circular dependency where Specmatic tests the endpoint it uses to
decide what to test.

**Why not in openapi.yaml:**
Infrastructure-only. Not part of the Veritas public API surface.

---

## GET /api/coverage

**Why excluded from spec:**
Internal diagnostic endpoint that returns aggregate counts of indexed chunks
and transcripts for developer observability. It is not consumed by any client
application (frontend, MCP tool, or external integrator) and exposes
implementation-level metrics that are not part of any consumer contract.

**Why not in openapi.yaml:**
Developer tooling only. Not part of the Veritas public API surface.

---

## All Spec Endpoints — 100% Covered (Not Listed Here)

The following endpoints are defined in `openapi.yaml` and are fully tested
by Specmatic. They do **not** belong in this document:

| Method | Path | Specmatic Status |
|--------|------|-----------------|
| GET | /health | 100% covered — 1 PASSED test |
| GET | /api/health | 100% covered — 1 PASSED test |
| POST | /api/search | 100% covered — 2 PASSED tests (200 + 422) |
| POST | /api/ingest/text | 100% covered — 1 PASSED test |
| POST | /api/research/query | 100% covered — 1 PASSED test |
| POST | /api/evaluation/evaluate | 100% covered — 3 PASSED tests (200 + 404 + 422) |
| POST | /api/interview/sessions | 100% covered — 1 PASSED test |
| GET | /api/tools | 100% covered — 1 PASSED test |

**Verified locally:** `Tests run: 11, Successes: 11, Failures: 0`
**Absolute Coverage: 100%**
