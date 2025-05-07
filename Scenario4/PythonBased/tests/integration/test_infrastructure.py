"""
Integration tests for the AI-driven Observability Pipeline infrastructure.

These tests verify that the infrastructure is deployed correctly and
that the components are working as expected.
"""

import os
import json
import time
import unittest
import subprocess
import boto3
import requests
from kubernetes import client, config


class TestInfrastructure(unittest.TestCase):
    """Integration tests for the infrastructure."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        # Get the Pulumi stack outputs
        cls.stack_outputs = cls._get_stack_outputs()
        
        # Configure Kubernetes client
        config.load_kube_config()
        cls.k8s_api = client.CoreV1Api()
        cls.k8s_apps_api = client.AppsV1Api()
    
    @staticmethod
    def _get_stack_outputs():
        """Get the Pulumi stack outputs."""
        # Run pulumi stack output command
        result = subprocess.run(
            ["pulumi", "stack", "output", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        # Parse the JSON output
        return json.loads(result.stdout)
    
    def test_vpc_exists(self):
        """Test that the VPC exists."""
        # Get the VPC ID from the stack outputs
        vpc_id = self.stack_outputs.get("vpc_id")
        self.assertIsNotNone(vpc_id, "VPC ID not found in stack outputs")
        
        # Check that the VPC exists in AWS
        ec2 = boto3.client("ec2")
        response = ec2.describe_vpcs(VpcIds=[vpc_id])
        
        self.assertEqual(len(response["Vpcs"]), 1, "VPC not found in AWS")
        self.assertEqual(response["Vpcs"][0]["VpcId"], vpc_id, "VPC ID mismatch")
    
    def test_eks_cluster_exists(self):
        """Test that the EKS cluster exists."""
        # Get the EKS cluster name from the stack outputs
        cluster_name = self.stack_outputs.get("eks_cluster_name")
        self.assertIsNotNone(cluster_name, "EKS cluster name not found in stack outputs")
        
        # Check that the EKS cluster exists in AWS
        eks = boto3.client("eks")
        response = eks.describe_cluster(name=cluster_name)
        
        self.assertEqual(response["cluster"]["name"], cluster_name, "EKS cluster name mismatch")
        self.assertEqual(response["cluster"]["status"], "ACTIVE", "EKS cluster is not active")
    
    def test_namespaces_exist(self):
        """Test that the required namespaces exist."""
        # List of required namespaces
        required_namespaces = [
            "observability",
            "kafka",
            "elasticsearch",
            "jaeger",
            "prometheus",
            "grafana",
            "opentelemetry",
            "sagemaker-integration",
        ]
        
        # Get the list of namespaces
        namespaces = self.k8s_api.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]
        
        # Check that all required namespaces exist
        for namespace in required_namespaces:
            self.assertIn(namespace, namespace_names, f"Namespace {namespace} not found")
    
    def test_prometheus_deployment(self):
        """Test that Prometheus is deployed and running."""
        # Check that the Prometheus StatefulSet exists and is ready
        try:
            stateful_set = self.k8s_apps_api.read_namespaced_stateful_set(
                name="prometheus-prometheus-kube-prometheus-prometheus",
                namespace="prometheus",
            )
            
            self.assertEqual(
                stateful_set.status.ready_replicas,
                stateful_set.status.replicas,
                "Not all Prometheus replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"Prometheus StatefulSet not found: {e}")
    
    def test_grafana_deployment(self):
        """Test that Grafana is deployed and running."""
        # Check that the Grafana Deployment exists and is ready
        try:
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name="prometheus-grafana",
                namespace="prometheus",
            )
            
            self.assertEqual(
                deployment.status.ready_replicas,
                deployment.status.replicas,
                "Not all Grafana replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"Grafana Deployment not found: {e}")
    
    def test_elasticsearch_deployment(self):
        """Test that Elasticsearch is deployed and running."""
        # Check that the Elasticsearch StatefulSet exists and is ready
        try:
            stateful_set = self.k8s_apps_api.read_namespaced_stateful_set(
                name="elasticsearch-master",
                namespace="elasticsearch",
            )
            
            self.assertEqual(
                stateful_set.status.ready_replicas,
                stateful_set.status.replicas,
                "Not all Elasticsearch replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"Elasticsearch StatefulSet not found: {e}")
    
    def test_kafka_deployment(self):
        """Test that Kafka is deployed and running."""
        # Check that the Kafka StatefulSet exists and is ready
        try:
            stateful_set = self.k8s_apps_api.read_namespaced_stateful_set(
                name="kafka",
                namespace="kafka",
            )
            
            self.assertEqual(
                stateful_set.status.ready_replicas,
                stateful_set.status.replicas,
                "Not all Kafka replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"Kafka StatefulSet not found: {e}")
    
    def test_jaeger_deployment(self):
        """Test that Jaeger is deployed and running."""
        # Check that the Jaeger Deployment exists and is ready
        try:
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name="jaeger-query",
                namespace="jaeger",
            )
            
            self.assertEqual(
                deployment.status.ready_replicas,
                deployment.status.replicas,
                "Not all Jaeger replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"Jaeger Deployment not found: {e}")
    
    def test_opentelemetry_deployment(self):
        """Test that OpenTelemetry is deployed and running."""
        # Check that the OpenTelemetry Deployment exists and is ready
        try:
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name="opentelemetry-operator-controller-manager",
                namespace="opentelemetry",
            )
            
            self.assertEqual(
                deployment.status.ready_replicas,
                deployment.status.replicas,
                "Not all OpenTelemetry replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"OpenTelemetry Deployment not found: {e}")
    
    def test_sagemaker_integration(self):
        """Test that SageMaker integration is deployed and running."""
        # Check that the SageMaker integration Deployment exists and is ready
        try:
            deployment = self.k8s_apps_api.read_namespaced_deployment(
                name="ecommerce-processor",
                namespace="sagemaker-integration",
            )
            
            self.assertEqual(
                deployment.status.ready_replicas,
                deployment.status.replicas,
                "Not all SageMaker integration replicas are ready",
            )
        except client.exceptions.ApiException as e:
            self.fail(f"SageMaker integration Deployment not found: {e}")
    
    def test_model_bucket_exists(self):
        """Test that the model bucket exists."""
        # Get the model bucket name from the stack outputs
        bucket_name = self.stack_outputs.get("model_bucket_name")
        self.assertIsNotNone(bucket_name, "Model bucket name not found in stack outputs")
        
        # Check that the bucket exists in AWS
        s3 = boto3.client("s3")
        try:
            s3.head_bucket(Bucket=bucket_name)
        except Exception as e:
            self.fail(f"Model bucket not found: {e}")
    
    def test_sagemaker_role_exists(self):
        """Test that the SageMaker role exists."""
        # Get the SageMaker role ARN from the stack outputs
        role_arn = self.stack_outputs.get("sagemaker_role_arn")
        self.assertIsNotNone(role_arn, "SageMaker role ARN not found in stack outputs")
        
        # Extract the role name from the ARN
        role_name = role_arn.split("/")[-1]
        
        # Check that the role exists in AWS
        iam = boto3.client("iam")
        try:
            iam.get_role(RoleName=role_name)
        except Exception as e:
            self.fail(f"SageMaker role not found: {e}")
    
    def test_grafana_url(self):
        """Test that the Grafana URL is accessible."""
        # Get the Grafana URL from the stack outputs
        grafana_url = self.stack_outputs.get("grafana_url")
        self.assertIsNotNone(grafana_url, "Grafana URL not found in stack outputs")
        
        # Skip this test if running in CI/CD
        if os.environ.get("CI") == "true":
            self.skipTest("Skipping URL test in CI/CD environment")
        
        # Check that the URL is accessible
        try:
            response = requests.get(grafana_url, timeout=10, verify=False)
            self.assertEqual(response.status_code, 200, "Grafana URL is not accessible")
        except requests.exceptions.RequestException as e:
            self.fail(f"Failed to access Grafana URL: {e}")


if __name__ == "__main__":
    unittest.main()
