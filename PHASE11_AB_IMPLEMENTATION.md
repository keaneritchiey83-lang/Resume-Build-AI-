# Phase 11A + 11B implementation

## Phase 11A — identity interoperability

Implemented:

- WebAuthn Level 3/passkey server flows using `py_webauthn`.
- User-verification-required registration and authentication.
- Single-use, expiring challenge records.
- Organization DID trust registries.
- Static trust resolution plus allowlisted `did:web`.
- No arbitrary DID/network fetching.
- W3C Bitstring Status List v1.0 data model.
- Minimum 131,072-bit status lists.
- Credential-to-status-slot assignments.
- HAIP 1.0 static readiness assessment.
- `mso_mdoc` structural ingestion and configurable cryptographic verifier.
- Wallet public-key attestation records.
- Hardware-backed claims stay pending until verified.
- No wallet private-key custody.

Important standards status:

- Bitstring Status List v1.0: W3C Recommendation, 15 May 2025.
- OpenID4VC HAIP 1.0: OpenID Final Specification, December 2025.
- WebAuthn Level 3: W3C Recommendation, 25 August 2026.
- DID Resolution v1: Candidate Recommendation Snapshot, 6 August 2026.
- ISO mdoc support is implemented as protocol/verification integration; this repository does not reproduce ISO copyrighted text or claim ISO certification.

## Phase 11B — security engineering

Implemented:

- Passkeys/WebAuthn.
- Confidential-computing opt-in Kubernetes workload template.
- Confidential-workload attestation evidence records.
- Cryptographic inventory and PQ migration status.
- NIST FIPS 203/204/205 target mapping.
- SBOM generation.
- GitHub/Sigstore build/SBOM attestations.
- Trivy image scanning.
- pip-audit and Bandit.
- Scheduled authorized ZAP baseline workflow.
- Security runbook.
- Phase 11 governance gate.

The PQ layer is deliberately "crypto-agility/readiness", not an unsafe unilateral replacement of TLS/JWT/VC algorithms. Protocol-specific PQ migration is enabled only when interoperable profiles and relying parties support it.
