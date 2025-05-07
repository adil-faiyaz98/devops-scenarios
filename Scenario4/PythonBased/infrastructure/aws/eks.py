"""
EKS Module for the AI-driven Observability Pipeline.

This module creates an EKS cluster with multiple node groups, IAM roles,
security groups, and other resources needed for a production-grade
Kubernetes cluster.

The EKS cluster is designed to be:
- Highly available: Control plane and worker nodes across multiple AZs
- Secure: Private networking, IAM roles, and security groups
- Scalable: Multiple node groups with autoscaling
- Cost-effective: Spot instances for non-critical workloads
"""

import base64
import json
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from typing import Dict, List, Any, Optional


class EksClusterResult:
    """Result object for EKS cluster creation."""
    
    def __init__(
        self,
        cluster_name: pulumi.Output[str],
        cluster_arn: pulumi.Output[str],
        cluster_endpoint: pulumi.Output[str],
        cluster_security_group_id: pulumi.Output[str],
        node_security_group_id: pulumi.Output[str],
        kubeconfig: pulumi.Output[str],
        k8s_provider: k8s.Provider,
        storage_class: k8s.storage.v1.StorageClass,
    ):
        self.cluster_name = cluster_name
        self.cluster_arn = cluster_arn
        self.cluster_endpoint = cluster_endpoint
        self.cluster_security_group_id = cluster_security_group_id
        self.node_security_group_id = node_security_group_id
        self.kubeconfig = kubeconfig
        self.k8s_provider = k8s_provider
        self.storage_class = storage_class


