#!/usr/bin/env python3
"""
Dynamic Thresholds Generator for Prometheus Alerts

This script fetches metrics from Prometheus, uses SageMaker endpoints to predict
anomaly thresholds, and generates dynamic alerting rules.
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
import boto3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from prometheus_api_client import PrometheusConnect, MetricsList

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DynamicThresholdGenerator:
    def __init__(self, config_file, prometheus_url, rules_dir):
        """Initialize the generator with configuration."""
        self.prometheus_url = prometheus_url
        self.rules_dir = rules_dir
        self.prom = PrometheusConnect(url=prometheus_url, disable_ssl=False)
        
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Initialize SageMaker client
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=self.config.get('region', 'us-east-1'))
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"Initialized with {len(self.config['metrics'])} metrics configurations")

    def _validate_config(self):
        """Validate the configuration file."""
        required_keys = ['metrics', 'endpoints', 'region']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required configuration key: {key}")
        
        for metric in self.config['metrics']:
            required_metric_keys = ['name', 'query', 'endpoint', 'window', 'alert_name']
            for key in required_metric_keys:
                if key not in metric:
                    raise ValueError(f"Missing required metric configuration key: {key} in {metric['name']}")

    def fetch_metric_data(self, metric_config):
        """Fetch metric data from Prometheus."""
        query = metric_config['query']
        window = metric_config.get('window', '1d')
        
        logger.info(f"Fetching data for metric: {metric_config['name']} with query: {query}")
        
        # Execute query
        result = self.prom.custom_query(query=query)
        
        if not result:
            logger.warning(f"No data returned for query: {query}")
            return None
        
        # Convert to DataFrame
        metric_data = []
        for item in result:
            metric_dict = item['metric']
            value = float(item['value'][1])
            
            data_point = {
                'value': value,
                'timestamp': datetime.fromtimestamp(item['value'][0])
            }
            
            # Add metric labels
            for k, v in metric_dict.items():
                data_point[k] = v
            
            metric_data.append(data_point)
        
        df = pd.DataFrame(metric_data)
        logger.info(f"Fetched {len(df)} data points")
        
        return df

    def get_prediction(self, endpoint_name, payload):
        """Get prediction from SageMaker endpoint."""
        endpoint_config = next((e for e in self.config['endpoints'] if e['name'] == endpoint_name), None)
        
        if not endpoint_config:
            raise ValueError(f"Endpoint configuration not found for: {endpoint_name}")
        
        logger.info(f"Sending prediction request to endpoint: {endpoint_config['endpoint_name']}")
        
        try:
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_config['endpoint_name'],
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            result = json.loads(response['Body'].read().decode())
            logger.info(f"Received prediction response: {result}")
            
            return result
        except Exception as e:
            logger.error(f"Error invoking SageMaker endpoint: {str(e)}")
            raise

    def generate_threshold(self, metric_config, metric_data):
        """Generate dynamic threshold using ML model."""
        if metric_data is None or len(metric_data) == 0:
            logger.warning(f"No data available for metric: {metric_config['name']}")
            return None
        
        # Prepare data for prediction
        prediction_data = self._prepare_prediction_data(metric_config, metric_data)
        
        # Get prediction from SageMaker
        prediction_result = self.get_prediction(metric_config['endpoint'], prediction_data)
        
        # Extract threshold from prediction
        threshold = self._extract_threshold(prediction_result, metric_config)
        
        logger.info(f"Generated threshold for {metric_config['name']}: {threshold}")
        
        return threshold

    def _prepare_prediction_data(self, metric_config, metric_data):
        """Prepare data for prediction."""
        # Calculate statistics
        stats = {
            'mean': metric_data['value'].mean(),
            'median': metric_data['value'].median(),
            'std': metric_data['value'].std(),
            'min': metric_data['value'].min(),
            'max': metric_data['value'].max(),
            'p90': np.percentile(metric_data['value'], 90),
            'p95': np.percentile(metric_data['value'], 95),
            'p99': np.percentile(metric_data['value'], 99),
            'count': len(metric_data)
        }
        
        # Add time-based features
        now = datetime.now()
        stats['hour_of_day'] = now.hour
        stats['day_of_week'] = now.weekday()
        stats['is_weekend'] = 1 if now.weekday() >= 5 else 0
        
        # Add metric-specific features
        stats['metric_name'] = metric_config['name']
        
        # Add any additional features specified in config
        for feature, value in metric_config.get('additional_features', {}).items():
            stats[feature] = value
        
        return stats

    def _extract_threshold(self, prediction_result, metric_config):
        """Extract threshold value from prediction result."""
        # Different endpoints might return different formats
        if isinstance(prediction_result, dict) and 'threshold' in prediction_result:
            return prediction_result['threshold']
        elif isinstance(prediction_result, dict) and 'predictions' in prediction_result:
            return prediction_result['predictions'][0]['threshold']
        elif isinstance(prediction_result, list) and len(prediction_result) > 0:
            return prediction_result[0].get('threshold', prediction_result[0].get('value', None))
        else:
            # Use fallback method based on prediction and configuration
            base_value = metric_config.get('base_threshold', 0)
            multiplier = metric_config.get('threshold_multiplier', 1.0)
            
            if isinstance(prediction_result, dict) and 'value' in prediction_result:
                return prediction_result['value'] * multiplier + base_value
            
            logger.warning(f"Could not extract threshold from prediction result: {prediction_result}")
            return None

    def generate_alert_rule(self, metric_config, threshold):
        """Generate Prometheus alert rule with dynamic threshold."""
        if threshold is None:
            logger.warning(f"Cannot generate alert rule for {metric_config['name']} without threshold")
            return None
        
        alert_name = metric_config['alert_name']
        query = metric_config['query']
        comparison = metric_config.get('comparison', '>')
        
        # Create alert rule
        rule = {
            "alert": alert_name,
            "expr": f"{query} {comparison} {threshold}",
            "for": metric_config.get('for', '5m'),
            "labels": {
                "severity": metric_config.get('severity', 'warning'),
                "type": "dynamic_threshold",
                "metric": metric_config['name']
            },
            "annotations": {
                "summary": f"{alert_name} - Dynamic threshold exceeded",
                "description": f"{{{{ $labels.instance }}}} has exceeded the dynamic threshold of {threshold} for {metric_config['name']}",
                "threshold_value": str(threshold),
                "dashboard": metric_config.get('dashboard', '')
            }
        }
        
        # Add custom labels and annotations
        rule['labels'].update(metric_config.get('labels', {}))
        rule['annotations'].update(metric_config.get('annotations', {}))
        
        return rule

    def write_rules_file(self, rules):
        """Write rules to a Prometheus rules file."""
        if not rules:
            logger.warning("No rules to write")
            return
        
        # Create rules directory if it doesn't exist
        os.makedirs(self.rules_dir, exist_ok=True)
        
        # Create rules file
        rules_file = os.path.join(self.rules_dir, f"dynamic_thresholds_{int(time.time())}.yml")
        
        # Format rules in Prometheus format
        rules_yaml = {
            "groups": [
                {
                    "name": "dynamic_thresholds",
                    "rules": rules
                }
            ]
        }
        
        # Write rules to file
        with open(rules_file, 'w') as f:
            json.dump(rules_yaml, f, indent=2)
        
        logger.info(f"Wrote {len(rules)} rules to {rules_file}")
        
        return rules_file

    def run(self):
        """Run the dynamic threshold generation process."""
        rules = []
        
        for metric_config in self.config['metrics']:
            try:
                # Fetch metric data
                metric_data = self.fetch_metric_data(metric_config)
                
                # Generate threshold
                threshold = self.generate_threshold(metric_config, metric_data)
                
                # Generate alert rule
                if threshold is not None:
                    rule = self.generate_alert_rule(metric_config, threshold)
                    if rule is not None:
                        rules.append(rule)
            except Exception as e:
                logger.error(f"Error processing metric {metric_config['name']}: {str(e)}")
        
        # Write rules to file
        if rules:
            rules_file = self.write_rules_file(rules)
            logger.info(f"Dynamic thresholds generation completed. Rules written to {rules_file}")
        else:
            logger.warning("No rules generated")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate dynamic thresholds for Prometheus alerts')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--prometheus-url', required=True, help='Prometheus API URL')
    parser.add_argument('--rules-dir', required=True, help='Directory to write rules files')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Create and run generator
    generator = DynamicThresholdGenerator(
        config_file=args.config,
        prometheus_url=args.prometheus_url,
        rules_dir=args.rules_dir
    )
    
    generator.run()

if __name__ == '__main__':
    main()
