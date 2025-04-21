# CI/CD Pipelines for Enterprise Kubernetes Platform

This directory contains CI/CD pipeline configurations for deploying and managing the Enterprise Kubernetes Platform. The pipelines automate the deployment and management of the platform components, including EKS clusters, ArgoCD, Istio, NGINX Ingress, Vault, monitoring stack with Kubecost integration, and tenant onboarding.

## Available Pipelines

### GitHub Actions

Located in `github-actions/platform-pipeline.yml`, this pipeline provides:

- Automated validation of Terraform, Kubernetes manifests, and Helm charts
- Security scanning with multiple tools (tfsec, Trivy, Gitleaks)
- Deployment of EKS clusters with Calico network policies
- Installation and configuration of platform services (ArgoCD, Istio, NGINX Ingress, Vault)
- Deployment of monitoring stack with Prometheus, Grafana, and Kubecost
- Tenant onboarding with proper isolation and resource quotas
- Comprehensive verification of the deployment

**Usage:**
- Automatically triggered on pushes to `main` and `develop` branches
- Can be manually triggered with environment and deployment type parameters

### GitLab CI/CD

Located in `gitlab/platform-pipeline.gitlab-ci.yml`, this pipeline provides:

- Multi-stage pipeline with validation, security, cluster, platform, monitoring, tenant, and verify stages
- Security scanning with SAST, Secret Detection, tfsec, and Trivy
- Environment-specific deployments based on branch
- Manual approval gates for production deployments
- Comprehensive verification and reporting

**Usage:**
- Automatically triggered on pushes to `main` and `develop` branches
- Deployment to production requires manual approval

### Jenkins

Located in `jenkins/Jenkinsfile`, this pipeline provides:

- Kubernetes-based Jenkins agents for isolation and reproducibility
- Parameterized builds for environment selection and deployment type
- Validation of Terraform, Kubernetes manifests, and Helm charts
- Security scanning with tfsec and Trivy
- Deployment of the complete platform stack
- Verification of the deployment
- Integration with Slack and JIRA for notifications

**Usage:**
- Configure a Jenkins pipeline job pointing to this Jenkinsfile
- Run the pipeline with parameters for environment and deployment type

## Pipeline Stages

All pipelines follow a similar workflow:

1. **Validation**: Validate Terraform configurations, Kubernetes manifests, and Helm charts
2. **Security Scanning**: Scan infrastructure code and Kubernetes manifests for security issues
3. **Cluster Deployment**: Deploy EKS clusters with Calico network policies
4. **Platform Services Deployment**: Install and configure ArgoCD, Istio, NGINX Ingress, and Vault
5. **Monitoring Deployment**: Deploy Prometheus, Grafana, and Kubecost for comprehensive monitoring
6. **Tenant Onboarding**: Onboard tenants with proper isolation, RBAC, and resource quotas
7. **Verification**: Verify the deployment and generate reports

## Kubecost Integration

The platform includes Kubecost integration for cost monitoring and chargeback:

- Deployed in the `kubecost` namespace
- Configured for tenant-level cost attribution
- Integrated with Prometheus for metrics collection
- Provides cost dashboards in Grafana
- Enables chargeback reporting for tenant teams

## Environment-Specific Configurations

The pipelines support multiple environments:

- **dev**: Development environment for testing new features
- **qa**: Quality Assurance environment for testing before production
- **prod**: Production environment for running workloads

Each environment has its own configuration files:

- `clusters/terraform/{env}/`: Terraform configurations for each environment
- `monitoring/prometheus/values-{env}.yaml`: Environment-specific Prometheus configurations
- `monitoring/grafana/values-{env}.yaml`: Environment-specific Grafana configurations
- `monitoring/cost/kubecost-values-{env}.yaml`: Environment-specific Kubecost configurations
- `service-mesh/istio/istio-{env}.yaml`: Environment-specific Istio configurations
- `ingress/nginx/values-{env}.yaml`: Environment-specific NGINX Ingress configurations
- `security/vault/values-{env}.yaml`: Environment-specific Vault configurations

## Deployment Types

The pipelines support different deployment types:

- **full**: Deploy the complete platform stack
- **cluster-only**: Deploy only the EKS clusters
- **platform-services-only**: Deploy only the platform services
- **tenant-onboarding**: Perform tenant onboarding only

This allows for more targeted deployments when only specific components need to be updated.
