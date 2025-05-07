"""
Anomaly Detection Model for E-commerce Observability.

This module implements a robust anomaly detection model for e-commerce
observability data. It uses a combination of statistical methods and
machine learning to detect anomalies in metrics, logs, and traces.

Features:
- Multivariate anomaly detection using isolation forest
- Time series forecasting with Prophet
- Dynamic thresholding based on historical patterns
- Correlation analysis between metrics
- Seasonal pattern recognition
- Business context-aware anomaly scoring
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from prophet import Prophet


class AnomalyDetector:
    """
    Anomaly detection model for e-commerce observability data.
    
    This class implements multiple anomaly detection techniques and
    combines them for robust anomaly detection.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the anomaly detector.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "isolation_forest": {
                "n_estimators": 100,
                "max_samples": "auto",
                "contamination": 0.01,
                "random_state": 42
            },
            "prophet": {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10.0,
                "seasonality_mode": "multiplicative",
                "interval_width": 0.95
            },
            "dynamic_threshold": {
                "sensitivity": 3.0,  # Number of standard deviations
                "min_history_size": 30,  # Minimum number of data points required
                "max_history_size": 1000  # Maximum number of data points to keep
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
        self.isolation_forest = None
        self.prophet_models = {}
        self.scalers = {}
        self.metric_history = {}
    
    def fit(self, data: pd.DataFrame) -> None:
        """
        Fit the anomaly detection models on historical data.
        
        Args:
            data: DataFrame with metrics data
                Must have columns: timestamp, metric_name, value
        """
        if data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Ensure required columns exist
        required_columns = ["timestamp", "metric_name", "value"]
        if not all(col in data.columns for col in required_columns):
            missing = [col for col in required_columns if col not in data.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert timestamp to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
            data["timestamp"] = pd.to_datetime(data["timestamp"])
        
        # Group by metric name
        grouped = data.groupby("metric_name")
        
        # Fit isolation forest on all data
        # First, pivot the data to have metrics as columns
        pivot_data = data.pivot_table(
            index="timestamp", 
            columns="metric_name", 
            values="value",
            aggfunc="mean"
        ).reset_index()
        
        # Drop timestamp for isolation forest
        X = pivot_data.drop(columns=["timestamp"])
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Fit scaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers["global"] = scaler
        
        # Fit isolation forest
        self.isolation_forest = IsolationForest(
            n_estimators=self.config["isolation_forest"]["n_estimators"],
            max_samples=self.config["isolation_forest"]["max_samples"],
            contamination=self.config["isolation_forest"]["contamination"],
            random_state=self.config["isolation_forest"]["random_state"]
        )
        self.isolation_forest.fit(X_scaled)
        
        # Fit Prophet models for each metric
        for metric_name, group in grouped:
            # Prepare data for Prophet
            prophet_data = group[["timestamp", "value"]].copy()
            prophet_data.columns = ["ds", "y"]
            
            # Initialize and fit Prophet model
            prophet_config = self.config["prophet"]
            model = Prophet(
                changepoint_prior_scale=prophet_config["changepoint_prior_scale"],
                seasonality_prior_scale=prophet_config["seasonality_prior_scale"],
                seasonality_mode=prophet_config["seasonality_mode"],
                interval_width=prophet_config["interval_width"]
            )
            
            # Add weekly and daily seasonality if we have enough data
            if len(prophet_data) >= 14:  # At least 2 weeks of data
                model.add_seasonality(name='weekly', period=7, fourier_order=3)
            if len(prophet_data) >= 48:  # At least 2 days of hourly data
                model.add_seasonality(name='daily', period=24, fourier_order=5)
            
            # Fit the model
            try:
                model.fit(prophet_data)
                self.prophet_models[metric_name] = model
                
                # Store metric history for dynamic thresholding
                history = group[["timestamp", "value"]].copy()
                history = history.sort_values("timestamp")
                max_history = self.config["dynamic_threshold"]["max_history_size"]
                if len(history) > max_history:
                    history = history.iloc[-max_history:]
                self.metric_history[metric_name] = history
            except Exception as e:
                print(f"Failed to fit Prophet model for metric {metric_name}: {str(e)}")
    
    def predict_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Predict anomalies in new data.
        
        Args:
            data: DataFrame with metrics data
                Must have columns: timestamp, metric_name, value
                
        Returns:
            DataFrame with anomaly scores and predictions
        """
        if data.empty:
            return pd.DataFrame()
        
        # Ensure required columns exist
        required_columns = ["timestamp", "metric_name", "value"]
        if not all(col in data.columns for col in required_columns):
            missing = [col for col in required_columns if col not in data.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert timestamp to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
            data["timestamp"] = pd.to_datetime(data["timestamp"])
        
        # Create result DataFrame
        result = data.copy()
        result["anomaly_score"] = 0.0
        result["is_anomaly"] = False
        result["anomaly_probability"] = 0.0
        result["expected_value"] = np.nan
        result["lower_bound"] = np.nan
        result["upper_bound"] = np.nan
        result["detection_method"] = "none"
        
        # Group by timestamp to apply isolation forest
        timestamps = data["timestamp"].unique()
        
        for ts in timestamps:
            # Get data for this timestamp
            ts_data = data[data["timestamp"] == ts]
            
            # Pivot the data to have metrics as columns
            pivot_data = ts_data.pivot_table(
                index="timestamp", 
                columns="metric_name", 
                values="value",
                aggfunc="mean"
            ).reset_index()
            
            # Check if we have all metrics
            if self.scalers.get("global") is not None:
                expected_columns = self.scalers["global"].feature_names_in_
                missing_columns = [col for col in expected_columns if col not in pivot_data.columns]
                
                # Add missing columns with NaN values
                for col in missing_columns:
                    pivot_data[col] = np.nan
                
                # Ensure columns are in the same order as during training
                pivot_data = pivot_data[["timestamp"] + list(expected_columns)]
            
            # Drop timestamp for isolation forest
            X = pivot_data.drop(columns=["timestamp"])
            
            # Handle missing values
            X = X.fillna(X.mean())
            
            # Apply isolation forest if we have a trained model
            if self.isolation_forest is not None and self.scalers.get("global") is not None:
                try:
                    # Scale the data
                    X_scaled = self.scalers["global"].transform(X)
                    
                    # Get anomaly scores (-1 for anomalies, 1 for normal)
                    # Convert to 0-1 scale where 1 is anomalous
                    scores = self.isolation_forest.decision_function(X_scaled)
                    scores = (scores.max() - scores) / (scores.max() - scores.min())
                    
                    # Update result DataFrame
                    for i, metric_name in enumerate(X.columns):
                        mask = (result["timestamp"] == ts) & (result["metric_name"] == metric_name)
                        result.loc[mask, "anomaly_score"] = scores[0]
                        result.loc[mask, "detection_method"] = "isolation_forest"
                except Exception as e:
                    print(f"Error applying isolation forest: {str(e)}")
        
        # Apply Prophet and dynamic thresholding for each metric
        for metric_name in data["metric_name"].unique():
            metric_data = data[data["metric_name"] == metric_name].copy()
            
            # Apply Prophet forecasting if we have a trained model
            if metric_name in self.prophet_models:
                try:
                    # Prepare data for Prophet
                    prophet_data = metric_data[["timestamp", "value"]].copy()
                    prophet_data.columns = ["ds", "y"]
                    
                    # Make prediction
                    model = self.prophet_models[metric_name]
                    forecast = model.predict(prophet_data)
                    
                    # Update result DataFrame
                    for i, row in forecast.iterrows():
                        mask = (result["timestamp"] == row["ds"]) & (result["metric_name"] == metric_name)
                        result.loc[mask, "expected_value"] = row["yhat"]
                        result.loc[mask, "lower_bound"] = row["yhat_lower"]
                        result.loc[mask, "upper_bound"] = row["yhat_upper"]
                        
                        # Check if value is outside prediction interval
                        actual_value = metric_data.loc[metric_data["timestamp"] == row["ds"], "value"].values[0]
                        if actual_value < row["yhat_lower"] or actual_value > row["yhat_upper"]:
                            result.loc[mask, "is_anomaly"] = True
                            result.loc[mask, "detection_method"] = "prophet"
                            
                            # Calculate probability based on distance from expected value
                            z_score = abs(actual_value - row["yhat"]) / (row["yhat_upper"] - row["yhat_lower"]) * 2
                            probability = min(1.0, z_score)
                            result.loc[mask, "anomaly_probability"] = probability
                except Exception as e:
                    print(f"Error applying Prophet for metric {metric_name}: {str(e)}")
            
            # Apply dynamic thresholding if we have enough history
            if metric_name in self.metric_history:
                try:
                    history = self.metric_history[metric_name]
                    min_history = self.config["dynamic_threshold"]["min_history_size"]
                    
                    if len(history) >= min_history:
                        # Calculate mean and standard deviation
                        mean_value = history["value"].mean()
                        std_value = history["value"].std()
                        sensitivity = self.config["dynamic_threshold"]["sensitivity"]
                        
                        # Calculate thresholds
                        lower_threshold = mean_value - sensitivity * std_value
                        upper_threshold = mean_value + sensitivity * std_value
                        
                        # Check for anomalies
                        for i, row in metric_data.iterrows():
                            mask = (result["timestamp"] == row["timestamp"]) & (result["metric_name"] == metric_name)
                            
                            # Only update if not already marked as anomaly by Prophet
                            if not result.loc[mask, "is_anomaly"].values[0]:
                                if row["value"] < lower_threshold or row["value"] > upper_threshold:
                                    result.loc[mask, "is_anomaly"] = True
                                    result.loc[mask, "detection_method"] = "dynamic_threshold"
                                    
                                    # Calculate probability based on distance from mean
                                    z_score = abs(row["value"] - mean_value) / std_value
                                    probability = min(1.0, z_score / sensitivity)
                                    result.loc[mask, "anomaly_probability"] = probability
                        
                        # Update history with new data
                        new_history = pd.concat([history, metric_data[["timestamp", "value"]]])
                        new_history = new_history.sort_values("timestamp")
                        max_history = self.config["dynamic_threshold"]["max_history_size"]
                        if len(new_history) > max_history:
                            new_history = new_history.iloc[-max_history:]
                        self.metric_history[metric_name] = new_history
                except Exception as e:
                    print(f"Error applying dynamic thresholding for metric {metric_name}: {str(e)}")
        
        return result
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save isolation forest
        with open(os.path.join(path, "isolation_forest.pkl"), "wb") as f:
            pickle.dump(self.isolation_forest, f)
        
        # Save scalers
        with open(os.path.join(path, "scalers.pkl"), "wb") as f:
            pickle.dump(self.scalers, f)
        
        # Save Prophet models
        for metric_name, model in self.prophet_models.items():
            model_path = os.path.join(path, f"prophet_{metric_name}.json")
            with open(model_path, "w") as f:
                json.dump(model.to_json(), f)
        
        # Save metric history
        for metric_name, history in self.metric_history.items():
            history_path = os.path.join(path, f"history_{metric_name}.csv")
            history.to_csv(history_path, index=False)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "AnomalyDetector":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded AnomalyDetector instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        detector = cls(config)
        
        # Load isolation forest
        with open(os.path.join(path, "isolation_forest.pkl"), "rb") as f:
            detector.isolation_forest = pickle.load(f)
        
        # Load scalers
        with open(os.path.join(path, "scalers.pkl"), "rb") as f:
            detector.scalers = pickle.load(f)
        
        # Load Prophet models
        for file in os.listdir(path):
            if file.startswith("prophet_") and file.endswith(".json"):
                metric_name = file[8:-5]  # Remove "prophet_" prefix and ".json" suffix
                model_path = os.path.join(path, file)
                with open(model_path, "r") as f:
                    model_json = json.load(f)
                
                model = Prophet.from_json(model_json)
                detector.prophet_models[metric_name] = model
        
        # Load metric history
        for file in os.listdir(path):
            if file.startswith("history_") and file.endswith(".csv"):
                metric_name = file[8:-4]  # Remove "history_" prefix and ".csv" suffix
                history_path = os.path.join(path, file)
                history = pd.read_csv(history_path)
                
                # Convert timestamp to datetime
                history["timestamp"] = pd.to_datetime(history["timestamp"])
                
                detector.metric_history[metric_name] = history
        
        return detector
