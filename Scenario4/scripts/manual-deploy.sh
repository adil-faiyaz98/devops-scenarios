#!/bin/bash
set -e

# AI-driven Observability Pipeline Manual Deployment Script
# This script automates the manual deployment of the observability pipeline

# Configuration
NAMESPACE_OBSERVABILITY="observability"
NAMESPACE_KAFKA="kafka"
GRAFANA_ADMIN_PASSWORD="admin123"  # Change this in production
AWS_REGION="us-east-1"
ELASTICSEARCH_PASSWORD="changeme"  # Change this in production

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Print section header
section() {
    echo -e "\n${GREEN}==== $1 ====${NC}\n"
}

# Print info message
info() {
    echo -e "${YELLOW}INFO: $1${NC}"
}

# Print error message
error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        error "$1 is required but not installed. Please install it and try again."
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    section "Checking Prerequisites"
    
    # Check required commands
    check_command kubectl
    check_command helm
    check_command aws
    
    # Check kubectl connection
    info "Checking Kubernetes connection..."
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    # Check AWS credentials
    info "Checking AWS credentials..."
    if ! aws sts get-caller-identity &> /dev/null; then
        error "Cannot authenticate with AWS. Please check your AWS credentials."
        exit 1
    fi
    
    info "All prerequisites satisfied."
}

# Create namespaces
create_namespaces() {
    section "Creating Namespaces"
    
    kubectl create namespace $NAMESPACE_OBSERVABILITY --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace $NAMESPACE_KAFKA --dry-run=client -o yaml | kubectl apply -f -
    
    info "Namespaces created successfully."
}

# Deploy Kafka
deploy_kafka() {
    section "Deploying Kafka"
    
    # Add Strimzi Helm repository
    info "Adding Strimzi Helm repository..."
    helm repo add strimzi https://strimzi.io/charts/ 2>/dev/null || true
    helm repo update
    
    # Install Strimzi Operator
    info "Installing Strimzi Operator..."
    helm upgrade --install kafka-operator strimzi/strimzi-kafka-operator \
        --namespace $NAMESPACE_KAFKA \
        --wait --timeout 5m
    
    # Deploy Kafka cluster and topics
    info "Deploying Kafka cluster and topics..."
    kubectl apply -f ai-observability/kafka/kafka-config.yaml
    
    # Wait for Kafka to be ready
    info "Waiting for Kafka to be ready..."
    kubectl wait --for=condition=Ready --timeout=10m kafka/kafka-cluster -n $NAMESPACE_KAFKA
    
    info "Kafka deployed successfully."
}

# Deploy Elasticsearch and Jaeger
deploy_elasticsearch_jaeger() {
    section "Deploying Elasticsearch and Jaeger"
    
    # Add Elastic Helm repository
    info "Adding Elastic Helm repository..."
    helm repo add elastic https://helm.elastic.co 2>/dev/null || true
    helm repo update
    
    # Create Elasticsearch credentials secret
    kubectl create secret generic elasticsearch-credentials \
        --from-literal=username=elastic \
        --from-literal=password=$ELASTICSEARCH_PASSWORD \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Install Elasticsearch
    info "Installing Elasticsearch..."
    helm upgrade --install elasticsearch elastic/elasticsearch \
        --namespace $NAMESPACE_OBSERVABILITY \
        --set replicas=3 \
        --set minimumMasterNodes=2 \
        --set resources.requests.cpu=1 \
        --set resources.requests.memory=2Gi \
        --set resources.limits.cpu=2 \
        --set resources.limits.memory=4Gi \
        --wait --timeout 10m
    
    # Install Jaeger Operator
    info "Installing Jaeger Operator..."
    kubectl apply -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.35.0/jaeger-operator.yaml -n $NAMESPACE_OBSERVABILITY
    
    # Wait for Jaeger Operator to be ready
    kubectl wait --for=condition=Available --timeout=5m deployment/jaeger-operator -n $NAMESPACE_OBSERVABILITY
    
    # Deploy Jaeger
    info "Deploying Jaeger..."
    # Replace placeholders in the Jaeger deployment file
    sed "s/\${ES_USERNAME}/elastic/g; s/\${ES_PASSWORD}/$ELASTICSEARCH_PASSWORD/g" \
        ai-observability/jaeger/jaeger-deployment.yaml | kubectl apply -f -
    
    # Wait for Jaeger to be ready
    info "Waiting for Jaeger to be ready..."
    kubectl wait --for=condition=Available --timeout=10m jaeger/jaeger -n $NAMESPACE_OBSERVABILITY
    
    info "Elasticsearch and Jaeger deployed successfully."
}

