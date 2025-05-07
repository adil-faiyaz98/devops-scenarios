"""
ML Model Integration for E-commerce Observability Pipeline.

This module integrates all ML models used in the observability pipeline,
providing a unified interface for model management, training, and inference.

Key features:
- Centralized model management
- Unified training and inference interfaces
- Model versioning and tracking
- Model performance monitoring
- Automated model retraining
"""

import os
import json
import logging
import datetime
import threading
import time
from typing import Dict, List, Any, Optional, Union, Callable

from ml.models.anomaly_detector import AnomalyDetector
from ml.models.root_cause_analyzer import RootCauseAnalyzer
from ml.models.predictive_alerting import PredictiveAlerting
from ml.models.fraud_detector import FraudDetector
from ml.models.inventory_optimizer import InventoryOptimizer
from ml.models.intrusion_detector import IntrusionDetector

from automation.alerting.alert_integration import AlertIntegration


class ModelRegistry:
    """Registry for ML models."""
    
    def __init__(self, base_path: str):
        """
        Initialize the model registry.
        
        Args:
            base_path: Base path for model storage
        """
        self.base_path = base_path
        self.models = {}
        self.model_versions = {}
        self.model_metadata = {}
        
        # Create base directory if it doesn't exist
        os.makedirs(base_path, exist_ok=True)
        
        # Initialize logger
        self.logger = logging.getLogger("model-registry")
    
    def register_model(self, model_name: str, model: Any, version: str = "latest") -> None:
        """
        Register a model in the registry.
        
        Args:
            model_name: Name of the model
            model: Model instance
            version: Model version
        """
        self.models[model_name] = model
        
        # Update version information
        if model_name not in self.model_versions:
            self.model_versions[model_name] = []
        
        if version not in self.model_versions[model_name]:
            self.model_versions[model_name].append(version)
        
        # Update metadata
        if model_name not in self.model_metadata:
            self.model_metadata[model_name] = {}
        
        self.model_metadata[model_name][version] = {
            "registered_at": datetime.datetime.now().isoformat(),
            "model_type": type(model).__name__
        }
        
        self.logger.info(f"Registered model {model_name} version {version}")
    
    def get_model(self, model_name: str, version: str = "latest") -> Optional[Any]:
        """
        Get a model from the registry.
        
        Args:
            model_name: Name of the model
            version: Model version
            
        Returns:
            Model instance or None if not found
        """
        if model_name not in self.models:
            self.logger.warning(f"Model {model_name} not found in registry")
            return None
        
        if version == "latest" and model_name in self.models:
            return self.models[model_name]
        
        # Load specific version from disk
        model_path = os.path.join(self.base_path, model_name, version)
        if not os.path.exists(model_path):
            self.logger.warning(f"Model {model_name} version {version} not found on disk")
            return None
        
        # Load model based on type
        model_type = self.model_metadata[model_name][version]["model_type"]
        
        if model_type == "AnomalyDetector":
            model = AnomalyDetector.load(model_path)
        elif model_type == "RootCauseAnalyzer":
            model = RootCauseAnalyzer.load(model_path)
        elif model_type == "PredictiveAlerting":
            model = PredictiveAlerting.load(model_path)
        elif model_type == "FraudDetector":
            model = FraudDetector.load(model_path)
        elif model_type == "InventoryOptimizer":
            model = InventoryOptimizer.load(model_path)
        elif model_type == "IntrusionDetector":
            model = IntrusionDetector.load(model_path)
        else:
            self.logger.error(f"Unknown model type: {model_type}")
            return None
        
        return model
    
    def save_model(self, model_name: str, version: str = "latest") -> bool:
        """
        Save a model to disk.
        
        Args:
            model_name: Name of the model
            version: Model version
            
        Returns:
            True if successful, False otherwise
        """
        if model_name not in self.models:
            self.logger.warning(f"Model {model_name} not found in registry")
            return False
        
        model = self.models[model_name]
        
        # Create model directory
        model_path = os.path.join(self.base_path, model_name, version)
        os.makedirs(model_path, exist_ok=True)
        
        # Save model
        try:
            model.save(model_path)
            
            # Save metadata
            metadata_path = os.path.join(model_path, "metadata.json")
            with open(metadata_path, "w") as f:
                json.dump(self.model_metadata[model_name][version], f)
            
            self.logger.info(f"Saved model {model_name} version {version} to {model_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save model {model_name} version {version}: {str(e)}")
            return False
    
    def load_model(self, model_name: str, version: str = "latest") -> Optional[Any]:
        """
        Load a model from disk.
        
        Args:
            model_name: Name of the model
            version: Model version
            
        Returns:
            Model instance or None if not found
        """
        # Determine model path
        if version == "latest":
            # Find latest version
            model_dir = os.path.join(self.base_path, model_name)
            if not os.path.exists(model_dir):
                self.logger.warning(f"Model directory for {model_name} not found")
                return None
            
            versions = [v for v in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, v))]
            if not versions:
                self.logger.warning(f"No versions found for model {model_name}")
                return None
            
            # Sort versions (assuming semantic versioning or timestamp-based versioning)
            versions.sort()
            version = versions[-1]
        
        model_path = os.path.join(self.base_path, model_name, version)
        
        # Check if model exists
        if not os.path.exists(model_path):
            self.logger.warning(f"Model {model_name} version {version} not found on disk")
            return None
        
        # Load metadata
        metadata_path = os.path.join(model_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            # Update registry metadata
            if model_name not in self.model_metadata:
                self.model_metadata[model_name] = {}
            
            self.model_metadata[model_name][version] = metadata
            
            # Update version information
            if model_name not in self.model_versions:
                self.model_versions[model_name] = []
            
            if version not in self.model_versions[model_name]:
                self.model_versions[model_name].append(version)
        
        # Load model based on type
        model_type = metadata.get("model_type", "")
        
        try:
            if model_type == "AnomalyDetector":
                model = AnomalyDetector.load(model_path)
            elif model_type == "RootCauseAnalyzer":
                model = RootCauseAnalyzer.load(model_path)
            elif model_type == "PredictiveAlerting":
                model = PredictiveAlerting.load(model_path)
            elif model_type == "FraudDetector":
                model = FraudDetector.load(model_path)
            elif model_type == "InventoryOptimizer":
                model = InventoryOptimizer.load(model_path)
            elif model_type == "IntrusionDetector":
                model = IntrusionDetector.load(model_path)
            else:
                self.logger.error(f"Unknown model type: {model_type}")
                return None
            
            # Register model
            self.register_model(model_name, model, version)
            
            self.logger.info(f"Loaded model {model_name} version {version} from {model_path}")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load model {model_name} version {version}: {str(e)}")
            return None
    
    def list_models(self) -> Dict[str, List[str]]:
        """
        List all models in the registry.
        
        Returns:
            Dictionary mapping model names to lists of versions
        """
        return self.model_versions
    
    def get_model_metadata(self, model_name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """
        Get metadata for a model.
        
        Args:
            model_name: Name of the model
            version: Model version
            
        Returns:
            Model metadata or None if not found
        """
        if model_name not in self.model_metadata:
            return None
        
        if version == "latest":
            # Find latest version
            versions = list(self.model_metadata[model_name].keys())
            if not versions:
                return None
            
            # Sort versions (assuming semantic versioning or timestamp-based versioning)
            versions.sort()
            version = versions[-1]
        
        if version not in self.model_metadata[model_name]:
            return None
        
        return self.model_metadata[model_name][version]


class MLIntegration:
    """Integration for all ML models in the observability pipeline."""
    
    def __init__(self, config_path: str, alert_config_path: str):
        """
        Initialize the ML integration.
        
        Args:
            config_path: Path to ML configuration file
            alert_config_path: Path to alert configuration file
        """
        # Load configuration
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        # Initialize model registry
        self.registry = ModelRegistry(self.config.get("model_base_path", "models"))
        
        # Initialize alert integration
        self.alert_integration = AlertIntegration(alert_config_path)
        
        # Initialize logger
        self.logger = logging.getLogger("ml-integration")
        
        # Initialize models
        self._initialize_models()
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitor_models, daemon=True)
        self.monitoring_thread.start()
    
    def _initialize_models(self) -> None:
        """Initialize ML models."""
        # Load models from disk or create new ones
        self._initialize_anomaly_detector()
        self._initialize_root_cause_analyzer()
        self._initialize_predictive_alerting()
        self._initialize_fraud_detector()
        self._initialize_inventory_optimizer()
        self._initialize_intrusion_detector()
    
    def _initialize_anomaly_detector(self) -> None:
        """Initialize anomaly detector model."""
        model_name = "anomaly_detector"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("anomaly_detector", {})
            model = AnomalyDetector(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _initialize_root_cause_analyzer(self) -> None:
        """Initialize root cause analyzer model."""
        model_name = "root_cause_analyzer"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("root_cause_analyzer", {})
            model = RootCauseAnalyzer(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _initialize_predictive_alerting(self) -> None:
        """Initialize predictive alerting model."""
        model_name = "predictive_alerting"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("predictive_alerting", {})
            model = PredictiveAlerting(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _initialize_fraud_detector(self) -> None:
        """Initialize fraud detector model."""
        model_name = "fraud_detector"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("fraud_detector", {})
            model = FraudDetector(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _initialize_inventory_optimizer(self) -> None:
        """Initialize inventory optimizer model."""
        model_name = "inventory_optimizer"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("inventory_optimizer", {})
            model = InventoryOptimizer(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _initialize_intrusion_detector(self) -> None:
        """Initialize intrusion detector model."""
        model_name = "intrusion_detector"
        
        # Try to load from disk
        model = self.registry.load_model(model_name)
        
        if model is None:
            # Create new model
            model_config = self.config.get("intrusion_detector", {})
            model = IntrusionDetector(model_config)
            self.registry.register_model(model_name, model)
            self.registry.save_model(model_name)
    
    def _monitor_models(self) -> None:
        """Monitor models for performance and trigger retraining if needed."""
        while True:
            # Sleep for monitoring interval
            monitoring_interval = self.config.get("monitoring_interval_seconds", 3600)
            time.sleep(monitoring_interval)
            
            # Check model performance
            self._check_model_performance()
    
    def _check_model_performance(self) -> None:
        """Check model performance and trigger retraining if needed."""
        # This would be implemented based on specific performance metrics
        # For now, just log that we're checking
        self.logger.info("Checking model performance")
    
    def detect_anomalies(self, metrics_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in metrics data.
        
        Args:
            metrics_data: Dictionary with metrics data
            
        Returns:
            List of detected anomalies
        """
        model = self.registry.get_model("anomaly_detector")
        if model is None:
            self.logger.error("Anomaly detector model not found")
            return []
        
        # Detect anomalies
        anomalies = model.detect_anomalies(metrics_data)
        
        # Send alerts for anomalies
        for anomaly in anomalies:
            self.alert_integration.send_anomaly_alert(anomaly)
        
        return anomalies
    
    def analyze_root_cause(self, anomaly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze root cause of an anomaly.
        
        Args:
            anomaly_data: Dictionary with anomaly data
            
        Returns:
            Dictionary with root cause analysis results
        """
        model = self.registry.get_model("root_cause_analyzer")
        if model is None:
            self.logger.error("Root cause analyzer model not found")
            return {"success": False, "error": "Model not found"}
        
        # Analyze root cause
        return model.analyze_anomaly(anomaly_data)
    
    def predict_issues(self, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Predict potential issues.
        
        Args:
            current_data: Dictionary with current metrics data
            
        Returns:
            List of predicted issues
        """
        model = self.registry.get_model("predictive_alerting")
        if model is None:
            self.logger.error("Predictive alerting model not found")
            return []
        
        # Predict issues
        predictions = model.predict_issues(current_data)
        
        # Send alerts for predictions
        for prediction in predictions:
            self.alert_integration.send_predictive_alert(prediction)
        
        return predictions
    
    def detect_fraud(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect fraud in a transaction.
        
        Args:
            transaction: Dictionary with transaction data
            
        Returns:
            Dictionary with fraud detection results
        """
        model = self.registry.get_model("fraud_detector")
        if model is None:
            self.logger.error("Fraud detector model not found")
            return {"success": False, "error": "Model not found"}
        
        # Detect fraud
        result = model.predict(transaction)
        
        # Send alert if fraud is detected
        if result.get("is_fraud", False):
            self.alert_integration.send_fraud_alert(result)
        
        return result
    
    def optimize_inventory(self, product_id: str) -> Dict[str, Any]:
        """
        Get inventory recommendations for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with inventory recommendations
        """
        model = self.registry.get_model("inventory_optimizer")
        if model is None:
            self.logger.error("Inventory optimizer model not found")
            return {"success": False, "error": "Model not found"}
        
        # Get inventory recommendations
        result = model.get_inventory_recommendations(product_id)
        
        # Send alert if reorder is needed
        if result.get("success", False) and result.get("reorder_needed", False):
            self.alert_integration.send_inventory_alert(result)
        
        return result
    
    def detect_intrusions(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect intrusions in security data.
        
        Args:
            data: Dictionary with security data
            
        Returns:
            List of detected intrusions
        """
        model = self.registry.get_model("intrusion_detector")
        if model is None:
            self.logger.error("Intrusion detector model not found")
            return []
        
        # Detect intrusions
        intrusions = model.detect_intrusions(data)
        
        # Send alerts for intrusions
        for intrusion in intrusions:
            self.alert_integration.send_intrusion_alert(intrusion)
        
        return intrusions
    
    def train_model(self, model_name: str, training_data: Dict[str, Any]) -> bool:
        """
        Train a model with new data.
        
        Args:
            model_name: Name of the model to train
            training_data: Dictionary with training data
            
        Returns:
            True if training was successful, False otherwise
        """
        model = self.registry.get_model(model_name)
        if model is None:
            self.logger.error(f"Model {model_name} not found")
            return False
        
        try:
            # Train model based on type
            if model_name == "anomaly_detector":
                model.fit(training_data.get("metrics", []))
            elif model_name == "root_cause_analyzer":
                if "service_dependencies" in training_data:
                    model.build_service_graph(training_data["service_dependencies"])
                if "metrics_data" in training_data:
                    model.compute_correlation_matrix(training_data["metrics_data"])
                if "incidents_data" in training_data:
                    model.train_classifier(training_data["incidents_data"])
            elif model_name == "predictive_alerting":
                if "metrics_data" in training_data:
                    model.fit_forecasting_models(training_data["metrics_data"])
                    model.fit_anomaly_detection_model(training_data["metrics_data"])
            elif model_name == "fraud_detector":
                model.fit(
                    training_data.get("transactions", []),
                    training_data.get("labels", None)
                )
            elif model_name == "inventory_optimizer":
                if "sales_data" in training_data:
                    model.fit_demand_models(training_data["sales_data"])
                if "order_data" in training_data:
                    model.fit_lead_time_model(training_data["order_data"])
                if "product_data" in training_data:
                    model.set_product_data(training_data["product_data"])
            elif model_name == "intrusion_detector":
                if "network_data" in training_data:
                    model.fit_network_model(training_data["network_data"])
                if "user_data" in training_data and "labels" in training_data:
                    model.fit_user_model(training_data["user_data"], training_data["labels"])
                if "api_data" in training_data:
                    model.fit_api_model(training_data["api_data"])
                if "attack_signatures" in training_data:
                    model.add_attack_signatures(training_data["attack_signatures"])
            
            # Create new version
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            version = f"v_{timestamp}"
            
            # Register and save new version
            self.registry.register_model(model_name, model, version)
            self.registry.save_model(model_name, version)
            
            self.logger.info(f"Successfully trained model {model_name} version {version}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to train model {model_name}: {str(e)}")
            return False
