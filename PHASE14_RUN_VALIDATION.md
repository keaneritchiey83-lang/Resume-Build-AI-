# Phase 14 runnable release — validation 2026-10-29

| Check | Outcome | Evidence |
|---|---|---|
| Phase 13/14 dependency-light security suite | PASS, 24 tests | `backend/tests/test_phase13.py`, `test_phase14.py`, `test_phase14_integration_contract.py` |
| Phase 13 governance gate | PASS, 17 checks | `backend/scripts/run_phase13_governance_gate.py` |
| Phase 14 governance gate | PASS | `backend/scripts/run_phase14_governance_gate.py` |
| Local launcher/live-smoke/failover-safety unit tests | PASS, 10 tests | `python -m unittest discover -s ops/phase14/validation -p 'test_*.py'` |
| Python compileall | PASS | Source and validation scripts |
| React source TypeScript syntax transpile | PASS, 3 files | Syntax only; no React/Vite dependency resolution |
| Real npm dependency installation | BLOCKED | Offline environment; npm registry packages absent |
| Real TypeScript + Vite frontend bundle build | PENDING | Run `frontend` CI job or connected machine |
| PostgreSQL, pgvector, live Alembic 0012 | PENDING | Docker/psql unavailable |
| Live Compose API, workers, compiled web | PENDING | Docker daemon unavailable |
| Active-active cloud failover | PENDING | Requires protected staging infrastructure and operator approval |

## Actual fixes

- `scripts/start_local.py` performs local secure configuration, preflight,
  production Docker Compose startup and actual smoke checks.
- The frontend Compose target now builds real React/Vite production files
  with `frontend/Dockerfile.prod`, checks the emitted assets, and serves them
  from unprivileged nginx on host port 5173.
- `live_smoke.py` now fetches a real compiled JS asset (not just the HTML
  shell), waits for API readiness before checking the migration database,
  and checks `0012_phase14`, pgvector, required tables and default-deny.
- The failover GitHub Action fixes shell continuations and adds explicit
  `FAILOVER STAGING` confirmation; the original staging protected environment
  and self-restoring selector drill remain mandatory.
- Added local configuration validation tests and non-disruptive staging
  failover dry-run tests.
- No cloud credentials, real keys or production secrets are bundled.

All remaining PENDING entries need tests executed in a connected development,
CI or approved staging environment; no fictitious green status has been given.

---

## Important — external validation still required

**Important:** The project-side setup and validation improvements are packaged, but I can't yet confirm that the full application runs successfully. Docker and PostgreSQL aren't available in this environment, and I couldn't download npm dependencies here.

- **Actual npm installation and Vite build:** require connected execution.
- **Live database and Docker deployment:** require Docker execution.
- **Real multi-region failover:** requires approved staging infrastructure.

These checks must remain **PENDING / NOT VERIFIED** until successfully executed in the required environment. See `RUN_PHASE14.md` and `PHASE14_BUILD_AND_LIVE_VALIDATION.md` for the execution procedures.