# Deploy Prometheus and Thanos
deploy_prometheus_thanos() {
    section "Deploying Prometheus and Thanos"
    
    # Add Prometheus Helm repository
    info "Adding Prometheus Helm repository..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update
    
    # Apply Prometheus configuration
    info "Applying Prometheus configuration..."
    kubectl apply -f ai-observability/prometheus/prometheus-config.yaml
    
    # Install Prometheus Operator
    info "Installing Prometheus Operator..."
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace $NAMESPACE_OBSERVABILITY \
        --set prometheus.prometheusSpec.configMaps[0]=prometheus-server-conf \
        --wait --timeout 5m
    
    # Create S3 credentials for Thanos
    info "Creating S3 credentials for Thanos..."
    # In a real deployment, you would use actual AWS credentials
    kubectl create secret generic thanos-objstore \
        --from-literal=aws_access_key_id=AKIAIOSFODNN7EXAMPLE \
        --from-literal=aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy Thanos
    info "Deploying Thanos..."
    kubectl apply -f ai-observability/prometheus/thanos-config.yaml
    
    # Wait for Thanos components to be ready
    info "Waiting for Thanos components to be ready..."
    kubectl wait --for=condition=Ready --timeout=5m pod -l app=thanos-query -n $NAMESPACE_OBSERVABILITY
    
    info "Prometheus and Thanos deployed successfully."
}

# Deploy OpenTelemetry Collector
deploy_opentelemetry() {
    section "Deploying OpenTelemetry Collector"
    
    # Add OpenTelemetry Helm repository
    info "Adding OpenTelemetry Helm repository..."
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
    helm repo update
    
    # Install OpenTelemetry Operator
    info "Installing OpenTelemetry Operator..."
    helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
        --namespace $NAMESPACE_OBSERVABILITY \
        --wait --timeout 5m
    
    # Apply OpenTelemetry configuration
    info "Applying OpenTelemetry configuration..."
    kubectl apply -f ai-observability/opentelemetry/collector-config.yaml
    
    info "OpenTelemetry Collector deployed successfully."
}

# Set up SageMaker Integration
setup_sagemaker() {
    section "Setting up SageMaker Integration"
    
    # In a real deployment, you would create SageMaker models and endpoints
    info "This step would create SageMaker models and endpoints in a real deployment."
    info "For this demo, we'll just apply the Kubernetes configuration."
    
    # Deploy SageMaker integration
    info "Deploying SageMaker integration..."
    kubectl apply -f ai-observability/sagemaker/sagemaker-integration.yaml
    
    info "SageMaker integration set up successfully."
}

# Deploy Grafana
deploy_grafana() {
    section "Deploying Grafana"
    
    # Create Grafana admin password secret
    info "Creating Grafana admin password secret..."
    kubectl create secret generic grafana-secrets \
        --from-literal=admin-password=$GRAFANA_ADMIN_PASSWORD \
        --from-literal=oauth-client-id=grafana-client \
        --from-literal=oauth-client-secret=secret123 \
        --from-literal=slack-sre-webhook-url=https://hooks.slack.com/services/T0123456/B0123456/abcdef1234567890 \
        --from-literal=slack-api-token=xoxb-1234-567890 \
        --from-literal=pagerduty-integration-key=1234567890abcdef \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Grafana configuration
    info "Applying Grafana configuration..."
    kubectl apply -f ai-observability/grafana/grafana-config.yaml
    
    # Apply Grafana RBAC configuration
    info "Applying Grafana RBAC configuration..."
    kubectl apply -f ai-observability/grafana/rbac-config.yaml
    
    # Create dashboard ConfigMaps
    info "Creating dashboard ConfigMaps..."
    mkdir -p ai-observability/grafana/dashboards/{default,sre,dev,business}
    
    # Move service-overview.json to the default folder
    cp ai-observability/grafana/dashboards/service-overview.json ai-observability/grafana/dashboards/default/
    
    kubectl create configmap grafana-dashboards-default \
        --from-file=ai-observability/grafana/dashboards/default/ \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap grafana-dashboards-sre \
        --from-file=ai-observability/grafana/dashboards/sre/ \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap grafana-dashboards-dev \
        --from-file=ai-observability/grafana/dashboards/dev/ \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create configmap grafana-dashboards-business \
        --from-file=ai-observability/grafana/dashboards/business/ \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Wait for Grafana to be ready
    info "Waiting for Grafana to be ready..."
    kubectl wait --for=condition=Available --timeout=5m deployment/grafana -n $NAMESPACE_OBSERVABILITY
    
    info "Grafana deployed successfully."
}

