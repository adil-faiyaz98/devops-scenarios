"""
SageMaker Training Script for Anomaly Detection Model.

This script is used to train the anomaly detection model on SageMaker.
It loads data from S3, trains the model, and saves it back to S3.
"""

import os
import sys
import json
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path to import anomaly_detector module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.anomaly_detector import AnomalyDetector


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    
    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train'))
    parser.add_argument('--validation', type=str, default=os.environ.get('SM_CHANNEL_VALIDATION', '/opt/ml/input/data/validation'))
    
    # Model specific arguments
    parser.add_argument('--isolation-forest-estimators', type=int, default=100)
    parser.add_argument('--isolation-forest-contamination', type=float, default=0.01)
    parser.add_argument('--prophet-changepoint-prior-scale', type=float, default=0.05)
    parser.add_argument('--prophet-seasonality-prior-scale', type=float, default=10.0)
    parser.add_argument('--dynamic-threshold-sensitivity', type=float, default=3.0)
    
    return parser.parse_args()


def load_data(data_dir):
    """
    Load data from CSV files in the specified directory.
    
    Args:
        data_dir: Directory containing CSV files
        
    Returns:
        DataFrame with combined data
    """
    all_data = []
    
    # List all CSV files in the directory
    for file in os.listdir(data_dir):
        if file.endswith('.csv'):
            file_path = os.path.join(data_dir, file)
            print(f"Loading data from {file_path}")
            
            try:
                # Load CSV file
                df = pd.read_csv(file_path)
                
                # Ensure required columns exist
                required_columns = ["timestamp", "metric_name", "value"]
                if not all(col in df.columns for col in required_columns):
                    missing = [col for col in required_columns if col not in df.columns]
                    print(f"Skipping {file_path}: Missing required columns: {missing}")
                    continue
                
                # Convert timestamp to datetime
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                
                # Append to list
                all_data.append(df)
            except Exception as e:
                print(f"Error loading {file_path}: {str(e)}")
    
    # Combine all data
    if not all_data:
        raise ValueError("No valid data files found")
    
    combined_data = pd.concat(all_data, ignore_index=True)
    print(f"Loaded {len(combined_data)} rows of data")
    
    return combined_data


def preprocess_data(data):
    """
    Preprocess data for training.
    
    Args:
        data: DataFrame with raw data
        
    Returns:
        Preprocessed DataFrame
    """
    # Sort by timestamp
    data = data.sort_values("timestamp")
    
    # Remove duplicates
    data = data.drop_duplicates(subset=["timestamp", "metric_name"])
    
    # Handle missing values
    # For each metric, interpolate missing values
    for metric_name, group in data.groupby("metric_name"):
        group = group.sort_values("timestamp")
        group["value"] = group["value"].interpolate(method="time")
        data.loc[group.index, "value"] = group["value"]
    
    # Remove remaining rows with NaN values
    data = data.dropna(subset=["value"])
    
    # Remove outliers (optional, as we're training an anomaly detection model)
    # This is just to remove extreme outliers that might affect training
    for metric_name, group in data.groupby("metric_name"):
        q1 = group["value"].quantile(0.01)
        q3 = group["value"].quantile(0.99)
        iqr = q3 - q1
        lower_bound = q1 - 10 * iqr
        upper_bound = q3 + 10 * iqr
        
        # Filter out extreme outliers
        mask = (group["value"] >= lower_bound) & (group["value"] <= upper_bound)
        data = data.loc[mask.index[mask]]
    
    print(f"After preprocessing: {len(data)} rows of data")
    return data


def train_model(train_data, validation_data, args):
    """
    Train the anomaly detection model.
    
    Args:
        train_data: Training data
        validation_data: Validation data
        args: Command line arguments
        
    Returns:
        Trained model
    """
    # Create model configuration
    config = {
        "isolation_forest": {
            "n_estimators": args.isolation_forest_estimators,
            "max_samples": "auto",
            "contamination": args.isolation_forest_contamination,
            "random_state": 42
        },
        "prophet": {
            "changepoint_prior_scale": args.prophet_changepoint_prior_scale,
            "seasonality_prior_scale": args.prophet_seasonality_prior_scale,
            "seasonality_mode": "multiplicative",
            "interval_width": 0.95
        },
        "dynamic_threshold": {
            "sensitivity": args.dynamic_threshold_sensitivity,
            "min_history_size": 30,
            "max_history_size": 1000
        }
    }
    
    # Create and fit model
    print("Creating anomaly detection model")
    model = AnomalyDetector(config)
    
    print("Fitting model on training data")
    model.fit(train_data)
    
    # Evaluate model on validation data
    if not validation_data.empty:
        print("Evaluating model on validation data")
        results = model.predict_anomalies(validation_data)
        
        # Calculate metrics
        anomalies = results[results["is_anomaly"]]
        anomaly_rate = len(anomalies) / len(results) * 100
        
        print(f"Validation anomaly rate: {anomaly_rate:.2f}%")
        print(f"Anomalies by detection method:")
        for method, count in anomalies["detection_method"].value_counts().items():
            print(f"  {method}: {count} ({count/len(anomalies)*100:.2f}%)")
    
    return model


def save_model(model, model_dir):
    """
    Save the trained model.
    
    Args:
        model: Trained model
        model_dir: Directory to save the model
    """
    print(f"Saving model to {model_dir}")
    model.save(model_dir)
    
    # Save a model info file with metadata
    model_info = {
        "model_type": "AnomalyDetector",
        "training_time": datetime.now().isoformat(),
        "config": model.config
    }
    
    with open(os.path.join(model_dir, "model_info.json"), "w") as f:
        json.dump(model_info, f, indent=2)
    
    print("Model saved successfully")


def main():
    """Main training function."""
    args = parse_args()
    
    try:
        # Load training data
        print("Loading training data")
        train_data = load_data(args.train)
        
        # Load validation data if available
        validation_data = pd.DataFrame()
        if os.path.exists(args.validation):
            print("Loading validation data")
            validation_data = load_data(args.validation)
        
        # Preprocess data
        print("Preprocessing training data")
        train_data = preprocess_data(train_data)
        
        if not validation_data.empty:
            print("Preprocessing validation data")
            validation_data = preprocess_data(validation_data)
        
        # Train model
        model = train_model(train_data, validation_data, args)
        
        # Save model
        save_model(model, args.model_dir)
        
        print("Training completed successfully")
    except Exception as e:
        print(f"Training failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
