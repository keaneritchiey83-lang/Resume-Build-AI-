# Phase 15–17 B-track — CI execution, security review and staging failover

**Validation date:** October 29, 2026  
**Status:** local preflight completed; *not* a successful GitHub-hosted CI run or a production certification.

## Fixes made in this revision

- Fixed Phase 13 and Phase 14 governance gates to accept a newer semantic `APP_VERSION` while enforcing consistency with `backend/pyproject.toml`. Earlier gates incorrectly required `0.14.0` despite the Phase 15–17 application reporting `0.17.0`. Regression tests cover compatible versions, obsolete versions and mismatched versions.
- Changed local Compose-published API, frontend and optional sensor ports to bind to `127.0.0.1` by default. This is for local/CI deployments; production exposure must use a reviewed reverse proxy and separately reviewed network policies.
- Added `ops/phase15_17/security_review.py`: a **limited static configuration check** for temporary secrets, localhost port exposure, same-origin proxying, and staging failover guardrails. It is **not** an independent security assessment or vulnerability scan.
- Added `ops/phase15_17/run_release_checks.py`: a reproducible, evidence-writing preflight with explicit `PASS`, `FAIL`, and `BLOCKED` statuses and a `production_ready=false` result whenever an essential gate remains unverified.
- Added a non-disruptive GitHub Actions preflight (`.github/workflows/phase15-17-release-readiness.yml`) that runs on a clean Python 3.12 checkout with no backend runtime install. Its artifact is explicitly **preflight evidence only**.
- Enabled manual `workflow_dispatch` for `.github/workflows/ci.yml` and added the static security check to the Compose integration workflow. Protected staging failover remains separate and manual.
- Added dry-run failover execution to the local preflight and extra release regression tests.

## Actual observed execution (local, not GitHub-hosted)

| Test or gate | Outcome |
| --- | --- |
| Dependency-light deployment/release test suite | **22 passed** |
| Targeted backend Phase 13–17 test suite | **28 passed** |
| Phase 13 governance gate | **PASS** |
| Phase 14 governance gate | **PASS** (including its 17 tests) |
| Python source compilation | **PASS** |
| Static configuration review | **PASS** |
| Failover `DRY_RUN` (no cluster interaction) | **PASS** |
| GitHub workflow YAML parse | **14 files parse** (not a GitHub Actions execution) |
| npm install / production Vite bundle | **BLOCKED**: npm registry DNS fails with `EAI_AGAIN`; packages not present |
| Full backend test collection | **BLOCKED locally**: missing `pgvector` and other backend dependencies |
| Docker Compose, live PostgreSQL migration and end-to-end smoke | **BLOCKED**: no Docker runtime here |
| Real staging regional failover | **NOT EXECUTED**: requires protected staging environment and authorized outage |
| Independent security review / production approval | **NOT COMPLETED** |

Evidence: `reports/phase15-17-local-release-evidence.json` (full local checks) and `reports/phase15-17-clean-ci-preflight-evidence.json` (standard-library-only preflight).

## GitHub connection and launching real CI

A connected GitHub repository, `keaneritchiey83-lang/Resume-Build-AI-`, was found, but its default branch does **not** include this Phase 15–17 application's `frontend/`, `backend/` or CI workflows. **No repository files were modified and no workflow was triggered there.** Pushing only the workflow would not validate this application.

To execute CI, commit the **full source tree inside this ZIP**, including `.github/workflows`, into a GitHub repository intended to host the application. Review before publishing since the connected repository is public. Do **not** include local `.env`, credentials, resume uploads, databases, `node_modules`, or user information. Then use the Actions tab to trigger these workflows (or run `gh workflow run` from a properly configured GitHub CLI):

1. `ci.yml`: full backend tests, governance gates, frontend npm/TypeScript/Vite build, Terraform and Kubernetes validation.
2. `phase14-live-validation.yml`: on a GitHub-hosted runner with internet and Docker, a disposable Compose stack with pgvector migrations, web proxy smoke, sessions, CSRF, isolation and Phase 15–17 integration checks. This workflow **destroys its isolated CI volumes** at teardown; do not aim it at a real database.
3. `phase15-17-release-readiness.yml`: non-disruptive preflight artifact, **not** proof of full deployment success.

Review run-specific failed steps and logs, make the corresponding code/configuration fixes, push changes and rerun until all required jobs pass. Use a genuine npm-generated `frontend/package-lock.json` committed by a connected runner to enable reproducible `npm ci`; do not fabricate lockfiles. If DNS fails, repair the CI runner's network, DNS or approved registry mirror before claiming a frontend build.

## Staging and final approval

Staging failover must use a separately configured and **protected** GitHub `staging` environment with required human reviewers, correct cluster credentials and staging URLs. Confirm that the namespace and URLs are isolated from production before triggering `phase14-staging-failover.yml`. The workflow requires the exact manual confirmation `FAILOVER STAGING`. Arrange an approved impact window; independently verify traffic, service identity, restoration and rollback. A local dry-run is not a failover test.

Production release remains **blocked** until the full GitHub pipeline, the real disposable Compose smoke, an independent security review, and the approved staging regional failover have documented passing results. A green *preflight-only* job must not bypass these release conditions.

## Local commands to reproduce

```bash
python ops/phase15_17/run_release_checks.py
python ops/phase15_17/run_release_checks.py --light --output reports/preflight.json
python ops/phase15_17/security_review.py
python -m unittest discover -s ops/phase14/validation -p 'test_*.py' -v
```

Run the complete workflow only from a connected CI runner or appropriate authorized staging environment.
