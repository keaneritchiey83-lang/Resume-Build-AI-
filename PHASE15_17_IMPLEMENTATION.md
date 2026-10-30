# Phases 15–17 implementation (2026-10-29)

This release extends the Phase 14 deployment recovery project and **does not certify a live production deployment**.

## Phase 15A — evidence-backed resume qualification mapping

Authenticated `POST /v1/phase15/resume/evidence-map` takes organization-scoped job requirements and explicit candidate evidence (`id`, `description`). Returns conservative lexical potential matches and gaps, each marked for human fact review. It **does not** create unverified credentials, claim ATS outcomes, or use arbitrary internet content. Evidence is processed per request and is not persisted by this endpoint. Phase 15B's production LLM drafting, export, and employer-specific templates are not part of this bounded release.

## Phase 16A — structured interview preparation

`POST /v1/phase16/interview/plan` generates competency-focused behavioral interview prompts and links any potential candidate evidence IDs. `POST /v1/phase16/interview/review` provides heuristic STAR coaching prompts, not a factual score or hiring probability. Both require authentication and organization membership. Phase 16B production live voice simulation and rubric calibration are not implemented.

## Phase 17A — fail-closed deployment evidence gate

`POST /v1/phase17/release/readiness` accepts up to eight unique operator-reported checks (npm, Vite build, backend tests, database upgrade, PostgreSQL health, Docker smoke, security review, staging failover). Only owners/admins may access this endpoint. It requires status, evidence URI and reviewer for a check to count as *reported evidence*. It **always returns `release_unblocked: false`** pending separate independent CI/CD validation and human change approval. No deployment, database migration, external job applications or failover is executed by this API. Phase 17B automated cross-region operation is not implemented.

## Example

All endpoints use existing session authentication, CSRF protections, and membership authorization. Request:

```json
{"organization_id":"<your-org-uuid>","requirements":["hydraulic maintenance diagnostics"],"evidence":[{"id":"work-1","description":"Performed hydraulic maintenance diagnostics on aircraft"}]}
```

## Verification

From `backend/`: `python -m pytest tests/test_phase15_17.py -q`.

For full deployment on a connected runner, follow `DEPLOYMENT_RECOVERY.md`. `npm install`, actual Vite build, PostgreSQL Alembic upgrade, Docker and staging failover remain pending until run in their respective environments. The new stateless endpoints do not add tables and do not require a new migration.
