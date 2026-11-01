# Phase 15–17 B-track: deployment integration validation

Date: 2026-10-29

| Check | Result | Scope |
|---|---|---|
| Targeted backend tests | PASS — 28 tests | Phase 13, Phase 14, Phase 15/16/17 A & B; **not** full backend suite |
| Deployment contract unit tests | PASS — 17 tests | Static routing, password generation, script contracts, simulated smoke helpers |
| Python bytecode compilation | PASS | Backend and deployment helpers |
| TypeScript parser/transpilation diagnostics | PASS | 4 frontend source/configuration files; **not** TS type checking or Vite bundling |
| YAML syntax parsing | PASS | Compose + two edited CI workflows |
| Full backend pytest suite | BLOCKED | Missing dependencies including `pgvector` and Agents SDK (`agents`) |
| npm dependency install / frontend production bundle | BLOCKED | This environment cannot resolve `registry.npmjs.org` |
| Docker Compose deployment | NOT RUN | Docker binary / daemon unavailable |
| PostgreSQL/Alembic live migration | NOT RUN | PostgreSQL/containers unavailable |
| Authenticated live end-to-end CI smoke | CONFIGURED, NOT RUN | `ops/phase15_17/integration_smoke.py` requires isolated deployed stack |
| Regional failover | NOT RUN | Requires approved staging cloud infrastructure |

No claims of fully operational deployment, migration success, or failover execution are made.

## Production approval

Do not release to public users until connected CI passes frontend npm install + Vite, full backend tests, Docker database initialization and migration, live `/ready` health, authenticated Phase 15–17 workflow smoke, plus security review. Do not run the synthetic-user smoke against production. Regional disaster recovery requires additional independently observed staging exercises and authorization.
