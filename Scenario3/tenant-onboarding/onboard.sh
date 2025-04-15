#!/bin/bash
set -e

# Validate input parameters
if [ $# -lt 3 ]; then
    echo "Usage: $0 <tenant-name> <environment> <team-name> [cost-center] [department]"
    echo "Example: $0 team-a dev engineering CC001 Technology"
    exit 1
fi

TENANT_NAME=$1
TENANT_ENV=$2
TENANT_TEAM=$3
COST_CENTER=${4:-"CC000"}
DEPARTMENT=${5:-"Default"}

echo "Starting onboarding process for tenant: ${TENANT_NAME}"

# Create namespace with labels for cost allocation
kubectl create namespace ${TENANT_NAME}
kubectl label namespace ${TENANT_NAME} tenant=${TENANT_NAME} environment=${TENANT_ENV} \
    team=${TENANT_TEAM} cost-center=${COST_CENTER} department=${DEPARTMENT}

# Apply resource quotas
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ${TENANT_NAME}-quota
  namespace: ${TENANT_NAME}
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "100"
EOF

# Setup RBAC
kubectl apply -f - << EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${TENANT_NAME}-admin
  namespace: ${TENANT_NAME}
subjects:
- kind: Group
  name: ${TENANT_TEAM}
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: admin
  apiGroup: rbac.authorization.k8s.io
EOF

# Create ArgoCD project
argocd proj create ${TENANT_NAME} \
  --dest namespace:${TENANT_NAME},server:https://kubernetes.default.svc \
  --src https://github.com/company/${TENANT_NAME}-apps.git

# Setup network policies
envsubst < ../security/network-policies/tenant-isolation.yaml | kubectl apply -f -

# Setup Istio service mesh integration
kubectl label namespace ${TENANT_NAME} istio-injection=enabled

# Setup cost monitoring for the tenant
TENANT_NAMESPACE=${TENANT_NAME} envsubst < ../monitoring/tenant-monitoring/prometheus-rules.yaml | kubectl apply -f -

# Add tenant to chargeback configuration
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${TENANT_NAME}-cost-config
  namespace: kubecost
data:
  tenant.json: |
    {
      "name": "${TENANT_NAME}",
      "namespaces": ["${TENANT_NAME}"],
      "labels": {
        "team": "${TENANT_TEAM}",
        "department": "${DEPARTMENT}"
      },
      "costCenter": "${COST_CENTER}"
    }
EOF

# Create tenant documentation
mkdir -p ../docs/tenants/${TENANT_NAME}
cat << EOF > ../docs/tenants/${TENANT_NAME}/README.md
# ${TENANT_NAME} Tenant

## Overview
This tenant belongs to the ${TENANT_TEAM} team in the ${DEPARTMENT} department.

## Environment
- Environment: ${TENANT_ENV}
- Cost Center: ${COST_CENTER}

## Access
Access is managed through the ${TENANT_TEAM} group in Azure AD.

## Resources
- Namespace: ${TENANT_NAME}
- Resource Quota: ${TENANT_NAME}-quota
- Network Policy: tenant-isolation

## GitOps
- ArgoCD Project: ${TENANT_NAME}
- Source Repository: https://github.com/company/${TENANT_NAME}-apps.git
EOF

echo "Tenant ${TENANT_NAME} has been successfully onboarded!"
echo "Documentation created at ../docs/tenants/${TENANT_NAME}/README.md"