# Global Career Architecture AI — Phase 14A + Phase 14B (merged)

> **Start here:** [RUN_PHASE14.md](RUN_PHASE14.md) contains the runnable
> local Docker Compose launcher, generated local secrets, and CI/staging
> validation steps. Frontend and live-stack checks require a connected machine
> with Docker; they remain unverified in this sandbox. Multi-region failover
> requires separately configured, approved staging infrastructure.

**Source:** the uploaded 217-file `global-career-ai-phase13(1).zip`.
This is a real source merge into the original Phase 13 application, NOT a
standalone add-on. It includes a Phase 14 Alembic revision, authenticated
FastAPI handlers, a small admin UI, operations templates and security tests.

## Phase 14A — Multi-agent orchestration

- Phase 14 ledger-backed, short-lived Ed25519 capability tokens with exact
  action/resource scopes, attenuation, delegation, audience binding and
  revocation. Parent grants carry the authenticated initiating human ID.
- Root issuance requires an authenticated organization owner or admin AND a
  current approved, active Phase 13 `AgentPermissionManifest` for the agent.
  Explicit denied actions override allowed actions.
- Dispatch checks source and target approved manifests, signed grant,
  tenant-specific directed trust edge, and registered recipient handler.
- Default configuration has no trusted agent edges; `PHASE14_ENABLED=false`.
  The only bundled example handler is `audit-agent / audit.digest`, which
  returns a SHA-256 digest of input without external/network/tool effects.
- Human checkpoints are exact action/resource/payload/tenant/workflow/token
  commitments. A different authorized human must approve; the initiating
  human is not allowed to approve their own checkpoints. One-time,
  transactional consumption precedes action.
- Encrypted `tenant + agent + workflow + key` memory vault; the API checks
  both exact capability and an approved Phase 13 permission manifest.
- The React admin panel can inspect approval metadata and its digest
  before allowing an explicit approve/reject decision. It does not show raw
  capability tokens or private signing material.

## Phase 14B — Operations

- Separate same-application deployment overlays at `k8s/phase14/overlays/`.
  Existing Phase 13 base Kubernetes manifests and names are preserved.
- Healthy-region traffic steering and regional health checks:
  `ops/phase14/terraform/` (Route53 example).
- `/ready` checks actual SQL database connectivity; `/metrics` uses
  bounded-cardinality labels and rejects unauthenticated callers.
- Prometheus recording/alert rules and a live Prometheus SLO gate.
- Dry-run-by-default staging failover drill and opt-in Chaos Mesh pod kill,
  never executed automatically in production.
- Example N-1 pod/capacity and spending governance; replace estimated
  values with measured traffic, cost and capacity evidence before deployment.

## Quickstart — tested local launcher

Install Docker Desktop / Docker Engine with Compose V2 and allow container
registries, PyPI and npm registry access. On your own machine:

```bash
cd global-career-ai-phase14
python3 scripts/start_local.py start
```

The launcher securely generates `.env` if missing (never overwrites it), keeps
Phase 14 autonomous agents disabled, builds the frontend production bundle,
starts PostgreSQL/pgvector, Redis, migrations, API, worker, beat, web, and
verifies the database and live HTTP endpoints. Open `http://localhost:5173`
and `http://localhost:8000/docs` after all checks pass. Use
`python3 scripts/start_local.py logs` to troubleshoot or `stop` to stop
containers without deleting database volumes.

**If you have an existing `.env`, the launcher will refuse invalid or
placeholder secrets rather than replacing them.** See
[RUN_PHASE14.md](RUN_PHASE14.md) for step-by-step local, CI, and staging
instructions. The launcher and test scripts have passed source-level checks;
actual images/database/cloud services were not exercised here.

**Do not blindly enable Phase 14 in production.** Use the original Phase 13
PostgreSQL + pgvector database with Alembic head `0012_phase14`. Deploy an
external global strongly consistent PostgreSQL transaction authority for
cross-region approval/token/step state. Terraform/DNS templates alone do not
create active-active database writes, clusters, global identity validation or
production traffic; plan/review all operations before use. Region trust links
remain subject to Phase 13 manual verification and DR trust restoration never
occurs automatically. Multi-region overlays are illustrative and require
updating image/region/ingress/secret values and workload identities.

## Critical configuration

`PHASE14_ENABLED=false` by default. If enabling, configure:

- `PHASE14_TOKEN_SIGNING_KEY_PEM_B64`: base64 of a persistent Ed25519 PKCS8
  PEM private key (store in vault; do not print or commit).
- `PHASE14_MEMORY_MASTER_KEY_B64`: base64 of >=32 random bytes; loss
  renders existing vault entries inaccessible.
- `PHASE14_AGENT_TRUST_EDGES_JSON`: JSON array of
  `{organization_id, source, target, actions}` with explicit directed edges.
  Example structure: `[{"organization_id":"<real org UUID>","source":"coordinator","target":"audit-agent","actions":["audit.digest"]}]`
  (no edges = all handoffs denied).
- `PHASE14_REGION_ID` as the region's trusted ID.
- `PHASE14_METRICS_BEARER_TOKEN` for the internal Prometheus scraper.
  If unset, `/metrics` returns 404.

