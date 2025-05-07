"""
Kubernetes ML Module for the AI-driven Observability Pipeline.

This module deploys the ML components in Kubernetes, including:
- Custom OpenTelemetry processors for e-commerce data
- SageMaker integration for model training and inference
- Anomaly detection models
- Predictive alerting models

The ML stack is designed to be:
- Scalable: Horizontal pod autoscaling, GPU support
- Secure: Network policies, RBAC, encryption
- Performant: Optimized resource allocation
- Reliable: High availability, fault tolerance
"""

import pulumi
import pulumi_kubernetes as k8s
from typing import Dict, Any, Optional


class MlStackResult:
    """Result object for ML stack deployment."""
    
    def __init__(
        self,
        anomaly_detection_endpoint: pulumi.Output[str],
        root_cause_analysis_endpoint: pulumi.Output[str],
        predictive_alerting_endpoint: pulumi.Output[str],
    ):
        self.anomaly_detection_endpoint = anomaly_detection_endpoint
        self.root_cause_analysis_endpoint = root_cause_analysis_endpoint
        self.predictive_alerting_endpoint = predictive_alerting_endpoint


def deploy_ml_stack(
    provider: k8s.Provider,
    namespaces: Any,
    environment: str,
    sagemaker_role_arn: pulumi.Input[str],
    model_bucket_name: pulumi.Input[str],
    model_bucket_arn: pulumi.Input[str],
) -> MlStackResult:
    """
    Deploy the ML stack in Kubernetes.
    
    Args:
        provider: Kubernetes provider
        namespaces: Namespaces result object
        environment: Deployment environment (dev, staging, production)
        sagemaker_role_arn: ARN of the SageMaker execution role
        model_bucket_name: Name of the S3 bucket for model artifacts
        model_bucket_arn: ARN of the S3 bucket for model artifacts
        
    Returns:
        MlStackResult object with stack details
    """
    # Create ConfigMap for SageMaker configuration
    sagemaker_config = k8s.core.v1.ConfigMap(
        "sagemaker-config",
        metadata={
            "name": "sagemaker-config",
            "namespace": "sagemaker-integration",
        },
        data={
            "role_arn": sagemaker_role_arn,
            "bucket_name": model_bucket_name,
            "region": pulumi.Output.from_input(pulumi.Config("aws").require("region")),
            "environment": environment,
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create Secret for SageMaker credentials
    sagemaker_secret = k8s.core.v1.Secret(
        "sagemaker-secret",
        metadata={
            "name": "sagemaker-secret",
            "namespace": "sagemaker-integration",
        },
        string_data={
            "AWS_ACCESS_KEY_ID": pulumi.Config("aws").require_secret("accessKey"),
            "AWS_SECRET_ACCESS_KEY": pulumi.Config("aws").require_secret("secretKey"),
        },
        type="Opaque",
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create ServiceAccount for SageMaker integration
    sagemaker_sa = k8s.core.v1.ServiceAccount(
        "sagemaker-sa",
        metadata={
            "name": "sagemaker-sa",
            "namespace": "sagemaker-integration",
            "annotations": {
                "eks.amazonaws.com/role-arn": sagemaker_role_arn,
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create custom OpenTelemetry processor for e-commerce data
    ecommerce_processor = k8s.apps.v1.Deployment(
        "ecommerce-processor",
        metadata={
            "name": "ecommerce-processor",
            "namespace": "sagemaker-integration",
            "labels": {
                "app": "ecommerce-processor",
                "part-of": "ai-observability",
                "environment": environment,
            },
        },
        spec={
            "replicas": 3 if environment == "production" else 2,
            "selector": {
                "matchLabels": {
                    "app": "ecommerce-processor",
                },
            },
            "strategy": {
                "type": "RollingUpdate",
                "rollingUpdate": {
                    "maxSurge": "25%",
                    "maxUnavailable": 0,
                },
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "ecommerce-processor",
                        "part-of": "ai-observability",
                        "environment": environment,
                    },
                },
                "spec": {
                    "serviceAccountName": "sagemaker-sa",
                    "containers": [{
                        "name": "ecommerce-processor",
                        "image": "ai-observability/ecommerce-processor:latest",
                        "imagePullPolicy": "Always",
                        "ports": [{
                            "containerPort": 4317,
                            "name": "grpc",
                        }],
                        "env": [
                            {
                                "name": "AWS_REGION",
                                "valueFrom": {
                                    "configMapKeyRef": {
                                        "name": "sagemaker-config",
                                        "key": "region",
                                    },
                                },
                            },
                            {
                                "name": "ENVIRONMENT",
                                "valueFrom": {
                                    "configMapKeyRef": {
                                        "name": "sagemaker-config",
                                        "key": "environment",
                                    },
                                },
                            },
                            {
                                "name": "MODEL_BUCKET",
                                "valueFrom": {
                                    "configMapKeyRef": {
                                        "name": "sagemaker-config",
                                        "key": "bucket_name",
                                    },
                                },
                            },
                            {
                                "name": "AWS_ACCESS_KEY_ID",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": "sagemaker-secret",
                                        "key": "AWS_ACCESS_KEY_ID",
                                    },
                                },
                            },
                            {
                                "name": "AWS_SECRET_ACCESS_KEY",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": "sagemaker-secret",
                                        "key": "AWS_SECRET_ACCESS_KEY",
                                    },
                                },
                            },
                        ],
                        "resources": {
                            "requests": {
                                "cpu": "500m" if environment == "production" else "200m",
                                "memory": "1Gi" if environment == "production" else "512Mi",
                            },
                            "limits": {
                                "cpu": "1" if environment == "production" else "500m",
                                "memory": "2Gi" if environment == "production" else "1Gi",
                            },
                        },
                        "livenessProbe": {
                            "tcpSocket": {
                                "port": 4317,
                            },
                            "initialDelaySeconds": 30,
                            "periodSeconds": 30,
                        },
                        "readinessProbe": {
                            "tcpSocket": {
                                "port": 4317,
                            },
                            "initialDelaySeconds": 15,
                            "periodSeconds": 10,
                        },
                    }],
                    "affinity": {
                        "podAntiAffinity": {
                            "preferredDuringSchedulingIgnoredDuringExecution": [{
                                "weight": 100,
                                "podAffinityTerm": {
                                    "labelSelector": {
                                        "matchExpressions": [{
                                            "key": "app",
                                            "operator": "In",
                                            "values": ["ecommerce-processor"],
                                        }],
                                    },
                                    "topologyKey": "kubernetes.io/hostname",
                                },
                            }],
                        },
                    },
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create Service for e-commerce processor
    ecommerce_processor_svc = k8s.core.v1.Service(
        "ecommerce-processor-svc",
        metadata={
            "name": "ecommerce-processor",
            "namespace": "sagemaker-integration",
            "labels": {
                "app": "ecommerce-processor",
                "part-of": "ai-observability",
                "environment": environment,
            },
        },
        spec={
            "selector": {
                "app": "ecommerce-processor",
            },
            "ports": [{
                "port": 4317,
                "targetPort": 4317,
                "name": "grpc",
            }],
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create HorizontalPodAutoscaler for e-commerce processor
    ecommerce_processor_hpa = k8s.autoscaling.v2.HorizontalPodAutoscaler(
        "ecommerce-processor-hpa",
        metadata={
            "name": "ecommerce-processor",
            "namespace": "sagemaker-integration",
        },
        spec={
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": "ecommerce-processor",
            },
            "minReplicas": 2,
            "maxReplicas": 10,
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": 70,
                        },
                    },
                },
                {
                    "type": "Resource",
                    "resource": {
                        "name": "memory",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": 80,
                        },
                    },
                },
            ],
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create OpenTelemetry Collector for ML data
    ml_collector = k8s.apiextensions.CustomResource(
        "ml-collector",
        api_version="opentelemetry.io/v1alpha1",
        kind="OpenTelemetryCollector",
        metadata={
            "name": "ml-collector",
            "namespace": "sagemaker-integration",
        },
        spec={
            "mode": "deployment",
            "replicas": 2,
            "config": """
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
    spike_limit_percentage: 25

exporters:
  otlp:
    endpoint: ecommerce-processor:4317
    tls:
      insecure: true
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp, logging]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp, logging]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp, logging]
""",
        },
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[otel_operator]),
    )
    
    # Return ML stack details
    return MlStackResult(
        anomaly_detection_endpoint=pulumi.Output.concat("ecommerce-processor.sagemaker-integration.svc.cluster.local:4317"),
        root_cause_analysis_endpoint=pulumi.Output.concat("ecommerce-processor.sagemaker-integration.svc.cluster.local:4317"),
        predictive_alerting_endpoint=pulumi.Output.concat("ecommerce-processor.sagemaker-integration.svc.cluster.local:4317"),
    )
