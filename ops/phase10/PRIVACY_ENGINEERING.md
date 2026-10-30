# Phase 10 privacy-engineering operations

## Discovery

Discovery inspects schema/table/column metadata only. Do not change it to sample production
plaintext unless a separately approved privacy/security design exists.

## Consent

Consent receipts are evidence of a recorded action, not proof that consent was the correct
lawful basis for every jurisdiction or purpose. Keep policy versions immutable.

## Deletion

Run a dry-run plan first. Confirm identity, legal holds, retention requirements, employment
record obligations and litigation requirements before executing an erasure workflow.

## Differential privacy

The reference uses fixed sensitivity-1 count queries with Laplace noise and a daily epsilon
budget. The same query hash reuses a prior release to reduce averaging attacks. Select an
epsilon budget through a documented privacy-risk process; do not treat the default as a
universal standard.

## Audit trail

Hash chaining detects mutation when a trusted chain head exists. For stronger assurance,
enable Ed25519 signatures and periodically anchor chain heads outside the application
database/administrative trust domain.