Manifest examples: create and approve a Phase 13 manifest for the source agent
with `audit.digest` allowed, and for `audit-agent` also allowing `audit.digest`.
Only after separate approval do `/v1/phase14/capabilities/issue` and the
orchestration dispatch API permit the example action. For memory, include
`memory.read` / `memory.write` in the manifest and grant exact resource `own`.
Actions that Phase 13 designates as requiring human approval and which lack
a checkpoint mechanism (memory routes) are denied by the API.

**Phase 14 API:** `/v1/phase14/readiness`, `/capabilities/issue`,
`/capabilities/revoke`, `/memory/write`, `/memory/read`,
`/orchestration/dispatch`, `/approvals/{id}`, `/approvals/{id}/review`.

## Scope and outstanding production integration

- Root issuance in this reference uses authenticated first-party human
  sessions and Phase 13 organization/manifest checks. It does not yet bind
  each agent token cryptographically to a SPIFFE workload attestation.
  Before cross-region autonomous operations, enforce SPIRE/mTLS workload
  identity and validated regional trust continuity at the service boundary.
- Only the deterministic hash handler is registered. Real career actions,
  email, payments, and model-based agent execution require separate
  trusted handler implementations, downstream idempotency, data classification,
  destination allowlists, external call budgets, Phase 13 gateway release
  gates, and workflow-specific operator approval.
- Phase 14 approval/token/receipt tables create durable local evidence, but
  the new records are **not automatically appended to Phase 13's
  tamper-evident transparency hash chain**; production audit/outbox
  integration remains a separate release task.
- Recovery of a reserved-but-incomplete step is intentionally manual,
  avoiding unsafe retry of partially completed external effects.
- The Phase 13 snapshot restoration process and signing trust anchors stay
  independent of the Phase 14 availability/failover controls.

See `PHASE14_AB_IMPLEMENTATION.md`, `VALIDATION_PHASE14.md`,
`ops/phase14/`, and `k8s/phase14/`.

---
# Global Career Architecture AI — Phase 13

Phase 13 extends Phase 12 with multi-region trust continuity and a bounded AI-security
control plane.

## Phase 13A

- organization-scoped deployment regions and pinned regional SPIFFE trust links
- cross-cloud workload-identity bindings without stored cloud secrets
- AWS STS / Microsoft Entra federation deployment guidance
- tamper-evident application transparency hash chains
- encrypted/signed disaster-recovery trust-continuity snapshots
- human-approved trust restoration

## Phase 13B

- allowlisted AI model gateway with tools disabled
- dependency-light prompt-injection detection plus architectural containment
- approved-document confidential RAG
- passed-evaluation/signed model-release gates
- default-deny autonomous-agent permission manifests
- immutable container release signing through Sigstore/Cosign

See `PHASE13_AB_IMPLEMENTATION.md`,
`docs/phase13-cross-cloud-workload-identity.md`,
`ops/phase13/trust-continuity-runbook.md`, and
`ops/phase13/ai-security-runbook.md`.

---


# Global Career Architecture AI — Phase 12

Phase 12 extends Phase 11 with federation-grade trust and production runtime security.

## Phase 12A

- OpenID Federation 1.1 trust anchors and bounded trust-chain validation
- organization-reviewed federation entities and signed entity statements
- wallet-attestation certificate trust chains
- credential-policy negotiation
- federation/trust-framework-aware credential decisions
- no automatic trust from remote resolution

## Phase 12B

- AWS KMS / Azure Managed HSM credential signing references
- production fail-closed HSM requirement
- attestation-gated confidential inference
- SPIFFE/SPIRE workload-identity deployment boundary
- Falco/Falcosidekick runtime event integration
- secret redaction, event deduplication and retention
- bounded automated containment for reversible application controls
- human/authorized-controller gate for network/workload isolation

See `PHASE12_AB_IMPLEMENTATION.md` for implementation detail and
`docs/phase12-incident-response.md` for the containment runbook.

---

# Global Career Architecture AI — Phase 11

Phase 11 extends the Phase 10 full-stack career architecture with high-assurance identity interoperability and security engineering.

## Phase 11A

- WebAuthn Level 3 passkeys
- DID trust registry and allowlisted did:web resolution
- W3C Bitstring Status List v1.0
- HAIP 1.0 readiness checks
- mso_mdoc integration with a configurable cryptographic verifier
- hardware-backed wallet-key attestation evidence
- no custody of wallet/passkey private keys

## Phase 11B

- confidential-computing deployment hooks
- confidential-workload attestation records
- post-quantum crypto inventory/migration planning
- NIST FIPS 203/204/205 target mapping
- SBOMs and signed build attestations
- Trivy/pip-audit/Bandit security gates
- scheduled authorized DAST
- Phase 11 governance gate



Phase 10 extends Phase 9 with standards-based wallet interoperability and a deeper
privacy-engineering control plane.

## Phase 10A — OpenID4VCI/OpenID4VP, approved issuers/verifiers, selective disclosure

### OpenID4VCI 1.0

The reference issuer implements the 2025 OpenID Final Specification profile for:

