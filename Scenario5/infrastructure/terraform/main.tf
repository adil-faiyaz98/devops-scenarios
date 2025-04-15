terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

module "edge_fleet_aws" {
  source = "./modules/aws-edge-fleet"
  
  fleet_name = var.fleet_name
  environment = var.environment
  
  greengrass_config = {
    version = "2.5.0"
    component_updates_enabled = true
    local_cache_size_gb = 10
  }
  
  device_groups = {
    production = {
      device_count = 50
      device_type = "industrial"
    }
    development = {
      device_count = 10
      device_type = "development"
    }
  }
}

module "edge_fleet_azure" {
  source = "./modules/azure-edge-fleet"
  
  fleet_name = var.fleet_name
  environment = var.environment
  
  iot_edge_config = {
    version = "1.4"
    update_mode = "automatic"
    storage_size_gb = 20
  }
}