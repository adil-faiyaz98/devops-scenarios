"""
Predictive Alerting Model for E-commerce Observability.

This module implements a predictive alerting model that forecasts potential
issues before they occur, enabling proactive remediation.

Key features:
- Time series forecasting with confidence intervals
- Anomaly prediction based on historical patterns
- Multi-metric correlation for early warning
- Business impact prediction
- Adaptive thresholds based on context
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
from prophet import Prophet
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class PredictiveAlerting:
    """
    Predictive alerting model for e-commerce observability data.
    
    This class implements multiple techniques to predict potential issues
    before they occur, enabling proactive remediation.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the predictive alerting model.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "forecast_horizon": 24,  # Hours
            "forecast_frequency": "5min",
            "alert_threshold": 0.9,  # Probability threshold for alerting
            "min_confidence": 0.7,  # Minimum confidence for predictions
            "prophet": {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10.0,
                "seasonality_mode": "multiplicative",
                "interval_width": 0.95
            },
            "isolation_forest": {
                "n_estimators": 100,
                "max_samples": "auto",
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
        self.prophet_models = {}
        self.isolation_forest = None
        self.scaler = None
        self.metric_correlations = {}
        self.business_impact_scores = {}
    
    def fit_forecasting_models(self, metrics_data: pd.DataFrame) -> None:
        """
        Fit time series forecasting models for each metric.
        
        Args:
            metrics_data: DataFrame with metrics data
                Must have columns: timestamp, metric_name, value, service
        """
        # Group by service and metric
        grouped = metrics_data.groupby(['service', 'metric_name'])
        
        # Fit Prophet models for each group
        for (service, metric_name), group in grouped:
            # Prepare data for Prophet
            prophet_data = group[['timestamp', 'value']].copy()
            prophet_data.columns = ['ds', 'y']
            
            # Initialize and fit Prophet model
            prophet_config = self.config['prophet']
            model = Prophet(
                changepoint_prior_scale=prophet_config['changepoint_prior_scale'],
                seasonality_prior_scale=prophet_config['seasonality_prior_scale'],
                seasonality_mode=prophet_config['seasonality_mode'],
                interval_width=prophet_config['interval_width']
            )
            
            # Add weekly and daily seasonality if we have enough data
            if len(prophet_data) >= 14 * 24 * 12:  # At least 2 weeks of 5-minute data
                model.add_seasonality(name='weekly', period=7, fourier_order=5)
            if len(prophet_data) >= 2 * 24 * 12:  # At least 2 days of 5-minute data
                model.add_seasonality(name='daily', period=24, fourier_order=12)
            
            # Fit the model
            try:
                model.fit(prophet_data)
                self.prophet_models[(service, metric_name)] = model
            except Exception as e:
                print(f"Failed to fit Prophet model for {service}/{metric_name}: {str(e)}")
    
    def fit_anomaly_detection_model(self, metrics_data: pd.DataFrame) -> None:
        """
        Fit anomaly detection model for multivariate anomalies.
        
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
        
        # Handle remaining missing values
        pivot_data = pivot_data.fillna(pivot_data.mean())
        
        # Fit scaler
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(pivot_data)
        
        # Fit isolation forest
        isolation_config = self.config['isolation_forest']
        self.isolation_forest = IsolationForest(
            n_estimators=isolation_config['n_estimators'],
            max_samples=isolation_config['max_samples'],
            contamination=isolation_config['contamination'],
            random_state=isolation_config['random_state']
        )
        self.isolation_forest.fit(X_scaled)
        
        # Compute metric correlations
        correlation_matrix = pivot_data.corr()
        
        # Store metric correlations
        for col in correlation_matrix.columns:
            # Get top 5 correlated metrics
            top_correlations = correlation_matrix[col].abs().sort_values(ascending=False)[1:6]
            self.metric_correlations[col] = {
                other_col: float(corr)
                for other_col, corr in top_correlations.items()
            }
    
    def set_business_impact_scores(self, impact_scores: Dict[Tuple[str, str], float]) -> None:
        """
        Set business impact scores for metrics.
        
        Args:
            impact_scores: Dictionary mapping (service, metric_name) to impact score
        """
        self.business_impact_scores = impact_scores
    
    def predict_issues(self, current_data: pd.DataFrame, horizon_hours: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Predict potential issues in the future.
        
        Args:
            current_data: DataFrame with current metrics data
                Must have columns: timestamp, metric_name, value, service
            horizon_hours: Number of hours to forecast (default: from config)
                
        Returns:
            List of predicted issues with details
        """
        if horizon_hours is None:
            horizon_hours = self.config['forecast_horizon']
        
        # Initialize results
        predicted_issues = []
        
        # Make forecasts for each metric
        for (service, metric_name), model in self.prophet_models.items():
            # Create future dataframe
            future = model.make_future_dataframe(
                periods=int(horizon_hours * 60 / 5),  # Convert hours to 5-minute periods
                freq=self.config['forecast_frequency']
            )
            
            # Make forecast
            forecast = model.predict(future)
            
            # Get latest data point for this metric
            latest_data = current_data[
                (current_data['service'] == service) &
                (current_data['metric_name'] == metric_name)
            ].sort_values('timestamp').iloc[-1:]
            
            if latest_data.empty:
                continue
            
            latest_value = latest_data['value'].values[0]
            latest_timestamp = latest_data['timestamp'].values[0]
            
            # Check future predictions for anomalies
            for _, row in forecast[forecast['ds'] > latest_timestamp].iterrows():
                # Check if predicted value is outside normal bounds
                if row['yhat'] < row['yhat_lower'] or row['yhat'] > row['yhat_upper']:
                    # Calculate confidence
                    z_score = abs(row['yhat'] - (row['yhat_lower'] + row['yhat_upper']) / 2) / (row['yhat_upper'] - row['yhat_lower']) * 2
                    confidence = min(1.0, z_score)
                    
                    # Skip if confidence is too low
                    if confidence < self.config['min_confidence']:
                        continue
                    
                    # Calculate time until issue
                    time_until = (row['ds'] - pd.Timestamp(latest_timestamp)).total_seconds() / 3600  # Hours
                    
                    # Get business impact
                    business_impact = self.business_impact_scores.get((service, metric_name), 0.5)
                    
                    # Get correlated metrics
                    correlated_metrics = self.metric_correlations.get((service, metric_name), {})
                    
                    # Create issue
                    issue = {
                        'service': service,
                        'metric_name': metric_name,
                        'current_value': float(latest_value),
                        'predicted_value': float(row['yhat']),
                        'lower_bound': float(row['yhat_lower']),
                        'upper_bound': float(row['yhat_upper']),
                        'timestamp': row['ds'].isoformat(),
                        'confidence': float(confidence),
                        'time_until_hours': float(time_until),
                        'business_impact': float(business_impact),
                        'severity': self._calculate_severity(confidence, business_impact, time_until),
                        'correlated_metrics': [
                            {
                                'metric': metric,
                                'correlation': corr
                            }
                            for metric, corr in correlated_metrics.items()
                        ]
                    }
                    
                    predicted_issues.append(issue)
        
        # Detect multivariate anomalies
        if self.isolation_forest is not None and self.scaler is not None:
            # Pivot current data
            pivot_data = current_data.pivot_table(
                index='timestamp',
                columns=['service', 'metric_name'],
                values='value'
            ).fillna(method='ffill')
            
            # Handle missing columns
            for col in self.scaler.feature_names_in_:
                if col not in pivot_data.columns:
                    pivot_data[col] = np.nan
            
            # Ensure columns are in the same order as during training
            pivot_data = pivot_data[self.scaler.feature_names_in_]
            
            # Handle missing values
            pivot_data = pivot_data.fillna(pivot_data.mean())
            
            # Scale data
            X_scaled = self.scaler.transform(pivot_data)
            
            # Predict anomalies
            anomaly_scores = self.isolation_forest.decision_function(X_scaled)
            
            # If anomaly score is low, add multivariate anomaly prediction
            if anomaly_scores.min() < -0.5:
                # Find most anomalous timestamp
                most_anomalous_idx = np.argmin(anomaly_scores)
                most_anomalous_timestamp = pivot_data.index[most_anomalous_idx]
                
                # Find most anomalous metrics
                feature_importances = np.abs(X_scaled[most_anomalous_idx])
                most_important_indices = np.argsort(feature_importances)[-5:]
                most_important_features = [self.scaler.feature_names_in_[i] for i in most_important_indices]
                
                # Create issue
                issue = {
                    'service': 'multiple',
                    'metric_name': 'multivariate_anomaly',
                    'current_value': float(anomaly_scores.min()),
                    'predicted_value': float(anomaly_scores.min()),
                    'lower_bound': -1.0,
                    'upper_bound': 0.0,
                    'timestamp': most_anomalous_timestamp.isoformat(),
                    'confidence': float(min(1.0, abs(anomaly_scores.min()) * 2)),
                    'time_until_hours': 0.0,  # Immediate
                    'business_impact': 0.8,  # High impact for multivariate anomalies
                    'severity': 'critical',
                    'contributing_metrics': [
                        {
                            'metric': feature,
                            'importance': float(feature_importances[i])
                        }
                        for i, feature in zip(most_important_indices, most_important_features)
                    ]
                }
                
                predicted_issues.append(issue)
        
        # Sort by severity and time until issue
        predicted_issues.sort(key=lambda x: (
            self._severity_to_int(x['severity']),
            x['time_until_hours']
        ))
        
        return predicted_issues
    
    def _calculate_severity(self, confidence: float, business_impact: float, time_until: float) -> str:
        """
        Calculate severity based on confidence, business impact, and time until issue.
        
        Args:
            confidence: Prediction confidence (0-1)
            business_impact: Business impact score (0-1)
            time_until: Time until issue in hours
            
        Returns:
            Severity level (critical, high, medium, low)
        """
        # Calculate combined score
        combined_score = confidence * business_impact * (1.0 / (1.0 + time_until / 24.0))
        
        # Determine severity
        if combined_score > 0.8:
            return 'critical'
        elif combined_score > 0.6:
            return 'high'
        elif combined_score > 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _severity_to_int(self, severity: str) -> int:
        """
        Convert severity string to integer for sorting.
        
        Args:
            severity: Severity level
            
        Returns:
            Integer representation (lower is more severe)
        """
        severity_map = {
            'critical': 0,
            'high': 1,
            'medium': 2,
            'low': 3
        }
        return severity_map.get(severity, 4)
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save Prophet models
        os.makedirs(os.path.join(path, 'prophet_models'), exist_ok=True)
        for (service, metric_name), model in self.prophet_models.items():
            model_path = os.path.join(path, 'prophet_models', f"{service}_{metric_name}.json")
            with open(model_path, "w") as f:
                json.dump(model.to_json(), f)
        
        # Save isolation forest
        if self.isolation_forest is not None:
            with open(os.path.join(path, "isolation_forest.pkl"), "wb") as f:
                pickle.dump(self.isolation_forest, f)
        
        # Save scaler
        if self.scaler is not None:
            with open(os.path.join(path, "scaler.pkl"), "wb") as f:
                pickle.dump(self.scaler, f)
        
        # Save metric correlations
        with open(os.path.join(path, "metric_correlations.json"), "w") as f:
            # Convert tuple keys to strings
            serializable_correlations = {
                f"{service}|{metric_name}": correlations
                for (service, metric_name), correlations in self.metric_correlations.items()
            }
            json.dump(serializable_correlations, f)
        
        # Save business impact scores
        with open(os.path.join(path, "business_impact_scores.json"), "w") as f:
            # Convert tuple keys to strings
            serializable_scores = {
                f"{service}|{metric_name}": score
                for (service, metric_name), score in self.business_impact_scores.items()
            }
            json.dump(serializable_scores, f)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "PredictiveAlerting":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded PredictiveAlerting instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        model = cls(config)
        
        # Load Prophet models
        prophet_models_dir = os.path.join(path, 'prophet_models')
        if os.path.exists(prophet_models_dir):
            for file_name in os.listdir(prophet_models_dir):
                if file_name.endswith('.json'):
                    # Extract service and metric name from file name
                    service, metric_name = file_name[:-5].split('_', 1)
                    
                    # Load model
                    model_path = os.path.join(prophet_models_dir, file_name)
                    with open(model_path, "r") as f:
                        model_json = json.load(f)
                    
                    # Create Prophet model
                    prophet_model = Prophet.from_json(model_json)
                    model.prophet_models[(service, metric_name)] = prophet_model
        
        # Load isolation forest
        if os.path.exists(os.path.join(path, "isolation_forest.pkl")):
            with open(os.path.join(path, "isolation_forest.pkl"), "rb") as f:
                model.isolation_forest = pickle.load(f)
        
        # Load scaler
        if os.path.exists(os.path.join(path, "scaler.pkl")):
            with open(os.path.join(path, "scaler.pkl"), "rb") as f:
                model.scaler = pickle.load(f)
        
        # Load metric correlations
        if os.path.exists(os.path.join(path, "metric_correlations.json")):
            with open(os.path.join(path, "metric_correlations.json"), "r") as f:
                serialized_correlations = json.load(f)
                
                # Convert string keys back to tuples
                model.metric_correlations = {
                    tuple(key.split('|', 1)): correlations
                    for key, correlations in serialized_correlations.items()
                }
        
        # Load business impact scores
        if os.path.exists(os.path.join(path, "business_impact_scores.json")):
            with open(os.path.join(path, "business_impact_scores.json"), "r") as f:
                serialized_scores = json.load(f)
                
                # Convert string keys back to tuples
                model.business_impact_scores = {
                    tuple(key.split('|', 1)): score
                    for key, score in serialized_scores.items()
                }
        
        return model
