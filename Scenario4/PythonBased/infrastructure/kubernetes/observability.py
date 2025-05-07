"""
Kubernetes Observability Module for the AI-driven Observability Pipeline.

This module deploys the observability stack in Kubernetes, including:
- Prometheus for metrics collection and storage
- Grafana for visualization
- Elasticsearch for log storage
- Jaeger for distributed tracing
- Kafka for data streaming
- OpenTelemetry for data collection

The observability stack is designed to be:
- Highly available: Multiple replicas, anti-affinity rules
- Scalable: Horizontal pod autoscaling, storage scaling
- Secure: Network policies, RBAC, encryption
- Performant: Optimized resource allocation
"""

import pulumi
import pulumi_kubernetes as k8s
from typing import Dict, Any, Optional


class ObservabilityStackResult:
    """Result object for observability stack deployment."""
    
    def __init__(
        self,
        prometheus_url: pulumi.Output[str],
        grafana_url: pulumi.Output[str],
        elasticsearch_url: pulumi.Output[str],
        jaeger_url: pulumi.Output[str],
        kafka_bootstrap_servers: pulumi.Output[str],
    ):
        self.prometheus_url = prometheus_url
        self.grafana_url = grafana_url
        self.elasticsearch_url = elasticsearch_url
        self.jaeger_url = jaeger_url
        self.kafka_bootstrap_servers = kafka_bootstrap_servers


