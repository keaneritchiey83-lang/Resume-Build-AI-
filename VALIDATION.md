# Phase 13A + 13B validation report

Validation date: 2026-09-16

## Passed in the export environment

- Python syntax compilation: **PASS**
  - `backend/app`
  - `backend/tests`
  - `backend/alembic`
  - `backend/scripts`
- Dependency-light Phase 13 security tests: **PASS**
  - 7/7 tests
  - prompt-injection scoring
  - deterministic object hashing
  - public-only SPIFFE bundle validation
  - HTTPS-only peer endpoints
  - peer endpoint allowlisting
- Phase 13 governance gate: **PASS**
  - 17/17 checks
- Alembic migration chain: **PASS**
  - `0001_phase3 -> 0002_phase4 -> 0003_phase5 -> 0004_phase6`
  - `-> 0005_phase7 -> 0006_phase8 -> 0007_phase9`
  - `-> 0008_phase10 -> 0009_phase11 -> 0010_phase12 -> 0011_phase13`
- YAML syntax parsing: **PASS**
  - 46 YAML/YML files
  - 62 YAML documents
- JSON syntax parsing: **PASS**
- Application version: **0.13.0**
- Phase 13 router registration: **PASS**
- Region/trust-link organization scoping: **PRESENT**
- Pinned SPIFFE bundle digest verification: **PRESENT**
- Remote trust endpoints require HTTPS and allowlisting: **PRESENT**
- Remote bundle data is not automatically trusted: **PRESENT**
- Cross-cloud workload bindings contain no long-lived cloud secrets: **PRESENT**
- Append-only application transparency hash chain: **PRESENT**
- Database row locking for concurrent transparency appends: **PRESENT**
- Signed/encrypted trust-continuity snapshots: **PRESENT**
- Trust restore requires explicit human/platform approval: **PRESENT**
- Prompt-injection scanner available without model/database dependencies: **PRESENT**
- Governed model gateway with arbitrary tools disabled: **PRESENT**
- Confidential RAG uses approved knowledge and excludes blocked retrieved documents: **PRESENT**
- Model release requires a passing evaluation: **PRESENT**
- Optional signed model-release requirement: **PRESENT**
- Agent permission manifests are default-deny: **PRESENT**
- Denied agent actions override allowed actions: **PRESENT**
- Human-approval actions are preserved as review decisions: **PRESENT**
- Sigstore/Cosign immutable image release workflow: **PRESENT**
- Cross-cloud AWS/Entra SPIFFE federation runbook: **PRESENT**
- Phase 13 Kubernetes image defaults: **PRESENT**
- Common committed-secret scan: **PASS**
  - no OpenAI `sk-*` pattern
  - no AWS `AKIA*` access-key pattern
  - no GitHub personal-token pattern
  - no committed `.env`
- Active Kubernetes manifests contain no inherited Phase 12 image tag: **PASS**

## Important architecture statements

- The application transparency ledger is a SHA-256 hash chain. It is tamper-evident,
  but it is not represented as a Merkle-tree transparency service.
- Container releases can additionally use keyless Sigstore/Cosign transparency.
- Prompt-injection scanning is a detection signal, not the primary security boundary.
  The stronger boundaries are no model tools, approved RAG only, signed/evaluated
  releases, explicit agent permission manifests, and narrow external-call policies.
- Disaster-recovery trust restoration is deliberately human approved.
- Cross-cloud workload identity stores binding metadata, not exchanged bearer tokens.

## Full pytest attempt

The complete inherited test suite was attempted with:

```bash
pytest -q backend/tests
```

Collection stopped because this export environment does not contain the project's
complete dependency set. The first repeated blocker was:

```text
ModuleNotFoundError: No module named 'pgvector'
```

Ten inherited test modules that import the full SQLAlchemy model layer therefore could
not be collected. This does not replace the full CI gate.

The standalone Phase 13 security suite did execute successfully:

```text
7 passed
```

## Not executable in this export environment

### Full application integration tests

Install all backend development dependencies and PostgreSQL/pgvector, then run:

```bash
cd backend
pip install -e ".[dev]"
pytest -q
python scripts/run_phase13_governance_gate.py
```

### Frontend build

The export environment does not contain the project's installed npm dependency tree.
CI should run:

```bash
cd frontend
npm install
npm run build
```

### Cloud/federation interoperability

No live AWS STS, Microsoft Entra, SPIRE federation, OpenID Federation peer, public
transparency service, KMS/HSM, private Kubernetes cluster, or model provider was
exercised during export. Those require the owner's credentials and controlled
infrastructure.

## Production gates

1. Pin regional SPIFFE bundles through an independently verified channel.
2. Keep peer bundle and federation endpoints on a strict egress/host allowlist.
3. Use exact SPIFFE subjects and narrow AWS IAM / Entra permissions.
4. Never store exchanged cloud bearer credentials in application configuration.
5. Require independent human approval before restoring regional trust.
6. Protect trust-snapshot and release signing keys with KMS/HSM in production.
7. Require passed evals and signed releases for production model policies.
8. Keep model tools disabled unless a separately reviewed capability is explicitly added.
9. Treat all job postings, resumes, retrieved documents and provider payloads as untrusted data.
10. Keep agent manifests default-deny and constrain destination hosts/external-call budgets.
11. Verify immutable container image signatures/attestations before promotion.
12. Run the full dependency-installed CI suite and private-cloud integration tests before release.
