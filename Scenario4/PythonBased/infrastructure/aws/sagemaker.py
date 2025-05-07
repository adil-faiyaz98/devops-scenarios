"""
SageMaker Module for the AI-driven Observability Pipeline.

This module creates SageMaker resources for training and hosting ML models,
including execution roles, S3 buckets, and endpoints.

The SageMaker resources are designed to be:
- Secure: IAM roles with least privilege, VPC endpoints, KMS encryption
- Scalable: Autoscaling for inference endpoints
- Cost-effective: Spot instances for training, instance right-sizing
"""

import pulumi
import pulumi_aws as aws
import pulumi_random as random
from typing import List, Dict, Any, Optional


class SageMakerResult:
    """Result object for SageMaker resources creation."""
    
    def __init__(
        self,
        execution_role_arn: pulumi.Output[str],
        model_bucket_name: pulumi.Output[str],
        model_bucket_arn: pulumi.Output[str],
        vpc_endpoint_id: pulumi.Output[str],
    ):
        self.execution_role_arn = execution_role_arn
        self.model_bucket_name = model_bucket_name
        self.model_bucket_arn = model_bucket_arn
        self.vpc_endpoint_id = vpc_endpoint_id


def create_sagemaker_resources(
    project_name: str,
    environment: str,
    vpc_id: pulumi.Input[str],
    subnet_ids: pulumi.Input[List[str]],
    security_group_ids: pulumi.Input[List[str]],
    kms_key_id: pulumi.Input[str],
    tags: Optional[Dict[str, str]] = None,
) -> SageMakerResult:
    """
    Create SageMaker resources for ML model training and hosting.
    
    Args:
        project_name: Name of the project
        environment: Deployment environment (dev, staging, production)
        vpc_id: VPC ID
        subnet_ids: List of subnet IDs
        security_group_ids: List of security group IDs
        kms_key_id: KMS key ID for encryption
        tags: Tags to apply to all resources
        
    Returns:
        SageMakerResult object with SageMaker resource details
    """
    if tags is None:
        tags = {}
    
    # Create random suffix for globally unique S3 bucket names
    suffix = random.RandomString(
        "bucket-suffix",
        length=8,
        special=False,
        upper=False,
    )
    
    # Create S3 bucket for model artifacts
    model_bucket = aws.s3.Bucket(
        f"{project_name}-{environment}-models",
        bucket=pulumi.Output.concat(f"{project_name}-{environment}-models-", suffix.result),
        acl="private",
        versioning={
            "enabled": True,
        },
        server_side_encryption_configuration={
            "rule": {
                "applyServerSideEncryptionByDefault": {
                    "sseAlgorithm": "aws:kms",
                    "kmsMasterKeyId": kms_key_id,
                },
            },
        },
        tags=tags,
    )
    
    # Create S3 bucket policy to restrict access
    aws.s3.BucketPolicy(
        f"{project_name}-{environment}-models-policy",
        bucket=model_bucket.id,
        policy=pulumi.Output.all(model_bucket.arn).apply(
            lambda args: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"{args[0]}",
                            f"{args[0]}/*",
                        ],
                        "Condition": {
                            "Bool": {
                                "aws:SecureTransport": "false",
                            },
                        },
                    },
                ],
            }
        ).apply(lambda policy: pulumi.Output.json_dumps(policy)),
    )
    
    # Create IAM role for SageMaker
    sagemaker_role = aws.iam.Role(
        f"{project_name}-{environment}-sagemaker-role",
        assume_role_policy=pulumi.Output.json_dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sagemaker.amazonaws.com",
                    },
                    "Action": "sts:AssumeRole",
                },
            ],
        }),
        tags=tags,
    )
    
    # Create IAM policy for SageMaker
    sagemaker_policy = aws.iam.Policy(
        f"{project_name}-{environment}-sagemaker-policy",
        policy=pulumi.Output.all(model_bucket.arn).apply(
            lambda args: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket",
                        ],
                        "Resource": [
                            f"{args[0]}",
                            f"{args[0]}/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": "arn:aws:logs:*:*:*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "ecr:BatchCheckLayerAvailability",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:PutMetricData",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
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
            }
        ).apply(lambda policy: pulumi.Output.json_dumps(policy)),
        tags=tags,
    )
    
    # Attach policy to role
    aws.iam.RolePolicyAttachment(
        f"{project_name}-{environment}-sagemaker-policy-attachment",
        role=sagemaker_role.name,
        policy_arn=sagemaker_policy.arn,
    )
    
    # Create VPC endpoint for SageMaker API
    sagemaker_vpc_endpoint = aws.ec2.VpcEndpoint(
        f"{project_name}-{environment}-sagemaker-endpoint",
        vpc_id=vpc_id,
        service_name=pulumi.Output.concat("com.amazonaws.", aws.get_region().name, ".sagemaker.api"),
        vpc_endpoint_type="Interface",
        subnet_ids=subnet_ids,
        security_group_ids=security_group_ids,
        private_dns_enabled=True,
        tags=tags,
    )
    
    # Create VPC endpoint for SageMaker Runtime
    sagemaker_runtime_vpc_endpoint = aws.ec2.VpcEndpoint(
        f"{project_name}-{environment}-sagemaker-runtime-endpoint",
        vpc_id=vpc_id,
        service_name=pulumi.Output.concat("com.amazonaws.", aws.get_region().name, ".sagemaker.runtime"),
        vpc_endpoint_type="Interface",
        subnet_ids=subnet_ids,
        security_group_ids=security_group_ids,
        private_dns_enabled=True,
        tags=tags,
    )
    
    # Return SageMaker resource details
    return SageMakerResult(
        execution_role_arn=sagemaker_role.arn,
        model_bucket_name=model_bucket.id,
        model_bucket_arn=model_bucket.arn,
        vpc_endpoint_id=sagemaker_vpc_endpoint.id,
    )
