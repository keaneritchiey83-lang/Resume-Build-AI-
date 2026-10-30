#!/usr/bin/env bash
set -euo pipefail

CLOUD="${1:-}"
CLUSTER_NAME="${2:-}"

if [[ -z "${CLOUD}" || -z "${CLUSTER_NAME}" ]]; then
  echo "usage: $0 <eks|aks> <cluster-name>" >&2
  exit 2
fi

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo add kedacore https://kedacore.github.io/charts
helm repo add jetstack https://charts.jetstack.io
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

helm upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system

helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.metrics.enabled=true

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true

helm upgrade --install opentelemetry-operator \
  open-telemetry/opentelemetry-operator \
  --namespace opentelemetry-operator-system \
  --create-namespace

if [[ "${CLOUD}" == "eks" ]]; then
  helm repo add autoscaler https://kubernetes.github.io/autoscaler
  helm repo update

  helm upgrade --install keda kedacore/keda \
    --namespace keda \
    --create-namespace

  helm upgrade --install cluster-autoscaler \
    autoscaler/cluster-autoscaler \
    --namespace kube-system \
    --set autoDiscovery.clusterName="${CLUSTER_NAME}" \
    --set awsRegion="${AWS_REGION:?AWS_REGION is required for EKS}" \
    --set rbac.serviceAccount.create=true \
    --set rbac.serviceAccount.name=cluster-autoscaler \
    --set extraArgs.balance-similar-node-groups=true \
    --set extraArgs.skip-nodes-with-system-pods=false
elif [[ "${CLOUD}" == "aks" ]]; then
  echo "AKS KEDA is enabled by Terraform. Skipping the Helm KEDA installation."
else
  echo "Unsupported cloud: ${CLOUD}" >&2
  exit 2
fi

kubectl label namespace career-ai \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted \
  --overwrite 2>/dev/null || true
