# Phase 6 SIEM and observability integration

The application emits two categories of telemetry:

1. OpenTelemetry traces and metrics to the in-cluster OTLP Collector.
2. One-line JSON security/audit events on stdout with `event_type=security_audit`.

Do not put secrets, résumé bodies, provider payloads, access tokens, candidate
email addresses, or decrypted profile contents in telemetry.

## Collector

`k8s/base/otel-collector.yaml` accepts OTLP/gRPC and OTLP/HTTP and forwards
traces/metrics to the configured `SIEM_OTLP_ENDPOINT`. Use a vendor gateway or
an organization-controlled OTLP endpoint. Keep its authorization value in the
runtime secret store.

## AWS

- EKS control-plane audit/API/authenticator logs go to CloudWatch.
- Ship container stdout/stderr with your approved EKS logging integration.
- Route JSON security events and CloudTrail/EKS audit logs to the enterprise
  SIEM or Amazon Security Lake.
- Alert on authentication failures, permission denials, provider credential
  changes, webhook dead letters, data-key rotation failures, and unusual agent
  token volume.

## Azure

- AKS Container Insights sends cluster/container logs to Log Analytics.
- Enable Microsoft Sentinel on the workspace when Sentinel is the selected SIEM.
- Create analytics rules for the same security events listed above.
- Keep Key Vault diagnostics and AKS audit logs in the central workspace.

## Minimum alert rules

- repeated failed login/MFA attempts
- organization role escalation
- provider credential creation/rotation
- dead-letter webhook growth
- career-agent guardrail failures
- unusual job-monitor scan volume
- KMS/Key Vault decrypt failures
- Kubernetes privileged-pod or policy violations
