"""
Kubernetes Namespaces Module for the AI-driven Observability Pipeline.

This module creates Kubernetes namespaces for the observability pipeline,
along with resource quotas, limit ranges, and network policies.

The namespaces are designed to be:
- Isolated: Network policies to control traffic
- Resource-constrained: Resource quotas and limit ranges
- Well-labeled: Consistent labeling for all resources
"""

import pulumi
import pulumi_kubernetes as k8s
from typing import List, Dict, Any, Optional


class NamespacesResult:
    """Result object for namespaces creation."""
    
    def __init__(
        self,
        namespaces: Dict[str, k8s.core.v1.Namespace],
        resource_quotas: Dict[str, k8s.core.v1.ResourceQuota],
        limit_ranges: Dict[str, k8s.core.v1.LimitRange],
        network_policies: Dict[str, k8s.networking.v1.NetworkPolicy],
    ):
        self.namespaces = namespaces
        self.resource_quotas = resource_quotas
        self.limit_ranges = limit_ranges
        self.network_policies = network_policies


def create_namespaces(
    provider: k8s.Provider,
    namespaces: List[str],
    environment: str,
    resource_quotas: Optional[Dict[str, Dict[str, str]]] = None,
    limit_ranges: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
) -> NamespacesResult:
    """
    Create Kubernetes namespaces for the observability pipeline.
    
    Args:
        provider: Kubernetes provider
        namespaces: List of namespace names
        environment: Deployment environment (dev, staging, production)
        resource_quotas: Dictionary of resource quotas for each namespace
        limit_ranges: Dictionary of limit ranges for each namespace
        
    Returns:
        NamespacesResult object with namespace details
    """
    # Default resource quotas based on environment
    default_resource_quotas = {
        "dev": {
            "requests.cpu": "4",
            "requests.memory": "8Gi",
            "limits.cpu": "8",
            "limits.memory": "16Gi",
            "pods": "20",
        },
        "staging": {
            "requests.cpu": "8",
            "requests.memory": "16Gi",
            "limits.cpu": "16",
            "limits.memory": "32Gi",
            "pods": "50",
        },
        "production": {
            "requests.cpu": "16",
            "requests.memory": "32Gi",
            "limits.cpu": "32",
            "limits.memory": "64Gi",
            "pods": "100",
        },
    }
    
    # Default limit ranges based on environment
    default_limit_ranges = {
        "dev": {
            "default": {
                "cpu": "100m",
                "memory": "128Mi",
            },
            "defaultRequest": {
                "cpu": "50m",
                "memory": "64Mi",
            },
        },
        "staging": {
            "default": {
                "cpu": "200m",
                "memory": "256Mi",
            },
            "defaultRequest": {
                "cpu": "100m",
                "memory": "128Mi",
            },
        },
        "production": {
            "default": {
                "cpu": "300m",
                "memory": "512Mi",
            },
            "defaultRequest": {
                "cpu": "150m",
                "memory": "256Mi",
            },
        },
    }
    
    # Use provided resource quotas or defaults
    if resource_quotas is None:
        resource_quotas = {}
        for ns in namespaces:
            resource_quotas[ns] = default_resource_quotas[environment]
    
    # Use provided limit ranges or defaults
    if limit_ranges is None:
        limit_ranges = {}
        for ns in namespaces:
            limit_ranges[ns] = default_limit_ranges[environment]
    
    # Create namespaces
    namespace_resources = {}
    resource_quota_resources = {}
    limit_range_resources = {}
    network_policy_resources = {}
    
    for ns in namespaces:
        # Create namespace
        namespace = k8s.core.v1.Namespace(
            ns,
            metadata={
                "name": ns,
                "labels": {
                    "name": ns,
                    "part-of": "ai-observability",
                    "environment": environment,
                },
            },
            opts=pulumi.ResourceOptions(provider=provider),
        )
        namespace_resources[ns] = namespace
        
        # Create resource quota
        if ns in resource_quotas:
            resource_quota = k8s.core.v1.ResourceQuota(
                f"{ns}-quota",
                metadata={
                    "name": f"{ns}-quota",
                    "namespace": ns,
                },
                spec={
                    "hard": resource_quotas[ns],
                },
                opts=pulumi.ResourceOptions(provider=provider, depends_on=[namespace]),
            )
            resource_quota_resources[ns] = resource_quota
        
        # Create limit range
        if ns in limit_ranges:
            limit_range = k8s.core.v1.LimitRange(
                f"{ns}-limits",
                metadata={
                    "name": f"{ns}-limits",
                    "namespace": ns,
                },
                spec={
                    "limits": [{
                        "type": "Container",
                        **limit_ranges[ns],
                    }],
                },
                opts=pulumi.ResourceOptions(provider=provider, depends_on=[namespace]),
            )
            limit_range_resources[ns] = limit_range
        
        # Create default deny network policy
        default_deny = k8s.networking.v1.NetworkPolicy(
            f"{ns}-default-deny",
            metadata={
                "name": "default-deny-all",
                "namespace": ns,
            },
            spec={
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
            },
            opts=pulumi.ResourceOptions(provider=provider, depends_on=[namespace]),
        )
        network_policy_resources[f"{ns}-default-deny"] = default_deny
        
        # Create allow ingress network policy
        allow_ingress = k8s.networking.v1.NetworkPolicy(
            f"{ns}-allow-ingress",
            metadata={
                "name": "allow-ingress",
                "namespace": ns,
            },
            spec={
                "podSelector": {},
                "policyTypes": ["Ingress"],
                "ingress": [{
                    "from": [
                        # Allow traffic from the same namespace
                        {
                            "podSelector": {},
                        },
                        # Allow traffic from observability namespace
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "name": "observability",
                                },
                            },
                        },
                    ],
                }],
            },
            opts=pulumi.ResourceOptions(provider=provider, depends_on=[namespace]),
        )
        network_policy_resources[f"{ns}-allow-ingress"] = allow_ingress
        
        # Create allow egress network policy
        allow_egress = k8s.networking.v1.NetworkPolicy(
            f"{ns}-allow-egress",
            metadata={
                "name": "allow-egress",
                "namespace": ns,
            },
            spec={
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [
                    # Allow DNS traffic
                    {
                        "to": [{
                            "namespaceSelector": {
                                "matchLabels": {
                                    "name": "kube-system",
                                },
                            },
                        }],
                        "ports": [
                            {"port": 53, "protocol": "UDP"},
                            {"port": 53, "protocol": "TCP"},
                        ],
                    },
                    # Allow traffic to observability namespace
                    {
                        "to": [{
                            "namespaceSelector": {
                                "matchLabels": {
                                    "name": "observability",
                                },
                            },
                        }],
                    },
                    # Allow traffic to other namespaces in the observability pipeline
                    {
                        "to": [{
                            "namespaceSelector": {
                                "matchLabels": {
                                    "part-of": "ai-observability",
                                },
                            },
                        }],
                    },
                ],
            },
            opts=pulumi.ResourceOptions(provider=provider, depends_on=[namespace]),
        )
        network_policy_resources[f"{ns}-allow-egress"] = allow_egress
    
    # Return namespace details
    return NamespacesResult(
        namespaces=namespace_resources,
        resource_quotas=resource_quota_resources,
        limit_ranges=limit_range_resources,
        network_policies=network_policy_resources,
    )
