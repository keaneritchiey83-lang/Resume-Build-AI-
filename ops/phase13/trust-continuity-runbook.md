# Phase 13 trust continuity / disaster-recovery runbook

## Purpose

Restore trust configuration after a regional failure without automatically trusting stale,
tampered, or foreign trust material.

## Before an incident

1. Register every active region through `/v1/phase13/regions`.
2. Review each cross-region link and pin the peer SPIFFE bundle digest.
3. Maintain OpenID Federation trust anchors through an independent administrative channel.
4. Configure the Phase 13 trust-snapshot signing key in a managed signing system where possible.
5. Confirm periodic `career.create_phase13_trust_snapshots` Celery jobs succeed.
6. Verify the `trust-continuity` transparency chain.
7. Keep cloud KMS/HSM keys regionally resilient according to the provider's documented service design.
8. Test restore procedures without changing production trust.

## During regional failover

1. Freeze automatic trust changes.
2. Identify the newest unexpired sealed snapshot.
3. Call the snapshot verification endpoint and verify the transparency-chain head independently.
4. Confirm the snapshot's region, federation-anchor digests, SPIFFE trust domains and HSM public keys.
5. Have an authorized human approve the snapshot for restore.
6. Restore configuration through an infrastructure controller with its own authorization boundary.
7. Do not let the public API mutate SPIRE Server, KMS/HSM trust roots or cloud IAM directly.
8. Validate SVID, OpenID Federation and credential-verification interoperability before reopening traffic.

## After recovery

1. Rotate temporary recovery credentials.
2. Capture a new continuity snapshot.
3. Append the recovery event to an independent incident/audit system.
4. Compare peer trust bundles against the pre-incident snapshot.
5. Re-run model/evaluation release gates before enabling AI automation in the recovered region.

## RTO/RPO

Set organization-specific targets. The reference code does not claim a particular RTO/RPO.
