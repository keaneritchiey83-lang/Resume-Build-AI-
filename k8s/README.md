# Kubernetes deployment

`base` contains vendor-neutral workloads. `overlays/eks` and `overlays/aks`
supply cloud-specific identity/encryption configuration.

Prerequisites:

- ingress-nginx
- Metrics Server
- KEDA
- cert-manager if the cluster owns certificate issuance
- a `career-runtime` Secret synchronized from the organization's secret manager
- PostgreSQL + pgvector and Redis reachable from private cluster subnets

Run migrations once per release using `k8s/jobs/migrate.yaml`. Do not put
`alembic upgrade head` in every API replica.

The worker KEDA manifest uses the Redis list named `celery`. If your managed
Redis deployment uses Redis Cluster, adapt the scaler to `redis-cluster` and
supply `REDIS_ADDRESSES` as described by the KEDA Redis Cluster scaler.

For production, pin Kubernetes add-on/chart/image versions after testing them
rather than tracking `latest`.

## Cloud networking choices

The EKS foundation uses a dedicated VPC CNI Pod Identity and a separate
application Pod Identity. Managed node groups provide Cluster Autoscaler
discovery; the autoscaler IAM policy additionally requires the cluster
autoscaler resource tags.

The AKS foundation uses Azure CNI Overlay with Cilium. The default pod/service
CIDRs in `infra/aks/variables.tf` are examples and must be changed if they
overlap with the target VNet, connected networks, VPN ranges, or on-premises
routes.

## Runtime secret injection

`career-runtime` is deliberately not committed. For local/non-production use,
start from `runtime-secret.example.yaml`. In production, populate the secret
through your approved secret-delivery system (for example Secrets Store CSI or
External Secrets backed by Secrets Manager/Key Vault). Never place production
secret values in Git or Terraform state as plaintext variables.
