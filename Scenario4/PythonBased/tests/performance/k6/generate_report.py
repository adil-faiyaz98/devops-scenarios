#!/usr/bin/env python3
"""
Generate a summary report from k6 test results.

This script reads k6 JSON output files and generates an HTML report with
charts and tables summarizing the performance test results.
"""

import os
import json
import argparse
import glob
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate k6 test report')
    parser.add_argument('--input-dir', required=True, help='Directory containing k6 JSON output files')
    parser.add_argument('--output-file', required=True, help='Output HTML file')
    return parser.parse_args()


def load_k6_results(input_dir):
    """
    Load k6 test results from JSON files.
    
    Args:
        input_dir: Directory containing k6 JSON output files
        
    Returns:
        Dictionary with test results
    """
    results = {
        'anomaly_detection': [],
        'root_cause_analysis': [],
        'predictive_alerting': [],
        'dashboard_load': []
    }
    
    # Find all JSON files
    json_files = glob.glob(os.path.join(input_dir, 'k6-*.json'))
    
    for file_path in json_files:
        # Determine scenario from filename
        filename = os.path.basename(file_path)
        scenario = None
        
        for key in results.keys():
            if key in filename:
                scenario = key
                break
        
        if scenario is None:
            continue
        
        # Load JSON file
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Extract metrics
            metrics = {}
            
            # Extract custom metrics
            for metric_name, metric_data in data.get('metrics', {}).items():
                if metric_name in ['anomaly_detection_latency', 'root_cause_analysis_latency', 
                                  'predictive_alerting_latency', 'dashboard_load_latency']:
                    metrics[metric_name] = {
                        'avg': metric_data.get('values', {}).get('avg', 0),
                        'min': metric_data.get('values', {}).get('min', 0),
                        'med': metric_data.get('values', {}).get('med', 0),
                        'p90': metric_data.get('values', {}).get('p(90)', 0),
                        'p95': metric_data.get('values', {}).get('p(95)', 0),
                        'p99': metric_data.get('values', {}).get('p(99)', 0),
                        'max': metric_data.get('values', {}).get('max', 0)
                    }
                elif metric_name == 'error_rate':
                    metrics[metric_name] = metric_data.get('values', {}).get('rate', 0)
            
            # Extract standard metrics
            for metric_name in ['http_reqs', 'http_req_duration', 'iterations', 'vus', 'vus_max']:
                if metric_name in data.get('metrics', {}):
                    metric_data = data['metrics'][metric_name]
                    
                    if metric_name in ['http_req_duration']:
                        metrics[metric_name] = {
                            'avg': metric_data.get('values', {}).get('avg', 0),
                            'min': metric_data.get('values', {}).get('min', 0),
                            'med': metric_data.get('values', {}).get('med', 0),
                            'p90': metric_data.get('values', {}).get('p(90)', 0),
                            'p95': metric_data.get('values', {}).get('p(95)', 0),
                            'p99': metric_data.get('values', {}).get('p(99)', 0),
                            'max': metric_data.get('values', {}).get('max', 0)
                        }
                    else:
                        metrics[metric_name] = metric_data.get('values', {}).get('count', 0)
            
            # Add timestamp
            timestamp = datetime.fromtimestamp(data.get('timestamp', 0) / 1000)
            metrics['timestamp'] = timestamp
            
            # Add to results
            results[scenario].append(metrics)
    
    return results


