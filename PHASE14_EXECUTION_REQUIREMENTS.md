# Phase 14 — Important execution and validation requirements

## Important — external validation still required

**Important:** The project-side setup and validation improvements are packaged, but I can't yet confirm that the full application runs successfully. Docker and PostgreSQL aren't available in this environment, and I couldn't download npm dependencies here.

- **Actual npm installation and Vite build:** require connected execution.
- **Live database and Docker deployment:** require Docker execution.
- **Real multi-region failover:** requires approved staging infrastructure.

These checks must remain **PENDING / NOT VERIFIED** until successfully executed in the required environment. See `RUN_PHASE14.md` and `PHASE14_BUILD_AND_LIVE_VALIDATION.md` for the execution procedures.

### Suggested execution sequence

On a connected development or CI runner, install frontend dependencies and run the real build:

```bash
cd frontend
npm install --no-audit --no-fund
npm run build
npm run test:build
```

On a machine with Docker Engine and Compose V2, from the project root:

```bash
python3 scripts/start_local.py check
python3 scripts/start_local.py start
python3 scripts/start_local.py smoke
```

Multi-region failover must be tested separately in protected staging with explicit operator approval. Do not treat local smoke tests or a dry run as evidence of successful real failover.
