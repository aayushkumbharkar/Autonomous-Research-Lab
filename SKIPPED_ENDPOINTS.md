# Skipped Endpoints — Justification

This document records every API endpoint excluded from Specmatic contract
coverage enforcement, with a concrete rationale for each exclusion.
All other endpoints are covered at 100%.

---

## GET /health

**Reason:** Simple CI/CD readiness probe that returns `{"status": "ok"}`.

- Contains no business logic — it is a single-line FastAPI handler returning
  a hardcoded dict.
- Not part of any consumer contract: no client application calls this endpoint
  at runtime. It is invoked only by Docker health checks, load balancers, and
  CI pipelines (`curl -f http://localhost:8000/health`).
- Has no schema complexity: a fixed `{"status": "ok"}` response body with a
  single required string field constrained to the enum `["ok"]`.
- Explicitly modelled in `openapi.yaml` (operationId: `healthSimple`) with a
  `healthy` response example so the spec is complete, but it is intentionally
  not subject to coverage enforcement because infrastructure probes are not
  consumer-facing API surfaces.

**Decision:** Excluded from `minCoveragePercentage` enforcement.
The `openapi.yaml` entry is retained for documentation completeness only.

---

## GET /actuator/mappings

**Reason:** Specmatic introspection endpoint — not part of the Veritas API
contract.

- Added solely for Specmatic to discover all registered FastAPI routes and
  calculate true API coverage (analogous to Spring Boot Actuator).
- This endpoint is not consumed by any Veritas client (frontend, MCP tool,
  or external integrator) and is not documented in `openapi.yaml`.
- Its structure (Spring Actuator JSON format) is an implementation detail of
  the Specmatic toolchain, not a Veritas business concept.
- Including it in contract tests would create a circular dependency: Specmatic
  would test the endpoint it uses to discover what to test.

**Decision:** Not listed in `openapi.yaml`. Excluded from coverage by design.

---

## All Other Endpoints — Covered at 100%

| Method | Path | operationId | Covered |
|--------|------|-------------|---------|
| GET | /api/health | healthDetailed | ✅ |
| POST | /api/search | hybridSearch | ✅ |
| POST | /api/ingest/text | ingestText | ✅ |
| POST | /api/research/query | submitResearchQuery | ✅ |
| POST | /api/evaluation/evaluate | runEvaluation | ✅ |
| POST | /api/interview/sessions | createInterviewSession | ✅ |
| GET | /api/tools | listTools | ✅ |

Each of the above endpoints has:
- A named request body example (POST endpoints) matching a response example
  of the same name in `openapi.yaml`.
- A live FastAPI handler registered in `main.py` (discoverable via
  `/actuator/mappings`).
- Contract test coverage enforced by Specmatic (`minCoveragePercentage: 100`,
  `maxMissedOperationsInSpec: 0`, `enforce: true`).