# Configure Dynamic Thresholds
configure_dynamic_thresholds() {
    section "Configuring Dynamic Thresholds"
    
    # Create ConfigMap for dynamic thresholds script
    info "Creating ConfigMap for dynamic thresholds script..."
    kubectl create configmap dynamic-thresholds-script \
        --from-file=ai-observability/sagemaker/dynamic-thresholds.py \
        --namespace $NAMESPACE_OBSERVABILITY \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Create ConfigMap for thresholds configuration
    info "Creating ConfigMap for thresholds configuration..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: thresholds-config
  namespace: $NAMESPACE_OBSERVABILITY
data:
  thresholds-config.json: |
    {
      "region": "$AWS_REGION",
      "metrics": [
        {
          "name": "latency_p95",
          "query": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
          "endpoint": "latency-anomaly-detector",
          "window": "1h",
          "alert_name": "HighLatencyAnomaly",
          "comparison": ">",
          "for": "5m",
          "severity": "warning",
          "dashboard": "https://grafana.example.com/d/service-overview"
        },
        {
          "name": "error_rate",
          "query": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
          "endpoint": "error-anomaly-detector",
          "window": "1h",
          "alert_name": "HighErrorRateAnomaly",
          "comparison": ">",
          "for": "5m",
          "severity": "warning",
          "dashboard": "https://grafana.example.com/d/service-overview"
        }
      ],
      "endpoints": [
        {
          "name": "latency-anomaly-detector",
          "endpoint_name": "ecommerce-latency-anomaly-detector"
        },
        {
          "name": "error-anomaly-detector",
          "endpoint_name": "ecommerce-error-anomaly-detector"
        }
      ]
    }
EOF
    
    # Deploy dynamic thresholds job
    info "Deploying dynamic thresholds job..."
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dynamic-thresholds-generator
  namespace: $NAMESPACE_OBSERVABILITY
spec:
  schedule: "*/30 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: dynamic-thresholds
            image: python:3.9
            command:
            - python
            - /app/dynamic-thresholds.py
            - --config=/app/config/thresholds-config.json
            - --prometheus-url=http://prometheus-server.$NAMESPACE_OBSERVABILITY.svc.cluster.local:9090
            - --rules-dir=/app/rules
            volumeMounts:
            - name: dynamic-thresholds-script
              mountPath: /app
            - name: thresholds-config
              mountPath: /app/config
            - name: rules-volume
              mountPath: /app/rules
          volumes:
          - name: dynamic-thresholds-script
            configMap:
              name: dynamic-thresholds-script
          - name: thresholds-config
            configMap:
              name: thresholds-config
          - name: rules-volume
            emptyDir: {}
          restartPolicy: OnFailure
EOF
    
    info "Dynamic thresholds configured successfully."
}

# Verify deployment
verify_deployment() {
    section "Verifying Deployment"
    
    info "Checking Kafka..."
    kubectl get pods -n $NAMESPACE_KAFKA
    kubectl get kafkatopics -n $NAMESPACE_KAFKA
    
    info "Checking Elasticsearch and Jaeger..."
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=elasticsearch
    kubectl get jaeger -n $NAMESPACE_OBSERVABILITY
    
    info "Checking Prometheus and Thanos..."
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=prometheus
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=thanos-query
    
    info "Checking OpenTelemetry Collector..."
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=otel-collector
    
    info "Checking SageMaker Integration..."
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=sagemaker-predictor
    
    info "Checking Grafana..."
    kubectl get pods -n $NAMESPACE_OBSERVABILITY -l app=grafana
    
    info "Deployment verification completed."
}

# Print access information
print_access_info() {
    section "Access Information"
    
    echo -e "${GREEN}Grafana:${NC}"
    echo "URL: https://grafana.example.com"
    echo "Username: admin"
    echo "Password: $GRAFANA_ADMIN_PASSWORD"
    
    echo -e "\n${GREEN}Jaeger:${NC}"
    echo "URL: https://jaeger.example.com"
    
    echo -e "\n${GREEN}Prometheus:${NC}"
    echo "URL: http://prometheus-server.$NAMESPACE_OBSERVABILITY.svc.cluster.local:9090"
    
    echo -e "\n${GREEN}Thanos:${NC}"
    echo "URL: http://thanos-query.$NAMESPACE_OBSERVABILITY.svc.cluster.local:10902"
    
    echo -e "\n${YELLOW}NOTE: In a production environment, you should set up proper ingress with TLS for all services.${NC}"
}

# Main function
main() {
    section "Starting AI-driven Observability Pipeline Manual Deployment"
    
    check_prerequisites
    create_namespaces
    deploy_kafka
    deploy_elasticsearch_jaeger
    deploy_prometheus_thanos
    deploy_opentelemetry
    setup_sagemaker
    deploy_grafana
    configure_dynamic_thresholds
    verify_deployment
    print_access_info
    
    section "Deployment Completed Successfully"
    echo -e "${GREEN}The AI-driven Observability Pipeline has been deployed successfully.${NC}"
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Instrument your applications with OpenTelemetry"
    echo "2. Create custom dashboards in Grafana"
    echo "3. Set up alerts and notifications"
    echo "4. Train and deploy custom ML models"
}

# Run main function
main
