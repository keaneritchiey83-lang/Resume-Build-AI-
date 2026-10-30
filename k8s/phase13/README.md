# Phase 13 Kubernetes notes

Phase 13 adds multi-region trust continuity and a bounded AI model gateway.

Production rules:

- Keep the SPIFFE Workload API socket read-only.
- Configure SPIFFE federation relationships out-of-band and review peer trust
  bundles before activation.
- Set `PHASE13_REGION_ID`, cloud and jurisdiction per regional overlay.
- Allow model egress only to the fixed model/confidential-inference endpoints.
- Do not grant the model gateway Kubernetes credentials or provider job-board
  credentials.
- Run Celery Beat as a single replica so trust snapshots are not duplicated.
- Use immutable image digests and verify release attestations before rollout.
