# Phase 10A + 10B implementation manifest

## Phase 10A

### OpenID4VCI
- organization-scoped issuer profiles;
- platform approval gate;
- ES256 issuer signing keys, envelope encrypted at rest;
- final well-known issuer-metadata path handling;
- OAuth authorization-server metadata;
- pre-registered wallet clients;
- authorization-code + PKCE S256 flow;
- pre-authorized-code flow with optional transaction code;
- one-use hashed authorization codes;
- one-use hashed pre-authorized codes;
- hashed bearer access tokens;
- nonce endpoint and nonce-bound holder proofs;
- final `proofs.jwt[]` Credential Request shape;
- `jwt_vc_json` profile;
- `dc+sd-jwt` current draft-profile support;
- candidate evidence assembled only from existing encrypted/verified platform data;
- credential issuance/status/revocation records;
- local project status profile with explicit non-Bitstring-Status warning;
- expired protocol-state minimization task.

### OpenID4VP
- organization-scoped verifier profiles;
- platform approval gate;
- `redirect_uri:` Client Identifier Prefix;
- DCQL request construction;
- `direct_post`;
- replay-safe nonce/state binding;
- encrypted presentation verification result;
- local issuer trust;
- administrator-installed external static JWK trust anchors;
- no arbitrary key URL fetching.

### RFC 9901 selective disclosure
- 128-bit random disclosure salt;
- base64url disclosure encoding;
- SHA-256 `_sd` commitments;
- selected-disclosure verification;
- KB-JWT `sd_hash`;
- verifier audience and nonce validation;
- EC P-256 holder binding.

## Phase 10B

### Data discovery
- SQLAlchemy schema-metadata discovery only;
- built-in classifications;
- organization custom classification rules;
- no plaintext sampling;
- scheduled organization scans.

### Consent receipts
- purpose-specific grant/revoke receipts;
- policy/lawful-basis/data-category metadata;
- candidate/purpose hash chaining.

### Deletion orchestration
- dry-run plans;
- optional identity-verified erasure DSAR binding;
- legal-hold enforcement;
- candidate-owned data inventory;
- credential protocol-state deletion;
- account pseudonymization/disable finalization.

### Privacy-preserving analytics
- fixed allowlisted count queries;
- organization membership boundary;
- minimum cohort suppression;
- Laplace mechanism;
- CSPRNG noise;
- daily epsilon composition budget;
- identical-query release reuse.

### Cryptographic audit
- append-only policy;
- SHA-256 per-organization chain;
- payload digests, not raw payloads;
- optional Ed25519 signatures;
- immutable organization identifier;
- scheduled verification.

## New backend files
- `backend/app/phase10_api.py`
- `backend/app/phase10_schemas.py`
- `backend/app/phase10_services.py`
- `backend/tests/test_phase10.py`
- `backend/alembic/versions/0008_phase10_credentials_privacy.py`
- `backend/scripts/run_phase10_governance_gate.py`

## New governance files
- `governance/phase10/openid_credential_interop.json`
- `governance/phase10/privacy_engineering_profile.json`
- `governance/phase10/selective_disclosure_profile.json`

## Retained safety boundaries
Phase 10 does not add autonomous job applications, autonomous employer messages,
candidate-wallet private-key custody, arbitrary trust-key retrieval, unrestricted web
scraping, protected-trait ranking, or automatic claims that an unverified credential is
verified.
