# Phase 12 incident containment runbook

1. Confirm the runtime event source, severity, workload, namespace and event digest.
2. Check whether an automatic reversible action already disabled provider connectors or
   paused career monitors.
3. Preserve evidence before changing infrastructure state.
4. For `request_network_quarantine` or `request_workload_isolation`, approve only after
   confirming the target identity through workload identity / cluster telemetry.
5. Execute infrastructure isolation with a dedicated security-controller identity, not
   with the public API service account.
6. Rotate exposed provider credentials or signing permissions if compromise is suspected.
7. Verify cryptographic audit and runtime logs.
8. Re-enable connectors/monitoring only after remediation and human review.
9. Mark the runtime event resolved and retain evidence according to policy.
10. Run a post-incident review and update detection/containment policy.
