# Phase 11 security runbook

## Passkeys

- Set `PHASE11_WEBAUTHN_RP_ID` to the registrable application domain.
- Set `PHASE11_WEBAUTHN_ORIGINS` to exact HTTPS origins.
- Never use wildcard origins.
- Passkey private keys remain on authenticators. The database stores only COSE public-key material and counters.
- Retain recovery methods for account recovery; do not silently downgrade a high-assurance tenant to password-only authentication.

## DID resolution and trust

- Remote resolution is restricted to `did:web`.
- Every remote host must be present in `PHASE11_DID_WEB_ALLOWED_HOSTS`.
- HTTP redirects are disabled.
- A remotely resolved DID is `untrusted_remote` until explicitly added/reviewed in an organization trust registry.
- DID Resolution v1 is a W3C Candidate Recommendation Snapshot as of August 2026; avoid claiming Recommendation status.

## Bitstring Status List

- Lists are at least 131,072 bits.
- Public status-list retrieval should be cacheable through a privacy-preserving CDN.
- Production issuers must cryptographically secure the status-list credential with the same security family/parameters expected for the credential ecosystem.
- Status-list identifiers can create correlation risk. Disclose status only when required by the exchange.

## HAIP and mdoc

- HAIP static checks do not equal certification.
- mdoc structural parsing does not equal ISO cryptographic verification.
- Configure a certified/approved mdoc verifier before returning `verified`.
- Hardware-backed key claims remain `pending` until attestation evidence is checked under an explicit trust policy.

## Post-quantum migration

Inventory:
- TLS key exchange and server certificates.
- OIDC/JWT signing.
- OpenID4VC issuer/verifier signatures.
- backups and long-lived archives.
- KMS/HSM key wrapping.
- artifact signing.

NIST migration targets currently include:
- FIPS 203 / ML-KEM for key establishment.
- FIPS 204 / ML-DSA for signatures.
- FIPS 205 / SLH-DSA as a stateless hash-based signature alternative.

Do not replace protocol algorithms merely because a PQ algorithm exists. Use hybrid/migration profiles only when the relevant protocol, runtime, cloud service, and relying parties support them.

## Supply chain

Release workflows must:
1. build immutable artifacts;
2. generate SPDX or CycloneDX SBOMs;
3. create GitHub/Sigstore attestations;
4. scan for critical/high vulnerabilities;
5. verify the attestation before promotion.

## Confidential computing

Confidential-compute manifests are opt-in examples. Before scheduling production PII workloads:
- verify the runtime/TEE capability;
- validate remote attestation;
- pin expected measurements/policies;
- release secrets only after successful attestation;
- document fallback behavior.

## Continuous testing

The scheduled workflow performs dependency/static testing and optionally ZAP against `PENTEST_TARGET_URL`.
Only point DAST tooling at assets you own or are explicitly authorized to test.
High/critical findings require a human-owned remediation record; scans do not auto-close findings.
