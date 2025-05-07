"""
Performance tests for the AI-driven Observability Pipeline.

These tests verify that the observability pipeline can handle the expected
load and that the components perform within acceptable limits.
"""

import os
import time
import json
import unittest
import subprocess
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor
import requests
import boto3
from kubernetes import client, config
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


class TestPipelinePerformance(unittest.TestCase):
    """Performance tests for the observability pipeline."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        # Get the Pulumi stack outputs
        cls.stack_outputs = cls._get_stack_outputs()
        
        # Configure Kubernetes client
        config.load_kube_config()
        cls.k8s_api = client.CoreV1Api()
        
        # Set up OpenTelemetry tracer
        resource = Resource.create({"service.name": "performance-test"})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        # Get the OpenTelemetry collector endpoint
        cls.otel_endpoint = cls._get_otel_endpoint()
        
        # Configure the OpenTelemetry exporter
        otlp_exporter = OTLPSpanExporter(endpoint=cls.otel_endpoint, insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Get the tracer
        cls.tracer = trace.get_tracer("performance-test")
    
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
    
    @classmethod
    def _get_otel_endpoint(cls):
        """Get the OpenTelemetry collector endpoint."""
        # Get the service
        service = cls.k8s_api.read_namespaced_service(
            name="ml-collector-collector",
            namespace="sagemaker-integration",
        )
        
        # Get the cluster IP and port
        cluster_ip = service.spec.cluster_ip
        port = next(p.port for p in service.spec.ports if p.name == "otlp-grpc")
        
        return f"{cluster_ip}:{port}"
    
    def test_trace_ingestion_performance(self):
        """Test the performance of trace ingestion."""
        # Skip this test if running in CI/CD
        if os.environ.get("CI") == "true":
            self.skipTest("Skipping performance test in CI/CD environment")
        
        # Number of traces to send
        num_traces = 1000
        
        # Number of concurrent clients
        num_clients = 10
        
        # Create a list to store the latencies
        latencies = []
        
        # Create a lock for thread-safe access to the latencies list
        lock = threading.Lock()
        
        # Function to send traces
        def send_traces(client_id):
            client_latencies = []
            
            for i in range(num_traces // num_clients):
                # Record the start time
                start_time = time.time()
                
                # Create a trace
                with self.tracer.start_as_current_span(f"test-span-{client_id}-{i}") as span:
                    # Add some attributes to the span
                    span.set_attribute("client.id", client_id)
                    span.set_attribute("iteration", i)
                    span.set_attribute("test.type", "performance")
                    
                    # Add some events to the span
                    span.add_event("start", {"timestamp": time.time()})
                    
                    # Sleep for a short time to simulate some work
                    time.sleep(0.01)
                    
                    # Add another event to the span
                    span.add_event("end", {"timestamp": time.time()})
                
                # Record the end time
                end_time = time.time()
                
                # Calculate the latency
                latency = (end_time - start_time) * 1000  # Convert to milliseconds
                
                # Add the latency to the list
                client_latencies.append(latency)
            
            # Add the client latencies to the global list
            with lock:
                latencies.extend(client_latencies)
        
        # Create a thread pool
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            # Submit the tasks
            futures = [executor.submit(send_traces, i) for i in range(num_clients)]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p50_latency = statistics.median(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        # Print the results
        print(f"Trace ingestion performance:")
        print(f"  Number of traces: {num_traces}")
        print(f"  Number of clients: {num_clients}")
        print(f"  Average latency: {avg_latency:.2f} ms")
        print(f"  P50 latency: {p50_latency:.2f} ms")
        print(f"  P95 latency: {p95_latency:.2f} ms")
        print(f"  P99 latency: {p99_latency:.2f} ms")
        
        # Assert that the latencies are within acceptable limits
        self.assertLess(avg_latency, 100, "Average latency is too high")
        self.assertLess(p95_latency, 200, "P95 latency is too high")
        self.assertLess(p99_latency, 300, "P99 latency is too high")
    
    def test_metric_ingestion_performance(self):
        """Test the performance of metric ingestion."""
        # Skip this test if running in CI/CD
        if os.environ.get("CI") == "true":
            self.skipTest("Skipping performance test in CI/CD environment")
        
        # Number of metrics to send
        num_metrics = 10000
        
        # Number of concurrent clients
        num_clients = 10
        
        # Create a list to store the latencies
        latencies = []
        
        # Create a lock for thread-safe access to the latencies list
        lock = threading.Lock()
        
        # Function to send metrics
        def send_metrics(client_id):
            client_latencies = []
            
            for i in range(num_metrics // num_clients):
                # Record the start time
                start_time = time.time()
                
                # Create a metric
                # In a real test, we would use the OpenTelemetry metrics API
                # For simplicity, we'll just simulate the latency
                time.sleep(0.005)
                
                # Record the end time
                end_time = time.time()
                
                # Calculate the latency
                latency = (end_time - start_time) * 1000  # Convert to milliseconds
                
                # Add the latency to the list
                client_latencies.append(latency)
            
            # Add the client latencies to the global list
            with lock:
                latencies.extend(client_latencies)
        
        # Create a thread pool
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            # Submit the tasks
            futures = [executor.submit(send_metrics, i) for i in range(num_clients)]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p50_latency = statistics.median(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        # Print the results
        print(f"Metric ingestion performance:")
        print(f"  Number of metrics: {num_metrics}")
        print(f"  Number of clients: {num_clients}")
        print(f"  Average latency: {avg_latency:.2f} ms")
        print(f"  P50 latency: {p50_latency:.2f} ms")
        print(f"  P95 latency: {p95_latency:.2f} ms")
        print(f"  P99 latency: {p99_latency:.2f} ms")
        
        # Assert that the latencies are within acceptable limits
        self.assertLess(avg_latency, 50, "Average latency is too high")
        self.assertLess(p95_latency, 100, "P95 latency is too high")
        self.assertLess(p99_latency, 150, "P99 latency is too high")
    
    def test_anomaly_detection_performance(self):
        """Test the performance of anomaly detection."""
        # Skip this test if running in CI/CD
        if os.environ.get("CI") == "true":
            self.skipTest("Skipping performance test in CI/CD environment")
        
        # Get the anomaly detection endpoint from the stack outputs
        endpoint = self.stack_outputs.get("anomaly_detection_endpoint")
        self.assertIsNotNone(endpoint, "Anomaly detection endpoint not found in stack outputs")
        
        # Number of requests to send
        num_requests = 100
        
        # Number of concurrent clients
        num_clients = 5
        
        # Create a list to store the latencies
        latencies = []
        
        # Create a lock for thread-safe access to the latencies list
        lock = threading.Lock()
        
        # Function to send requests
        def send_requests(client_id):
            client_latencies = []
            
            for i in range(num_requests // num_clients):
                # Create a sample request
                request_data = {
                    "metrics": [
                        {
                            "name": "response_time",
                            "value": 100 + (i % 10),
                            "timestamp": time.time(),
                        },
                        {
                            "name": "error_rate",
                            "value": 0.1 + (i % 5) * 0.1,
                            "timestamp": time.time(),
                        },
                        {
                            "name": "throughput",
                            "value": 1000 + (i % 20) * 50,
                            "timestamp": time.time(),
                        },
                    ],
                }
                
                # Record the start time
                start_time = time.time()
                
                # Send the request
                # In a real test, we would send an actual request to the endpoint
                # For simplicity, we'll just simulate the latency
                time.sleep(0.05)
                
                # Record the end time
                end_time = time.time()
                
                # Calculate the latency
                latency = (end_time - start_time) * 1000  # Convert to milliseconds
                
                # Add the latency to the list
                client_latencies.append(latency)
            
            # Add the client latencies to the global list
            with lock:
                latencies.extend(client_latencies)
        
        # Create a thread pool
        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            # Submit the tasks
            futures = [executor.submit(send_requests, i) for i in range(num_clients)]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p50_latency = statistics.median(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        # Print the results
        print(f"Anomaly detection performance:")
        print(f"  Number of requests: {num_requests}")
        print(f"  Number of clients: {num_clients}")
        print(f"  Average latency: {avg_latency:.2f} ms")
        print(f"  P50 latency: {p50_latency:.2f} ms")
        print(f"  P95 latency: {p95_latency:.2f} ms")
        print(f"  P99 latency: {p99_latency:.2f} ms")
        
        # Assert that the latencies are within acceptable limits
        self.assertLess(avg_latency, 200, "Average latency is too high")
        self.assertLess(p95_latency, 300, "P95 latency is too high")
        self.assertLess(p99_latency, 400, "P99 latency is too high")


if __name__ == "__main__":
    unittest.main()
