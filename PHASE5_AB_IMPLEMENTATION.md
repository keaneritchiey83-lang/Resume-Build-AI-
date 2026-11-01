# Phase 5A + 5B implementation manifest

This build combines both Phase 5 tracks into one deployable repository.

## Phase 5A

Primary files:

- `backend/app/webhook_pipeline.py`
- `backend/app/tasks.py`
- `backend/app/celery_app.py`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/alembic/versions/0003_phase5_webhook_pipeline.py`
- `backend/tests/test_phase5_webhooks.py`

Inbound partner callbacks are authenticated before durable storage. Expensive
candidate and resume processing occurs asynchronously. PostgreSQL is the durable
inbox so a transient Redis/worker failure does not discard an authenticated event.

## Phase 5B

Primary files:

- `infra/aws/main.tf`
- `infra/aws/variables.tf`
- `infra/aws/outputs.tf`
- `infra/azure/main.tf`
- `infra/azure/variables.tf`
- `infra/azure/outputs.tf`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `infra/README.md`

The AWS reference uses IAM/KMS/Secrets Manager rather than embedded cloud
credentials. The Azure reference uses managed identity/Key Vault and Azure Managed
Redis with private connectivity.

## Provider boundary

LinkedIn, Indeed and ZipRecruiter functionality is activated only when the
organization has the corresponding approved integration agreement and credentials.
The adapters are not web scrapers and are not treated as unrestricted public
job-search feeds.

## Production gates

Before production:

1. Run backend tests and frontend build.
2. Run `terraform fmt` and `terraform validate`.
3. Configure HTTPS callback URLs with each provider.
4. Store provider credentials through the encrypted organization credential API.
5. Verify replay/idempotency behavior in provider sandboxes.
6. Configure malware scanning/CDR for resume attachments.
7. Configure retention schedules and candidate privacy/deletion workflows.
8. Test database restore and dead-letter reprocessing.
9. Use protected GitHub environments with required reviewers.
10. Perform provider-specific security review before enabling live callbacks.
