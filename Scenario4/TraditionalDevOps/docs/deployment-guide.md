# AI-driven Observability Pipeline Deployment Guide

This guide provides step-by-step instructions for deploying the AI-driven Observability Pipeline for E-commerce.

## Prerequisites

Before deploying the observability pipeline, ensure you have the following:

1. **Kubernetes Cluster**
   - EKS, GKE, or AKS cluster with version 1.19+
   - Minimum 6 worker nodes (8 CPU, 32GB RAM each)
   - Node autoscaling enabled

2. **AWS Account**
   - IAM permissions for SageMaker, S3, and CloudWatch
   - SageMaker execution role with appropriate permissions

3. **Helm**
   - Helm 3.0+ installed

4. **kubectl**
   - Configured to access your Kubernetes cluster

5. **Storage**
   - Default StorageClass configured
   - At least 500GB available storage

## Deployment Steps

### 1. Create Namespaces

```bash
kubectl create namespace observability
kubectl create namespace kafka
```

### 2. Deploy Kafka

```bash
# Add Strimzi Helm repository
helm repo add strimzi https://strimzi.io/charts/
helm repo update

# Install Strimzi Operator
helm install kafka-operator strimzi/strimzi-kafka-operator --namespace kafka

# Deploy Kafka cluster and topics
kubectl apply -f ai-observability/kafka/kafka-config.yaml
```

### 3. Deploy Elasticsearch and Jaeger

```bash
# Add Elastic Helm repository
helm repo add elastic https://helm.elastic.co
helm repo update

# Install Elasticsearch
helm install elasticsearch elastic/elasticsearch \
  --namespace observability \
  --set replicas=3 \
  --set minimumMasterNodes=2 \
  --set resources.requests.cpu=1 \
  --set resources.requests.memory=2Gi \
  --set resources.limits.cpu=2 \
  --set resources.limits.memory=4Gi

# Install Jaeger Operator
kubectl create -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.35.0/jaeger-operator.yaml -n observability

# Deploy Jaeger
kubectl apply -f ai-observability/jaeger/jaeger-deployment.yaml
```

### 4. Deploy Prometheus and Thanos

```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace observability \
  --set prometheus.prometheusSpec.configMaps[0]=prometheus-server-conf

# Apply Prometheus configuration
kubectl apply -f ai-observability/prometheus/prometheus-config.yaml

# Deploy Thanos
kubectl apply -f ai-observability/prometheus/thanos-config.yaml
```

### 5. Deploy OpenTelemetry Collector

```bash
# Add OpenTelemetry Helm repository
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Install OpenTelemetry Operator
helm install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace observability

# Apply OpenTelemetry configuration
kubectl apply -f ai-observability/opentelemetry/collector-config.yaml
```

### 6. Set up SageMaker Integration

```bash
# Create SageMaker model
aws sagemaker create-model \
  --model-name ecommerce-latency-anomaly-detector \
  --execution-role-arn arn:aws:iam::123456789012:role/SageMakerExecutionRole \
  --primary-container '{
    "Image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/anomaly-detection:latest",
    "ModelDataUrl": "s3://your-bucket/models/anomaly-detection/model.tar.gz"
  }'

# Create SageMaker endpoint configuration
aws sagemaker create-endpoint-config \
  --endpoint-config-name ecommerce-latency-anomaly-detector-config \
  --production-variants '[{
    "VariantName": "AllTraffic",
    "ModelName": "ecommerce-latency-anomaly-detector",
    "InitialInstanceCount": 2,
    "InstanceType": "ml.c5.xlarge"
  }]'

# Create SageMaker endpoint
aws sagemaker create-endpoint \
  --endpoint-name ecommerce-latency-anomaly-detector \
  --endpoint-config-name ecommerce-latency-anomaly-detector-config

# Deploy SageMaker integration
kubectl apply -f ai-observability/sagemaker/sagemaker-integration.yaml
```

### 7. Deploy Grafana

```bash
# Apply Grafana configuration
kubectl apply -f ai-observability/grafana/grafana-config.yaml

# Apply Grafana RBAC configuration
kubectl apply -f ai-observability/grafana/rbac-config.yaml

# Create dashboard ConfigMaps
kubectl create configmap grafana-dashboards-default --from-file=ai-observability/grafana/dashboards/default/ -n observability
kubectl create configmap grafana-dashboards-sre --from-file=ai-observability/grafana/dashboards/sre/ -n observability
kubectl create configmap grafana-dashboards-dev --from-file=ai-observability/grafana/dashboards/dev/ -n observability
kubectl create configmap grafana-dashboards-business --from-file=ai-observability/grafana/dashboards/business/ -n observability
```

### 8. Configure Dynamic Thresholds

```bash
# Deploy dynamic thresholds job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dynamic-thresholds-generator
  namespace: observability
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
            - --prometheus-url=http://prometheus-server.observability.svc.cluster.local:9090
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

# Create ConfigMap for dynamic thresholds script
kubectl create configmap dynamic-thresholds-script --from-file=ai-observability/sagemaker/dynamic-thresholds.py -n observability
```

## Verification

### 1. Check Kafka

```bash
kubectl get pods -n kafka
kubectl get kafkatopics -n kafka
```

### 2. Check Elasticsearch and Jaeger

```bash
kubectl get pods -n observability -l app=elasticsearch
kubectl get jaeger -n observability
```

### 3. Check Prometheus and Thanos

```bash
kubectl get pods -n observability -l app=prometheus
kubectl get pods -n observability -l app=thanos-query
```

### 4. Check OpenTelemetry Collector

```bash
kubectl get pods -n observability -l app=otel-collector
```

### 5. Check SageMaker Integration

```bash
kubectl get pods -n observability -l app=sagemaker-predictor
aws sagemaker describe-endpoint --endpoint-name ecommerce-latency-anomaly-detector
```

### 6. Check Grafana

```bash
kubectl get pods -n observability -l app=grafana
```

## Accessing the Services

### Grafana

Access Grafana at: https://grafana.example.com

Default credentials:
- Username: admin
- Password: admin123 (change after first login)

### Jaeger

Access Jaeger at: https://jaeger.example.com

### Prometheus

Access Prometheus at: http://prometheus-server.observability.svc.cluster.local:9090

### Thanos

Access Thanos Query at: http://thanos-query.observability.svc.cluster.local:10902

## Troubleshooting

### Kafka Issues

If Kafka pods are not starting:

```bash
kubectl describe pod -n kafka kafka-cluster-kafka-0
kubectl logs -n kafka kafka-cluster-kafka-0
```

### OpenTelemetry Collector Issues

If the collector is not receiving data:

```bash
kubectl logs -n observability -l app=otel-collector
```

### SageMaker Integration Issues

If predictions are not working:

```bash
kubectl logs -n observability -l app=sagemaker-predictor
aws sagemaker describe-endpoint --endpoint-name ecommerce-latency-anomaly-detector
```

### Grafana Issues

If dashboards are not loading:

```bash
kubectl logs -n observability -l app=grafana
kubectl get configmaps -n observability | grep grafana
```

## Next Steps

1. **Instrument Applications**
   - Follow the [Custom Instrumentation Guide](../opentelemetry/custom-instrumentation.md)
   - Add OpenTelemetry sidecars to your services

2. **Create Custom Dashboards**
   - Use the provided templates in Grafana
   - Create business-specific dashboards

3. **Set Up Alerts**
   - Configure alert rules in Prometheus
   - Set up notification channels in Grafana

4. **Train Custom ML Models**
   - Use the provided SageMaker notebooks
   - Deploy custom anomaly detection models
