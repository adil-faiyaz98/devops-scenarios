# AWS VPC Configuration
resource "aws_vpc" "primary" {
  cidr_block           = var.aws_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "fintech-vpc-${var.environment}"
  }
}

# Azure VNet Configuration
resource "azurerm_virtual_network" "primary" {
  name                = "fintech-vnet-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.azure_location
  address_space       = [var.azure_vnet_cidr]
}

# AWS Transit Gateway
resource "aws_ec2_transit_gateway" "main" {
  description = "Fintech Transit Gateway"
  
  tags = {
    Name = "fintech-tgw-${var.environment}"
  }
}

# Azure ExpressRoute Circuit
resource "azurerm_express_route_circuit" "main" {
  name                  = "fintech-expressroute-${var.environment}"
  resource_group_name   = var.resource_group_name
  location             = var.azure_location
  service_provider_name = "Equinix"
  peering_location     = "Silicon Valley"
  bandwidth_in_mbps    = 1000

  sku {
    tier   = "Premium"
    family = "MeteredData"
  }
}

# Global Load Balancer Configuration
resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_endpoint
  port              = 443
  type              = "HTTPS"
  request_interval  = "10"
  failure_threshold = "3"
}

resource "azurerm_traffic_manager_profile" "global" {
  name                = "fintech-tm-${var.environment}"
  resource_group_name = var.resource_group_name
  traffic_routing_method = "Performance"

  dns_config {
    relative_name = "fintech-${var.environment}"
    ttl          = 60
  }

  monitor_config {
    protocol = "HTTPS"
    port     = 443
    path     = "/health"
  }
}