# Phase 8A + 8B implementation manifest

## Phase 8A

### Credential verification
- `backend/app/credential_verification.py`
- `verified_credentials`
- Structural W3C VC / Open Badges 3 inspection
- Expiry detection
- Proof/status presence reporting
- Optional fixed remote verifier integration
- Explicit structural-vs-cryptographic status boundary
- Envelope/KMS encrypted original credential payload
- Credential evidence separated from candidate-authored claims

### Learning provider integrations
- `backend/app/learning_providers.py`
- Organization-scoped encrypted connection credentials
- `LEARNING_PROVIDER_ALLOWED_HOSTS` SSRF boundary
- Open edX course-catalog connector
- Contract/API-bound configurable catalog adapter for enterprise providers
- Provider catalog normalization and provenance
- Celery scheduled sync

### Labor-market trends
- `backend/app/labor_market.py`
- Provenance-bearing labor observations
- BLS Public Data API v2 adapter for supplied series IDs (optional registered API key)
- OLS slope
- annualized historical change
- historical volatility
- coverage/stability confidence
- one-year linear projection
- explicit non-probability disclaimer

### Career portfolio
- `backend/app/portfolio.py`
- One encrypted portfolio per user
- Verified-credential section
- Candidate-authored projects/links
- Expiring random share tokens stored as hashes
- Share revocation
- contact excluded by default
- section-level visibility

## Phase 8B

### AI inventory and classification triage
- `backend/app/governance8.py`
- versioned organization AI inventory
- intended purpose / operator role / lifecycle / jurisdiction / model / data-category tracking
- employment and education use flags
- profiling and decision-influence flags
- human-oversight state
- conservative EU AI Act Annex III triage
- 2027-12-02 standalone high-risk applicability date
- Article 6(3) exemption left for documented case-specific review

### Risk management
- versioned AI risk assessments
- inherent/residual score
- control/hazard records
- approval state
- critical residual risk opens human review
- employment decision systems cannot be approved without human oversight

### Incident management
- encrypted incident details
- severity/category/status
- detection/containment/closure/reporting timestamps
- serious-incident candidate triage flag
- human-review trigger
- runbook in `ops/incidents/AI_INCIDENT_RUNBOOK.md`

### Control mapping
- `governance/phase8/eu_ai_act_crosswalk.json`
- `governance/phase8/iso42001_crosswalk.json`
- `governance/phase8/ai_inventory_template.json`
- `governance/phase8/credential_trust_profiles.json`
- public-law EU AI Act references
- high-level ISO/IEC 42001 themes only; no reproduction of the copyrighted standard

### Evidence automation
- scheduled Phase 8 evidence collection
- hash-addressed inventory/control/incident evidence
- reuses Phase 7 compliance evidence store
- audit-preparation disclaimer

### Policy-as-code additions
- local in-process Phase 8 enforcement mirrors OPA rules
`governance/policies/career.rego` additionally denies:
- representing structurally checked credentials as cryptographically verified
- public portfolio contact sharing without explicit selection
- high-risk-candidate employment AI release without human oversight
- high-risk-candidate employment AI release without approved risk assessment

## Database
Alembic:
- `0006_phase8_credentials_governance.py`

New tables:
1. `verified_credentials`
2. `learning_provider_connections`
3. `learning_catalog_items`
4. `labor_market_observations`
5. `labor_trend_snapshots`
6. `career_portfolios`
7. `career_portfolio_shares`
8. `ai_system_inventory`
9. `ai_risk_assessments`
10. `ai_incidents`
11. `governance_control_mappings`

## UI
The React dashboard adds:
- Credentials
- Portfolio
- Learning
- Assurance

## CI
- Phase 8 unit tests
- Python compile
- frontend build
- Phase 7 governance gate
- Phase 8 governance gate
- existing Terraform validation
- existing Kubernetes rendering/security checks
