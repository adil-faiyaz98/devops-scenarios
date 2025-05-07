packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.1"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-gov-west-1"
}

variable "environment" {
  type = string
}

source "amazon-ebs" "govcloud" {
  region        = var.aws_region
  instance_type = "t3.micro"
  ami_name      = "hardened-govcloud-${var.environment}-${formatdate("YYYYMMDD-hhmmss", timestamp())}"
  source_ami_filter {
    filters = {
      virtualization-type = "hvm"
      name               = "RHEL-8.*_HVM-*-x86_64-*"
      root-device-type   = "ebs"
    }
    owners      = ["219670896067"] # GovCloud RHEL owner ID
    most_recent = true
  }
  ssh_username = "ec2-user"

  tags = {
    Environment = var.environment
    Compliance  = "STIG-RHEL8"
    BuildDate   = formatdate("YYYY-MM-DD", timestamp())
  }
}

build {
  sources = ["source.amazon-ebs.govcloud"]

  provisioner "shell" {
    script = "scripts/install-hardening.sh"
  }

  provisioner "shell" {
    script = "scripts/apply-stig.sh"
  }

  provisioner "shell" {
    script = "scripts/install-monitoring.sh"
  }

  post-processor "manifest" {
    output = "manifest.json"
    strip_path = true
  }
}