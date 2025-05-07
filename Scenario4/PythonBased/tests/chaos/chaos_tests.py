#!/usr/bin/env python3
"""
Chaos Engineering Tests for the AI-driven Observability Pipeline.

This module implements chaos engineering tests to verify the resilience
and fault tolerance of the observability pipeline.

Key features:
- Pod termination tests
- Network disruption tests
- Resource exhaustion tests
- Dependency failure tests
- Recovery verification
"""

import os
import sys
import json
import time
import random
import logging
import argparse
import requests
import subprocess
from typing import Dict, List, Any, Optional
from kubernetes import client, config


class ChaosTest:
    """Base class for chaos tests."""
    
    def __init__(self, namespace: str, logger: logging.Logger):
        """
        Initialize the chaos test.
        
        Args:
            namespace: Kubernetes namespace
            logger: Logger instance
        """
        self.namespace = namespace
        self.logger = logger
        
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                raise RuntimeError("Could not configure Kubernetes client")
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        
        # Initialize API client
        self.base_url = os.environ.get('BASE_URL', 'http://localhost:8080')
        self.api_key = os.environ.get('API_KEY', 'test-api-key')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
    
    def setup(self) -> None:
        """Set up the test environment."""
        pass
    
    def run(self) -> Dict[str, Any]:
        """
        Run the chaos test.
        
        Returns:
            Dictionary with test results
        """
        raise NotImplementedError("Subclasses must implement run")
    
    def cleanup(self) -> None:
        """Clean up the test environment."""
        pass
    
    def check_health(self) -> bool:
        """
        Check if the system is healthy.
        
        Returns:
            True if the system is healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/health",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def wait_for_health(self, timeout: int = 300, interval: int = 5) -> bool:
        """
        Wait for the system to become healthy.
        
        Args:
            timeout: Timeout in seconds
            interval: Check interval in seconds
            
        Returns:
            True if the system became healthy within the timeout, False otherwise
        """
        self.logger.info(f"Waiting for system to become healthy (timeout: {timeout}s)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_health():
                self.logger.info("System is healthy")
                return True
            
            self.logger.info(f"System is not healthy yet, waiting {interval}s...")
            time.sleep(interval)
        
        self.logger.error(f"System did not become healthy within {timeout}s")
        return False


class PodTerminationTest(ChaosTest):
    """Test resilience against pod terminations."""
    
    def __init__(self, namespace: str, logger: logging.Logger, service: str):
        """
        Initialize the pod termination test.
        
        Args:
            namespace: Kubernetes namespace
            logger: Logger instance
            service: Service to target
        """
        super().__init__(namespace, logger)
        self.service = service
    
    def run(self) -> Dict[str, Any]:
        """
        Run the pod termination test.
        
        Returns:
            Dictionary with test results
        """
        self.logger.info(f"Running pod termination test for service {self.service}")
        
        # Check initial health
        if not self.check_health():
            return {
                'success': False,
                'message': "System is not healthy before test",
                'service': self.service
            }
        
        # Get pods for the service
        pods = self.core_v1.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"app={self.service}"
        ).items
        
        if not pods:
            return {
                'success': False,
                'message': f"No pods found for service {self.service}",
                'service': self.service
            }
        
        # Select a random pod
        pod = random.choice(pods)
        pod_name = pod.metadata.name
        
        self.logger.info(f"Selected pod {pod_name} for termination")
        
        # Delete the pod
        self.logger.info(f"Terminating pod {pod_name}")
        self.core_v1.delete_namespaced_pod(
            name=pod_name,
            namespace=self.namespace
        )
        
        # Wait for the pod to be terminated
        start_time = time.time()
        while time.time() - start_time < 60:
            try:
                self.core_v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace
                )
                self.logger.info(f"Pod {pod_name} is still terminating...")
                time.sleep(5)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    self.logger.info(f"Pod {pod_name} has been terminated")
                    break
                else:
                    raise
        
        # Wait for a new pod to be created
        self.logger.info("Waiting for a new pod to be created")
        start_time = time.time()
        new_pod_ready = False
        
        while time.time() - start_time < 300:
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app={self.service}"
            ).items
            
            # Check if all pods are ready
            all_ready = True
            for pod in pods:
                if not pod.status.container_statuses:
                    all_ready = False
                    break
                
                for container in pod.status.container_statuses:
                    if not container.ready:
                        all_ready = False
                        break
                
                if not all_ready:
                    break
            
            if all_ready and len(pods) > 0:
                new_pod_ready = True
                break
            
            self.logger.info("Waiting for new pod to be ready...")
            time.sleep(10)
        
        if not new_pod_ready:
            return {
                'success': False,
                'message': f"New pod for service {self.service} did not become ready",
                'service': self.service
            }
        
        # Wait for the system to become healthy
        if not self.wait_for_health():
            return {
                'success': False,
                'message': f"System did not become healthy after pod {pod_name} was terminated",
                'service': self.service
            }
        
        return {
            'success': True,
            'message': f"System recovered after pod {pod_name} was terminated",
            'service': self.service
        }


class NetworkDisruptionTest(ChaosTest):
    """Test resilience against network disruptions."""
    
    def __init__(self, namespace: str, logger: logging.Logger, service: str, duration: int = 60):
        """
        Initialize the network disruption test.
        
        Args:
            namespace: Kubernetes namespace
            logger: Logger instance
            service: Service to target
            duration: Disruption duration in seconds
        """
        super().__init__(namespace, logger)
        self.service = service
        self.duration = duration
    
    def run(self) -> Dict[str, Any]:
        """
        Run the network disruption test.
        
        Returns:
            Dictionary with test results
        """
        self.logger.info(f"Running network disruption test for service {self.service} (duration: {self.duration}s)")
        
        # Check initial health
        if not self.check_health():
            return {
                'success': False,
                'message': "System is not healthy before test",
                'service': self.service
            }
        
        # Create network policy to block all ingress and egress traffic
        network_policy_name = f"{self.service}-chaos-network-policy"
        
        network_policy = client.NetworkingV1Api().create_namespaced_network_policy(
            namespace=self.namespace,
            body=client.V1NetworkPolicy(
                metadata=client.V1ObjectMeta(
                    name=network_policy_name
                ),
                spec=client.V1NetworkPolicySpec(
                    pod_selector=client.V1LabelSelector(
                        match_labels={"app": self.service}
                    ),
                    policy_types=["Ingress", "Egress"],
                    ingress=[],
                    egress=[]
                )
            )
        )
        
        self.logger.info(f"Created network policy {network_policy_name} to disrupt network for {self.service}")
        
        # Wait for the specified duration
        self.logger.info(f"Waiting for {self.duration}s...")
        time.sleep(self.duration)
        
        # Delete the network policy
        client.NetworkingV1Api().delete_namespaced_network_policy(
            name=network_policy_name,
            namespace=self.namespace
        )
        
        self.logger.info(f"Deleted network policy {network_policy_name}")
        
        # Wait for the system to become healthy
        if not self.wait_for_health():
            return {
                'success': False,
                'message': f"System did not become healthy after network disruption for {self.service}",
                'service': self.service
            }
        
        return {
            'success': True,
            'message': f"System recovered after network disruption for {self.service}",
            'service': self.service
        }


class ResourceExhaustionTest(ChaosTest):
    """Test resilience against resource exhaustion."""
    
    def __init__(self, namespace: str, logger: logging.Logger, service: str, resource: str, duration: int = 60):
        """
        Initialize the resource exhaustion test.
        
        Args:
            namespace: Kubernetes namespace
            logger: Logger instance
            service: Service to target
            resource: Resource to exhaust (cpu or memory)
            duration: Exhaustion duration in seconds
        """
        super().__init__(namespace, logger)
        self.service = service
        self.resource = resource
        self.duration = duration
        self.stress_pod_name = f"{self.service}-{self.resource}-stress"
    
    def run(self) -> Dict[str, Any]:
        """
        Run the resource exhaustion test.
        
        Returns:
            Dictionary with test results
        """
        self.logger.info(f"Running {self.resource} exhaustion test for service {self.service} (duration: {self.duration}s)")
        
        # Check initial health
        if not self.check_health():
            return {
                'success': False,
                'message': "System is not healthy before test",
                'service': self.service
            }
        
        # Get pods for the service
        pods = self.core_v1.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"app={self.service}"
        ).items
        
        if not pods:
            return {
                'success': False,
                'message': f"No pods found for service {self.service}",
                'service': self.service
            }
        
        # Select a random pod
        pod = random.choice(pods)
        pod_name = pod.metadata.name
        
        # Create a stress pod that runs in the same node
        node_name = pod.spec.node_name
        
        # Determine stress command based on resource
        if self.resource == 'cpu':
            stress_command = ["stress", "--cpu", "4", "--timeout", str(self.duration)]
        elif self.resource == 'memory':
            stress_command = ["stress", "--vm", "2", "--vm-bytes", "1G", "--timeout", str(self.duration)]
        else:
            return {
                'success': False,
                'message': f"Unsupported resource type: {self.resource}",
                'service': self.service
            }
        
        # Create stress pod
        stress_pod = self.core_v1.create_namespaced_pod(
            namespace=self.namespace,
            body=client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=self.stress_pod_name
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="stress",
                            image="polinux/stress",
                            command=stress_command,
                            resources=client.V1ResourceRequirements(
                                limits={
                                    "cpu": "3" if self.resource == 'cpu' else "100m",
                                    "memory": "100Mi" if self.resource == 'cpu' else "2Gi"
                                },
                                requests={
                                    "cpu": "2" if self.resource == 'cpu' else "50m",
                                    "memory": "50Mi" if self.resource == 'cpu' else "1Gi"
                                }
                            )
                        )
                    ],
                    node_name=node_name,
                    restart_policy="Never"
                )
            )
        )
        
        self.logger.info(f"Created stress pod {self.stress_pod_name} on node {node_name}")
        
        # Wait for the stress pod to complete
        self.logger.info(f"Waiting for stress pod to complete (up to {self.duration + 30}s)...")
        start_time = time.time()
        while time.time() - start_time < self.duration + 30:
            try:
                pod_status = self.core_v1.read_namespaced_pod_status(
                    name=self.stress_pod_name,
                    namespace=self.namespace
                )
                
                if pod_status.status.phase in ["Succeeded", "Failed"]:
                    self.logger.info(f"Stress pod completed with status: {pod_status.status.phase}")
                    break
                
                self.logger.info(f"Stress pod is still running...")
                time.sleep(10)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    self.logger.info("Stress pod not found, assuming it completed")
                    break
                else:
                    raise
        
        # Delete the stress pod
        try:
            self.core_v1.delete_namespaced_pod(
                name=self.stress_pod_name,
                namespace=self.namespace
            )
            self.logger.info(f"Deleted stress pod {self.stress_pod_name}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                self.logger.warning(f"Failed to delete stress pod: {e}")
        
        # Wait for the system to become healthy
        if not self.wait_for_health():
            return {
                'success': False,
                'message': f"System did not become healthy after {self.resource} exhaustion",
                'service': self.service
            }
        
        return {
            'success': True,
            'message': f"System recovered after {self.resource} exhaustion",
            'service': self.service
        }


class DependencyFailureTest(ChaosTest):
    """Test resilience against dependency failures."""
    
    def __init__(self, namespace: str, logger: logging.Logger, service: str, dependency: str, duration: int = 60):
        """
        Initialize the dependency failure test.
        
        Args:
            namespace: Kubernetes namespace
            logger: Logger instance
            service: Service to target
            dependency: Dependency service to fail
            duration: Failure duration in seconds
        """
        super().__init__(namespace, logger)
        self.service = service
        self.dependency = dependency
        self.duration = duration
    
    def run(self) -> Dict[str, Any]:
        """
        Run the dependency failure test.
        
        Returns:
            Dictionary with test results
        """
        self.logger.info(f"Running dependency failure test for {self.service} -> {self.dependency} (duration: {self.duration}s)")
        
        # Check initial health
        if not self.check_health():
            return {
                'success': False,
                'message': "System is not healthy before test",
                'service': self.service,
                'dependency': self.dependency
            }
        
        # Create network policy to block traffic to dependency
        network_policy_name = f"{self.service}-{self.dependency}-chaos-network-policy"
        
        network_policy = client.NetworkingV1Api().create_namespaced_network_policy(
            namespace=self.namespace,
            body=client.V1NetworkPolicy(
                metadata=client.V1ObjectMeta(
                    name=network_policy_name
                ),
                spec=client.V1NetworkPolicySpec(
                    pod_selector=client.V1LabelSelector(
                        match_labels={"app": self.service}
                    ),
                    policy_types=["Egress"],
                    egress=[
                        {
                            "to": [
                                {
                                    "pod_selector": {
                                        "match_labels": {
                                            "app": self.dependency
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                )
            )
        )
        
        self.logger.info(f"Created network policy {network_policy_name} to block traffic from {self.service} to {self.dependency}")
        
        # Wait for the specified duration
        self.logger.info(f"Waiting for {self.duration}s...")
        time.sleep(self.duration)
        
        # Delete the network policy
        client.NetworkingV1Api().delete_namespaced_network_policy(
            name=network_policy_name,
            namespace=self.namespace
        )
        
        self.logger.info(f"Deleted network policy {network_policy_name}")
        
        # Wait for the system to become healthy
        if not self.wait_for_health():
            return {
                'success': False,
                'message': f"System did not become healthy after dependency failure {self.service} -> {self.dependency}",
                'service': self.service,
                'dependency': self.dependency
            }
        
        return {
            'success': True,
            'message': f"System recovered after dependency failure {self.service} -> {self.dependency}",
            'service': self.service,
            'dependency': self.dependency
        }


def run_chaos_tests():
    """Run chaos tests."""
    parser = argparse.ArgumentParser(description='Run chaos tests')
    parser.add_argument('--namespace', default='default', help='Kubernetes namespace')
    parser.add_argument('--service', required=True, help='Service to target')
    parser.add_argument('--dependency', help='Dependency service for dependency failure test')
    parser.add_argument('--test-type', choices=['pod', 'network', 'cpu', 'memory', 'dependency', 'all'], default='all', help='Type of chaos test to run')
    parser.add_argument('--duration', type=int, default=60, help='Duration of chaos in seconds')
    parser.add_argument('--output', help='Output file for test results')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("chaos-tests")
    
    # Run tests
    results = []
    
    if args.test_type in ['pod', 'all']:
        test = PodTerminationTest(args.namespace, logger, args.service)
        results.append({
            'test_type': 'pod_termination',
            'result': test.run()
        })
    
    if args.test_type in ['network', 'all']:
        test = NetworkDisruptionTest(args.namespace, logger, args.service, args.duration)
        results.append({
            'test_type': 'network_disruption',
            'result': test.run()
        })
    
    if args.test_type in ['cpu', 'all']:
        test = ResourceExhaustionTest(args.namespace, logger, args.service, 'cpu', args.duration)
        results.append({
            'test_type': 'cpu_exhaustion',
            'result': test.run()
        })
    
    if args.test_type in ['memory', 'all']:
        test = ResourceExhaustionTest(args.namespace, logger, args.service, 'memory', args.duration)
        results.append({
            'test_type': 'memory_exhaustion',
            'result': test.run()
        })
    
    if (args.test_type in ['dependency', 'all']) and args.dependency:
        test = DependencyFailureTest(args.namespace, logger, args.service, args.dependency, args.duration)
        results.append({
            'test_type': 'dependency_failure',
            'result': test.run()
        })
    
    # Print results
    logger.info("Chaos test results:")
    for result in results:
        logger.info(f"  {result['test_type']}: {'SUCCESS' if result['result']['success'] else 'FAILURE'} - {result['result']['message']}")
    
    # Save results to file
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output}")
    
    # Return exit code
    return 0 if all(r['result']['success'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(run_chaos_tests())
