# CI/CD Pipelines for AI-driven Observability

This directory contains CI/CD pipeline configurations for deploying the AI-driven Observability Pipeline for E-commerce. The pipelines automate the deployment and management of the observability stack, including Prometheus, Thanos, Jaeger, OpenTelemetry, SageMaker integration, and Grafana.

## Available Pipelines

### GitHub Actions

Located in `github-actions/observability-pipeline.yml`, this pipeline provides:

- Automated validation of Kubernetes manifests and Python scripts
- Security scanning with Trivy
- Building and packaging of Grafana dashboards
- Building and deploying SageMaker models
- Deployment of the complete observability stack
- Verification of the deployment
- Slack notifications

**Usage:**
- Automatically triggered on pushes to `main` and `develop` branches
- Can be manually triggered with environment and deployment type parameters

### Jenkins

Located in `jenkins/Jenkinsfile`, this pipeline provides:

- Kubernetes-based Jenkins agents for isolation and reproducibility
- Parameterized builds for environment selection and deployment type
- Validation of Kubernetes manifests and Python scripts
- Security scanning with Bandit
- Building and packaging of Grafana dashboards and SageMaker models
- Deployment of the complete observability stack
- Verification of the deployment

**Usage:**
- Configure a Jenkins pipeline job pointing to this Jenkinsfile
- Run the pipeline with parameters for environment and deployment type

### GitLab CI/CD

Located in `gitlab/.gitlab-ci.yml`, this pipeline provides:

- Multi-stage pipeline with validation, build, and deployment stages
- Security scanning with Bandit
- Building and packaging of Grafana dashboards and SageMaker models
- Deployment of the complete observability stack with manual approval gates
- Environment-specific deployments
- Verification of the deployment

**Usage:**
- Automatically triggered on pushes to `main` and `develop` branches
- Deployment stages require manual approval for safety

## Pipeline Stages

All pipelines follow a similar workflow:

1. **Validate**: Check Kubernetes manifests and Python scripts for errors
2. **Security Scan**: Scan code for vulnerabilities and security issues
3. **Build**: Package Grafana dashboards and SageMaker models
4. **Deploy Infrastructure**: Deploy Kafka, Elasticsearch, Jaeger, Prometheus, Thanos, and OpenTelemetry
5. **Deploy SageMaker**: Deploy SageMaker models and integration components
6. **Deploy Grafana**: Deploy Grafana with dashboards and RBAC configuration
7. **Verify**: Verify the deployment by checking all components

## Required Secrets

The pipelines require the following secrets to be configured:

### AWS Credentials
- `AWS_ACCESS_KEY_ID`: AWS access key with permissions for SageMaker and S3
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `SAGEMAKER_ROLE_ARN`: ARN of the IAM role for SageMaker execution
- `SAGEMAKER_MODEL_BUCKET`: S3 bucket for storing SageMaker models
- `AWS_ACCOUNT_ID`: AWS account ID for ECR image references
- `THANOS_AWS_ACCESS_KEY_ID`: AWS access key for Thanos S3 storage
- `THANOS_AWS_SECRET_ACCESS_KEY`: AWS secret key for Thanos S3 storage

### Kubernetes and Deployment
- `KUBECONFIG`: Kubernetes configuration for accessing the cluster
- `ELASTICSEARCH_PASSWORD`: Password for Elasticsearch
- `GRAFANA_ADMIN_PASSWORD`: Admin password for Grafana

### Grafana and Notifications
- `GRAFANA_OAUTH_CLIENT_ID`: OAuth client ID for Grafana
- `GRAFANA_OAUTH_CLIENT_SECRET`: OAuth client secret for Grafana
- `SLACK_SRE_WEBHOOK_URL`: Slack webhook URL for SRE notifications
- `SLACK_API_TOKEN`: Slack API token
- `PAGERDUTY_INTEGRATION_KEY`: PagerDuty integration key
- `SLACK_WEBHOOK_URL`: Slack webhook URL for pipeline notifications

## Manual Deployment

For manual deployment without CI/CD, use the `scripts/manual-deploy.sh` script in the parent directory.

## Best Practices

1. **Environment Separation**: Use different environments (dev, staging, prod) for testing changes
2. **Security First**: Always run security scans before deployment
3. **Validation**: Validate all configurations before applying them
4. **Incremental Updates**: Use the deployment type parameter to update specific components
5. **Verification**: Always verify the deployment after changes
6. **Notifications**: Configure notifications to alert teams of deployment status

## Troubleshooting

If the pipeline fails, check the following:

1. **Secret Configuration**: Ensure all required secrets are properly configured
2. **Kubernetes Access**: Verify that the pipeline has access to the Kubernetes cluster
3. **AWS Permissions**: Check that AWS credentials have the necessary permissions
4. **Resource Constraints**: Ensure the cluster has sufficient resources for the deployment
5. **Timeouts**: Increase timeouts for long-running operations like Elasticsearch deployment
