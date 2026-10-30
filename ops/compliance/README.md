# Compliance evidence operations

The application stores engineering evidence in `compliance_evidence`. Celery Beat
runs `career.collect_phase7_compliance_evidence` daily.

Before an audit/readiness review, add organization-specific evidence collectors for:

- cloud IAM exports
- KMS/Key Vault key rotation state
- PostgreSQL backup/PITR state
- vulnerability and image scan results
- incident-response exercises
- DR restore-test records
- change approvals
- penetration-test remediation
- employee access reviews

Evidence collectors should store hashes and metadata, not broad copies of secrets,
candidate resumes, or raw sensitive logs.

This system supports evidence preparation. Only an appropriately qualified independent
service auditor can issue a SOC report.
