# Quarterly restore test checklist

- [ ] Recovery ticket/change record created.
- [ ] Isolated recovery account/subscription and network confirmed.
- [ ] Backup recovery point selected and recorded.
- [ ] Database restored successfully.
- [ ] Encryption keys usable without exporting key material.
- [ ] `alembic current` matches the production application release.
- [ ] Random encrypted profiles decrypt successfully.
- [ ] Cross-tenant access tests fail as expected.
- [ ] Webhook inbox idempotency tests pass.
- [ ] Career-monitor consent remains unchanged after restore.
- [ ] No revoked consent is re-enabled.
- [ ] API and worker health checks pass.
- [ ] RPO/RTO measurements recorded.
- [ ] Recovery resources destroyed or sanitized after evidence capture.