- Credential Issuer metadata at the path formed by
  `/.well-known/openid-credential-issuer` plus the issuer path.
- OAuth authorization-server metadata.
- authorization-code issuance with pre-registered wallet redirect URIs and PKCE S256.
- pre-authorized-code credential offers, including optional transaction codes.
- a dedicated nonce endpoint.
- the final Credential Request `proofs` object with JWT holder proof.
- `jwt_vc_json` and `dc+sd-jwt` credential configuration profiles.
- hashed authorization codes, pre-authorized codes and bearer access tokens.
- one-use holder proof nonce consumption.
- encrypted ES256 issuer private keys.

Issuer profiles are organization-owned but remain inactive until a platform administrator
approves them. Credential offers can only be created by issuer owners/admins and are
explicitly bound to a subject user. Authorization-code issuance additionally requires the
authenticated subject to belong to the issuer organization.

This reference build accepts one JWT key proof per credential request. It deliberately does
not advertise batch issuance, deferred issuance, DPoP, key attestation, CWT proofs, mdoc,
PAR or dynamic wallet registration. Add those only with their own interoperability tests.

### OpenID4VP 1.0

The verifier implements:

- `response_type=vp_token`;
- DCQL queries;
- `response_mode=direct_post`;
- nonce and state replay binding;
- the `redirect_uri:` Client Identifier Prefix;
- unsigned request objects for that prefix, as required by the final profile;
- encrypted storage of verified presentation results;
- organization-scoped static issuer trust anchors.

External signing keys are never fetched from arbitrary URLs at runtime. Trust anchors must
be installed by an authorized organization administrator. Local platform issuers are trusted
only after platform approval.

### Selective disclosure

Selective-disclosure mechanics follow RFC 9901:

- disclosures encode `[salt, claim-name, claim-value]`;
- SHA-256 digests commit disclosures in `_sd`;
- holders can present a subset of disclosures;
- holder-bound presentations use a KB-JWT with `sd_hash`, audience and request nonce.

The `dc+sd-jwt` credential format is implemented as the current SD-JWT VC profile. As of
September 2026, the SD-JWT VC specification itself remains an IETF Internet-Draft even
though RFC 9901 selective-disclosure JWT is final. The project therefore never labels the
SD-JWT VC profile as a final RFC.

The implementation intentionally supports top-level selectively disclosable claims only.
Nested disclosure, decoy digests and additional holder-binding methods require additional
conformance work before being enabled.

### Credential-status boundary

Locally issued credentials have an authenticated project-local status endpoint named
`PlatformCredentialStatus2026`. This is not represented as a W3C Bitstring Status List.
Do not relabel it as such without implementing the actual status-list specification.

## Phase 10B — privacy engineering and cryptographic audit

### Automated data discovery and classification

`POST /v1/phase10/privacy/{organization_id}/discovery` scans SQLAlchemy schema metadata,
not live plaintext values. Built-in and organization-specific regular-expression rules
classify fields such as contact information, authentication secrets, credential material,
career profiles, locations, financial data and audit records.

The scheduled Celery task reruns metadata discovery for organizations without turning the
feature into a content crawler.

### Consent receipts

`POST /v1/phase10/privacy/consent-receipts` records purpose, grant/revoke action, policy
version, lawful basis, processing purposes and data categories. Receipts are hash-chained
per candidate/purpose to make later mutation detectable.

### Deletion orchestration

Candidates can create a dry-run deletion plan before executing erasure. An identity-verified
Phase-9 erasure request can be linked to the plan. Legal hold always blocks execution.
Candidate-owned profile, resume, application, credential, wallet/passport, recommendation,
issuance-token and consent records are included in the deletion plan. The account is
pseudonymized and disabled rather than silently removed.

### Privacy-preserving analytics

Organization analytics expose three fixed count queries only. Releases use:

- minimum-cohort suppression;
- Laplace noise with count-query sensitivity 1;
- a CSPRNG-backed random source;
- a configurable daily epsilon budget;
- deterministic query hashing so an identical request returns the same stored release
  instead of consuming privacy budget repeatedly.

This is a reference differential-privacy mechanism informed by NIST SP 800-226. It is not
a blanket guarantee that every downstream dataset or analysis is anonymous.

### Cryptographic audit trail

Security-relevant events can be written to an append-only SHA-256 hash chain. Each entry
contains a payload digest rather than the raw payload. Deployments can configure an
Ed25519 signing seed so entries are also signed. The organization identifier in the audit
record is immutable metadata rather than an `ON DELETE SET NULL` foreign key, so deleting
an organization cannot rewrite the data used to calculate historic entry hashes.

For production, anchor audit heads in an independent system and keep the signing key in a
managed signing/HSM service rather than a long-lived application environment secret.

## Phase 10 policy gates

The built-in policy engine and OPA policy both deny:

- unapproved credential issuer activation;
- unapproved credential verifier activation;
- issuer private-key export;
- arbitrary dynamic trust-anchor fetching;
- privacy-analytics release below the cohort floor;
- privacy-analytics release after the epsilon budget is exhausted;
- cryptographic audit-entry deletion.

