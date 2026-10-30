# Phases 15B–17B: B-track bounded implementation

Date: 2026-10-29. This extends the uploaded Phases 15–17 A-track foundation. **This is not production certification.**

## 15B — Evidence-controlled resume drafts

`POST /v1/phase15/resume/draft` (authenticated member) accepts a candidate name, target role, verified summary, job requirements, identified candidate evidence, and `general`, `technical`, or `federal` template selection. Returns a reviewable plaintext resume and HTML with safely escaped user content. The frontend Career Studio includes text download. HTML may be saved or printed to PDF by the user; this release does not generate native DOCX/PDF. Federal mode includes a completeness checklist, not automatic USAJOBS compliance certification. Lexical evidence linkage and gaps are retained; draft includes only user-provided facts. **Not** implemented: generative LLM composition, employer-specific layout tuning, native PDF/DOCX rendering, or ATS ranking predictions.

## 16B — Structured interview practice

`POST /v1/phase16/interview/simulate` (authenticated member) scores six observable text signals on a published rule-based, 30-point *practice* rubric, reports gaps, and proposes a fact-check question. The frontend provides question/answer practice. It is not a calibrated hiring predictor or a technical/factual validator. **Not** implemented: realtime microphone/voice interaction, streaming conversation, human-calibrated scoring, or session history storage.

## 17B — Multi-region operations planning (dry-run only)

`POST /v1/phase17/operations/plan` (organization owner/admin only) accepts a constrained list of regions and operator attestations, reports blockers and a stable plan identifier, and returns manual validation/cutover/rollback steps. It does not query infrastructure independently, perform traffic changes, mutate deployments, or enable automated failover. All production cutovers require out-of-band approvals and independently observed replication, consistency and service health. **Not** implemented: autonomous region failover, Kubernetes controllers, DNS cutover, production orchestration, or RPO/RTO verification.

## Security and data handling

B-track endpoints inherit existing auth, CSRF, and organization role enforcement. Pydantic limits fields, enum choices, unique evidence IDs, region IDs, and attestations. Resume HTML escapes user input. No new database tables or migrations. No user input is forwarded to an external model and no server-side storage is added. Review source changes and test with production credentials only in an approved environment.

## Verification performed

From `backend/`: `python -m pytest -q tests/test_phase15_17.py tests/test_phase15_17_b.py` → **9 passed**. Python compilation passed. Frontend `node_modules` absent, so `npm ci`, `npm run build`, and runtime UI validation NOT performed. PostgreSQL migration, Docker, and actual multi-region failover NOT executed. API integration against live auth/DB NOT verified. For complete checks see `DEPLOYMENT_RECOVERY.md`.

## Routes

- POST `/v1/phase15/resume/draft`
- POST `/v1/phase16/interview/simulate`
- POST `/v1/phase17/operations/plan`

## Release gating

Keep original Phase 17A `release_unblocked: false` until independently verified CI/CD, actual PostgreSQL migration, authorized security review and approved change-management evidence exist. Do not infer production readiness from operator submitted fields.