def create_eks_cluster(
    name: str,
    vpc_id: pulumi.Input[str],
    subnet_ids: pulumi.Input[List[str]],
    node_groups: Dict[str, Dict[str, Any]],
    kubernetes_version: str = "1.24",
    tags: Optional[Dict[str, str]] = None,
) -> EksClusterResult:
    """
    Create an EKS cluster with multiple node groups.
    
    Args:
        name: Name of the EKS cluster
        vpc_id: VPC ID
        subnet_ids: List of subnet IDs
        node_groups: Dictionary of node groups with their configurations
        kubernetes_version: Kubernetes version
        tags: Tags to apply to all resources
        
    Returns:
        EksClusterResult object with cluster details
    """
    if tags is None:
        tags = {}
    
    # Create IAM role for EKS cluster
    eks_role = aws.iam.Role(
        f"{name}-eks-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "eks.amazonaws.com",
                },
            }],
        }),
        tags={**tags, "Name": f"{name}-eks-role"},
    )
    
    # Attach policies to EKS role
    aws.iam.RolePolicyAttachment(
        f"{name}-eks-policy-cluster",
        role=eks_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    )
    
    aws.iam.RolePolicyAttachment(
        f"{name}-eks-policy-service",
        role=eks_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEKSServicePolicy",
    )
    
    # Create security group for EKS cluster
    cluster_sg = aws.ec2.SecurityGroup(
        f"{name}-cluster-sg",
        vpc_id=vpc_id,
        description="Security group for EKS cluster",
        tags={**tags, "Name": f"{name}-cluster-sg"},
    )
    
    # Allow all outbound traffic
    aws.ec2.SecurityGroupRule(
        f"{name}-cluster-sg-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=cluster_sg.id,
    )
    
    # Create KMS key for secrets encryption
    kms_key = aws.kms.Key(
        f"{name}-kms-key",
        description=f"KMS key for {name} EKS cluster",
        deletion_window_in_days=7,
        enable_key_rotation=True,
        tags={**tags, "Name": f"{name}-kms-key"},
    )
    
    # Create EKS cluster
    cluster = aws.eks.Cluster(
        name,
        role_arn=eks_role.arn,
        version=kubernetes_version,
        vpc_config={
            "subnetIds": subnet_ids,
            "securityGroupIds": [cluster_sg.id],
            "endpointPrivateAccess": True,
            "endpointPublicAccess": True,
        },
        encryption_config=[{
            "resources": ["secrets"],
            "provider": {
                "keyArn": kms_key.arn,
            },
        }],
        tags=tags,
    )
    
    # Create IAM role for node groups
    node_role = aws.iam.Role(
        f"{name}-node-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com",
                },
            }],
        }),
        tags={**tags, "Name": f"{name}-node-role"},
    )
    
    # Attach policies to node role
    aws.iam.RolePolicyAttachment(
        f"{name}-node-policy-worker",
        role=node_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    )
    
    aws.iam.RolePolicyAttachment(
        f"{name}-node-policy-cni",
        role=node_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    )
    
    aws.iam.RolePolicyAttachment(
        f"{name}-node-policy-registry",
        role=node_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    )
    
    # Create node groups
    node_group_resources = {}
    for ng_name, ng_config in node_groups.items():
        # Extract node group configuration
        instance_type = ng_config.get("instance_type", "t3.medium")
        min_size = ng_config.get("min_size", 1)
        max_size = ng_config.get("max_size", 3)
        desired_size = ng_config.get("desired_size", 2)
        labels = ng_config.get("labels", {})
        taints = ng_config.get("taints", [])
        
        # Create launch template for node group
        launch_template = aws.ec2.LaunchTemplate(
            f"{name}-{ng_name}-lt",
            name_prefix=f"{name}-{ng_name}-",
            block_device_mappings=[{
                "deviceName": "/dev/xvda",
                "ebs": {
                    "volumeSize": 50,
                    "volumeType": "gp3",
                    "deleteOnTermination": True,
                    "encrypted": True,
                },
            }],
            tag_specifications=[{
                "resourceType": "instance",
                "tags": {**tags, "Name": f"{name}-{ng_name}-node"},
            }],
            update_default_version=True,
            tags={**tags, "Name": f"{name}-{ng_name}-lt"},
        )
        
        # Create node group
        node_group = aws.eks.NodeGroup(
            f"{name}-{ng_name}",
            cluster_name=cluster.name,
            node_role_arn=node_role.arn,
            subnet_ids=subnet_ids,
            scaling_config={
                "desiredSize": desired_size,
                "maxSize": max_size,
                "minSize": min_size,
            },
            instance_types=[instance_type],
            labels=labels,
            tags={**tags, "Name": f"{name}-{ng_name}"},
            launch_template={
                "id": launch_template.id,
                "version": launch_template.latest_version,
            },
        )
        
        # Add taints if specified
        if taints:
            node_group_taints = []
            for taint in taints:
                node_group_taints.append({
                    "key": taint["key"],
                    "value": taint["value"],
                    "effect": taint["effect"],
                })
            node_group.taints = node_group_taints
        
        node_group_resources[ng_name] = node_group
    
    # Generate kubeconfig
    kubeconfig = pulumi.Output.all(cluster.name, cluster.endpoint, cluster.certificate_authority.apply(
        lambda ca: ca["data"])).apply(
        lambda args: json.dumps({
            "apiVersion": "v1",
            "clusters": [{
                "cluster": {
                    "server": args[1],
                    "certificate-authority-data": args[2],
                },
                "name": "kubernetes",
            }],
            "contexts": [{
                "context": {
                    "cluster": "kubernetes",
                    "user": "aws",
                },
                "name": "aws",
            }],
            "current-context": "aws",
            "kind": "Config",
            "users": [{
                "name": "aws",
                "user": {
                    "exec": {
                        "apiVersion": "client.authentication.k8s.io/v1beta1",
                        "command": "aws",
                        "args": [
                            "eks",
                            "get-token",
                            "--cluster-name",
                            args[0],
                        ],
                    },
                },
            }],
        })
    )
    
    # Create Kubernetes provider
    k8s_provider = k8s.Provider(
        f"{name}-k8s-provider",
        kubeconfig=kubeconfig,
    )
    
    # Create gp3 storage class
    storage_class = k8s.storage.v1.StorageClass(
        "gp3",
        metadata={
            "name": "gp3",
            "annotations": {
                "storageclass.kubernetes.io/is-default-class": "true",
            },
        },
        provisioner="kubernetes.io/aws-ebs",
        parameters={
            "type": "gp3",
            "fsType": "ext4",
        },
        volume_binding_mode="WaitForFirstConsumer",
        allow_volume_expansion=True,
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
    
    # Return cluster details
    return EksClusterResult(
        cluster_name=cluster.name,
        cluster_arn=cluster.arn,
        cluster_endpoint=cluster.endpoint,
        cluster_security_group_id=cluster.vpc_config.apply(lambda vpc: vpc["clusterSecurityGroupId"]),
        node_security_group_id=cluster_sg.id,
        kubeconfig=kubeconfig,
        k8s_provider=k8s_provider,
        storage_class=storage_class,
    )
