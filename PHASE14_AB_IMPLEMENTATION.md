# Phase 14A+B — Implemented engineering changes

## Backend

- `backend/phase14/security.py`: Ed25519 signed/ledger-backed capability JWTs,
  exact scope attenuation, revocation, explicit directed trust links, origin user propagation.
- `backend/phase14/services.py`: one-time human review with origin human
  separation, encrypted tenant/agent/workflow vault, reserved step receipts,
  explicit sequential orchestration and policy-required checkpoints.
- `backend/app/phase14_runtime.py`: fail-closed Phase 13 active/approved manifest
  integration; only deterministic local audit digest handler registered.
- `backend/app/phase14_api.py`: original Phase 13 auth/tenant dependencies
  for issuance, review, memory, revocation and dispatch.
- `backend/app/phase14_metrics.py`: authenticated scrape endpoint and bounded
  labels; existing `/health` and new `/ready` endpoints.
- `backend/alembic/versions/0012_phase14_agents_operations.py`: migration
  following the original `0011_phase13`, without rewriting prior revisions.
- `frontend/src/App.tsx`: Phase 14 readiness and two-person approval review UI.

## Operations

- `k8s/phase14/overlays/{region-a,region-b}`: regional Kubernetes
  customizations built on existing `k8s/base` (not duplicate deployment name).
- `ops/phase14/terraform`: two active regions Route53 health+latency routing,
  cost-budget notification example (not clusters/global database).
- `ops/phase14/failover`: reversible staging-only selector drill, opt-in impact.
- `ops/phase14/slo`: Prometheus metrics, SLO query gate and alert expressions.
- `ops/phase14/capacity`: illustrative N-1 capacity/cost gates.
- `.github/workflows/phase14-security.yml`: security and capacity checks;
  `.github/workflows/phase14-staging-failover.yml`: manual staging exercise.

## Unchanged safety boundaries

Phase 13 governed model gateway continues to disable arbitrary tools;
Phase 13 DR trust restoration stays human-controlled; remote SPIFFE bundles
do not become trusted by fetching them; Phase 13 cryptographic snapshot and
release-signing checks remain in effect.

## Build and live environment validation additions

- `frontend/scripts/verify-build.mjs` and `npm run test:build` verify
  frontend output and enforce a real Vite production build during Docker image creation.
- `ops/phase14/validation/create_ci_env.py` provisions disposable,
  uncommitted CI-only secrets and leaves Phase 14 autonomous execution disabled.
- `ops/phase14/validation/live_smoke.py` checks a running PostgreSQL/pgvector
  database at Alembic head `0012_phase14`, Phase 14 tables and deployed API/web.
- `.github/workflows/phase14-live-validation.yml` runs connected frontend
  and disposable Docker Compose validation on GitHub Actions.
- `PHASE14_BUILD_AND_LIVE_VALIDATION.md` documents commands and pending
  tests. CI checks are **not equivalent to a live production deployment**.
