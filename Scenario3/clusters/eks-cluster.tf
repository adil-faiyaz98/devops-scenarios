module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "enterprise-platform-${var.environment}"
  cluster_version = "1.27"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true

  # Enhanced security configurations
  cluster_encryption_config = [{
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }]

  # Node groups for different workload types
  eks_managed_node_groups = {
    system = {
      name = "system-pool"
      instance_types = ["m5.xlarge"]
      min_size     = 2
      max_size     = 4
      desired_size = 2
      labels = {
        workload-type = "system"
      }
      taints = [{
        key    = "system"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
    application = {
      name = "app-pool"
      instance_types = ["m5.2xlarge"]
      min_size     = 3
      max_size     = 10
      desired_size = 3
      labels = {
        workload-type = "application"
      }
    }
  }

  # OIDC Configuration for IAM roles
  enable_irsa = true

  tags = {
    Environment = var.environment
    Platform    = "enterprise-k8s"
  }
}