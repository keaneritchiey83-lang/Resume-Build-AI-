# Phase 10 OpenID credential operations

## Production prerequisites

- HTTPS public base URL.
- Stable issuer/verifier identifiers.
- Database migration `0008_phase10`.
- Envelope encryption backed by AWS KMS, Azure Key Vault or equivalent.
- Platform-admin approval workflow for every issuer and verifier.
- Approved wallet client registry.
- Static external issuer trust anchors.
- Monitoring for nonce, token and presentation verification failures.

## Signing keys

The reference issuer stores ES256 private keys through the existing envelope-encryption
layer. Production deployments should move signing operations behind an HSM/KMS signing
interface before treating the issuer as a high-assurance credential authority.

Never export issuer private keys through an API.

## Interoperability scope

The reference supports one JWT key proof per request. Batch issuance, mdoc, CWT proof,
key attestation, PAR, DPoP and deferred issuance are intentionally not advertised.

## SD-JWT VC

Selective-disclosure mechanics follow RFC 9901. The `dc+sd-jwt` credential profile follows
the current IETF SD-JWT VC draft and must not be represented as a final RFC profile until
that specification actually reaches that status.
