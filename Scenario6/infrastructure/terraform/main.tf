terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = var.environment
      Project     = "GovCloud-Secure"
      Compliance  = "FedRAMP-High"
    }
  }
}

module "secure_boundary_vpc" {
  source = "./modules/secure-vpc"
  
  vpc_cidr            = var.vpc_cidr
  environment         = var.environment
  availability_zones  = var.availability_zones
  enable_flow_logs    = true
  flow_logs_retention = 365
}

module "security_controls" {
  source = "./modules/security-controls"
  
  enable_guardduty    = true
  enable_config       = true
  enable_cloudtrail   = true
  enable_securityhub  = true
  
  cloudtrail_retention_days = 365
  config_retention_days     = 365
}

module "iam_policies" {
  source = "./modules/iam-policies"
  
  mfa_enforcement     = true
  password_policy     = var.password_policy
  session_duration    = var.session_duration
  require_encryption  = true
}

module "scp_policies" {
  source = "./modules/scp-policies"
  
  deny_root_access    = true
  enforce_encryption  = true
  restrict_regions    = ["us-gov-west-1"]
  require_mfa         = true
}