Earlier controls remain in force, including candidate-wallet non-custody, protected-trait
ranking prohibition, no autonomous applications/employer messaging, verified-credential
truthfulness, legal-hold deletion blocking and red-team release gates.

## Upgrade Phase 9 → Phase 10

```bash
cd backend
alembic upgrade head

pip install -e ".[dev]"
python -m compileall app tests alembic scripts
pytest -q

python scripts/run_phase7_governance_gate.py
python scripts/run_phase8_governance_gate.py
python scripts/run_phase9_governance_gate.py
python scripts/run_phase10_governance_gate.py
```

The new Alembic head is `0008_phase10`.

Important production values:

```dotenv
PHASE10_PUBLIC_BASE_URL=https://career.example.com
PHASE10_ACCESS_TOKEN_SECONDS=600
PHASE10_CREDENTIAL_VALID_DAYS=365
PHASE10_DAILY_EPSILON_LIMIT=2.0
PHASE10_AUDIT_ED25519_PRIVATE_KEY=
PHASE10_AUDIT_SIGNING_KEY_ID=phase10-audit-v1
```

OpenID credential interoperability requires HTTPS in production. Do not publish
`PHASE10_PUBLIC_BASE_URL` as `http://...` outside local development.

See:

- `PHASE10_AB_IMPLEMENTATION.md`
- `governance/phase10/`
- `ops/phase10/`
- `VALIDATION.md`

---

# Phase 9A + 9B — retained implementation history

Phase 9 extends Phase 8 with candidate-owned portable career records, public DID/wallet
registration boundaries, encrypted skills passports, education-to-career pathways, privacy
impact assessment workflows, data lineage, retention automation, DSAR operations, AI red
teaming and continuous governance/security monitoring.

## Phase 9A — portable identity, skills passports and career records

The platform follows a **non-custodial wallet boundary**: it accepts a candidate's public DID
and public wallet metadata but never stores the candidate's wallet private key.

W3C Verifiable Credentials Data Model 2.0 became a W3C Recommendation on 15 May 2025.
OpenID for Verifiable Presentations 1.0 became a Final Specification in July 2025, and
OpenID for Verifiable Credential Issuance 1.0 became a Final Specification in September
2025. Phase 9 records those interoperability boundaries without pretending an unsigned
platform export is a cryptographically verified credential.

`PUT /v1/skills-passport` creates an encrypted, versioned candidate passport. Candidate
skills can be self-asserted, but only skills linked to a credential whose Phase-8 verifier
status is `verified` are marked as credential-verified.

`GET /v1/portable-career-record` produces a VC-2.0-shaped JSON export and explicitly labels
it `unsigned_portable_export`. Deployments that want actual signed issuance must add an
authorized issuer, signing keys/HSM/KMS controls and cryptographic verification rather than
changing that label.

Education-to-career pathways combine candidate skills, verified credential evidence and the
organization's approved learning catalog. Recommendations remain options, not promises of
employment, promotion, licensure, visa eligibility or educational admission.

## Phase 9B — privacy operations and continuous assurance

### Privacy impact assessments and lineage

Organizations can record PIA/DPIA-style engineering assessments and metadata-only data
lineage. The lineage graph is deliberately for system/data-category metadata; do not put raw
candidate PII into lineage nodes or edges.

### Retention automation

Retention is allowlisted by record type and executed by Celery. A legal hold always blocks
the automated deletion path. Retention policy does not override statutory, litigation,
contractual or employment-record obligations.

### Data-subject requests

Authenticated candidates can create access, portability, rectification, erasure, restriction
and objection requests. The default due date is configurable and set to 30 days. Access and
portability can create an encrypted export from known candidate-owned platform data after
identity verification.

The 30-day default is an operational baseline, not a universal legal deadline. Apply the
actual jurisdiction, permitted extensions and exceptions with privacy counsel.

### Red teaming

Phase 9 never auto-passes a red-team scenario merely because a test fixture exists.
Policy-boundary checks run automatically. Prompt injection, data exfiltration, cross-tenant
attacks and model hallucination scenarios remain manual/system-execution tests until a real
deployment exercise is performed.

### Continuous controls

A scheduled control scan records overdue DSARs, overdue privacy reviews, red-team findings,
AI incident backlog and high-risk AI review gaps. These are operational signals rather than
certification or legal conclusions.

## Upgrade

```bash
cd backend
alembic upgrade head
python scripts/run_phase7_governance_gate.py
python scripts/run_phase8_governance_gate.py
python scripts/run_phase9_governance_gate.py
pytest -q
```

The new Alembic head is `0007_phase9`.

See:

- `PHASE9_AB_IMPLEMENTATION.md`
- `governance/phase9/`
- `ops/privacy/`
- `ops/redteam/`
- `VALIDATION.md`

---

# Phase 8A + 8B — retained implementation history

Phase 8 extends Phase 7 with verifiable credential handling, authorized learning-provider
catalogs, provenance-backed labor-market trends, candidate-controlled career portfolios,
and a deeper AI governance system for EU AI Act / ISO/IEC 42001 implementation work.

## Phase 8A — credentials, learning, labor trends and career portfolios

