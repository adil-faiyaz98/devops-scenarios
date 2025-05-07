"""
Intrusion Detection Model for E-commerce Platform.

This module implements a sophisticated intrusion detection system that
identifies potential security threats and attacks in the e-commerce platform.

Key features:
- Network traffic anomaly detection
- User behavior analysis
- API request pattern monitoring
- Known attack signature detection
- Zero-day attack detection using unsupervised learning
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN


class IntrusionDetector:
    """
    Intrusion detection model for e-commerce platform.
    
    This class implements multiple techniques to identify potential
    security threats and attacks in the e-commerce platform.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the intrusion detector.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "anomaly_threshold": 0.95,  # Threshold for anomaly detection
            "max_request_rate": 100,  # Maximum requests per minute per IP
            "max_failed_logins": 5,  # Maximum failed login attempts
            "isolation_forest": {
                "n_estimators": 100,
                "contamination": 0.01,
                "random_state": 42
            },
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            },
            "dbscan": {
                "eps": 0.5,
                "min_samples": 5
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
        
        # Initialize models
        self.network_anomaly_model = None  # Isolation Forest for network traffic
        self.user_behavior_model = None  # Random Forest for user behavior
        self.api_pattern_model = None  # DBSCAN for API request patterns
        self.network_scaler = None  # Scaler for network features
        self.user_scaler = None  # Scaler for user features
        self.api_scaler = None  # Scaler for API features
        
        # Initialize attack signatures
        self.attack_signatures = {}
        
        # Initialize IP blacklist
        self.ip_blacklist = set()
        
        # Initialize user risk scores
        self.user_risk_scores = {}
    
    def fit_network_model(self, network_data: pd.DataFrame) -> None:
        """
        Fit network traffic anomaly detection model.
        
        Args:
            network_data: DataFrame with network traffic data
                Should include features like request_count, bytes_sent, bytes_received,
                response_time, error_rate, etc.
        """
        if network_data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Preprocess data
        X, feature_names = self._preprocess_network_data(network_data)
        
        # Fit scaler
        self.network_scaler = StandardScaler()
        X_scaled = self.network_scaler.fit_transform(X)
        
        # Fit Isolation Forest
        iso_config = self.config["isolation_forest"]
        self.network_anomaly_model = IsolationForest(
            n_estimators=iso_config["n_estimators"],
            contamination=iso_config["contamination"],
            random_state=iso_config["random_state"]
        )
        self.network_anomaly_model.fit(X_scaled)
    
    def fit_user_model(self, user_data: pd.DataFrame, labels: pd.Series) -> None:
        """
        Fit user behavior anomaly detection model.
        
        Args:
            user_data: DataFrame with user behavior data
                Should include features like login_count, page_views, session_duration,
                failed_logins, unusual_activity_flags, etc.
            labels: Series with intrusion labels (1 for intrusion, 0 for normal)
        """
        if user_data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Preprocess data
        X, feature_names = self._preprocess_user_data(user_data)
        
        # Fit scaler
        self.user_scaler = StandardScaler()
        X_scaled = self.user_scaler.fit_transform(X)
        
        # Fit Random Forest
        rf_config = self.config["random_forest"]
        self.user_behavior_model = RandomForestClassifier(
            n_estimators=rf_config["n_estimators"],
            max_depth=rf_config["max_depth"],
            random_state=rf_config["random_state"]
        )
        self.user_behavior_model.fit(X_scaled, labels)
    
    def fit_api_model(self, api_data: pd.DataFrame) -> None:
        """
        Fit API request pattern anomaly detection model.
        
        Args:
            api_data: DataFrame with API request data
                Should include features like endpoint, method, params_count,
                response_time, status_code, etc.
        """
        if api_data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Preprocess data
        X, feature_names = self._preprocess_api_data(api_data)
        
        # Fit scaler
        self.api_scaler = StandardScaler()
        X_scaled = self.api_scaler.fit_transform(X)
        
        # Fit DBSCAN
        dbscan_config = self.config["dbscan"]
        self.api_pattern_model = DBSCAN(
            eps=dbscan_config["eps"],
            min_samples=dbscan_config["min_samples"]
        )
        self.api_pattern_model.fit(X_scaled)
    
    def add_attack_signatures(self, signatures: Dict[str, Dict[str, Any]]) -> None:
        """
        Add known attack signatures.
        
        Args:
            signatures: Dictionary mapping signature names to signature patterns
        """
        self.attack_signatures.update(signatures)
    
    def add_to_ip_blacklist(self, ip_addresses: List[str]) -> None:
        """
        Add IP addresses to blacklist.
        
        Args:
            ip_addresses: List of IP addresses to blacklist
        """
        self.ip_blacklist.update(ip_addresses)
    
    def update_user_risk_score(self, user_id: str, risk_score: float) -> None:
        """
        Update risk score for a user.
        
        Args:
            user_id: User ID
            risk_score: Risk score (0-1)
        """
        self.user_risk_scores[user_id] = risk_score
    
    def _preprocess_network_data(self, network_data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Preprocess network traffic data.
        
        Args:
            network_data: DataFrame with network traffic data
            
        Returns:
            Tuple of preprocessed features and feature names
        """
        # Copy data to avoid modifying the original
        data = network_data.copy()
        
        # Handle missing values
        numeric_columns = data.select_dtypes(include=np.number).columns
        data[numeric_columns] = data[numeric_columns].fillna(0)
        
        # Select features for model
        feature_columns = [
            "request_count", "bytes_sent", "bytes_received", "response_time",
            "error_rate", "distinct_endpoints", "distinct_user_agents",
            "distinct_referrers", "avg_request_interval", "max_request_interval",
            "min_request_interval", "std_request_interval"
        ]
        
        # Filter to only include columns that exist in the data
        feature_columns = [col for col in feature_columns if col in data.columns]
        
        # Extract features
        X = data[feature_columns].values
        
        return X, feature_columns
    
    def _preprocess_user_data(self, user_data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Preprocess user behavior data.
        
        Args:
            user_data: DataFrame with user behavior data
            
        Returns:
            Tuple of preprocessed features and feature names
        """
        # Copy data to avoid modifying the original
        data = user_data.copy()
        
        # Handle missing values
        numeric_columns = data.select_dtypes(include=np.number).columns
        data[numeric_columns] = data[numeric_columns].fillna(0)
        
        # Select features for model
        feature_columns = [
            "login_count", "page_views", "session_duration", "failed_logins",
            "password_changes", "profile_changes", "unusual_activity_flags",
            "distinct_ip_addresses", "distinct_devices", "distinct_browsers",
            "avg_session_interval", "max_session_interval", "min_session_interval",
            "std_session_interval", "login_time_deviation", "inactive_days"
        ]
        
        # Filter to only include columns that exist in the data
        feature_columns = [col for col in feature_columns if col in data.columns]
        
        # Extract features
        X = data[feature_columns].values
        
        return X, feature_columns
    
    def _preprocess_api_data(self, api_data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Preprocess API request data.
        
        Args:
            api_data: DataFrame with API request data
            
        Returns:
            Tuple of preprocessed features and feature names
        """
        # Copy data to avoid modifying the original
        data = api_data.copy()
        
        # Handle missing values
        numeric_columns = data.select_dtypes(include=np.number).columns
        data[numeric_columns] = data[numeric_columns].fillna(0)
        
        # One-hot encode categorical columns
        categorical_columns = ["endpoint", "method", "status_code"]
        for col in categorical_columns:
            if col in data.columns:
                dummies = pd.get_dummies(data[col], prefix=col, drop_first=True)
                data = pd.concat([data, dummies], axis=1)
                data = data.drop(columns=[col])
        
        # Select features for model (exclude non-feature columns)
        exclude_columns = ["timestamp", "request_id", "user_id", "ip_address"]
        feature_columns = [col for col in data.columns if col not in exclude_columns]
        
        # Extract features
        X = data[feature_columns].values
        
        return X, feature_columns
    
    def detect_network_anomalies(self, network_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect anomalies in network traffic.
        
        Args:
            network_data: DataFrame with network traffic data
            
        Returns:
            List of detected anomalies
        """
        if self.network_anomaly_model is None or self.network_scaler is None:
            return []
        
        # Preprocess data
        X, feature_names = self._preprocess_network_data(network_data)
        
        # Scale features
        X_scaled = self.network_scaler.transform(X)
        
        # Predict anomalies
        scores = self.network_anomaly_model.decision_function(X_scaled)
        predictions = self.network_anomaly_model.predict(X_scaled)
        
        # Find anomalies
        anomalies = []
        for i, (score, pred) in enumerate(zip(scores, predictions)):
            if pred == -1:  # Anomaly
                anomaly_score = 1.0 - (score + 0.5) / 2  # Convert to 0-1 scale
                
                if anomaly_score >= self.config["anomaly_threshold"]:
                    anomaly = {
                        "type": "network_anomaly",
                        "source_ip": network_data.iloc[i].get("ip_address", "unknown"),
                        "timestamp": network_data.iloc[i].get("timestamp", None),
                        "anomaly_score": float(anomaly_score),
                        "details": {
                            "request_count": network_data.iloc[i].get("request_count", 0),
                            "bytes_sent": network_data.iloc[i].get("bytes_sent", 0),
                            "bytes_received": network_data.iloc[i].get("bytes_received", 0),
                            "error_rate": network_data.iloc[i].get("error_rate", 0)
                        }
                    }
                    
                    # Check for rate limiting
                    if network_data.iloc[i].get("request_count", 0) > self.config["max_request_rate"]:
                        anomaly["attack_type"] = "rate_limiting_violation"
                        anomaly["severity"] = "high"
                    else:
                        anomaly["attack_type"] = "unusual_traffic_pattern"
                        anomaly["severity"] = "medium"
                    
                    # Check if IP is blacklisted
                    if network_data.iloc[i].get("ip_address") in self.ip_blacklist:
                        anomaly["attack_type"] = "blacklisted_ip"
                        anomaly["severity"] = "critical"
                    
                    anomalies.append(anomaly)
        
        return anomalies
    
    def detect_user_anomalies(self, user_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect anomalies in user behavior.
        
        Args:
            user_data: DataFrame with user behavior data
            
        Returns:
            List of detected anomalies
        """
        if self.user_behavior_model is None or self.user_scaler is None:
            return []
        
        # Preprocess data
        X, feature_names = self._preprocess_user_data(user_data)
        
        # Scale features
        X_scaled = self.user_scaler.transform(X)
        
        # Predict anomalies
        probas = self.user_behavior_model.predict_proba(X_scaled)
        
        # Find anomalies
        anomalies = []
        for i, proba in enumerate(probas):
            intrusion_probability = proba[1]  # Probability of class 1 (intrusion)
            
            if intrusion_probability >= self.config["anomaly_threshold"]:
                anomaly = {
                    "type": "user_anomaly",
                    "user_id": user_data.iloc[i].get("user_id", "unknown"),
                    "timestamp": user_data.iloc[i].get("timestamp", None),
                    "anomaly_score": float(intrusion_probability),
                    "details": {
                        "login_count": user_data.iloc[i].get("login_count", 0),
                        "failed_logins": user_data.iloc[i].get("failed_logins", 0),
                        "unusual_activity_flags": user_data.iloc[i].get("unusual_activity_flags", 0)
                    }
                }
                
                # Check for brute force attack
                if user_data.iloc[i].get("failed_logins", 0) > self.config["max_failed_logins"]:
                    anomaly["attack_type"] = "brute_force_attempt"
                    anomaly["severity"] = "high"
                else:
                    anomaly["attack_type"] = "unusual_user_behavior"
                    anomaly["severity"] = "medium"
                
                # Check user risk score
                user_id = user_data.iloc[i].get("user_id")
                if user_id in self.user_risk_scores and self.user_risk_scores[user_id] > 0.8:
                    anomaly["severity"] = "critical"
                
                anomalies.append(anomaly)
        
        return anomalies
    
    def detect_api_anomalies(self, api_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect anomalies in API request patterns.
        
        Args:
            api_data: DataFrame with API request data
            
        Returns:
            List of detected anomalies
        """
        if self.api_pattern_model is None or self.api_scaler is None:
            return []
        
        # Preprocess data
        X, feature_names = self._preprocess_api_data(api_data)
        
        # Scale features
        X_scaled = self.api_scaler.transform(X)
        
        # Predict clusters
        labels = self.api_pattern_model.fit_predict(X_scaled)
        
        # Find anomalies (points labeled as noise: -1)
        anomalies = []
        for i, label in enumerate(labels):
            if label == -1:  # Noise point (anomaly)
                anomaly = {
                    "type": "api_anomaly",
                    "source_ip": api_data.iloc[i].get("ip_address", "unknown"),
                    "user_id": api_data.iloc[i].get("user_id", "unknown"),
                    "endpoint": api_data.iloc[i].get("endpoint", "unknown"),
                    "method": api_data.iloc[i].get("method", "unknown"),
                    "timestamp": api_data.iloc[i].get("timestamp", None),
                    "anomaly_score": 0.9,  # DBSCAN doesn't provide scores, use fixed value
                    "details": {
                        "params_count": api_data.iloc[i].get("params_count", 0),
                        "response_time": api_data.iloc[i].get("response_time", 0),
                        "status_code": api_data.iloc[i].get("status_code", 0)
                    }
                }
                
                # Determine attack type and severity
                endpoint = api_data.iloc[i].get("endpoint", "")
                method = api_data.iloc[i].get("method", "")
                
                if "login" in endpoint.lower() or "auth" in endpoint.lower():
                    anomaly["attack_type"] = "authentication_anomaly"
                    anomaly["severity"] = "high"
                elif "admin" in endpoint.lower():
                    anomaly["attack_type"] = "admin_access_anomaly"
                    anomaly["severity"] = "critical"
                else:
                    anomaly["attack_type"] = "unusual_api_pattern"
                    anomaly["severity"] = "medium"
                
                anomalies.append(anomaly)
        
        return anomalies
    
    def detect_signature_attacks(self, request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect known attack signatures in request data.
        
        Args:
            request_data: Dictionary with request data
            
        Returns:
            List of detected attacks
        """
        detected_attacks = []
        
        for signature_name, signature_pattern in self.attack_signatures.items():
            matched = True
            
            # Check if all pattern conditions match
            for key, pattern in signature_pattern.items():
                if key not in request_data:
                    matched = False
                    break
                
                value = request_data[key]
                
                if isinstance(pattern, str):
                    # String pattern (exact match or contains)
                    if pattern.startswith("*") and pattern.endswith("*"):
                        # Contains
                        if pattern[1:-1] not in str(value):
                            matched = False
                            break
                    else:
                        # Exact match
                        if str(value) != pattern:
                            matched = False
                            break
                elif isinstance(pattern, dict):
                    # Dictionary pattern (min/max)
                    if "min" in pattern and value < pattern["min"]:
                        matched = False
                        break
                    if "max" in pattern and value > pattern["max"]:
                        matched = False
                        break
                elif isinstance(pattern, list):
                    # List pattern (one of)
                    if value not in pattern:
                        matched = False
                        break
            
            if matched:
                attack = {
                    "type": "signature_attack",
                    "attack_name": signature_name,
                    "source_ip": request_data.get("ip_address", "unknown"),
                    "user_id": request_data.get("user_id", "unknown"),
                    "timestamp": request_data.get("timestamp", None),
                    "severity": signature_pattern.get("severity", "high"),
                    "details": {
                        "endpoint": request_data.get("endpoint", "unknown"),
                        "method": request_data.get("method", "unknown"),
                        "params": request_data.get("params", {})
                    }
                }
                
                detected_attacks.append(attack)
        
        return detected_attacks
    
    def detect_intrusions(self, data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Detect intrusions using all available models.
        
        Args:
            data: Dictionary with different types of data
                Should include keys: network, user, api, requests
            
        Returns:
            List of detected intrusions
        """
        all_intrusions = []
        
        # Detect network anomalies
        if "network" in data and not data["network"].empty:
            network_anomalies = self.detect_network_anomalies(data["network"])
            all_intrusions.extend(network_anomalies)
        
        # Detect user anomalies
        if "user" in data and not data["user"].empty:
            user_anomalies = self.detect_user_anomalies(data["user"])
            all_intrusions.extend(user_anomalies)
        
        # Detect API anomalies
        if "api" in data and not data["api"].empty:
            api_anomalies = self.detect_api_anomalies(data["api"])
            all_intrusions.extend(api_anomalies)
        
        # Detect signature attacks
        if "requests" in data:
            for request in data["requests"]:
                signature_attacks = self.detect_signature_attacks(request)
                all_intrusions.extend(signature_attacks)
        
        return all_intrusions
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save network anomaly model
        if self.network_anomaly_model is not None:
            with open(os.path.join(path, "network_anomaly_model.pkl"), "wb") as f:
                pickle.dump(self.network_anomaly_model, f)
        
        # Save user behavior model
        if self.user_behavior_model is not None:
            with open(os.path.join(path, "user_behavior_model.pkl"), "wb") as f:
                pickle.dump(self.user_behavior_model, f)
        
        # Save API pattern model
        if self.api_pattern_model is not None:
            with open(os.path.join(path, "api_pattern_model.pkl"), "wb") as f:
                pickle.dump(self.api_pattern_model, f)
        
        # Save scalers
        if self.network_scaler is not None:
            with open(os.path.join(path, "network_scaler.pkl"), "wb") as f:
                pickle.dump(self.network_scaler, f)
        
        if self.user_scaler is not None:
            with open(os.path.join(path, "user_scaler.pkl"), "wb") as f:
                pickle.dump(self.user_scaler, f)
        
        if self.api_scaler is not None:
            with open(os.path.join(path, "api_scaler.pkl"), "wb") as f:
                pickle.dump(self.api_scaler, f)
        
        # Save attack signatures
        with open(os.path.join(path, "attack_signatures.json"), "w") as f:
            json.dump(self.attack_signatures, f)
        
        # Save IP blacklist
        with open(os.path.join(path, "ip_blacklist.json"), "w") as f:
            json.dump(list(self.ip_blacklist), f)
        
        # Save user risk scores
        with open(os.path.join(path, "user_risk_scores.json"), "w") as f:
            json.dump(self.user_risk_scores, f)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "IntrusionDetector":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded IntrusionDetector instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        detector = cls(config)
        
        # Load network anomaly model
        if os.path.exists(os.path.join(path, "network_anomaly_model.pkl")):
            with open(os.path.join(path, "network_anomaly_model.pkl"), "rb") as f:
                detector.network_anomaly_model = pickle.load(f)
        
        # Load user behavior model
        if os.path.exists(os.path.join(path, "user_behavior_model.pkl")):
            with open(os.path.join(path, "user_behavior_model.pkl"), "rb") as f:
                detector.user_behavior_model = pickle.load(f)
        
        # Load API pattern model
        if os.path.exists(os.path.join(path, "api_pattern_model.pkl")):
            with open(os.path.join(path, "api_pattern_model.pkl"), "rb") as f:
                detector.api_pattern_model = pickle.load(f)
        
        # Load scalers
        if os.path.exists(os.path.join(path, "network_scaler.pkl")):
            with open(os.path.join(path, "network_scaler.pkl"), "rb") as f:
                detector.network_scaler = pickle.load(f)
        
        if os.path.exists(os.path.join(path, "user_scaler.pkl")):
            with open(os.path.join(path, "user_scaler.pkl"), "rb") as f:
                detector.user_scaler = pickle.load(f)
        
        if os.path.exists(os.path.join(path, "api_scaler.pkl")):
            with open(os.path.join(path, "api_scaler.pkl"), "rb") as f:
                detector.api_scaler = pickle.load(f)
        
        # Load attack signatures
        if os.path.exists(os.path.join(path, "attack_signatures.json")):
            with open(os.path.join(path, "attack_signatures.json"), "r") as f:
                detector.attack_signatures = json.load(f)
        
        # Load IP blacklist
        if os.path.exists(os.path.join(path, "ip_blacklist.json")):
            with open(os.path.join(path, "ip_blacklist.json"), "r") as f:
                detector.ip_blacklist = set(json.load(f))
        
        # Load user risk scores
        if os.path.exists(os.path.join(path, "user_risk_scores.json")):
            with open(os.path.join(path, "user_risk_scores.json"), "r") as f:
                detector.user_risk_scores = json.load(f)
        
        return detector
