# Phase 6A + 6B implementation manifest

## Phase 6A

Implemented:

- purpose-specific candidate consent ledger;
- encrypted career-monitor policy;
- revocation-aware scheduled job monitoring;
- encrypted job recommendations;
- deterministic candidate/job preference scoring;
- in-app monitored-job alerts;
- three-agent bounded career-analysis team with a two-turn execution cap;
- fact-ledger evidence validation;
- Agents SDK candidate-run tracing disabled by default to avoid duplicate sensitive traces;
- no auto-apply/contact-employer tool surface;
- encrypted agent run records and token usage;
- recruiter organization role;
- recruiter pipeline endpoint;
- recruiter application-stage updates;
- aggregate organization analytics;
- analytics retention policy;
- dashboard UI for career agents and recruiters.

Primary files:

- `backend/app/career_agents.py`
- `backend/app/monitoring.py`
- `backend/app/recruiter_analytics.py`
- `backend/app/phase6_api.py`
- `backend/alembic/versions/0004_phase6_agents_analytics.py`
- `backend/tests/test_phase6_agents.py`
- `frontend/src/App.tsx`

## Phase 6B

Implemented:

- hardened non-root API image;
- one-shot migration job;
- Kubernetes base manifests;
- API/frontend HPA;
- KEDA worker scaling;
- PodDisruptionBudgets;
- topology spreading;
- restricted Pod Security namespace;
- default-deny NetworkPolicies;
- OpenTelemetry application instrumentation;
- in-cluster OTEL Collector;
- SIEM-friendly structured audit events;
- EKS private-cluster Terraform;
- EKS Pod Identity with a dedicated VPC CNI role and separate application role;
- EKS control-plane audit logging;
- managed node group + Cluster Autoscaler integration;
- AKS private-cluster Terraform;
- AKS Workload Identity;
- Azure CNI Overlay powered by Cilium;
- AKS KEDA and node autoscaling;
- Azure Policy and Container Insights;
- DR runbook and quarterly restore checklist;
- image release workflow;
- private-cluster deployment workflow;
- CI rendering/validation for Kubernetes and both new Terraform targets.

Primary files:

- `k8s/base/*`
- `k8s/overlays/eks/*`
- `k8s/overlays/aks/*`
- `infra/eks/*`
- `infra/aks/*`
- `backend/app/telemetry.py`
- `ops/siem/README.md`
- `ops/dr/*`
- `.github/workflows/deploy-kubernetes.yml`
- `.github/workflows/release-images.yml`
- `.github/workflows/release-cloud-images.yml`

## Explicit non-features

The agents do not:

- automatically apply to jobs;
- send recruiter/employer messages;
- modify candidate facts;
- bypass provider access controls;
- scrape restricted job boards;
- rank candidates using protected characteristics.

Those boundaries require separate product/legal/security decisions rather than
being silently introduced by a background agent.