### Verifiable credentials

`POST /v1/credentials` accepts JSON credentials such as W3C Verifiable Credentials and
Open Badges 3.0.

The local verifier intentionally distinguishes:

- **structural validation** — structure, issuer metadata, issuance/expiry and declared
  proof/status pointers;
- **cryptographic verification** — only when an administrator-configured verifier checks
  the signature/proof and credential status/revocation information.

A JSON credential with a `proof` field is **not** labeled verified merely because the
field exists. Raw credential material is encrypted with the existing envelope/KMS layer.

Open Badges 3.0 aligns with W3C Verifiable Credentials and requires proof/status
verification for a verifier implementation. The trust boundary is documented in
`governance/phase8/credential_trust_profiles.json`.

### Authorized learning-provider APIs

Organization owners/admins can configure encrypted learning connections. Every outbound
learning endpoint must match `LEARNING_PROVIDER_ALLOWED_HOSTS`, preventing the feature
from becoming an arbitrary URL fetcher.

Built-in behavior:

- `open_edx`: uses the documented `/api/courses/v1/courses/` catalog endpoint.
- `udemy_business`, `coursera_enterprise`, `generic_authorized_catalog`: require the
  organization's approved API access plus an explicitly configured catalog path and field
  mapping. The project does not guess private endpoints or scrape course sites.

Synced catalog records keep the provider, external ID, source URL, sync timestamp and
provider metadata.

### Labor-market trends

Phase 8 stores time-series observations with:

- source and data vintage;
- country/region;
- occupation code/title;
- metric and period;
- value/unit;
- source URL, license and source-specific metadata.

The BLS adapter uses the official Public Data API v2 for explicitly supplied series IDs. `BLS_API_KEY` is optional for normal public access and is used when configured for expanded registered limits. Other official/licensed datasets can use the provenance-required import endpoint.

`POST /v1/career/labor-trend` calculates a deterministic historical trend:

- ordinary least-squares slope over time;
- annualized change when mathematically valid;
- historical volatility;
- increasing/stable/decreasing direction;
- data-coverage/stability confidence;
- a one-year linear projection.

It is **not** a probability of getting hired, promoted, earning a specific wage, or a
claim about future labor-market conditions.

### Candidate career portfolios

Candidates can create one encrypted portfolio containing selected profile material,
projects, links and cryptographically verified credentials.

Public shares:

- use high-entropy token hashes;
- expire automatically;
- can be revoked;
- exclude email and phone by default;
- expose only candidate-selected sections;
- keep verified credentials separate from self-asserted certification text.

## Phase 8B — AI inventory, EU AI Act, ISO/IEC 42001, risk and incidents

### AI-system inventory

Each organization can register versioned AI systems with:

- intended purpose;
- provider/deployer role;
- lifecycle status;
- jurisdictions;
- model/version names;
- data categories;
- employment/education use;
- profiling and material-decision influence;
- human-oversight status;
- EU classification triage and review date;
- ISO/IEC 42001 AIMS scope flag.

### EU AI Act triage

The Phase 8 classifier is deliberately conservative. Employment recruitment/selection
uses are marked for Annex III review, and employment profiling is marked as a high-risk
candidate. It does **not** make a legal determination.

The repository's current timeline records standalone Annex III high-risk requirements as
applicable from **2 December 2027**, following the 2026 AI Omnibus amendments. Product-
embedded high-risk rules have a later application date.

Engineering mappings cover public-law themes including AI literacy, classification, risk
management, data governance, technical documentation, logging, transparency, human
oversight, robustness/cybersecurity, deployer duties, and conditional registration/FRIA
reviews.

See:

`governance/phase8/eu_ai_act_crosswalk.json`

### ISO/IEC 42001 management-system crosswalk

`governance/phase8/iso42001_crosswalk.json` contains only high-level implementation
themes: AIMS context/scope, leadership, planning, support, operations, performance
evaluation and continual improvement.

It intentionally does **not** reproduce the copyrighted ISO/IEC 42001 text, claim
conformity, or act as a certification checklist. Use a licensed copy of the standard and
qualified auditors for certification.

### AI risk and incident management

Versioned risk assessments record inherent/residual risk, hazards, controls and approval.
Critical residual risk automatically opens human review.

AI incidents store encrypted details and track detection, containment, closure and
external-report timestamps. `serious_incident_candidate` is a triage field only; actual
reporting obligations require current legal analysis of the facts and jurisdiction.

Runbook:

`ops/incidents/AI_INCIDENT_RUNBOOK.md`

### Automated evidence

Celery periodically records hash-addressed evidence snapshots for:

- AI inventory;
- EU AI Act / ISO 42001 implementation status;
- incident metrics;
- existing evaluation/fairness/review evidence.

This is audit preparation, not an EU conformity assessment, ISO certification, SOC 2
opinion or regulator filing.

## Phase 8 database migration

```bash
cd backend
alembic upgrade head
```

New Alembic head:

`0006_phase8`

New tables:

- `verified_credentials`
- `learning_provider_connections`
- `learning_catalog_items`
- `labor_market_observations`
- `labor_trend_snapshots`
- `career_portfolios`
- `career_portfolio_shares`
- `ai_system_inventory`
- `ai_risk_assessments`
- `ai_incidents`
- `governance_control_mappings`

