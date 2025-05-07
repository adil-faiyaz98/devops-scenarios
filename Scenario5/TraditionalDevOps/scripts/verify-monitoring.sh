#!/bin/bash
set -e

# Verify Monitoring Stack
echo "Verifying Monitoring Stack..."

# Check Prometheus
kubectl get pods -n monitoring | grep "prometheus" | while read -r line; do
    if [[ ! $line =~ "Running" ]]; then
        echo "Error: Prometheus not running properly"
        exit 1
    fi
done

# Check Grafana
kubectl get pods -n monitoring | grep "grafana" | while read -r line; do
    if [[ ! $line =~ "Running" ]]; then
        echo "Error: Grafana not running properly"
        exit 1
    fi
done

# Verify metrics collection
curl -s http://prometheus:9090/api/v1/query?query=up | grep "value.*1" || {
    echo "Error: Metrics collection not working"
    exit 1
}

echo "Monitoring stack verification completed successfully"