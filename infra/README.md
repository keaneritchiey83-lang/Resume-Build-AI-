# Phase 5 production infrastructure

This directory contains production reference Terraform for AWS and Azure.

## AWS

The AWS stack provisions:

- Two-AZ VPC with public and private subnets
- Application Load Balancer
- ECS/Fargate API and Celery worker services
- RDS PostgreSQL 16
- ElastiCache Redis with encryption in transit and at rest
- AWS KMS envelope key
- CloudWatch log groups

Create a Secrets Manager JSON secret before `terraform apply` and pass its ARN as
`app_secret_arn`. It must contain the environment keys referenced in `infra/aws/main.tf`.

Phase 6 runs Alembic as a single explicit migration job before rolling out API replicas.

## Azure

The Azure stack provisions:

- Resource group and monitoring workspace
- Azure Container Apps environment
- API and Celery worker apps
- PostgreSQL Flexible Server 16
- `VECTOR` in `azure.extensions` so the migration can create pgvector
- Azure Managed Redis
- Key Vault RSA envelope key
- User-assigned managed identity
- Azure Container Registry

The API supports `KEY_PROVIDER=azure_key_vault`; data keys are wrapped with RSA-OAEP-256.
Create the application secrets in Key Vault and pass their versionless secret URIs to the
Terraform variables.

## Before production

Run provider certification/test flows separately for LinkedIn, Indeed, and ZipRecruiter.
Use custom DNS + TLS, WAF/firewall policy, private endpoints, backup restore drills,
database migration review, alerting, and jurisdiction-specific privacy/retention policy
before live candidate traffic.

## Phase 6 Kubernetes targets

`infra/eks` and `infra/aks` add private managed Kubernetes control planes on
top of the managed data/security services from Phase 5B.

- `infra/eks` expects an existing VPC/private subnets, KMS key and Secrets
  Manager secret from the AWS production foundation.
- `infra/aks` expects an existing resource group/subnet, ACR, Key Vault and Log
  Analytics workspace from the Azure production foundation.

This split intentionally prevents the Kubernetes cluster lifecycle from
accidentally destroying the database, encryption keys or retained audit data.

Run `terraform plan` and review changes before every production apply.


## Phase 6 networking hardening

- EKS grants the VPC CNI its own Pod Identity instead of inheriting CNI
  permissions from every node.
- EKS application workloads use a separate Pod Identity for KMS and runtime
  secret access. Cluster Autoscaler has an independent least-privilege role.
- AKS uses Azure CNI Overlay with the Cilium data plane/network policy engine.
- AKS application workloads use Microsoft Entra Workload Identity.
- Kubernetes API endpoints are private. Production deploy jobs therefore run
  from self-hosted GitHub Actions runners with private network reachability.

## Image release path

Use `.github/workflows/release-cloud-images.yml` to publish immutable API and
web images directly to ECR or ACR. `deploy-kubernetes.yml` then deploys that
same immutable tag from a private-cluster runner.

### Azure Managed Redis queue compatibility

The Phase 6 Azure foundation sets Azure Managed Redis to `EnterpriseCluster`.
The application uses Redis as the Celery/KEDA queue and expects a single
endpoint. If you deliberately switch the cache to `OSSCluster`, you must also
replace/test the Celery broker transport and KEDA scaler with Redis
Cluster-aware equivalents before production rollout.
