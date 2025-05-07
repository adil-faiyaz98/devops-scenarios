"""
Security Module for the AI-driven Observability Pipeline.

This module creates security resources for the observability pipeline,
including KMS keys, IAM roles, and security groups.

The security resources are designed to be:
- Secure: Least privilege principle, encryption, secure defaults
- Compliant: Follows AWS security best practices
- Auditable: Enables logging and monitoring of security events
"""

import pulumi
import pulumi_aws as aws
from typing import Dict, Any, Optional


class SecurityResult:
    """Result object for security resources creation."""
    
    def __init__(
        self,
        kms_key_id: pulumi.Output[str],
        kms_key_arn: pulumi.Output[str],
        sagemaker_sg_id: pulumi.Output[str],
        elasticsearch_sg_id: pulumi.Output[str],
        kafka_sg_id: pulumi.Output[str],
    ):
        self.kms_key_id = kms_key_id
        self.kms_key_arn = kms_key_arn
        self.sagemaker_sg_id = sagemaker_sg_id
        self.elasticsearch_sg_id = elasticsearch_sg_id
        self.kafka_sg_id = kafka_sg_id


def create_security_resources(
    project_name: str,
    environment: str,
    tags: Optional[Dict[str, str]] = None,
) -> SecurityResult:
    """
    Create security resources for the observability pipeline.
    
    Args:
        project_name: Name of the project
        environment: Deployment environment (dev, staging, production)
        tags: Tags to apply to all resources
        
    Returns:
        SecurityResult object with security resource details
    """
    if tags is None:
        tags = {}
    
    # Create KMS key for encryption
    kms_key = aws.kms.Key(
        f"{project_name}-{environment}-kms-key",
        description=f"KMS key for {project_name} {environment}",
        deletion_window_in_days=30 if environment == "production" else 7,
        enable_key_rotation=True,
        policy=pulumi.Output.json_dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Enable IAM User Permissions",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": pulumi.Output.concat("arn:aws:iam::", aws.get_caller_identity().account_id, ":root"),
                    },
                    "Action": "kms:*",
                    "Resource": "*",
                },
                {
                    "Sid": "Allow SageMaker to use the key",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sagemaker.amazonaws.com",
                    },
                    "Action": [
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "Allow CloudWatch to use the key",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "logs.amazonaws.com",
                    },
                    "Action": [
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    "Resource": "*",
                },
            ],
        }),
        tags=tags,
    )
    
    # Create KMS alias
    aws.kms.Alias(
        f"{project_name}-{environment}-kms-alias",
        name=pulumi.Output.concat("alias/", project_name, "-", environment),
        target_key_id=kms_key.id,
    )
    
    # Create security group for SageMaker
    sagemaker_sg = aws.ec2.SecurityGroup(
        f"{project_name}-{environment}-sagemaker-sg",
        description=f"Security group for SageMaker in {project_name} {environment}",
        tags={**tags, "Name": f"{project_name}-{environment}-sagemaker-sg"},
    )
    
    # Create security group for Elasticsearch
    elasticsearch_sg = aws.ec2.SecurityGroup(
        f"{project_name}-{environment}-elasticsearch-sg",
        description=f"Security group for Elasticsearch in {project_name} {environment}",
        tags={**tags, "Name": f"{project_name}-{environment}-elasticsearch-sg"},
    )
    
    # Create security group for Kafka
    kafka_sg = aws.ec2.SecurityGroup(
        f"{project_name}-{environment}-kafka-sg",
        description=f"Security group for Kafka in {project_name} {environment}",
        tags={**tags, "Name": f"{project_name}-{environment}-kafka-sg"},
    )
    
    # Allow SageMaker to access Elasticsearch
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-sagemaker-to-elasticsearch",
        type="ingress",
        from_port=9200,
        to_port=9200,
        protocol="tcp",
        source_security_group_id=sagemaker_sg.id,
        security_group_id=elasticsearch_sg.id,
        description="Allow SageMaker to access Elasticsearch",
    )
    
    # Allow SageMaker to access Kafka
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-sagemaker-to-kafka",
        type="ingress",
        from_port=9092,
        to_port=9092,
        protocol="tcp",
        source_security_group_id=sagemaker_sg.id,
        security_group_id=kafka_sg.id,
        description="Allow SageMaker to access Kafka",
    )
    
    # Allow Elasticsearch to access Kafka
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-elasticsearch-to-kafka",
        type="ingress",
        from_port=9092,
        to_port=9092,
        protocol="tcp",
        source_security_group_id=elasticsearch_sg.id,
        security_group_id=kafka_sg.id,
        description="Allow Elasticsearch to access Kafka",
    )
    
    # Allow all outbound traffic from SageMaker
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-sagemaker-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=sagemaker_sg.id,
        description="Allow all outbound traffic from SageMaker",
    )
    
    # Allow all outbound traffic from Elasticsearch
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-elasticsearch-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=elasticsearch_sg.id,
        description="Allow all outbound traffic from Elasticsearch",
    )
    
    # Allow all outbound traffic from Kafka
    aws.ec2.SecurityGroupRule(
        f"{project_name}-{environment}-kafka-egress",
        type="egress",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        security_group_id=kafka_sg.id,
        description="Allow all outbound traffic from Kafka",
    )
    
    # Return security resource details
    return SecurityResult(
        kms_key_id=kms_key.id,
        kms_key_arn=kms_key.arn,
        sagemaker_sg_id=sagemaker_sg.id,
        elasticsearch_sg_id=elasticsearch_sg.id,
        kafka_sg_id=kafka_sg.id,
    )
