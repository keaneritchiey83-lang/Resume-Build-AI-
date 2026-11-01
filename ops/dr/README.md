# Phase 6 disaster recovery runbook

Target service objectives should be approved by the organization before launch.
The reference targets are:

- Tier 1 API / identity: RTO 2 hours, RPO 15 minutes
- Candidate/application database: RTO 4 hours, RPO 15 minutes
- Analytics: RTO 24 hours, RPO 24 hours
- Rebuildable job/taxonomy indexes: RTO 24 hours

## Required controls

- PostgreSQL point-in-time recovery and automated backups
- cross-region/geo-redundant backup where contractual requirements permit it
- Redis treated as replaceable queue/cache; durable webhook inbox remains in PostgreSQL
- container images retained in immutable registries
- Terraform state remotely stored, encrypted, locked, and backed up
- KMS/Key Vault keys protected from accidental deletion
- quarterly database restore test into an isolated recovery environment
- semiannual regional failover exercise
- documented DNS/ingress cutover procedure
- audit evidence for each recovery exercise

## Recovery order

1. Freeze inbound provider processing or route it to a maintenance endpoint.
2. Restore/validate KMS or Key Vault access.
3. Restore PostgreSQL to the chosen recovery point.
4. Provision the Kubernetes cluster and platform add-ons from Terraform.
5. Restore runtime secrets from the approved secrets manager.
6. Run `alembic upgrade head`.
7. Deploy API, worker, beat, frontend, and OTEL collector.
8. Validate tenant boundaries, authentication, and encryption decryption.
9. Re-enable provider webhooks.
10. Requeue `received` / `retry` durable webhook events.
11. Resume job-monitoring scans.
12. Rebuild expendable semantic/job indexes if needed.

Never restore production candidate data into developer laptops or an
uncontrolled test environment.
