"""
Main Pulumi program for the AI-driven Observability Pipeline.

This program orchestrates the deployment of all infrastructure components
for the observability pipeline, including:
- AWS resources (VPC, EKS, SageMaker, etc.)
- Kubernetes resources (namespaces, deployments, services, etc.)
- Observability components (Prometheus, Grafana, Elasticsearch, etc.)
- ML components (SageMaker endpoints, custom models, etc.)

The infrastructure is designed to be:
- Highly available: No single points of failure
- Scalable: Can handle 500+ microservices
- Secure: Follows AWS and Kubernetes security best practices
- Cost-effective: Uses appropriate instance types and autoscaling
- Maintainable: Modular design with clear separation of concerns
"""

import pulumi
from pulumi import Config, Output, export

# Import infrastructure modules
from infrastructure.aws.vpc import create_vpc
from infrastructure.aws.eks import create_eks_cluster
from infrastructure.aws.sagemaker import create_sagemaker_resources
from infrastructure.aws.security import create_security_resources
from infrastructure.kubernetes.namespaces import create_namespaces
from infrastructure.kubernetes.observability import deploy_observability_stack
from infrastructure.kubernetes.ml import deploy_ml_stack

# Load configuration
config = Config()
env = config.require("environment")
project_name = config.get("projectName") or "ai-observability"
aws_region = config.get("awsRegion") or "us-east-1"

# Create tags that will be applied to all resources
tags = {
    "Environment": env,
    "Project": project_name,
    "ManagedBy": "pulumi",
}

# Create VPC
vpc = create_vpc(
    name=f"{project_name}-vpc",
    cidr=config.get("vpcCidr") or "10.0.0.0/16",
    azs=config.get_object("availabilityZones") or ["us-east-1a", "us-east-1b", "us-east-1c"],
    private_subnets=config.get_object("privateSubnetCidrs") or ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"],
    public_subnets=config.get_object("publicSubnetCidrs") or ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"],
    enable_nat_gateway=True,
    single_nat_gateway=env != "production",
    tags=tags,
)

# Create EKS cluster
eks_cluster = create_eks_cluster(
    name=f"{project_name}-{env}",
    vpc_id=vpc.vpc_id,
    subnet_ids=vpc.private_subnet_ids,
    node_groups={
        "system": {
            "instance_type": config.get("systemNodeInstanceType") or "m5.xlarge",
            "min_size": config.get_int("systemNodeMinSize") or 3,
            "max_size": config.get_int("systemNodeMaxSize") or 6,
            "desired_size": config.get_int("systemNodeDesiredSize") or 3,
            "labels": {"role": "system"},
            "taints": [{"key": "dedicated", "value": "system", "effect": "NO_SCHEDULE"}],
        },
        "application": {
            "instance_type": config.get("appNodeInstanceType") or "m5.2xlarge",
            "min_size": config.get_int("appNodeMinSize") or 3,
            "max_size": config.get_int("appNodeMaxSize") or 20,
            "desired_size": config.get_int("appNodeDesiredSize") or 5,
            "labels": {"role": "application"},
        },
        "ml": {
            "instance_type": config.get("mlNodeInstanceType") or "g4dn.xlarge",
            "min_size": config.get_int("mlNodeMinSize") or 0,
            "max_size": config.get_int("mlNodeMaxSize") or 5,
            "desired_size": config.get_int("mlNodeDesiredSize") or 2,
            "labels": {"role": "ml"},
        },
    },
    kubernetes_version=config.get("kubernetesVersion") or "1.24",
    tags=tags,
)

# Create security resources (KMS keys, IAM roles, etc.)
security_resources = create_security_resources(
    project_name=project_name,
    environment=env,
    tags=tags,
)

# Create SageMaker resources
sagemaker_resources = create_sagemaker_resources(
    project_name=project_name,
    environment=env,
    vpc_id=vpc.vpc_id,
    subnet_ids=vpc.private_subnet_ids,
    security_group_ids=[security_resources.sagemaker_sg_id],
    kms_key_id=security_resources.kms_key_id,
    tags=tags,
)

# Create Kubernetes namespaces
namespaces = create_namespaces(
    provider=eks_cluster.k8s_provider,
    namespaces=[
        "observability",
        "kafka",
        "elasticsearch",
        "jaeger",
        "prometheus",
        "grafana",
        "opentelemetry",
        "sagemaker-integration",
    ],
    environment=env,
)

# Deploy observability stack
observability_stack = deploy_observability_stack(
    provider=eks_cluster.k8s_provider,
    namespaces=namespaces,
    environment=env,
    elasticsearch_storage_class=eks_cluster.storage_class.metadata["name"],
    prometheus_storage_class=eks_cluster.storage_class.metadata["name"],
    grafana_storage_class=eks_cluster.storage_class.metadata["name"],
    kafka_storage_class=eks_cluster.storage_class.metadata["name"],
    domain=config.get("domain") or f"{project_name}.example.com",
)

# Deploy ML stack
ml_stack = deploy_ml_stack(
    provider=eks_cluster.k8s_provider,
    namespaces=namespaces,
    environment=env,
    sagemaker_role_arn=sagemaker_resources.execution_role_arn,
    model_bucket_name=sagemaker_resources.model_bucket_name,
    model_bucket_arn=sagemaker_resources.model_bucket_arn,
)

# Export important outputs
export("vpc_id", vpc.vpc_id)
export("eks_cluster_name", eks_cluster.cluster_name)
export("eks_cluster_endpoint", eks_cluster.cluster_endpoint)
export("kubeconfig", eks_cluster.kubeconfig)
export("model_bucket_name", sagemaker_resources.model_bucket_name)
export("sagemaker_role_arn", sagemaker_resources.execution_role_arn)
export("grafana_url", observability_stack.grafana_url)
export("prometheus_url", observability_stack.prometheus_url)
export("elasticsearch_url", observability_stack.elasticsearch_url)
export("jaeger_url", observability_stack.jaeger_url)
export("kafka_bootstrap_servers", observability_stack.kafka_bootstrap_servers)
export("anomaly_detection_endpoint", ml_stack.anomaly_detection_endpoint)
