# Edge Computing + Centralized CI/CD for IoT Analytics

This solution implements a centralized GitOps-controlled edge device management system using AWS Greengrass and Azure IoT Edge, with ArgoCD for deployment management.

## Architecture Overview

The solution consists of:
- Multi-cloud edge device management (AWS Greengrass / Azure IoT Edge)
- Centralized GitOps control plane using ArgoCD
- Progressive deployment system with blue/green and canary capabilities
- Secure secret management with HashiCorp Vault
- Comprehensive monitoring and telemetry pipeline

## Directory Structure
```
edge-platform/
├── infrastructure/        # Terraform configurations
├── gitops/               # ArgoCD and GitOps configurations
├── edge-components/      # Edge device components
├── security/             # Security configurations
├── monitoring/           # Monitoring stack
├── ci-cd/               # CI/CD pipeline configurations
└── docs/                # Documentation
```

## Getting Started
See [Deployment Guide](./docs/deployment-guide.md) for setup instructions.