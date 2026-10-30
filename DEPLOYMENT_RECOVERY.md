# Deployment recovery and verification (Phase 14)

## What was changed

The frontend defaults to same-origin API requests (`VITE_API_URL=`, rather than a remote user's localhost). Production nginx forwards `/v1/`, `/health` and `/ready` to the internal Compose `api:8000` service. The React application and its cookies can therefore use the same public origin in a Compose deployment. `VITE_API_URL` can still be set explicitly for custom deployments. Cross-origin OIDC/IdP configuration must be configured for the actual public hostname.

## Dependency installation

On a network-connected host with Node 22 and npm: `cd frontend && npm install --no-audit --no-fund && npm run build && npm run test:build`. Commit the resulting `package-lock.json` to the repository. On subsequent builds use `npm ci --no-audit --no-fund` for repeatable dependency resolution. The Dockerfile currently installs dependencies with `npm install` until an npm-generated lockfile is available; do not fabricate a lockfile. If DNS fails (`EAI_AGAIN`), fix host DNS, firewall/proxy and npm registry access; source code alone cannot restore external DNS.

## Compose and migrations

From the project root, copy `.env.example` to `.env`, replace all sample secrets with random secrets and confirm any optional external integrations. Keep `.env` out of source control. Run `docker compose config` then `docker compose up --build -d`. Verify with `docker compose ps`, `python ops/phase14/validation/live_smoke.py --wait-seconds 180` and `docker compose logs --tail=100`. The migration service should exit successfully after applying Alembic revisions; never delete production PostgreSQL volumes to force a passing test. The Compose development credentials and HTTP ports must be hardened before Internet exposure.

## Staging regional failover

The GitHub Action `.github/workflows/phase14-staging-failover.yml` requires explicit staging confirmation, a protected staging environment, staging kubeconfig and known deployment endpoints. Run its dry-run checks first, then perform the controlled drill only on authorized staging infrastructure. Do not infer a real region failover pass from a dry run or a local Compose deployment.

## Local preflight

`python ops/phase14/validation/check_toolchain.py` and `python -m unittest discover -s ops/phase14/validation -p 'test_*.py' -v` work even when Docker or npm registry access is unavailable. These are not substitutes for a production bundle, live migrations or a failover drill.

## Phases 15–17

Do not activate higher-phase services without their verified database revisions, API contracts, UI flows and threat-model tests. This package focuses on closing identified Phase 14 deployment portability gaps; it does **not** assert that Phases 15–17 are implemented or production-ready.
