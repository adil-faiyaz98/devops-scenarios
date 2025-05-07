"""
Alert Integration for the AI-driven Observability Pipeline.

This module integrates the alert manager with various ML models and
monitoring systems to generate and send alerts based on detected issues.
"""

import os
import yaml
import json
import time
import logging
import threading
import datetime
from typing import Dict, List, Any, Optional
from string import Template

from automation.alerting.alert_manager import AlertManager, Alert, AlertSeverity


class AlertTemplate:
    """Template for generating alerts."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize alert template.
        
        Args:
            name: Template name
            config: Template configuration
        """
        self.name = name
        self.title_template = Template(config["title"])
        self.message_template = Template(config["message"])
        self.severity = AlertSeverity(config["severity"])
        self.tags = config.get("tags", [])
    
    def create_alert(self, source: str, context: Dict[str, Any]) -> Alert:
        """
        Create an alert from the template.
        
        Args:
            source: Alert source
            context: Context variables for the template
            
        Returns:
            Alert instance
        """
        # Substitute variables in title and message
        title = self.title_template.safe_substitute(context)
        message = self.message_template.safe_substitute(context)
        
        # Create alert
        return Alert(
            title=title,
            message=message,
            severity=self.severity,
            source=source,
            details=context,
            tags=self.tags
        )


