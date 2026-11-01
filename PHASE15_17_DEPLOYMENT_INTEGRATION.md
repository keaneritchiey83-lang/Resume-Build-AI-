# Phase 15–17 B-track deployment integration and verification

**Date:** October 29, 2026. **Status:** source changes packaged; connected application deployment not yet certified.

## Changes in this revision

1. Career Studio now has a responsive, organized UI for evidence-only resume drafting, gap review, interview practice, interview-question planning, and administrator-authorized *read-only* multi-region planning. Resume drafts export as UTF-8 TXT or escaped HTML; a user can open the HTML and print to PDF. Neither native DOCX nor native PDF is generated.
2. Docker Compose reads the PostgreSQL password from `.env` rather than embedding `career`. `scripts/start_local.py` generates matching random DB and API credentials in a private `.env` when absent, checks they match, and refuses to replace an existing one. **Do not re-use or modify an existing deployed PostgreSQL password without a coordinated credential rotation and backup.** Existing databases initialized with the old password will not accept a newly generated password automatically.
3. The frontend Docker build selects `npm ci` when a real npm-generated lockfile is committed and otherwise uses `npm install` for bootstrap. The CI workflow no longer requests a package-lock cache when none exists. Do not fabricate or hand-author a lockfile. When a connected environment first succeeds with `npm install`, review and commit `frontend/package-lock.json` and prefer `npm ci` everywhere.
4. The Phase 14 live Compose workflow now runs an additional Phase 15–17 authenticated integration smoke using the **public web proxy**. Tests create synthetic CI-only accounts to validate sign-in, CSRF, same-origin routing, organization isolation, draft HTML escaping, gap detection, interview feedback, and read-only failover defaults. The smoke refuses to run unless `--ack-isolated-stack` is explicitly provided. It persists synthetic user records; run it **only in a disposable CI/staging stack**, not production.

## Commands: connected development host

Prerequisites: working Docker Engine/Desktop with Compose V2, container registry access, DNS to npm and PyPI registries, and adequate disk/memory for Python ML dependencies. Use a new, isolated development database for first deployment.

```bash
python scripts/start_local.py check
python scripts/start_local.py start
python scripts/start_local.py smoke
python ops/phase15_17/integration_smoke.py --ack-isolated-stack --base-url http://127.0.0.1:5173
```

`check` checks Docker availability and local config, and generates `.env` once if missing. `start` builds containers, migrates the database, and performs live health and database checks. Inspect `docker compose logs --tail=150` if startup fails. `stop` preserves volumes; `docker compose down --volumes` destroys test data and must **never** be used against production data.

### Frontend production build

```bash
cd frontend
npm config get registry
npm install --no-audit --no-fund
npm run build
npm run test:build
```

DNS errors such as `EAI_AGAIN` or `Could not resolve host: registry.npmjs.org` require fixing the host's network, DNS, trusted mirror, or proxy configuration. Code changes alone cannot install unavailable external packages. Add the generated `package-lock.json` to version control after reviewing it; then `npm ci` is the preferred repeatable install.

### Backend

```bash
cd backend
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q app tests alembic scripts
```

The full suite depends on packages listed in `backend/pyproject.toml`. Missing `pgvector`, `redis`, `agents`, or other libraries prevent collection; a partial passing suite must not be portrayed as full validation.

### CI and operational approval

- `.github/workflows/phase14-live-validation.yml` is configured to run Docker Compose + real PostgreSQL and a real Vite build on GitHub-hosted runners. This archive does not prove GitHub Actions was executed; a repository push or manual workflow trigger is required.
- The staging failover workflow and approved, observable regional infrastructure remain separate prerequisites. The new Phase 17 operations endpoint only generates plans; it cannot change traffic, DNS, replication, or cloud infrastructure.
- A true release requires passed backend tests, installed frontend dependencies, compiled Vite assets, Alembic migration, pgvector availability, authenticated web-to-API integration, security review, and an authorized staging regional drill with recovery evidence.

## Validation observed in the packaging environment

- Targeted backend tests (`tests/test_phase15_17.py tests/test_phase15_17_b.py tests/test_phase14.py tests/test_phase13.py`): **28 passed**.
- Dependency-light Phase 14 deployment-validator tests: verified locally, see the current test report below.
- React/TypeScript source: transpiler syntax check passed; **full TypeScript type-check and Vite bundle not verified**.
- Full backend test collection: blocked by unavailable production dependencies (including `pgvector` and `agents`).
- `registry.npmjs.org` DNS: unavailable; npm install and production assets not verified.
- Docker, PostgreSQL service, Terraform, Kubernetes and real staging multi-region failover: unavailable / not executed here.

**Do not claim overall Phase 15–17 production-ready or fully functional solely from these local results.**
