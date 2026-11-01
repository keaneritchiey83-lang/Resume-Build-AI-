# Phase 12 federation onboarding runbook

1. Obtain the trust anchor entity ID and public keys through an independent trusted channel.
2. Platform admin installs the organization-scoped anchor.
3. Organization admin registers leaf/intermediate entity public JWKS and signed statements.
4. Validate each self-statement and parent subordinate statement.
5. Confirm the chain terminates at the intended approved anchor.
6. Review trust marks, metadata and metadata-policy requirements for the ecosystem.
7. Configure wallet-attestation certificate roots separately from federation JWT keys.
8. Create credential-negotiation policies only after the federation path is trusted.
9. Revalidate on key rotation, trust-mark changes, anchor updates or incident response.
10. Disable compromised anchors/entities immediately; do not trust dynamic resolution alone.
