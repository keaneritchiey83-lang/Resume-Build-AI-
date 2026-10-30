# Phase 9A + 9B Implementation Manifest

## Phase 9A — candidate-owned portable career records

### Candidate wallet/DID registration

- `candidate_wallets` stores public holder DID and public wallet protocol metadata only.
- Supported registration syntax: `did:key`, `did:web`, `did:jwk`, `did:ion`, `did:pkh`.
- Candidate wallet private keys are never accepted or persisted.
- OpenID4VC presentation/issuance endpoint fields are metadata boundaries for future
  authorized wallet integrations; Phase 9 does not falsely claim to be an issuer/wallet.

### Skills passport

- one encrypted candidate skills passport per user;
- combines candidate-declared skills/abilities with credential evidence;
- only cryptographically verified credentials can mark a skill as verified;
- contact information is opt-in;
- passport content is hash-addressed and versioned.

### Portable career record

`GET /v1/portable-career-record` exports a W3C VC Data Model 2.0-shaped JSON career record.
It is explicitly labeled `unsigned_portable_export` unless a real issuer has produced a valid
cryptographic proof. Source verified credentials retain their original evidence/status.

### Education-to-career pathways

The pathway endpoint compares candidate and credential-backed skills to an explicit target
occupation skill list, then selects matching items from the organization-approved learning
catalog. It does not guarantee hiring, licensure, immigration eligibility, admissions or
promotion.

## Phase 9B — privacy/security operations

### Privacy impact assessments

Organization owners/admins can create DPIA/PIA-style engineering assessments with:

- processing purposes and data categories;
- data subjects and jurisdictions;
- lawful-basis metadata;
- recipients/retention summary;
- international-transfer and automated-decision-support flags;
- mitigations, risk triage and annual review date.

The score is an engineering triage signal, not a legal conclusion.

### Data lineage

`data_assets` contains metadata only; raw candidate data does not belong in the lineage graph.
`data_lineage_edges` records upstream/downstream assets, transformation and processing purpose.

### Retention automation

Organization policies are limited to explicit record types. Legal hold blocks deletion.
Scheduled Celery execution applies enabled policies and records deletion counts.

### DSAR workflows

Candidates can submit access, portability, rectification, erasure, restriction and objection
requests. Access/portability results can be created from the user's encrypted profile,
applications, extracted résumé content, credentials, public wallet metadata and skills
passport after identity verification.

The software uses a configurable 30-day default due date; applicable legal rules can differ
and must be reviewed by privacy counsel.

### AI red teaming

Automated policy-boundary checks cover protected-trait ranking, credential-verification claims
and autonomous application behavior. Scenarios requiring actual model/system execution are
`manual_required` and create review work instead of auto-passing.

### Continuous controls

Celery periodically snapshots:

- overdue privacy requests;
- overdue privacy assessments;
- failed/manual-review red-team campaigns;
- open AI incidents;
- high-risk AI inventory records lacking review.

The output is an operational control signal, not an assurance opinion or certification.

## Database

New Alembic head: `0007_phase9`

New tables:

- `candidate_wallets`
- `skills_passports`
- `privacy_impact_assessments`
- `data_assets`
- `data_lineage_edges`
- `retention_policies`
- `data_subject_requests`
- `red_team_campaigns`
- `continuous_control_snapshots`

## Important endpoints

```text
POST   /v1/wallets
GET    /v1/wallets
DELETE /v1/wallets/{wallet}

PUT /v1/skills-passport
GET /v1/skills-passport
GET /v1/portable-career-record

POST /v1/organizations/{org}/education-career-pathway

POST /v1/organizations/{org}/privacy/assessments
GET  /v1/organizations/{org}/privacy/assessments

POST /v1/organizations/{org}/data-assets
GET  /v1/organizations/{org}/data-assets
POST /v1/organizations/{org}/data-lineage
GET  /v1/organizations/{org}/data-lineage

PUT  /v1/organizations/{org}/retention
POST /v1/organizations/{org}/retention/{policy}/run

POST  /v1/privacy/requests
GET   /v1/privacy/requests
GET   /v1/privacy/requests/{request}/result
GET   /v1/organizations/{org}/privacy/requests
PATCH /v1/organizations/{org}/privacy/requests/{request}

POST /v1/organizations/{org}/red-team
GET  /v1/organizations/{org}/red-team

POST /v1/organizations/{org}/continuous-controls
```
