import os
import json
import boto3
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SageMaker paths
prefix = '/opt/ml/'
input_path = prefix + 'input/data'
output_path = os.path.join(prefix, 'output')
model_path = os.path.join(prefix, 'model')
param_path = os.path.join(prefix, 'input/config/hyperparameters.json')

# Training script for anomaly detection model
def train():
    logger.info("Starting model training")
    
    # Load training data
    training_path = os.path.join(input_path, 'training')
    train_files = [os.path.join(training_path, file) for file in os.listdir(training_path)]
    
    if not train_files:
        raise ValueError(f"No training files found in {training_path}")
    
    # Read and combine training files
    dfs = []
    for file in train_files:
        df = pd.read_csv(file)
        dfs.append(df)
    
    train_data = pd.concat(dfs)
    logger.info(f"Loaded training data with shape: {train_data.shape}")
    
    # Load hyperparameters
    with open(param_path, 'r') as f:
        hyperparameters = json.load(f)
    
    n_estimators = int(hyperparameters.get('n_estimators', 100))
    contamination = float(hyperparameters.get('contamination', 0.01))
    max_features = float(hyperparameters.get('max_features', 1.0))
    
    logger.info(f"Hyperparameters: n_estimators={n_estimators}, contamination={contamination}, max_features={max_features}")
    
    # Prepare features
    features = train_data.select_dtypes(include=[np.number])
    feature_columns = features.columns.tolist()
    
    # Scale features
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    # Train model
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        max_features=max_features,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(scaled_features)
    logger.info("Model training completed")
    
    # Save model artifacts
    os.makedirs(model_path, exist_ok=True)
    joblib.dump(model, os.path.join(model_path, 'isolation_forest.joblib'))
    joblib.dump(scaler, os.path.join(model_path, 'scaler.joblib'))
    
    # Save feature columns
    with open(os.path.join(model_path, 'feature_columns.json'), 'w') as f:
        json.dump(feature_columns, f)
    
    logger.info("Model artifacts saved")

# Inference script for anomaly detection
def model_fn(model_dir):
    """Load model from the model_dir."""
    logger.info("Loading model")
    model = joblib.load(os.path.join(model_dir, 'isolation_forest.joblib'))
    scaler = joblib.load(os.path.join(model_dir, 'scaler.joblib'))
    
    with open(os.path.join(model_dir, 'feature_columns.json'), 'r') as f:
        feature_columns = json.load(f)
    
    return {
        'model': model,
        'scaler': scaler,
        'feature_columns': feature_columns
    }

def input_fn(request_body, request_content_type):
    """Parse input data payload."""
    logger.info(f"Received request with content type: {request_content_type}")
    
    if request_content_type == 'application/json':
        data = json.loads(request_body)
        
        # Convert to DataFrame if it's a list of records
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # If it's a single record
            df = pd.DataFrame([data])
        else:
            raise ValueError("Unsupported JSON format")
        
        return df
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, model_dict):
    """Make prediction with the loaded model."""
    logger.info("Performing prediction")
    
    model = model_dict['model']
    scaler = model_dict['scaler']
    feature_columns = model_dict['feature_columns']
    
    # Extract and validate features
    available_features = [col for col in feature_columns if col in input_data.columns]
    if len(available_features) < len(feature_columns):
        missing = set(feature_columns) - set(available_features)
        logger.warning(f"Missing features: {missing}")
    
    # Use available features
    features = input_data[available_features]
    
    # Fill missing values
    features = features.fillna(0)
    
    # Scale features
    scaled_features = scaler.transform(features)
    
    # Get anomaly scores (-1 for anomalies, 1 for normal)
    raw_predictions = model.predict(scaled_features)
    
    # Get decision scores (lower = more anomalous)
    decision_scores = model.decision_function(scaled_features)
    
    # Convert to anomaly probability (0 to 1, higher = more anomalous)
    # Normalize scores to 0-1 range where 1 is most anomalous
    min_score = decision_scores.min()
    max_score = decision_scores.max()
    
    if max_score == min_score:
        anomaly_scores = np.zeros(len(decision_scores))
    else:
        # Invert and normalize so 1 = anomaly, 0 = normal
        anomaly_scores = 1 - ((decision_scores - min_score) / (max_score - min_score))
    
    # Prepare results
    results = []
    for i, (pred, score) in enumerate(zip(raw_predictions, anomaly_scores)):
        record = input_data.iloc[i].to_dict()
        record['anomaly'] = 1 if pred == -1 else 0
        record['anomaly_score'] = float(score)
        results.append(record)
    
    return results

def output_fn(prediction, response_content_type):
    """Format prediction output."""
    logger.info(f"Formatting output to content type: {response_content_type}")
    
    if response_content_type == 'application/json':
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {response_content_type}")

if __name__ == '__main__':
    train()
