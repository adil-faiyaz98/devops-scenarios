"""
Fraud Detection Model for E-commerce Platform.

This module implements a sophisticated fraud detection model that
identifies potentially fraudulent transactions in the e-commerce platform.

Key features:
- Real-time transaction scoring
- User behavior analysis
- Device and location fingerprinting
- Pattern recognition for known fraud schemes
- Adaptive thresholds based on user history
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


class FraudDetector:
    """
    Fraud detection model for e-commerce transactions.
    
    This class implements multiple techniques to identify potentially
    fraudulent transactions in the e-commerce platform.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the fraud detector.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "risk_threshold": 0.7,  # Risk score threshold for flagging transactions
            "high_risk_threshold": 0.9,  # Threshold for high-risk transactions
            "user_history_window": 30,  # Days of user history to consider
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            },
            "xgboost": {
                "n_estimators": 100,
                "max_depth": 5,
                "learning_rate": 0.1,
                "random_state": 42
            },
            "isolation_forest": {
                "n_estimators": 100,
                "contamination": 0.01,
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
        
        # Initialize models
        self.random_forest = None
        self.xgboost = None
        self.isolation_forest = None
        self.scaler = None
        
        # Initialize user history
        self.user_history = {}
        
        # Initialize feature importance
        self.feature_importance = {}
    
    def fit(self, transactions: pd.DataFrame, labels: Optional[pd.Series] = None) -> None:
        """
        Fit the fraud detection models on historical data.
        
        Args:
            transactions: DataFrame with transaction data
            labels: Series with fraud labels (1 for fraud, 0 for legitimate)
        """
        if transactions.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Preprocess data
        X, feature_names = self._preprocess_data(transactions)
        
        # Fit scaler
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit supervised models if labels are provided
        if labels is not None:
            # Fit Random Forest
            rf_config = self.config["random_forest"]
            self.random_forest = RandomForestClassifier(
                n_estimators=rf_config["n_estimators"],
                max_depth=rf_config["max_depth"],
                random_state=rf_config["random_state"]
            )
            self.random_forest.fit(X_scaled, labels)
            
            # Fit XGBoost
            xgb_config = self.config["xgboost"]
            self.xgboost = XGBClassifier(
                n_estimators=xgb_config["n_estimators"],
                max_depth=xgb_config["max_depth"],
                learning_rate=xgb_config["learning_rate"],
                random_state=xgb_config["random_state"]
            )
            self.xgboost.fit(X_scaled, labels)
            
            # Store feature importance
            if self.random_forest is not None:
                rf_importance = self.random_forest.feature_importances_
                self.feature_importance["random_forest"] = {
                    feature: float(importance)
                    for feature, importance in zip(feature_names, rf_importance)
                }
            
            if self.xgboost is not None:
                xgb_importance = self.xgboost.feature_importances_
                self.feature_importance["xgboost"] = {
                    feature: float(importance)
                    for feature, importance in zip(feature_names, xgb_importance)
                }
        
        # Fit Isolation Forest (unsupervised)
        iso_config = self.config["isolation_forest"]
        self.isolation_forest = IsolationForest(
            n_estimators=iso_config["n_estimators"],
            contamination=iso_config["contamination"],
            random_state=iso_config["random_state"]
        )
        self.isolation_forest.fit(X_scaled)
        
        # Build user history
        self._build_user_history(transactions)
    
    def _preprocess_data(self, transactions: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Preprocess transaction data for model training or prediction.
        
        Args:
            transactions: DataFrame with transaction data
            
        Returns:
            Tuple of preprocessed features and feature names
        """
        # Copy data to avoid modifying the original
        data = transactions.copy()
        
        # Handle missing values
        data = data.fillna({
            "amount": 0,
            "user_age": data["user_age"].median(),
            "account_age_days": data["account_age_days"].median(),
            "days_since_last_purchase": data["days_since_last_purchase"].median(),
            "purchase_count_30d": 0,
            "avg_purchase_value_30d": 0,
            "max_purchase_value_30d": 0,
            "min_purchase_value_30d": 0,
            "std_purchase_value_30d": 0,
            "purchase_frequency_30d": 0,
            "shipping_billing_address_match": False,
            "shipping_address_change": False,
            "billing_address_change": False,
            "email_domain_match": True,
            "phone_number_match": True,
            "ip_address_risk_score": 0.5,
            "device_risk_score": 0.5,
            "browser_risk_score": 0.5,
            "time_of_day_risk_score": 0.5,
            "day_of_week_risk_score": 0.5,
            "payment_method_risk_score": 0.5,
            "product_category_risk_score": 0.5,
            "shipping_method_risk_score": 0.5,
            "coupon_code_risk_score": 0.5,
            "cart_abandonment_count": 0,
            "failed_payment_attempts": 0,
            "checkout_time_seconds": data["checkout_time_seconds"].median(),
            "page_views_count": data["page_views_count"].median(),
            "device_is_mobile": False,
            "device_is_new": False,
            "ip_address_is_proxy": False,
            "ip_address_country_match": True,
            "email_is_free": False,
            "email_is_disposable": False,
            "card_bin_risk_score": 0.5,
            "card_issuer_risk_score": 0.5,
            "card_type_risk_score": 0.5
        })
        
        # Convert boolean columns to integers
        bool_columns = [
            "shipping_billing_address_match", "shipping_address_change",
            "billing_address_change", "email_domain_match", "phone_number_match",
            "device_is_mobile", "device_is_new", "ip_address_is_proxy",
            "ip_address_country_match", "email_is_free", "email_is_disposable"
        ]
        
        for col in bool_columns:
            if col in data.columns:
                data[col] = data[col].astype(int)
        
        # Select features for model
        feature_columns = [
            "amount", "user_age", "account_age_days", "days_since_last_purchase",
            "purchase_count_30d", "avg_purchase_value_30d", "max_purchase_value_30d",
            "min_purchase_value_30d", "std_purchase_value_30d", "purchase_frequency_30d",
            "shipping_billing_address_match", "shipping_address_change",
            "billing_address_change", "email_domain_match", "phone_number_match",
            "ip_address_risk_score", "device_risk_score", "browser_risk_score",
            "time_of_day_risk_score", "day_of_week_risk_score", "payment_method_risk_score",
            "product_category_risk_score", "shipping_method_risk_score",
            "coupon_code_risk_score", "cart_abandonment_count", "failed_payment_attempts",
            "checkout_time_seconds", "page_views_count", "device_is_mobile",
            "device_is_new", "ip_address_is_proxy", "ip_address_country_match",
            "email_is_free", "email_is_disposable", "card_bin_risk_score",
            "card_issuer_risk_score", "card_type_risk_score"
        ]
        
        # Filter to only include columns that exist in the data
        feature_columns = [col for col in feature_columns if col in data.columns]
        
        # Extract features
        X = data[feature_columns].values
        
        return X, feature_columns
    
    def _build_user_history(self, transactions: pd.DataFrame) -> None:
        """
        Build user history from transaction data.
        
        Args:
            transactions: DataFrame with transaction data
        """
        if "user_id" not in transactions.columns:
            return
        
        # Group by user_id
        grouped = transactions.groupby("user_id")
        
        # Build user history
        for user_id, group in grouped:
            # Sort by timestamp
            if "timestamp" in group.columns:
                group = group.sort_values("timestamp")
            
            # Store user history
            self.user_history[user_id] = {
                "transactions": group.to_dict("records"),
                "transaction_count": len(group),
                "avg_amount": group["amount"].mean() if "amount" in group.columns else 0,
                "max_amount": group["amount"].max() if "amount" in group.columns else 0,
                "std_amount": group["amount"].std() if "amount" in group.columns else 0,
                "last_transaction_timestamp": group["timestamp"].max() if "timestamp" in group.columns else None
            }
    
    def predict(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict fraud risk for a transaction.
        
        Args:
            transaction: Dictionary with transaction data
            
        Returns:
            Dictionary with prediction results
        """
        # Convert transaction to DataFrame
        transaction_df = pd.DataFrame([transaction])
        
        # Preprocess data
        X, _ = self._preprocess_data(transaction_df)
        
        # Scale features
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        # Initialize results
        results = {
            "transaction_id": transaction.get("transaction_id", "unknown"),
            "user_id": transaction.get("user_id", "unknown"),
            "amount": transaction.get("amount", 0),
            "timestamp": transaction.get("timestamp", None),
            "risk_score": 0.0,
            "is_fraud": False,
            "risk_level": "low",
            "model_scores": {},
            "risk_factors": [],
            "user_risk_level": "low"
        }
        
        # Get model predictions
        if self.random_forest is not None:
            rf_score = self.random_forest.predict_proba(X_scaled)[0, 1]
            results["model_scores"]["random_forest"] = float(rf_score)
        
        if self.xgboost is not None:
            xgb_score = self.xgboost.predict_proba(X_scaled)[0, 1]
            results["model_scores"]["xgboost"] = float(xgb_score)
        
        if self.isolation_forest is not None:
            # Convert anomaly score to probability-like score
            iso_score = 1.0 - (self.isolation_forest.decision_function(X_scaled)[0] + 0.5) / 2
            results["model_scores"]["isolation_forest"] = float(iso_score)
        
        # Calculate overall risk score (weighted average of model scores)
        model_weights = {
            "random_forest": 0.4,
            "xgboost": 0.4,
            "isolation_forest": 0.2
        }
        
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for model, score in results["model_scores"].items():
            weight = model_weights.get(model, 0.0)
            weighted_sum += score * weight
            weight_sum += weight
        
        if weight_sum > 0:
            results["risk_score"] = weighted_sum / weight_sum
        
        # Adjust risk score based on user history
        user_id = transaction.get("user_id")
        if user_id in self.user_history:
            user_history = self.user_history[user_id]
            
            # Calculate user risk level
            if user_history["transaction_count"] > 10:
                # Established user with good history
                results["user_risk_level"] = "low"
                results["risk_score"] *= 0.8  # Reduce risk score
            elif user_history["transaction_count"] < 3:
                # New user
                results["user_risk_level"] = "medium"
                results["risk_score"] = min(results["risk_score"] * 1.2, 1.0)  # Increase risk score
            
            # Check for unusual amount
            if transaction.get("amount", 0) > user_history["max_amount"] * 2:
                results["risk_factors"].append("unusual_amount")
                results["risk_score"] = min(results["risk_score"] * 1.3, 1.0)
        else:
            # Unknown user
            results["user_risk_level"] = "high"
            results["risk_score"] = min(results["risk_score"] * 1.5, 1.0)
            results["risk_factors"].append("unknown_user")
        
        # Check for other risk factors
        if transaction.get("shipping_billing_address_match") is False:
            results["risk_factors"].append("address_mismatch")
        
        if transaction.get("ip_address_country_match") is False:
            results["risk_factors"].append("ip_country_mismatch")
        
        if transaction.get("email_is_disposable") is True:
            results["risk_factors"].append("disposable_email")
        
        if transaction.get("device_is_new") is True:
            results["risk_factors"].append("new_device")
        
        if transaction.get("failed_payment_attempts", 0) > 1:
            results["risk_factors"].append("multiple_payment_attempts")
        
        # Determine fraud flag and risk level
        if results["risk_score"] >= self.config["high_risk_threshold"]:
            results["is_fraud"] = True
            results["risk_level"] = "high"
        elif results["risk_score"] >= self.config["risk_threshold"]:
            results["is_fraud"] = True
            results["risk_level"] = "medium"
        else:
            results["is_fraud"] = False
            results["risk_level"] = "low"
        
        return results
    
    def update_user_history(self, transaction: Dict[str, Any], is_fraud: bool) -> None:
        """
        Update user history with a new transaction.
        
        Args:
            transaction: Transaction data
            is_fraud: Whether the transaction was fraudulent
        """
        user_id = transaction.get("user_id")
        if not user_id:
            return
        
        # Initialize user history if not exists
        if user_id not in self.user_history:
            self.user_history[user_id] = {
                "transactions": [],
                "transaction_count": 0,
                "avg_amount": 0,
                "max_amount": 0,
                "std_amount": 0,
                "last_transaction_timestamp": None
            }
        
        # Skip if transaction is fraudulent
        if is_fraud:
            return
        
        # Add transaction to history
        self.user_history[user_id]["transactions"].append(transaction)
        self.user_history[user_id]["transaction_count"] += 1
        
        # Update statistics
        amounts = [t.get("amount", 0) for t in self.user_history[user_id]["transactions"]]
        self.user_history[user_id]["avg_amount"] = np.mean(amounts)
        self.user_history[user_id]["max_amount"] = np.max(amounts)
        self.user_history[user_id]["std_amount"] = np.std(amounts)
        
        # Update last transaction timestamp
        timestamp = transaction.get("timestamp")
        if timestamp:
            self.user_history[user_id]["last_transaction_timestamp"] = timestamp
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save Random Forest
        if self.random_forest is not None:
            with open(os.path.join(path, "random_forest.pkl"), "wb") as f:
                pickle.dump(self.random_forest, f)
        
        # Save XGBoost
        if self.xgboost is not None:
            self.xgboost.save_model(os.path.join(path, "xgboost.json"))
        
        # Save Isolation Forest
        if self.isolation_forest is not None:
            with open(os.path.join(path, "isolation_forest.pkl"), "wb") as f:
                pickle.dump(self.isolation_forest, f)
        
        # Save scaler
        if self.scaler is not None:
            with open(os.path.join(path, "scaler.pkl"), "wb") as f:
                pickle.dump(self.scaler, f)
        
        # Save feature importance
        with open(os.path.join(path, "feature_importance.json"), "w") as f:
            json.dump(self.feature_importance, f)
        
        # Save user history (limited to avoid large files)
        user_history_summary = {}
        for user_id, history in self.user_history.items():
            user_history_summary[user_id] = {
                "transaction_count": history["transaction_count"],
                "avg_amount": history["avg_amount"],
                "max_amount": history["max_amount"],
                "std_amount": history["std_amount"],
                "last_transaction_timestamp": history["last_transaction_timestamp"]
            }
        
        with open(os.path.join(path, "user_history.json"), "w") as f:
            json.dump(user_history_summary, f)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "FraudDetector":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded FraudDetector instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        detector = cls(config)
        
        # Load Random Forest
        if os.path.exists(os.path.join(path, "random_forest.pkl")):
            with open(os.path.join(path, "random_forest.pkl"), "rb") as f:
                detector.random_forest = pickle.load(f)
        
        # Load XGBoost
        if os.path.exists(os.path.join(path, "xgboost.json")):
            detector.xgboost = XGBClassifier()
            detector.xgboost.load_model(os.path.join(path, "xgboost.json"))
        
        # Load Isolation Forest
        if os.path.exists(os.path.join(path, "isolation_forest.pkl")):
            with open(os.path.join(path, "isolation_forest.pkl"), "rb") as f:
                detector.isolation_forest = pickle.load(f)
        
        # Load scaler
        if os.path.exists(os.path.join(path, "scaler.pkl")):
            with open(os.path.join(path, "scaler.pkl"), "rb") as f:
                detector.scaler = pickle.load(f)
        
        # Load feature importance
        if os.path.exists(os.path.join(path, "feature_importance.json")):
            with open(os.path.join(path, "feature_importance.json"), "r") as f:
                detector.feature_importance = json.load(f)
        
        # Load user history
        if os.path.exists(os.path.join(path, "user_history.json")):
            with open(os.path.join(path, "user_history.json"), "r") as f:
                detector.user_history = json.load(f)
        
        return detector
