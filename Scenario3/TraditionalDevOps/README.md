# Enterprise Kubernetes Platform as a Product

## Requirement

Deliver a centralized Kubernetes platform (EKS/GKE + Rancher/Anthos) for 20+ application teams with self-service GitOps, cost monitoring, RBAC, and secrets management.

## Challenges

- Multi-tenant cluster security and network isolation (Calico, Istio)
- ArgoCD multi-app/multi-project GitOps with dynamic templating (Kustomize/Helm)
- RBAC federation via SSO/OIDC for Dev, QA, and Prod environments
- Ingress strategy for 200+ services with domain routing (NGINX/Envoy)
- Shared services mesh (Istio) with mTLS and traffic shifting

## Overview

Centralized Kubernetes platform solution for 20+ application teams in a Fortune 500 company, providing:

- Multi-tenant EKS clusters with Rancher management
- Self-service GitOps deployment pipeline with ArgoCD
- Cost monitoring and chargeback with Kubecost
- Federated RBAC with Azure AD SSO integration
- Centralized secrets management with Vault
- Service mesh with Istio mTLS and traffic management
- Network isolation with Calico policies
- Ingress strategy for 200+ services with NGINX

## Architecture Components

### Infrastructure

- Multi-tenant EKS clusters (Dev, QA, Prod)
- Rancher for unified cluster management
- Calico for network policies and micro-segmentation

### Deployment and GitOps

- ArgoCD for GitOps deployment
- Multi-project organization
- Environment promotion workflows

### Security

- Azure AD integration via OIDC
- Federated RBAC across environments
- Istio service mesh with mTLS
- Network isolation with Calico

### Ingress and Traffic Management

- NGINX ingress controller with domain routing
- Ingress sharding for high-volume services
- Rate limiting and traffic management

### Monitoring and Cost Management

- Prometheus/Grafana for monitoring
- Kubecost for cost attribution and chargeback
- Tenant-level resource tracking

## Directory Structure

```
Scenario3/
├── clusters/                 # Cluster configurations
│   └── eks-cluster.tf        # EKS cluster Terraform
├── gitops/                   # ArgoCD and GitOps configs
│   └── argocd/               # ArgoCD configurations
├── security/                 # Security configurations
│   ├── rbac/                 # RBAC definitions
│   ├── oidc/                 # OIDC integration
│   └── network-policies/     # Calico network policies
├── service-mesh/             # Istio configurations
│   ├── istio/                # Istio mesh config
│   └── tenant-policies/      # Tenant-specific policies
├── ingress/                  # Ingress configurations
│   └── nginx/                # NGINX ingress controller
├── monitoring/               # Monitoring stack
│   ├── tenant-monitoring/    # Tenant-specific monitoring
│   └── cost/                 # Kubecost integration
├── tenant-onboarding/        # Tenant setup automation
│   └── onboard.sh            # Tenant onboarding script
└── docs/                     # Platform documentation
    ├── architecture/         # Architecture documentation
    ├── tenant-guide.md       # Guide for tenant teams
    └── platform-guide.md     # Platform overview
```

## Getting Started

### Platform Setup

Follow the detailed setup instructions in `docs/platform-guide.md` to deploy the platform components.

### Tenant Onboarding

To onboard a new tenant, use the onboarding script:

```bash
./tenant-onboarding/onboard.sh <tenant-name> <environment> <team-name> [cost-center] [department]
```

### Documentation

- `docs/platform-guide.md` - Comprehensive platform guide
- `docs/tenant-guide.md` - Guide for tenant teams
- `docs/architecture/` - Detailed architecture documentation

## Key Features

### Multi-Tenant Isolation

Each tenant operates in an isolated environment with:

- Dedicated namespace
- Network policies for isolation
- Service mesh authorization policies
- Resource quotas

### Self-Service GitOps

Tenants deploy applications using GitOps workflows:

- Commit changes to Git repository
- ArgoCD automatically syncs changes
- Environment promotion through Git

### Cost Management

Comprehensive cost monitoring and chargeback:

- Tenant-level cost attribution
- Chargeback reporting
- Optimization recommendations