def generate_charts(results, output_dir):
    """
    Generate charts from test results.
    
    Args:
        results: Dictionary with test results
        output_dir: Directory to save charts
        
    Returns:
        Dictionary with chart file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    charts = {}
    
    # Set style
    sns.set_style('whitegrid')
    plt.rcParams['figure.figsize'] = (10, 6)
    
    # Generate latency comparison chart
    plt.figure()
    
    # Prepare data
    scenarios = []
    p95_latencies = []
    avg_latencies = []
    
    for scenario, scenario_results in results.items():
        if not scenario_results:
            continue
        
        # Get latest result
        latest_result = max(scenario_results, key=lambda x: x.get('timestamp', datetime.min))
        
        # Get latency metric name
        latency_metric = f"{scenario}_latency"
        
        if latency_metric in latest_result:
            scenarios.append(scenario)
            p95_latencies.append(latest_result[latency_metric]['p95'])
            avg_latencies.append(latest_result[latency_metric]['avg'])
    
    # Create chart
    x = range(len(scenarios))
    width = 0.35
    
    plt.bar([i - width/2 for i in x], avg_latencies, width, label='Average')
    plt.bar([i + width/2 for i in x], p95_latencies, width, label='P95')
    
    plt.xlabel('Scenario')
    plt.ylabel('Latency (ms)')
    plt.title('Latency Comparison by Scenario')
    plt.xticks(x, scenarios)
    plt.legend()
    
    # Save chart
    chart_path = os.path.join(output_dir, 'latency_comparison.png')
    plt.savefig(chart_path)
    charts['latency_comparison'] = chart_path
    
    # Generate error rate chart
    plt.figure()
    
    # Prepare data
    scenarios = []
    error_rates = []
    
    for scenario, scenario_results in results.items():
        if not scenario_results:
            continue
        
        # Get latest result
        latest_result = max(scenario_results, key=lambda x: x.get('timestamp', datetime.min))
        
        if 'error_rate' in latest_result:
            scenarios.append(scenario)
            error_rates.append(latest_result['error_rate'] * 100)  # Convert to percentage
    
    # Create chart
    plt.bar(scenarios, error_rates)
    plt.xlabel('Scenario')
    plt.ylabel('Error Rate (%)')
    plt.title('Error Rate by Scenario')
    
    # Save chart
    chart_path = os.path.join(output_dir, 'error_rate.png')
    plt.savefig(chart_path)
    charts['error_rate'] = chart_path
    
    # Generate throughput chart
    plt.figure()
    
    # Prepare data
    scenarios = []
    throughputs = []
    
    for scenario, scenario_results in results.items():
        if not scenario_results:
            continue
        
        # Get latest result
        latest_result = max(scenario_results, key=lambda x: x.get('timestamp', datetime.min))
        
        if 'http_reqs' in latest_result and 'timestamp' in latest_result:
            scenarios.append(scenario)
            
            # Calculate throughput (requests per second)
            throughput = latest_result['http_reqs']
            throughputs.append(throughput)
    
    # Create chart
    plt.bar(scenarios, throughputs)
    plt.xlabel('Scenario')
    plt.ylabel('Throughput (requests)')
    plt.title('Throughput by Scenario')
    
    # Save chart
    chart_path = os.path.join(output_dir, 'throughput.png')
    plt.savefig(chart_path)
    charts['throughput'] = chart_path
    
    return charts


def generate_html_report(results, charts, output_file):
    """
    Generate HTML report.
    
    Args:
        results: Dictionary with test results
        charts: Dictionary with chart file paths
        output_file: Output HTML file path
    """
    # Prepare data for report
    report_data = {
        'scenarios': {},
        'charts': charts,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    for scenario, scenario_results in results.items():
        if not scenario_results:
            continue
        
        # Get latest result
        latest_result = max(scenario_results, key=lambda x: x.get('timestamp', datetime.min))
        
        # Add to report data
        report_data['scenarios'][scenario] = {
            'timestamp': latest_result.get('timestamp').strftime('%Y-%m-%d %H:%M:%S'),
            'http_reqs': latest_result.get('http_reqs', 0),
            'iterations': latest_result.get('iterations', 0),
            'vus': latest_result.get('vus', 0),
            'vus_max': latest_result.get('vus_max', 0),
            'error_rate': latest_result.get('error_rate', 0) * 100,  # Convert to percentage
            'latency': {}
        }
        
        # Add latency metrics
        latency_metric = f"{scenario}_latency"
        if latency_metric in latest_result:
            report_data['scenarios'][scenario]['latency'] = latest_result[latency_metric]
        elif 'http_req_duration' in latest_result:
            report_data['scenarios'][scenario]['latency'] = latest_result['http_req_duration']
    
    # HTML template
    template = Template('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>k6 Performance Test Report</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }
            h1, h2, h3 {
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .summary {
                margin-bottom: 30px;
            }
            .charts {
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                margin-bottom: 30px;
            }
            .chart {
                width: 48%;
                margin-bottom: 20px;
                box-shadow: 0 0 5px rgba(0,0,0,0.1);
                padding: 10px;
            }
            .chart img {
                width: 100%;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }
            th, td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
            }
            .footer {
                margin-top: 30px;
                color: #777;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>k6 Performance Test Report</h1>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Report generated at: {{ generated_at }}</p>
                <p>Number of scenarios: {{ scenarios|length }}</p>
            </div>
            
            <div class="charts">
                <div class="chart">
                    <h3>Latency Comparison</h3>
                    <img src="{{ charts.latency_comparison }}" alt="Latency Comparison">
                </div>
                <div class="chart">
                    <h3>Error Rate</h3>
                    <img src="{{ charts.error_rate }}" alt="Error Rate">
                </div>
                <div class="chart">
                    <h3>Throughput</h3>
                    <img src="{{ charts.throughput }}" alt="Throughput">
                </div>
            </div>
            
            <h2>Scenario Details</h2>
            {% for scenario_name, scenario in scenarios.items() %}
            <h3>{{ scenario_name }}</h3>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Timestamp</td>
                    <td>{{ scenario.timestamp }}</td>
                </tr>
                <tr>
                    <td>HTTP Requests</td>
                    <td>{{ scenario.http_reqs }}</td>
                </tr>
                <tr>
                    <td>Iterations</td>
                    <td>{{ scenario.iterations }}</td>
                </tr>
                <tr>
                    <td>VUs</td>
                    <td>{{ scenario.vus }}</td>
                </tr>
                <tr>
                    <td>Max VUs</td>
                    <td>{{ scenario.vus_max }}</td>
                </tr>
                <tr>
                    <td>Error Rate</td>
                    <td>{{ "%.2f"|format(scenario.error_rate) }}%</td>
                </tr>
            </table>
            
            <h4>Latency (ms)</h4>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Average</td>
                    <td>{{ "%.2f"|format(scenario.latency.avg) }}</td>
                </tr>
                <tr>
                    <td>Minimum</td>
                    <td>{{ "%.2f"|format(scenario.latency.min) }}</td>
                </tr>
                <tr>
                    <td>Median</td>
                    <td>{{ "%.2f"|format(scenario.latency.med) }}</td>
                </tr>
                <tr>
                    <td>P90</td>
                    <td>{{ "%.2f"|format(scenario.latency.p90) }}</td>
                </tr>
                <tr>
                    <td>P95</td>
                    <td>{{ "%.2f"|format(scenario.latency.p95) }}</td>
                </tr>
                <tr>
                    <td>P99</td>
                    <td>{{ "%.2f"|format(scenario.latency.p99) }}</td>
                </tr>
                <tr>
                    <td>Maximum</td>
                    <td>{{ "%.2f"|format(scenario.latency.max) }}</td>
                </tr>
            </table>
            {% endfor %}
            
            <div class="footer">
                <p>Generated by k6 Performance Test Report Generator</p>
            </div>
        </div>
    </body>
    </html>
    ''')
    
    # Render template
    html = template.render(**report_data)
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(html)


def main():
    """Main function."""
    args = parse_args()
    
    # Load k6 results
    results = load_k6_results(args.input_dir)
    
    # Generate charts
    charts_dir = os.path.join(os.path.dirname(args.output_file), 'charts')
    charts = generate_charts(results, charts_dir)
    
    # Generate HTML report
    generate_html_report(results, charts, args.output_file)
    
    print(f"Report generated: {args.output_file}")


if __name__ == '__main__':
    main()
