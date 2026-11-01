# Run Global Career Architecture AI — Phase 14A + 14B

This release fixes local startup friction and adds real build/deployment
verification to CI. **It is not a claim of a completed live deployment.**
The execution environment used to prepare this release cannot reach npm/PyPI
or run Docker, PostgreSQL, or multi-region infrastructure.

## 1. Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine with the **Compose V2**
  plugin (Linux), running and available to your current user.
- A connected machine able to pull Docker images and npm/Python packages.
- Python 3.12+ to run the launcher (host installation, not required by Docker).
- Enough disk and RAM for backend ML dependencies; first builds are substantial.
- Free local ports **5173** (web) and **8000** (API).

You do not need a local Node/npm/Python virtual environment for the
Docker Compose app. Docker builds the React/TypeScript production assets
in a Node 22 builder image, then serves them with unprivileged nginx.

## 2. Start the complete stack

Extract `global-career-ai-phase14-runnable.zip`, open a terminal, and enter
the included `global-career-ai-phase14` directory:

```bash
python3 scripts/start_local.py check
python3 scripts/start_local.py start
```

The launcher creates a `.env` file with random local-only JWT, session and
encryption secrets if it does not exist. It refuses to replace an existing
`.env`, validates provided secrets and will not enable autonomous Phase 14
agent actions without an explicit security review. It then:

1. Checks Docker Engine and Compose V2.
2. Builds Postgres with pgvector, Redis, backend and **compiled web** images.
3. Applies Alembic migrations through **0012_phase14**.
4. Runs API, Celery worker, scheduler/beat, and web containers.
5. Checks API health/readiness, disabled-agent state, a real compiled JS
   asset, PostgreSQL pgvector, migration head and Phase 14 tables.

After a PASS, open:

- Web app: http://localhost:5173
- API/docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

Troubleshooting:

```bash
python3 scripts/start_local.py logs
docker compose ps
python3 scripts/start_local.py smoke
python3 scripts/start_local.py stop
```

`stop` preserves PostgreSQL and Redis volumes. To reset ALL local data,
explicitly run `docker compose down --volumes` (**destructive**).

### If the build fails

- `docker: command not found` or `Cannot connect to Docker daemon`:
  install/start Docker Desktop or Docker Engine with Compose V2.
- `npm ERR! ENOTCACHED` / `getaddrinfo ENOTFOUND` in frontend builder:
  allow registry.npmjs.org, configure your npm proxy, or build on a connected
  CI runner. No script can synthesize missing npm package contents offline.
- Python dependency installation failure: check container access to PyPI,
  storage and RAM; inspect `docker compose logs`.
- `unsafe JWT_SECRET` or `LOCAL_MASTER_KEYS_JSON`: your existing `.env`
  contains placeholders. Do not use `.env.example` unchanged. Remove the
  unused `.env` ONLY when no persistent data exists and let the launcher
  regenerate it, or configure new values manually while preserving encryption
  keys required to decrypt any existing records.
- Docker daemon works but ports busy: stop conflicting services, or adjust
  Compose port mapping and corresponding frontend API/CORS settings.
- Failed migrations: inspect `docker compose logs migrate` and validate the
  live database. Do NOT run `docker compose down --volumes` on valued data.

## 3. Frontend alone, without Docker

Requires Node.js 22 and internet/npm-registry access:

```bash
cd frontend
npm install --no-audit --no-fund
npm run build
npm run test:build
npm run dev
```

The production build checks TypeScript and emits Vite assets into `dist/`.
The default local API is `http://localhost:8000`; use the Docker stack or
start the backend and PostgreSQL separately before using API-dependent UI.
Do not describe a TypeScript parse-only check as a full Vite build.

## 4. Repeat the live checks in GitHub Actions

Push the repository to a GitHub repository with Actions enabled. Run
`.github/workflows/phase14-live-validation.yml` (workflow dispatch) or
push a branch. A connected `ubuntu-latest` runner performs:

- Actual npm dependency installation and React/Vite production build.
- Real built-asset verification.
- Docker Compose PostgreSQL/pgvector/Redis/backend/web startup.
- Alembic revision `0012_phase14` and required database tables.
- API health, readiness, Phase 14 default-deny and compiled JS HTTP smoke.
- Container log collection on failure and cleanup afterward.

Check both `frontend` and `live-compose` jobs are green. Only then can
these checks be reported as **verified in CI**. The current workspace
cannot execute them because it has neither online npm packages nor Docker.

## 5. Multi-region staging failover (separate, manual and disruptive)

Cloud active-active operation is NOT provisioned by the local Compose
stack. Provide independent staging regions, identity federation (SPIRE),
verified Phase 13 regional trust bundles, real global DNS/ingress,
cross-region transactional database consistency, runtime secrets, and
observability with operator sign-off. Validate the region identity in
the `/ready` response (`PHASE14_REGION_ID` per region).

The GitHub workflow `.github/workflows/phase14-staging-failover.yml`
requires the protected **staging** environment, a base64 staging
kubeconfig secret (`STAGING_KUBECONFIG_B64`), and environment variables:

- `STAGING_GLOBAL_URL`
- `STAGING_FAILED_REGION_URL`
- `STAGING_SURVIVOR_URL`
- `STAGING_SURVIVOR_REGION`
- `STAGING_FAILOVER_CONTEXT`

It is only a **manual workflow**. Input the exact acknowledgment
`FAILOVER STAGING` and approve the protected staging environment.
The drill checks survivor identity, isolates a staging Service selector,
looks for continued global traffic on the survivor, then restores the
original selector even if the drill fails. Do not run the drill in
production; Phase 13 trust restoration remains human-controlled.

**Pass criteria** require observed healthy global traffic on the survivor
after staging failure. A local dry run proves only CLI safety, not
active-active deployment or actual failover.

## Execution status of this supplied archive

- PASS: 24 dependency-light Phase 13/14 security tests.
- PASS: Phase 13 and 14 governance gates.
- PASS: 10 dependency-light local validator and failover-safety tests.
- PASS: Python compile and TypeScript syntax transpilation.
- PENDING: Real `npm install` and `npm run build` (unavailable packages).
- PENDING: Live PostgreSQL/Alembic and Docker Compose smoke (Docker absent).
- PENDING: Cloud multi-region failover (requires controlled staging).

The new launcher is ready to run on your Docker-enabled machine, but
none of the three pending infrastructure checks should be marked PASSED
until their real execution succeeds.

---

## Important — external validation still required

**Important:** The project-side setup and validation improvements are packaged, but I can't yet confirm that the full application runs successfully. Docker and PostgreSQL aren't available in this environment, and I couldn't download npm dependencies here.

- **Actual npm installation and Vite build:** require connected execution.
- **Live database and Docker deployment:** require Docker execution.
- **Real multi-region failover:** requires approved staging infrastructure.

These checks must remain **PENDING / NOT VERIFIED** until successfully executed in the required environment. See `RUN_PHASE14.md` and `PHASE14_BUILD_AND_LIVE_VALIDATION.md` for the execution procedures.

