#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
namespace="dst-airlines"
env_file="${K8S_ENV_FILE:-$repo_dir/.env.k8s}"

if [[ -f "$env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
fi

required_variables=(
  POSTGRES_PASSWORD
  NEO4J_PASSWORD
  NEO4J_AUTH
  DATABASE_URL
  API_IMAGE
  DASHBOARD_IMAGE
)

for variable_name in "${required_variables[@]}"; do
  if [[ -z "${!variable_name:-}" ]]; then
    echo "Missing required variable: $variable_name" >&2
    echo "Copy .env.k8s.example to .env.k8s and replace all placeholders." >&2
    exit 1
  fi
done

kubectl create namespace "$namespace" \
  --dry-run=client \
  --output=yaml | kubectl apply -f -

kubectl --namespace "$namespace" create secret generic dst-airlines-secret \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  --from-literal=NEO4J_AUTH="$NEO4J_AUTH" \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --dry-run=client \
  --output=yaml | kubectl apply -f -

kubectl --namespace "$namespace" create configmap postgres-init \
  --from-file=init.sql="$repo_dir/database/sql/init.sql" \
  --dry-run=client \
  --output=yaml | kubectl apply -f -

kubectl apply -f "$repo_dir/k8s/configmap.yaml"
kubectl apply -f "$repo_dir/k8s/postgres-deployment.yaml"
kubectl apply -f "$repo_dir/k8s/mongo-deployment.yaml"
kubectl apply -f "$repo_dir/k8s/neo4j-deployment.yaml"
kubectl apply -f "$repo_dir/k8s/api-service.yaml"
kubectl apply -f "$repo_dir/k8s/api-deployment.yaml"
kubectl apply -f "$repo_dir/k8s/dashboard-service.yaml"
kubectl apply -f "$repo_dir/k8s/dashboard-deployment.yaml"

kubectl --namespace "$namespace" set image deployment/api "api=$API_IMAGE"
kubectl --namespace "$namespace" set image deployment/dashboard "dashboard=$DASHBOARD_IMAGE"

kubectl --namespace "$namespace" rollout status deployment/db --timeout=300s
kubectl --namespace "$namespace" rollout status deployment/mongo --timeout=300s
kubectl --namespace "$namespace" rollout status deployment/neo4j --timeout=300s
kubectl --namespace "$namespace" rollout status deployment/api --timeout=300s
kubectl --namespace "$namespace" rollout status deployment/dashboard --timeout=300s

kubectl --namespace "$namespace" get pods,services,persistentvolumeclaims