## Important Phase 8 API endpoints

```text
POST   /v1/credentials
GET    /v1/credentials
DELETE /v1/credentials/{credential}

POST /v1/organizations/{org}/learning/connections
GET  /v1/organizations/{org}/learning/connections
POST /v1/organizations/{org}/learning/connections/{connection}/sync
GET  /v1/organizations/{org}/learning/catalog

POST /v1/admin/phase8/labor/observations
POST /v1/admin/phase8/labor/bls-series
POST /v1/career/labor-trend

PUT    /v1/portfolio
GET    /v1/portfolio
POST   /v1/portfolio/shares
DELETE /v1/portfolio/shares/{share}
GET    /v1/public/portfolio/{token}

POST /v1/organizations/{org}/ai-inventory
GET  /v1/organizations/{org}/ai-inventory
POST /v1/organizations/{org}/ai-inventory/{system}/risk-assessments
POST /v1/organizations/{org}/ai-incidents
GET  /v1/organizations/{org}/ai-incidents
PATCH /v1/organizations/{org}/ai-incidents/{incident}
GET  /v1/organizations/{org}/governance/phase8/controls
PATCH /v1/organizations/{org}/governance/phase8/controls/{control}
POST /v1/organizations/{org}/governance/phase8/evidence
GET  /v1/organizations/{org}/governance/phase8/dashboard
```

## Phase 8 configuration

Add approved hosts/endpoints only:

```dotenv
CREDENTIAL_REMOTE_VERIFIER_URL=
CREDENTIAL_REMOTE_VERIFIER_TOKEN=

LEARNING_PROVIDER_ALLOWED_HOSTS=learning.example,training.example
PHASE8_LEARNING_SYNC_HOURS=24

BLS_API_KEY=
PHASE8_LABOR_MIN_POINTS=4

PHASE8_PORTFOLIO_DEFAULT_SHARE_DAYS=30
PHASE8_EVIDENCE_INTERVAL_HOURS=24
```

Do not accept credential-verifier or learning-provider URLs directly from candidate
requests. Add domains administratively after security/legal/vendor review.

## Phase 8 governance gate

CI now runs:

```bash
python scripts/run_phase8_governance_gate.py
```

It checks the current recorded Annex III timeline, human-oversight mapping, ISO copyright
boundary, credential-verification boundary, Phase 8 OPA rules and migration presence.

---

## Phase 7A — career pathways, skills gaps, salary and global mobility

### Career pathway scenarios

`POST /v1/career/forecast` builds explainable pathway scenarios from the candidate's
verified skills and the trusted career taxonomy cache. The score is **skill overlap**,
not a probability of getting hired, promoted, licensed, or admitted to a program.

Career forecasting requires active `ai_career_analysis` consent. Results are encrypted
per user and persist the method/data version used to create the scenario.

### Skills-gap learning plans

`POST /v1/career/learning-plan` compares verified candidate skills with explicit target
skills and recommends only education/certification records that have been approved in
`education_pathways`.

The system never treats course completion as equivalent to work experience and does
not claim a certification, license, degree, or skill until the candidate verifies it.

### Salary intelligence

Salary benchmarks are stored with:

- occupation code and title
- country and region
- source and data vintage
- currency
- p10/p25/median/p75/p90 where available
- annual mean and employment where available
- source URL and license/provenance

`salary.publish` policy rejects records without source provenance. The platform does
not convert salary benchmarks into guarantees, offers, or hiring probabilities.

### Global occupation mobility

`mobility_mappings` can connect occupation systems across jurisdictions through common
taxonomies such as ISCO-08. Mappings preserve source evidence and transition effort.

Mobility output explicitly does **not** establish immigration eligibility, right to work,
credential recognition, or professional licensing. Those must be checked with the
relevant jurisdiction.

## Phase 7B — enterprise AI governance

### Policy as code

The baseline in-process policy gate is mirrored in:

`governance/policies/career.rego`

It blocks:

- autonomous job application
- autonomous employer messaging
- protected-trait ranking
- salary publication without provenance
- career forecasting without consent
- model/workflow release without an evaluation gate

Set `OPA_URL` to use an external Open Policy Agent deployment. With
`OPA_FAIL_CLOSED=true`, OPA outages deny governed actions rather than silently bypassing
policy.

### Model evaluations

Organizations can create deterministic evaluation suites for:

- unsupported numeric claims
- unverified skill claims
- protected-trait leakage
- missing evidence IDs
- prohibited autonomous actions

Failed runs automatically create a human-review item. The repository includes a baseline
suite in `governance/evals/default_cases.json`.

These local evaluation gates complement, rather than replace, provider/platform eval
systems and human review.

### Fairness monitoring

Fairness monitoring accepts **aggregate cohort counts only**. It does not ingest
individual protected-trait attributes into candidate ranking.

Safeguards:

- minimum cohort size
- suppressed small groups
- configurable selection-rate review threshold
- automatic human-review queue creation
- no automatic candidate-score changes
- explicit statement that the result is not a legal discrimination determination

