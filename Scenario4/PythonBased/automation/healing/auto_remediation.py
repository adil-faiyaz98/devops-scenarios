"""
Automated Remediation System for E-commerce Observability.

This module implements an automated remediation system that can take
corrective actions in response to detected or predicted issues.

Key features:
- Rule-based remediation actions
- ML-driven remediation selection
- Safe execution with rollback capability
- Audit logging of all actions
- Approval workflows for critical actions
"""

import os
import json
import time
import logging
import datetime
import subprocess
import threading
import requests
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from kubernetes import client, config


class RemediationAction:
    """Base class for remediation actions."""
    
    def __init__(self, name: str, description: str, severity: str):
        """
        Initialize a remediation action.
        
        Args:
            name: Name of the action
            description: Description of the action
            severity: Severity level (low, medium, high, critical)
        """
        self.name = name
        self.description = description
        self.severity = severity
        self.requires_approval = severity in ['high', 'critical']
    
    def can_remediate(self, issue: Dict[str, Any]) -> bool:
        """
        Check if this action can remediate the given issue.
        
        Args:
            issue: Issue to remediate
            
        Returns:
            True if this action can remediate the issue, False otherwise
        """
        raise NotImplementedError("Subclasses must implement can_remediate")
    
    def execute(self, issue: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the remediation action.
        
        Args:
            issue: Issue to remediate
            dry_run: If True, only simulate the action
            
        Returns:
            Dictionary with execution results
        """
        raise NotImplementedError("Subclasses must implement execute")
    
    def rollback(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback the remediation action.
        
        Args:
            execution_result: Result of the execute method
            
        Returns:
            Dictionary with rollback results
        """
        raise NotImplementedError("Subclasses must implement rollback")


class ScaleUpDeploymentAction(RemediationAction):
    """Action to scale up a Kubernetes deployment."""
    
    def __init__(self):
        """Initialize the action."""
        super().__init__(
            name="scale_up_deployment",
            description="Scale up a Kubernetes deployment",
            severity="medium"
        )
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                raise RuntimeError("Could not configure Kubernetes client")
        
        self.apps_v1 = client.AppsV1Api()
    
    def can_remediate(self, issue: Dict[str, Any]) -> bool:
        """
        Check if this action can remediate the given issue.
        
        Args:
            issue: Issue to remediate
            
        Returns:
            True if this action can remediate the issue, False otherwise
        """
        # Check if issue is related to high CPU or memory usage
        if issue.get('metric_name') in ['cpu_usage', 'memory_usage']:
            # Check if the service is a Kubernetes deployment
            try:
                service = issue.get('service')
                namespace = issue.get('namespace', 'default')
                
                # Try to get the deployment
                self.apps_v1.read_namespaced_deployment(
                    name=service,
                    namespace=namespace
                )
                
                return True
            except client.exceptions.ApiException:
                return False
        
        return False
    
    def execute(self, issue: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the remediation action.
        
        Args:
            issue: Issue to remediate
            dry_run: If True, only simulate the action
            
        Returns:
            Dictionary with execution results
        """
        service = issue.get('service')
        namespace = issue.get('namespace', 'default')
        
        # Get current deployment
        deployment = self.apps_v1.read_namespaced_deployment(
            name=service,
            namespace=namespace
        )
        
        # Get current replica count
        current_replicas = deployment.spec.replicas
        
        # Calculate new replica count (increase by 50%, minimum 1)
        new_replicas = max(current_replicas + 1, int(current_replicas * 1.5))
        
        # Execute the scaling
        result = {
            'action': self.name,
            'service': service,
            'namespace': namespace,
            'previous_replicas': current_replicas,
            'new_replicas': new_replicas,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': False,
            'dry_run': dry_run
        }
        
        if not dry_run:
            try:
                # Update deployment
                deployment.spec.replicas = new_replicas
                self.apps_v1.patch_namespaced_deployment(
                    name=service,
                    namespace=namespace,
                    body=deployment
                )
                result['success'] = True
            except Exception as e:
                result['error'] = str(e)
        else:
            result['success'] = True
        
        return result
    
    def rollback(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback the remediation action.
        
        Args:
            execution_result: Result of the execute method
            
        Returns:
            Dictionary with rollback results
        """
        if execution_result.get('dry_run', False):
            return {
                'action': f"rollback_{self.name}",
                'service': execution_result.get('service'),
                'namespace': execution_result.get('namespace'),
                'success': True,
                'message': "No rollback needed for dry run",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        service = execution_result.get('service')
        namespace = execution_result.get('namespace', 'default')
        previous_replicas = execution_result.get('previous_replicas')
        
        # Execute the rollback
        result = {
            'action': f"rollback_{self.name}",
            'service': service,
            'namespace': namespace,
            'current_replicas': execution_result.get('new_replicas'),
            'rollback_replicas': previous_replicas,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': False
        }
        
        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=service,
                namespace=namespace
            )
            
            # Update deployment
            deployment.spec.replicas = previous_replicas
            self.apps_v1.patch_namespaced_deployment(
                name=service,
                namespace=namespace,
                body=deployment
            )
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result


class RestartPodAction(RemediationAction):
    """Action to restart a problematic pod."""
    
    def __init__(self):
        """Initialize the action."""
        super().__init__(
            name="restart_pod",
            description="Restart a problematic pod",
            severity="medium"
        )
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                raise RuntimeError("Could not configure Kubernetes client")
        
        self.core_v1 = client.CoreV1Api()
    
    def can_remediate(self, issue: Dict[str, Any]) -> bool:
        """
        Check if this action can remediate the given issue.
        
        Args:
            issue: Issue to remediate
            
        Returns:
            True if this action can remediate the issue, False otherwise
        """
        # Check if issue is related to a specific pod
        if issue.get('pod_name'):
            # Check if the pod exists
            try:
                pod_name = issue.get('pod_name')
                namespace = issue.get('namespace', 'default')
                
                # Try to get the pod
                self.core_v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=namespace
                )
                
                return True
            except client.exceptions.ApiException:
                return False
        
        return False
    
    def execute(self, issue: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the remediation action.
        
        Args:
            issue: Issue to remediate
            dry_run: If True, only simulate the action
            
        Returns:
            Dictionary with execution results
        """
        pod_name = issue.get('pod_name')
        namespace = issue.get('namespace', 'default')
        
        # Execute the restart
        result = {
            'action': self.name,
            'pod_name': pod_name,
            'namespace': namespace,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': False,
            'dry_run': dry_run
        }
        
        if not dry_run:
            try:
                # Delete the pod (it will be recreated by the controller)
                self.core_v1.delete_namespaced_pod(
                    name=pod_name,
                    namespace=namespace
                )
                result['success'] = True
            except Exception as e:
                result['error'] = str(e)
        else:
            result['success'] = True
        
        return result
    
    def rollback(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback the remediation action.
        
        Args:
            execution_result: Result of the execute method
            
        Returns:
            Dictionary with rollback results
        """
        # No rollback possible for pod restart
        return {
            'action': f"rollback_{self.name}",
            'pod_name': execution_result.get('pod_name'),
            'namespace': execution_result.get('namespace'),
            'success': True,
            'message': "No rollback possible for pod restart",
            'timestamp': datetime.datetime.now().isoformat()
        }


class CircuitBreakerAction(RemediationAction):
    """Action to enable circuit breaker for a failing dependency."""
    
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize the action.
        
        Args:
            api_url: URL of the circuit breaker API
            api_key: API key for authentication
        """
        super().__init__(
            name="circuit_breaker",
            description="Enable circuit breaker for a failing dependency",
            severity="high"
        )
        self.api_url = api_url
        self.api_key = api_key
    
    def can_remediate(self, issue: Dict[str, Any]) -> bool:
        """
        Check if this action can remediate the given issue.
        
        Args:
            issue: Issue to remediate
            
        Returns:
            True if this action can remediate the issue, False otherwise
        """
        # Check if issue is related to a dependency failure
        return (
            issue.get('metric_name') == 'dependency_error_rate' and
            issue.get('dependency') is not None
        )
    
    def execute(self, issue: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the remediation action.
        
        Args:
            issue: Issue to remediate
            dry_run: If True, only simulate the action
            
        Returns:
            Dictionary with execution results
        """
        service = issue.get('service')
        dependency = issue.get('dependency')
        
        # Execute the circuit breaker
        result = {
            'action': self.name,
            'service': service,
            'dependency': dependency,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': False,
            'dry_run': dry_run
        }
        
        if not dry_run:
            try:
                # Call circuit breaker API
                response = requests.post(
                    f"{self.api_url}/circuit-breaker",
                    headers={
                        'Authorization': f"Bearer {self.api_key}",
                        'Content-Type': 'application/json'
                    },
                    json={
                        'service': service,
                        'dependency': dependency,
                        'enabled': True,
                        'timeout_seconds': 300  # 5 minutes
                    }
                )
                
                response.raise_for_status()
                result['success'] = True
                result['timeout_seconds'] = 300
            except Exception as e:
                result['error'] = str(e)
        else:
            result['success'] = True
            result['timeout_seconds'] = 300
        
        return result
    
    def rollback(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback the remediation action.
        
        Args:
            execution_result: Result of the execute method
            
        Returns:
            Dictionary with rollback results
        """
        if execution_result.get('dry_run', False):
            return {
                'action': f"rollback_{self.name}",
                'service': execution_result.get('service'),
                'dependency': execution_result.get('dependency'),
                'success': True,
                'message': "No rollback needed for dry run",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        service = execution_result.get('service')
        dependency = execution_result.get('dependency')
        
        # Execute the rollback
        result = {
            'action': f"rollback_{self.name}",
            'service': service,
            'dependency': dependency,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': False
        }
        
        try:
            # Call circuit breaker API
            response = requests.post(
                f"{self.api_url}/circuit-breaker",
                headers={
                    'Authorization': f"Bearer {self.api_key}",
                    'Content-Type': 'application/json'
                },
                json={
                    'service': service,
                    'dependency': dependency,
                    'enabled': False
                }
            )
            
            response.raise_for_status()
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result


class AutoRemediation:
    """Automated remediation system."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the automated remediation system.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.actions = []
        self.approval_callbacks = {}
        self.execution_history = []
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("auto-remediation")
        
        # Initialize actions
        self._initialize_actions()
    
    def _initialize_actions(self) -> None:
        """Initialize remediation actions."""
        # Add scale up deployment action
        self.actions.append(ScaleUpDeploymentAction())
        
        # Add restart pod action
        self.actions.append(RestartPodAction())
        
        # Add circuit breaker action if configured
        if 'circuit_breaker' in self.config:
            self.actions.append(CircuitBreakerAction(
                api_url=self.config['circuit_breaker']['api_url'],
                api_key=self.config['circuit_breaker']['api_key']
            ))
    
    def register_approval_callback(self, severity: str, callback: Callable[[Dict[str, Any], RemediationAction], bool]) -> None:
        """
        Register a callback for approval of remediation actions.
        
        Args:
            severity: Severity level to register for
            callback: Callback function that returns True if approved, False otherwise
        """
        self.approval_callbacks[severity] = callback
    
    def remediate(self, issue: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Remediate an issue.
        
        Args:
            issue: Issue to remediate
            dry_run: If True, only simulate the action
            
        Returns:
            Dictionary with remediation results
        """
        # Find applicable actions
        applicable_actions = [
            action for action in self.actions
            if action.can_remediate(issue)
        ]
        
        if not applicable_actions:
            return {
                'issue': issue,
                'success': False,
                'message': "No applicable remediation actions found",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        # Sort actions by severity (prefer less severe actions)
        severity_order = {
            'low': 0,
            'medium': 1,
            'high': 2,
            'critical': 3
        }
        applicable_actions.sort(key=lambda a: severity_order.get(a.severity, 4))
        
        # Select the first applicable action
        selected_action = applicable_actions[0]
        
        # Check if approval is required
        if selected_action.requires_approval and not dry_run:
            # Get approval callback for this severity
            callback = self.approval_callbacks.get(selected_action.severity)
            
            if callback:
                # Call approval callback
                approved = callback(issue, selected_action)
                
                if not approved:
                    return {
                        'issue': issue,
                        'action': selected_action.name,
                        'success': False,
                        'message': "Remediation action not approved",
                        'timestamp': datetime.datetime.now().isoformat()
                    }
            else:
                # No approval callback, default to not approved
                return {
                    'issue': issue,
                    'action': selected_action.name,
                    'success': False,
                    'message': "Remediation action requires approval, but no approval callback registered",
                    'timestamp': datetime.datetime.now().isoformat()
                }
        
        # Execute the action
        self.logger.info(f"Executing remediation action {selected_action.name} for issue in service {issue.get('service')}")
        execution_result = selected_action.execute(issue, dry_run)
        
        # Record execution
        self.execution_history.append({
            'issue': issue,
            'action': selected_action.name,
            'result': execution_result,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        # Check if execution was successful
        if not execution_result.get('success', False):
            self.logger.error(f"Remediation action {selected_action.name} failed: {execution_result.get('error')}")
            return {
                'issue': issue,
                'action': selected_action.name,
                'success': False,
                'message': f"Remediation action failed: {execution_result.get('error')}",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        self.logger.info(f"Remediation action {selected_action.name} executed successfully")
        return {
            'issue': issue,
            'action': selected_action.name,
            'success': True,
            'execution_result': execution_result,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def rollback(self, remediation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback a remediation action.
        
        Args:
            remediation_result: Result of the remediate method
            
        Returns:
            Dictionary with rollback results
        """
        if not remediation_result.get('success', False):
            return {
                'success': False,
                'message': "Cannot rollback unsuccessful remediation",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        action_name = remediation_result.get('action')
        execution_result = remediation_result.get('execution_result')
        
        # Find the action
        action = next((a for a in self.actions if a.name == action_name), None)
        
        if not action:
            return {
                'success': False,
                'message': f"Action {action_name} not found",
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        # Execute rollback
        self.logger.info(f"Rolling back remediation action {action_name}")
        rollback_result = action.rollback(execution_result)
        
        # Record rollback
        self.execution_history.append({
            'action': f"rollback_{action_name}",
            'result': rollback_result,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        return rollback_result
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Get execution history.
        
        Returns:
            List of execution history entries
        """
        return self.execution_history