class AlertIntegration:
    """Integration between ML models and the alert manager."""
    
    def __init__(self, config_path: str):
        """
        Initialize alert integration.
        
        Args:
            config_path: Path to alert configuration file
        """
        # Load configuration
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        # Initialize alert manager
        self.alert_manager = AlertManager(self.config)
        
        # Initialize templates
        self.templates = {}
        for name, template_config in self.config.get("templates", {}).items():
            self.templates[name] = AlertTemplate(name, template_config)
        
        # Initialize logger
        self.logger = logging.getLogger("alert-integration")
    
    def send_anomaly_alert(self, anomaly: Dict[str, Any]) -> bool:
        """
        Send an alert for a detected anomaly.
        
        Args:
            anomaly: Anomaly data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("anomaly")
        if not template:
            self.logger.error("Anomaly alert template not found")
            return False
        
        # Create context
        context = {
            "service": anomaly.get("service", "unknown"),
            "metric": anomaly.get("metric_name", "unknown"),
            "value": anomaly.get("value", 0),
            "expected_value": anomaly.get("expected_value", 0),
            "lower_bound": anomaly.get("lower_bound", 0),
            "upper_bound": anomaly.get("upper_bound", 0),
            "anomaly_score": anomaly.get("anomaly_score", 0),
            "timestamp": anomaly.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["service"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_predictive_alert(self, prediction: Dict[str, Any]) -> bool:
        """
        Send an alert for a predicted issue.
        
        Args:
            prediction: Prediction data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("predictive")
        if not template:
            self.logger.error("Predictive alert template not found")
            return False
        
        # Create context
        context = {
            "service": prediction.get("service", "unknown"),
            "metric": prediction.get("metric_name", "unknown"),
            "time_until": prediction.get("time_until_hours", 0),
            "confidence": int(prediction.get("confidence", 0) * 100),
            "severity": prediction.get("severity", "unknown"),
            "predicted_value": prediction.get("predicted_value", 0),
            "current_value": prediction.get("current_value", 0),
            "timestamp": prediction.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["service"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_service_health_alert(self, service_health: Dict[str, Any]) -> bool:
        """
        Send an alert for a service health issue.
        
        Args:
            service_health: Service health data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("service_health")
        if not template:
            self.logger.error("Service health alert template not found")
            return False
        
        # Create context
        context = {
            "service": service_health.get("service", "unknown"),
            "status": service_health.get("status", "unknown"),
            "message": service_health.get("message", ""),
            "timestamp": service_health.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["service"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_resource_alert(self, resource_data: Dict[str, Any]) -> bool:
        """
        Send an alert for a resource utilization issue.
        
        Args:
            resource_data: Resource utilization data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("resource_utilization")
        if not template:
            self.logger.error("Resource utilization alert template not found")
            return False
        
        # Create context
        context = {
            "service": resource_data.get("service", "unknown"),
            "resource": resource_data.get("resource", "unknown"),
            "value": resource_data.get("value", 0),
            "threshold": resource_data.get("threshold", 0),
            "timestamp": resource_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["service"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_security_alert(self, security_data: Dict[str, Any]) -> bool:
        """
        Send an alert for a security issue.
        
        Args:
            security_data: Security issue data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("security")
        if not template:
            self.logger.error("Security alert template not found")
            return False
        
        # Create context
        context = {
            "type": security_data.get("type", "unknown"),
            "source": security_data.get("source", "unknown"),
            "details": security_data.get("details", ""),
            "timestamp": security_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["source"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_dependency_alert(self, dependency_data: Dict[str, Any]) -> bool:
        """
        Send an alert for a dependency failure.
        
        Args:
            dependency_data: Dependency failure data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("dependency_failure")
        if not template:
            self.logger.error("Dependency failure alert template not found")
            return False
        
        # Create context
        context = {
            "service": dependency_data.get("service", "unknown"),
            "dependency": dependency_data.get("dependency", "unknown"),
            "error_rate": dependency_data.get("error_rate", 0),
            "message": dependency_data.get("message", ""),
            "timestamp": dependency_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert(context["service"], context)
        return self.alert_manager.send_alert(alert)
    
    def send_fraud_alert(self, fraud_data: Dict[str, Any]) -> bool:
        """
        Send an alert for a potential fraud detection.
        
        Args:
            fraud_data: Fraud detection data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("fraud")
        if not template:
            self.logger.error("Fraud alert template not found")
            return False
        
        # Create context
        context = {
            "transaction_id": fraud_data.get("transaction_id", "unknown"),
            "risk_score": fraud_data.get("risk_score", 0),
            "user_id": fraud_data.get("user_id", "unknown"),
            "amount": fraud_data.get("amount", 0),
            "timestamp": fraud_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert("fraud-detection", context)
        return self.alert_manager.send_alert(alert)
    
    def send_inventory_alert(self, inventory_data: Dict[str, Any]) -> bool:
        """
        Send an alert for an inventory issue.
        
        Args:
            inventory_data: Inventory data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("inventory")
        if not template:
            self.logger.error("Inventory alert template not found")
            return False
        
        # Create context
        context = {
            "product": inventory_data.get("product", "unknown"),
            "level": inventory_data.get("level", 0),
            "threshold": inventory_data.get("threshold", 0),
            "warehouse": inventory_data.get("warehouse", "unknown"),
            "timestamp": inventory_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert("inventory-management", context)
        return self.alert_manager.send_alert(alert)
    
    def send_intrusion_alert(self, intrusion_data: Dict[str, Any]) -> bool:
        """
        Send an alert for an intrusion detection.
        
        Args:
            intrusion_data: Intrusion detection data
            
        Returns:
            True if the alert was sent successfully, False otherwise
        """
        # Get template
        template = self.templates.get("intrusion")
        if not template:
            self.logger.error("Intrusion alert template not found")
            return False
        
        # Create context
        context = {
            "source_ip": intrusion_data.get("source_ip", "unknown"),
            "attack_type": intrusion_data.get("attack_type", "unknown"),
            "target": intrusion_data.get("target", "unknown"),
            "severity": intrusion_data.get("severity", "unknown"),
            "timestamp": intrusion_data.get("timestamp", datetime.datetime.now().isoformat())
        }
        
        # Create and send alert
        alert = template.create_alert("intrusion-detection", context)
        return self.alert_manager.send_alert(alert)
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts as dictionaries
        """
        return self.alert_manager.get_alert_history(limit)