def deploy_observability_stack(
    provider: k8s.Provider,
    namespaces: Any,
    environment: str,
    elasticsearch_storage_class: str,
    prometheus_storage_class: str,
    grafana_storage_class: str,
    kafka_storage_class: str,
    domain: str,
) -> ObservabilityStackResult:
    """
    Deploy the observability stack in Kubernetes.
    
    Args:
        provider: Kubernetes provider
        namespaces: Namespaces result object
        environment: Deployment environment (dev, staging, production)
        elasticsearch_storage_class: Storage class for Elasticsearch
        prometheus_storage_class: Storage class for Prometheus
        grafana_storage_class: Storage class for Grafana
        kafka_storage_class: Storage class for Kafka
        domain: Domain name for ingress
        
    Returns:
        ObservabilityStackResult object with stack details
    """
    # Create Prometheus operator
    prometheus_operator = k8s.helm.v3.Release(
        "prometheus-operator",
        chart="kube-prometheus-stack",
        version="45.7.1",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://prometheus-community.github.io/helm-charts",
        ),
        namespace="prometheus",
        values={
            "prometheus": {
                "prometheusSpec": {
                    "replicas": 2 if environment == "production" else 1,
                    "retention": "15d",
                    "storageSpec": {
                        "volumeClaimTemplate": {
                            "spec": {
                                "storageClassName": prometheus_storage_class,
                                "accessModes": ["ReadWriteOnce"],
                                "resources": {
                                    "requests": {
                                        "storage": "100Gi" if environment == "production" else "50Gi",
                                    },
                                },
                            },
                        },
                    },
                    "resources": {
                        "requests": {
                            "cpu": "1" if environment == "production" else "500m",
                            "memory": "4Gi" if environment == "production" else "2Gi",
                        },
                        "limits": {
                            "cpu": "2" if environment == "production" else "1",
                            "memory": "8Gi" if environment == "production" else "4Gi",
                        },
                    },
                    "podAntiAffinity": {
                        "preferredDuringSchedulingIgnoredDuringExecution": [{
                            "weight": 100,
                            "podAffinityTerm": {
                                "labelSelector": {
                                    "matchExpressions": [{
                                        "key": "app",
                                        "operator": "In",
                                        "values": ["prometheus"],
                                    }],
                                },
                                "topologyKey": "kubernetes.io/hostname",
                            },
                        }],
                    },
                    "securityContext": {
                        "fsGroup": 2000,
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                    },
                },
            },
            "alertmanager": {
                "alertmanagerSpec": {
                    "replicas": 2 if environment == "production" else 1,
                    "resources": {
                        "requests": {
                            "cpu": "100m",
                            "memory": "256Mi",
                        },
                        "limits": {
                            "cpu": "200m",
                            "memory": "512Mi",
                        },
                    },
                    "podAntiAffinity": {
                        "preferredDuringSchedulingIgnoredDuringExecution": [{
                            "weight": 100,
                            "podAffinityTerm": {
                                "labelSelector": {
                                    "matchExpressions": [{
                                        "key": "app",
                                        "operator": "In",
                                        "values": ["alertmanager"],
                                    }],
                                },
                                "topologyKey": "kubernetes.io/hostname",
                            },
                        }],
                    },
                    "securityContext": {
                        "fsGroup": 2000,
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                    },
                },
            },
            "grafana": {
                "replicas": 2 if environment == "production" else 1,
                "persistence": {
                    "enabled": True,
                    "storageClassName": grafana_storage_class,
                    "size": "10Gi",
                },
                "resources": {
                    "requests": {
                        "cpu": "200m",
                        "memory": "512Mi",
                    },
                    "limits": {
                        "cpu": "500m",
                        "memory": "1Gi",
                    },
                },
                "podAntiAffinity": {
                    "preferredDuringSchedulingIgnoredDuringExecution": [{
                        "weight": 100,
                        "podAffinityTerm": {
                            "labelSelector": {
                                "matchExpressions": [{
                                    "key": "app.kubernetes.io/name",
                                    "operator": "In",
                                    "values": ["grafana"],
                                }],
                            },
                            "topologyKey": "kubernetes.io/hostname",
                        },
                    }],
                },
                "securityContext": {
                    "fsGroup": 472,
                    "runAsNonRoot": True,
                    "runAsUser": 472,
                },
                "ingress": {
                    "enabled": True,
                    "hosts": [f"grafana.{domain}"],
                    "tls": [{
                        "hosts": [f"grafana.{domain}"],
                        "secretName": "grafana-tls",
                    }],
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create Elasticsearch
    elasticsearch = k8s.helm.v3.Release(
        "elasticsearch",
        chart="elasticsearch",
        version="19.5.0",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://helm.elastic.co",
        ),
        namespace="elasticsearch",
        values={
            "replicas": 3 if environment == "production" else 1,
            "minimumMasterNodes": 2 if environment == "production" else 1,
            "volumeClaimTemplate": {
                "storageClassName": elasticsearch_storage_class,
                "accessModes": ["ReadWriteOnce"],
                "resources": {
                    "requests": {
                        "storage": "100Gi" if environment == "production" else "50Gi",
                    },
                },
            },
            "resources": {
                "requests": {
                    "cpu": "1" if environment == "production" else "500m",
                    "memory": "4Gi" if environment == "production" else "2Gi",
                },
                "limits": {
                    "cpu": "2" if environment == "production" else "1",
                    "memory": "8Gi" if environment == "production" else "4Gi",
                },
            },
            "antiAffinity": "soft",
            "esJavaOpts": "-Xmx2g -Xms2g",
            "securityContext": {
                "fsGroup": 1000,
                "runAsUser": 1000,
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create Jaeger
    jaeger = k8s.helm.v3.Release(
        "jaeger",
        chart="jaeger",
        version="0.65.0",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://jaegertracing.github.io/helm-charts",
        ),
        namespace="jaeger",
        values={
            "collector": {
                "replicas": 2 if environment == "production" else 1,
                "resources": {
                    "requests": {
                        "cpu": "200m",
                        "memory": "512Mi",
                    },
                    "limits": {
                        "cpu": "500m",
                        "memory": "1Gi",
                    },
                },
            },
            "query": {
                "replicas": 2 if environment == "production" else 1,
                "resources": {
                    "requests": {
                        "cpu": "200m",
                        "memory": "512Mi",
                    },
                    "limits": {
                        "cpu": "500m",
                        "memory": "1Gi",
                    },
                },
                "ingress": {
                    "enabled": True,
                    "hosts": [f"jaeger.{domain}"],
                    "tls": [{
                        "hosts": [f"jaeger.{domain}"],
                        "secretName": "jaeger-tls",
                    }],
                },
            },
            "agent": {
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "256Mi",
                    },
                    "limits": {
                        "cpu": "200m",
                        "memory": "512Mi",
                    },
                },
            },
            "storage": {
                "type": "elasticsearch",
                "elasticsearch": {
                    "host": "elasticsearch-master.elasticsearch.svc.cluster.local",
                    "port": 9200,
                    "user": "elastic",
                    "usePassword": True,
                    "indexPrefix": "jaeger",
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[elasticsearch]),
    )
    
    # Create Kafka
    kafka = k8s.helm.v3.Release(
        "kafka",
        chart="kafka",
        version="22.1.5",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://charts.bitnami.com/bitnami",
        ),
        namespace="kafka",
        values={
            "replicaCount": 3 if environment == "production" else 1,
            "persistence": {
                "enabled": True,
                "storageClass": kafka_storage_class,
                "size": "100Gi" if environment == "production" else "50Gi",
            },
            "resources": {
                "requests": {
                    "cpu": "1" if environment == "production" else "500m",
                    "memory": "4Gi" if environment == "production" else "2Gi",
                },
                "limits": {
                    "cpu": "2" if environment == "production" else "1",
                    "memory": "8Gi" if environment == "production" else "4Gi",
                },
            },
            "podAntiAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [{
                    "weight": 100,
                    "podAffinityTerm": {
                        "labelSelector": {
                            "matchExpressions": [{
                                "key": "app.kubernetes.io/name",
                                "operator": "In",
                                "values": ["kafka"],
                            }],
                        },
                        "topologyKey": "kubernetes.io/hostname",
                    },
                }],
            },
            "securityContext": {
                "fsGroup": 1001,
                "runAsUser": 1001,
            },
            "zookeeper": {
                "replicaCount": 3 if environment == "production" else 1,
                "persistence": {
                    "enabled": True,
                    "storageClass": kafka_storage_class,
                    "size": "10Gi",
                },
                "resources": {
                    "requests": {
                        "cpu": "200m",
                        "memory": "512Mi",
                    },
                    "limits": {
                        "cpu": "500m",
                        "memory": "1Gi",
                    },
                },
                "podAntiAffinity": {
                    "preferredDuringSchedulingIgnoredDuringExecution": [{
                        "weight": 100,
                        "podAffinityTerm": {
                            "labelSelector": {
                                "matchExpressions": [{
                                    "key": "app.kubernetes.io/name",
                                    "operator": "In",
                                    "values": ["zookeeper"],
                                }],
                            },
                            "topologyKey": "kubernetes.io/hostname",
                        },
                    }],
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Create OpenTelemetry Operator
    otel_operator = k8s.helm.v3.Release(
        "opentelemetry-operator",
        chart="opentelemetry-operator",
        version="0.24.0",
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://open-telemetry.github.io/opentelemetry-helm-charts",
        ),
        namespace="opentelemetry",
        values={
            "admissionWebhooks": {
                "create": True,
                "failurePolicy": "Fail",
            },
            "manager": {
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi",
                    },
                    "limits": {
                        "cpu": "200m",
                        "memory": "256Mi",
                    },
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    # Return stack details
    return ObservabilityStackResult(
        prometheus_url=pulumi.Output.concat("https://prometheus-operated.prometheus.svc.cluster.local:9090"),
        grafana_url=pulumi.Output.concat("https://grafana.", domain),
        elasticsearch_url=pulumi.Output.concat("https://elasticsearch-master.elasticsearch.svc.cluster.local:9200"),
        jaeger_url=pulumi.Output.concat("https://jaeger.", domain),
        kafka_bootstrap_servers=pulumi.Output.concat("kafka.kafka.svc.cluster.local:9092"),
    )
