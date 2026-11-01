# Phase 14 — frontend build and live database/deployment validation

This release adds **executable checks** for two previously unverified areas.
They are integrated into `.github/workflows/phase14-live-validation.yml`.
CI status must be observed on a connected GitHub runner; including a workflow
does **not** mean the checks have already passed.

## A. Frontend dependency install and production build

On a machine with npm registry access and Node.js 22:

```bash
cd frontend
npm install --no-audit --no-fund
npm run build
npm run test:build
```

The `build` command executes TypeScript and Vite; `test:build` verifies that
`dist/index.html` and referenced JavaScript/CSS assets exist and are nonempty.
The frontend Docker image now performs both checks during image creation,
so a broken frontend bundle fails the Docker build.

**Dependency lockfile:** The Phase 13/14 source does not contain a
`frontend/package-lock.json`. To make subsequent builds deterministic, run
`npm install` in a connected and trusted development environment, review
the resulting `package-lock.json`, commit it, then switch the CI and Docker
installation steps from `npm install` to `npm ci`. Do not invent a lockfile.

## B. Local live PostgreSQL + Docker Compose smoke validation

Requires a machine with Docker Engine and `docker compose`; pulls images
and Python/npm dependencies. Use a **disposable local CI database**, not
a production or shared development database.

```bash
# From the project root; only when there is NO pre-existing .env
python ops/phase14/validation/create_ci_env.py

# Builds containers; runs migrations; starts Postgres/pgvector, Redis, API,
# worker, beat, and frontend
docker compose up --build -d

# Checks real database migration and HTTP services
python ops/phase14/validation/live_smoke.py --wait-seconds 180

# Tear down the disposable stack and data after the test
docker compose down --volumes --remove-orphans
rm .env
```

The smoke test checks the actual database for:
- Alembic head `0012_phase14`, following `0011_phase13`;
- pgvector extension;
- `phase14_tokens`, `phase14_approvals`, `phase14_agent_memory`,
  `phase14_step_receipts`.

It also checks `GET /health`, database-backed `GET /ready`, default-disabled
Phase 14 `GET /v1/phase14/readiness`, and the frontend homepage on port 5173.

The CI env generator creates short-lived local random secrets, keeps Phase 14
autonomous execution disabled and refuses to replace an existing `.env`.
**Never run the `down --volumes` command on valuable or shared databases.**

## C. GitHub Actions

`.github/workflows/phase14-live-validation.yml` runs a `frontend` job and a
`live-compose` job for pushes, pull requests, and manual dispatch. The Compose
job creates disposable credentials, starts the actual stack, verifies the live
migration/health endpoints, and destroys the test data even on failure.
The normal `.github/workflows/ci.yml` also runs the Phase 14 governance
gate and validates frontend production assets.

## D. Still requires separate infrastructure testing

A successful local Compose smoke test **does not** certify production
deployments. A separate operator-approved staging run must validate active-active
regional routing, controlled failover and recovery, chaos policies, SLOs,
cross-region storage consistency, cloud IAM/SPIFFE federation and measured
capacity budgets. The existing `phase14-staging-failover.yml` remains a manual
gated exercise. Never auto-restore Phase 13 trust from a failed region.

## Validation in this sandbox (2026-10-29)

- **PASS:** 24 Phase 13/14 dependency-light security tests.
- **PASS:** 5 new validator unit tests.
- **PASS:** Phase 13 and Phase 14 governance gates, Python compile checks.
- **PASS:** Node syntax of asset verification script and YAML workflow parsing.
- **BLOCKED:** Frontend dependency installation. `npm install --offline`
  failed with `ENOTCACHED` for `@types/react`, so no real Vite bundle was
  produced or verified here.
- **NOT EXECUTED:** Live database migrations and Docker Compose smoke.
  Docker and a PostgreSQL/pgvector server are unavailable in this sandbox.
- **NOT EXECUTED:** Live multi-region/cloud failover or deployment.

**Do not label frontend or live database/deployment tests PASSED until a
connected CI environment has run them successfully.**

---

## Important — external validation still required

**Important:** The project-side setup and validation improvements are packaged, but I can't yet confirm that the full application runs successfully. Docker and PostgreSQL aren't available in this environment, and I couldn't download npm dependencies here.

- **Actual npm installation and Vite build:** require connected execution.
- **Live database and Docker deployment:** require Docker execution.
- **Real multi-region failover:** requires approved staging infrastructure.

These checks must remain **PENDING / NOT VERIFIED** until successfully executed in the required environment. See `RUN_PHASE14.md` and `PHASE14_BUILD_AND_LIVE_VALIDATION.md` for the execution procedures.