### Human review queue

Owner/admin users can review policy, fairness, evaluation, privacy, security, and
employment-risk exceptions. Review context is encrypted when stored.

### SOC 2 evidence automation

Celery Beat captures recurring engineering evidence from application access controls,
MFA state, monitoring configuration, deployment controls, and governance state.

The evidence catalog is in:

`governance/control_catalog.json`

This is evidence preparation only. It is **not** a SOC 2 report, audit opinion,
certification, or reproduction of the AICPA Trust Services Criteria.

### Compliance dashboard

Organization owners/admins can view:

- open and critical human reviews
- latest model-evaluation score
- fairness reviews awaiting action
- control evidence captured in the prior 30 days
- evidence freshness

## Phase 7 database migration

```bash
cd backend
alembic upgrade head
```

New Alembic head:

`0005_phase7`

New tables:

- `salary_benchmarks`
- `education_pathways`
- `mobility_mappings`
- `career_forecasts`
- `learning_plans`
- `governance_policies`
- `model_eval_suites`
- `model_eval_runs`
- `fairness_snapshots`
- `human_review_items`
- `compliance_evidence`

## Important Phase 7 API endpoints

```text
POST /v1/career/forecast
POST /v1/career/learning-plan
GET  /v1/career/salary
GET  /v1/career/mobility

POST /v1/admin/phase7/salary-benchmarks
POST /v1/admin/phase7/education-pathways
POST /v1/admin/phase7/mobility-mappings
POST /v1/admin/phase7/policies/baseline

POST /v1/organizations/{org}/governance/fairness
POST /v1/organizations/{org}/governance/eval-suites
POST /v1/organizations/{org}/governance/eval-suites/{suite}/run
GET  /v1/organizations/{org}/governance/reviews
POST /v1/organizations/{org}/governance/reviews
PATCH /v1/organizations/{org}/governance/reviews/{review}
POST /v1/organizations/{org}/compliance/evidence/collect
GET  /v1/organizations/{org}/compliance/dashboard
```


## Phase 6 compatibility and deployment foundation

## Phase 6A — career agents, consent, monitoring, recruiter workspace

### Candidate consent and monitoring

The candidate must explicitly opt into each purpose:

- `job_monitoring`
- `ai_career_analysis`
- `in_app_notifications`

Consent is append-only in `consent_events`. The active preferences are encrypted
in `career_monitor_policies`. Revoking monitoring causes all scheduled monitor
and agent tasks to fail closed on their next consent check.

Automated monitoring:

1. reads only normalized jobs already licensed/authorized for the platform;
2. loads the candidate's encrypted verified profile;
3. computes a deterministic fit score from verified skills and user preferences;
4. stores candidate-specific explanations encrypted;
5. generates in-app recommendations at/above the candidate's threshold;
6. optionally queues AI analysis only when `ai_career_analysis` is active.

It does **not** apply to jobs, contact employers, or add qualifications to the
profile.

### Bounded AI career-agent team

`backend/app/career_agents.py` uses three specialists:

- Career Fit Analyst
- Truthful Resume Strategist
- Interview Practice Coach

The Python orchestrator owns the workflow. Agents have no browser, provider
credential, email, application-submission, or profile-mutation tools. Positive
candidate claims must reference fact-ledger IDs. Post-generation validation
rejects unknown evidence IDs and unverified skills. Agent runs are limited to two
turns and the Agents SDK's default remote tracing is disabled for candidate runs;
application OpenTelemetry remains the operational observability path.

### Recruiter dashboard

Organization roles now include `recruiter`. Recruiters can access only their
organization's inbound candidates/applications and can:

- review pipeline stages;
- move applications through received/review/screen/interview/offer/hired/etc.;
- view source and funnel aggregates;
- see webhook dead-letter counts;
- review the processing basis/privacy notice metadata already stored by Phase 5.

Protected/self-identification fields remain excluded from matching/ranking.

## Phase 6B — Kubernetes, autoscaling, telemetry, SIEM and DR

### Kubernetes topology

The reference deployment contains:

- 3+ FastAPI replicas
- Celery workers
- exactly one Celery Beat scheduler
- React/Nginx frontend
- OpenTelemetry Collector
- HPA for API/frontend
- KEDA queue-depth scaling for workers
- PodDisruptionBudgets
- topology spreading
- restricted Pod Security
- default-deny NetworkPolicies
- non-root/read-only containers
- a separate one-shot Alembic migration Job

The API's in-process scheduler is disabled in Kubernetes. This is required
because scaled API replicas must not independently run the same scheduled job.

### EKS

`infra/eks` provisions:

- private EKS control plane endpoint;
- control-plane audit/API/authenticator logs;
- managed node group across existing private subnets;
- encrypted Kubernetes secrets;
- EKS Pod Identity;
- separate application and Cluster Autoscaler IAM roles;
- API-based cluster access;
- least-privilege KMS/Secrets Manager permissions.

The included add-on script installs Metrics Server, ingress-nginx,
cert-manager, OpenTelemetry Operator, KEDA, and Cluster Autoscaler.

### AKS

`infra/aks` provisions:

