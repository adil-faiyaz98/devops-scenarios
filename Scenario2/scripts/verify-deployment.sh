#!/bin/bash
set -e

# Configuration
PRIMARY_REGION="us-east-1"
SECONDARY_REGION="us-west-2"
AZURE_PRIMARY="eastus"
AZURE_SECONDARY="westus2"

# Verify AWS Infrastructure
verify_aws() {
    local region=$1
    echo "Verifying AWS infrastructure in $region..."
    
    # Check VPC and networking
    aws ec2 describe-vpcs --region $region
    aws ec2 describe-transit-gateways --region $region
    
    # Check security groups
    aws ec2 describe-security-groups --region $region
    
    # Check Route53 health checks
    aws route53 get-health-check --health-check-id $HEALTH_CHECK_ID
}

# Verify Azure Infrastructure
verify_azure() {
    local region=$1
    echo "Verifying Azure infrastructure in $region..."
    
    # Check VNet and networking
    az network vnet list --resource-group $RESOURCE_GROUP --query "[?location=='$region']"
    
    # Check ExpressRoute
    az network express-route list --resource-group $RESOURCE_GROUP
    
    # Check Azure Monitor
    az monitor activity-log list --resource-group $RESOURCE_GROUP
}

# Verify Cross-Cloud Connectivity
verify_connectivity() {
    echo "Verifying cross-cloud connectivity..."
    
    # Test VPC/VNet peering
    ping -c 3 $AZURE_ENDPOINT
    ping -c 3 $AWS_ENDPOINT
    
    # Test load balancer
    curl -f https://$GLOBAL_ENDPOINT/health
}

# Main verification flow
main() {
    echo "Starting deployment verification..."
    
    # Verify AWS regions
    verify_aws $PRIMARY_REGION
    verify_aws $SECONDARY_REGION
    
    # Verify Azure regions
    verify_azure $AZURE_PRIMARY
    verify_azure $AZURE_SECONDARY
    
    # Verify cross-cloud connectivity
    verify_connectivity
    
    # Verify monitoring
    curl -f https://$DATADOG_API/v1/validate
    curl -f https://$AZURE_MONITOR_ENDPOINT/health
    
    echo "Deployment verification completed successfully!"
}

main "$@"