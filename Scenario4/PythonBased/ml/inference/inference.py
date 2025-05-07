"""
SageMaker Inference Script for Anomaly Detection Model.

This script is used to serve the anomaly detection model on SageMaker.
It loads the model from disk and provides functions for preprocessing
input data, making predictions, and postprocessing the results.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from io import StringIO

# Add parent directory to path to import anomaly_detector module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.anomaly_detector import AnomalyDetector


# Global variables
model = None
model_dir = '/opt/ml/model'


def model_fn(model_dir):
    """
    Load the model from disk.
    
    Args:
        model_dir: Directory where model files are stored
        
    Returns:
        Loaded model
    """
    print(f"Loading model from {model_dir}")
    model = AnomalyDetector.load(model_dir)
    print("Model loaded successfully")
    return model


def input_fn(request_body, request_content_type):
    """
    Preprocess input data.
    
    Args:
        request_body: The request body
        request_content_type: The request content type
        
    Returns:
        Preprocessed input data
    """
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == 'application/json':
        # Parse JSON input
        input_data = json.loads(request_body)
        
        # Check if input is a list of metrics or a DataFrame-like structure
        if isinstance(input_data, list):
            # Convert list of metrics to DataFrame
            df = pd.DataFrame(input_data)
        elif isinstance(input_data, dict) and 'metrics' in input_data:
            # Convert list of metrics to DataFrame
            df = pd.DataFrame(input_data['metrics'])
        else:
            # Assume DataFrame-like structure
            df = pd.DataFrame(input_data)
        
        # Ensure required columns exist
        required_columns = ["timestamp", "metric_name", "value"]
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        return df
    
    elif request_content_type == 'text/csv':
        # Parse CSV input
        df = pd.read_csv(StringIO(request_body))
        
        # Ensure required columns exist
        required_columns = ["timestamp", "metric_name", "value"]
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        return df
    
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model):
    """
    Make predictions using the model.
    
    Args:
        input_data: Preprocessed input data
        model: Loaded model
        
    Returns:
        Model predictions
    """
    print(f"Making predictions on {len(input_data)} data points")
    
    # Make predictions
    predictions = model.predict_anomalies(input_data)
    
    return predictions


def output_fn(predictions, accept):
    """
    Postprocess the predictions.
    
    Args:
        predictions: Model predictions
        accept: Accept header
        
    Returns:
        Postprocessed predictions
    """
    print(f"Postprocessing predictions with accept type: {accept}")
    
    if accept == 'application/json' or accept == '*/*':
        # Convert predictions to JSON
        predictions_json = predictions.to_json(orient='records', date_format='iso')
        return predictions_json, 'application/json'
    
    elif accept == 'text/csv':
        # Convert predictions to CSV
        predictions_csv = predictions.to_csv(index=False)
        return predictions_csv, 'text/csv'
    
    else:
        # Default to JSON
        predictions_json = predictions.to_json(orient='records', date_format='iso')
        return predictions_json, 'application/json'