- private AKS;
- local accounts disabled;
- OIDC issuer + Workload Identity;
- Azure Policy;
- Azure CNI Overlay powered by Cilium;
- Key Vault CSI provider with rotation;
- Container Insights;
- cluster node autoscaling;
- managed KEDA add-on;
- federated identities for API/worker/beat service accounts.

It reuses the Phase 5 managed PostgreSQL, Azure Managed Redis, Key Vault and
registry resources. The Azure Redis foundation uses `EnterpriseCluster` so
Celery and the KEDA Redis-list scaler can use the service's single endpoint.

### Observability / SIEM

The app exports OTLP traces/metrics to the in-cluster collector when
`OTEL_ENABLED=true`.

Security events are emitted as one-line JSON with:

```json
{
  "event_type": "security_audit",
  "event": "career_agent.run",
  "actor": "...",
  "environment": "production",
  "service": "global-career-ai"
}
```

Do not place candidate/resume contents or secrets in telemetry. See
`ops/siem/README.md`.

### Disaster recovery

See `ops/dr/README.md` and `ops/dr/restore-test-checklist.md`.

The durable webhook inbox remains PostgreSQL-backed, so Redis loss does not
erase provider applications. Redis is treated as replaceable queue/cache
infrastructure.

## Local development

```bash
cp .env.example .env

python - <<'PY'
import base64
import json
import os
import secrets

print("JWT_SECRET=" + secrets.token_urlsafe(48))
print("OIDC_SESSION_SECRET=" + secrets.token_urlsafe(48))
print(
    "LOCAL_MASTER_KEYS_JSON="
    + json.dumps(
        {
            "local-v1": base64.urlsafe_b64encode(os.urandom(32)).decode()
        },
        separators=(",", ":"),
    )
)
PY

# Add the generated values to .env.
docker compose up --build
```

Local services:

- Dashboard: `http://localhost:5173`
- OpenAPI: `http://localhost:8000/docs`

Docker Compose runs database migration once through the `migrate` service
before starting the API.

## Upgrade from Phase 5

```bash
cd backend
alembic upgrade head
```

The new migration is:

`0004_phase6_agents_analytics.py`

It adds:

- `consent_events`
- `career_monitor_policies`
- `job_recommendations`
- `career_agent_runs`
- `analytics_daily`

## Tests

```bash
cd backend
pip install -e ".[dev]"
python -m compileall app tests alembic
pytest -q
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

## Kubernetes

Install the cloud cluster first, then add-ons:

```bash
# EKS
terraform -chdir=infra/eks init
terraform -chdir=infra/eks apply
AWS_REGION=us-east-1 ./k8s/install-addons.sh eks global-career-ai

# AKS
terraform -chdir=infra/aks init
terraform -chdir=infra/aks apply
./k8s/install-addons.sh aks global-career-ai-aks
```

Provision `career-runtime` with your approved secrets synchronization mechanism.
Do not apply `runtime-secret.example.yaml` with real secrets committed to Git.

Render manifests before deployment:

```bash
kubectl kustomize k8s/base >/tmp/phase6.yaml
```

Build/publish immutable cloud images with
`.github/workflows/release-cloud-images.yml`. Production deployments use
`.github/workflows/deploy-kubernetes.yml` from a self-hosted runner that can
reach the private EKS/AKS API.

## Deployment security requirements

Before production:

- use immutable image tags/digests;
- sign and scan images;
- use a managed secrets system;
- keep EKS/AKS API endpoints private;
- terminate TLS at the approved ingress/WAF layer;
- configure SIEM export and alerting;
- test database PITR;
- test consent revocation;
- run cross-tenant authorization tests;
- review OpenAI/API data handling requirements for your organization;
- obtain provider API/feed agreements before enabling restricted job sources;
- conduct privacy, employment-law, accessibility and security review for each
  country/region where the product operates.

## Important architecture boundary

"Self-updating" means new authorized job/career material becomes versioned
retrieval knowledge. External pages/job descriptions do not rewrite model
weights or system instructions. Untrusted provider/web content stays data.

## Phase 11 upgrade

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
python scripts/run_phase11_governance_gate.py
pytest -q
```

For passkeys, production must use an HTTPS origin and exact RP ID/origins.
For `did:web`, populate `PHASE11_DID_WEB_ALLOWED_HOSTS`; remote DIDs remain untrusted until reviewed.
For mdoc, `manual_required` is returned unless a configured cryptographic verifier returns a verified result.
See `ops/PHASE11_SECURITY_RUNBOOK.md`.

---

## Important — external validation still required

**Important:** The project-side setup and validation improvements are packaged, but I can't yet confirm that the full application runs successfully. Docker and PostgreSQL aren't available in this environment, and I couldn't download npm dependencies here.

- **Actual npm installation and Vite build:** require connected execution.
- **Live database and Docker deployment:** require Docker execution.
- **Real multi-region failover:** requires approved staging infrastructure.

These checks must remain **PENDING / NOT VERIFIED** until successfully executed in the required environment. See `RUN_PHASE14.md` and `PHASE14_BUILD_AND_LIVE_VALIDATION.md` for the execution procedures.

