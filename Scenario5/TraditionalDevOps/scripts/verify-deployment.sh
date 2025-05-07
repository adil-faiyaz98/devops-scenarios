#!/bin/bash
set -e

# Verify Edge Components
echo "Verifying Edge Components..."

# Check if edge components are running
kubectl get pods -n edge-system | grep "edge-" | while read -r line; do
    if [[ ! $line =~ "Running" ]]; then
        echo "Error: Edge component not running properly"
        exit 1
    fi
done

# Verify AWS Greengrass deployment
aws greengrassv2 list-core-devices --status HEALTHY | grep "coreDeviceId" || {
    echo "Error: No healthy Greengrass core devices found"
    exit 1
}

# Verify Azure IoT Edge deployment
az iot hub device-identity list --hub-name $IOT_HUB_NAME --query "[?status=='enabled']" || {
    echo "Error: No enabled IoT Edge devices found"
    exit 1
}

# Check sync status
kubectl exec -n edge-system deployment/sync-manager -- curl -s localhost:8080/health | grep "status.*UP" || {
    echo "Error: Sync manager health check failed"
    exit 1
}

echo "Edge Components verification completed successfully"