"""
Root Cause Analysis Model for E-commerce Observability.

This module implements a sophisticated root cause analysis model that
identifies the underlying causes of anomalies in the e-commerce platform.

Key features:
- Causal inference to identify root causes
- Correlation analysis across services
- Trace analysis for distributed systems
- Topology-aware analysis
- Temporal pattern recognition
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
import networkx as nx
from typing import Dict, List, Tuple, Optional, Union, Any
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class RootCauseAnalyzer:
    """
    Root cause analysis model for e-commerce observability data.
    
    This class implements multiple techniques to identify the root causes
    of anomalies in the e-commerce platform.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the root cause analyzer.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "correlation_threshold": 0.7,
            "causality_threshold": 0.6,
            "max_causes": 5,
            "time_window": 300,  # 5 minutes in seconds
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            }
        }
        
        # Merge default config with provided config
        for key, default_value in self.default_config.items():
            if key not in self.config:
                self.config[key] = default_value
            elif isinstance(default_value, dict):
                for subkey, subvalue in default_value.items():
                    if subkey not in self.config[key]:
                        self.config[key][subkey] = subvalue
        
        # Initialize models and data structures
        self.service_graph = nx.DiGraph()
        self.correlation_matrix = None
        self.classifier = None
        self.scaler = None
        self.metric_importance = {}
        self.historical_incidents = []
    
    def build_service_graph(self, service_dependencies: List[Dict[str, str]]) -> None:
        """
        Build a directed graph of service dependencies.
        
        Args:
            service_dependencies: List of dictionaries with 'source' and 'target' keys
        """
        # Clear existing graph
        self.service_graph.clear()
        
        # Add nodes and edges
        for dependency in service_dependencies:
            source = dependency['source']
            target = dependency['target']
            
            # Add nodes if they don't exist
            if not self.service_graph.has_node(source):
                self.service_graph.add_node(source)
            
            if not self.service_graph.has_node(target):
                self.service_graph.add_node(target)
            
            # Add edge
            self.service_graph.add_edge(source, target)
    
    def compute_correlation_matrix(self, metrics_data: pd.DataFrame) -> None:
        """
        Compute correlation matrix between metrics.
        
        Args:
            metrics_data: DataFrame with metrics data
                Must have columns: timestamp, metric_name, value, service
        """
        # Pivot data to have metrics as columns
        pivot_data = metrics_data.pivot_table(
            index='timestamp',
            columns=['service', 'metric_name'],
            values='value'
        ).fillna(method='ffill')
        
        # Compute correlation matrix
        self.correlation_matrix = pivot_data.corr()
    
    def train_classifier(self, incidents_data: pd.DataFrame) -> None:
        """
        Train a classifier to predict root causes based on historical incidents.
        
        Args:
            incidents_data: DataFrame with historical incidents
                Must have columns: incident_id, timestamp, affected_service, root_cause, metrics
        """
        # Prepare training data
        X = []
        y = []
        
        for _, incident in incidents_data.iterrows():
            # Extract features from metrics
            features = self._extract_features(incident['metrics'])
            
            # Add to training data
            X.append(features)
            y.append(incident['root_cause'])
        
        # Convert to numpy arrays
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train classifier
        self.classifier = RandomForestClassifier(
            n_estimators=self.config['random_forest']['n_estimators'],
            max_depth=self.config['random_forest']['max_depth'],
            random_state=self.config['random_forest']['random_state']
        )
        self.classifier.fit(X_scaled, y)
        
        # Compute feature importance
        feature_names = list(incident['metrics'].keys())
        importances = self.classifier.feature_importances_
        
        # Store feature importance
        self.metric_importance = {
            feature: importance
            for feature, importance in zip(feature_names, importances)
        }
    
    def _extract_features(self, metrics: Dict[str, float]) -> List[float]:
        """
        Extract features from metrics dictionary.
        
        Args:
            metrics: Dictionary of metric values
            
        Returns:
            List of feature values
        """
        # Sort keys to ensure consistent order
        sorted_keys = sorted(metrics.keys())
        
        # Extract values
        return [metrics[key] for key in sorted_keys]
    
    def analyze_anomaly(self, anomaly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an anomaly to identify root causes.
        
        Args:
            anomaly_data: Dictionary with anomaly data
                Must have keys: timestamp, affected_service, metrics
                
        Returns:
            Dictionary with root cause analysis results
        """
        # Extract data
        timestamp = anomaly_data['timestamp']
        affected_service = anomaly_data['affected_service']
        metrics = anomaly_data['metrics']
        
        # Initialize results
        results = {
            'timestamp': timestamp,
            'affected_service': affected_service,
            'root_causes': [],
            'confidence': 0.0,
            'related_services': [],
            'contributing_metrics': []
        }
        
        # Apply different analysis techniques
        self._apply_correlation_analysis(metrics, results)
        self._apply_graph_analysis(affected_service, results)
        self._apply_classifier(metrics, results)
        
        # Sort root causes by confidence
        results['root_causes'] = sorted(
            results['root_causes'],
            key=lambda x: x['confidence'],
            reverse=True
        )
        
        # Limit number of root causes
        results['root_causes'] = results['root_causes'][:self.config['max_causes']]
        
        # Set overall confidence
        if results['root_causes']:
            results['confidence'] = results['root_causes'][0]['confidence']
        
        return results
    
    def _apply_correlation_analysis(self, metrics: Dict[str, float], results: Dict[str, Any]) -> None:
        """
        Apply correlation analysis to identify related metrics.
        
        Args:
            metrics: Dictionary of metric values
            results: Results dictionary to update
        """
        if self.correlation_matrix is None:
            return
        
        # Find highly correlated metrics
        for metric_name, value in metrics.items():
            if metric_name not in self.correlation_matrix:
                continue
            
            # Get correlations for this metric
            correlations = self.correlation_matrix[metric_name].abs().sort_values(ascending=False)
            
            # Filter by threshold
            high_correlations = correlations[correlations > self.config['correlation_threshold']]
            
            # Add to contributing metrics
            for correlated_metric, correlation in high_correlations.items():
                if correlated_metric != metric_name:
                    results['contributing_metrics'].append({
                        'metric': correlated_metric,
                        'correlation': float(correlation),
                        'value': metrics.get(correlated_metric, None)
                    })
    
    def _apply_graph_analysis(self, affected_service: str, results: Dict[str, Any]) -> None:
        """
        Apply graph analysis to identify related services.
        
        Args:
            affected_service: Name of the affected service
            results: Results dictionary to update
        """
        if not self.service_graph.has_node(affected_service):
            return
        
        # Get upstream services (potential causes)
        upstream_services = list(self.service_graph.predecessors(affected_service))
        
        # Get downstream services (potential effects)
        downstream_services = list(self.service_graph.successors(affected_service))
        
        # Add to related services
        for service in upstream_services:
            results['related_services'].append({
                'service': service,
                'relationship': 'upstream',
                'potential_cause': True
            })
            
            # Add as potential root cause
            results['root_causes'].append({
                'service': service,
                'type': 'dependency',
                'confidence': 0.6,
                'description': f"Upstream service {service} may be causing issues in {affected_service}"
            })
        
        for service in downstream_services:
            results['related_services'].append({
                'service': service,
                'relationship': 'downstream',
                'potential_cause': False
            })
    
    def _apply_classifier(self, metrics: Dict[str, float], results: Dict[str, Any]) -> None:
        """
        Apply classifier to predict root causes.
        
        Args:
            metrics: Dictionary of metric values
            results: Results dictionary to update
        """
        if self.classifier is None or self.scaler is None:
            return
        
        # Extract features
        features = self._extract_features(metrics)
        
        # Scale features
        features_scaled = self.scaler.transform([features])
        
        # Predict root cause
        root_cause = self.classifier.predict(features_scaled)[0]
        
        # Get prediction probability
        probabilities = self.classifier.predict_proba(features_scaled)[0]
        max_prob_idx = np.argmax(probabilities)
        confidence = probabilities[max_prob_idx]
        
        # Add to root causes
        results['root_causes'].append({
            'service': root_cause,
            'type': 'ml_prediction',
            'confidence': float(confidence),
            'description': f"ML model predicts {root_cause} as the root cause"
        })
        
        # Add important metrics
        for metric, importance in sorted(
            self.metric_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]:
            if metric in metrics:
                results['contributing_metrics'].append({
                    'metric': metric,
                    'importance': float(importance),
                    'value': metrics[metric]
                })
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save service graph
        nx.write_gpickle(self.service_graph, os.path.join(path, "service_graph.gpickle"))
        
        # Save correlation matrix
        if self.correlation_matrix is not None:
            self.correlation_matrix.to_pickle(os.path.join(path, "correlation_matrix.pkl"))
        
        # Save classifier
        if self.classifier is not None:
            with open(os.path.join(path, "classifier.pkl"), "wb") as f:
                pickle.dump(self.classifier, f)
        
        # Save scaler
        if self.scaler is not None:
            with open(os.path.join(path, "scaler.pkl"), "wb") as f:
                pickle.dump(self.scaler, f)
        
        # Save metric importance
        with open(os.path.join(path, "metric_importance.json"), "w") as f:
            json.dump(self.metric_importance, f)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "RootCauseAnalyzer":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded RootCauseAnalyzer instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        analyzer = cls(config)
        
        # Load service graph
        if os.path.exists(os.path.join(path, "service_graph.gpickle")):
            analyzer.service_graph = nx.read_gpickle(os.path.join(path, "service_graph.gpickle"))
        
        # Load correlation matrix
        if os.path.exists(os.path.join(path, "correlation_matrix.pkl")):
            analyzer.correlation_matrix = pd.read_pickle(os.path.join(path, "correlation_matrix.pkl"))
        
        # Load classifier
        if os.path.exists(os.path.join(path, "classifier.pkl")):
            with open(os.path.join(path, "classifier.pkl"), "rb") as f:
                analyzer.classifier = pickle.load(f)
        
        # Load scaler
        if os.path.exists(os.path.join(path, "scaler.pkl")):
            with open(os.path.join(path, "scaler.pkl"), "rb") as f:
                analyzer.scaler = pickle.load(f)
        
        # Load metric importance
        if os.path.exists(os.path.join(path, "metric_importance.json")):
            with open(os.path.join(path, "metric_importance.json"), "r") as f:
                analyzer.metric_importance = json.load(f)
        
        return analyzer
