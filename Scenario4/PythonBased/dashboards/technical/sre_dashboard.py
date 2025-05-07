"""
SRE Technical Dashboard Generator.

This module generates Grafana dashboards for SRE teams to monitor the
health and performance of the e-commerce platform.

Key features:
- Service health and availability
- Error rates and latency metrics
- Resource utilization
- SLO/SLI tracking
- Alerting thresholds
"""

import os
import json
import requests
import argparse
from typing import Dict, List, Any, Optional


class GrafanaClient:
    """Client for interacting with the Grafana API."""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the Grafana client.
        
        Args:
            base_url: Base URL of the Grafana instance
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
    
    def create_or_update_dashboard(self, dashboard: Dict[str, Any], folder_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Create or update a dashboard.
        
        Args:
            dashboard: Dashboard definition
            folder_id: ID of the folder to save the dashboard in
            
        Returns:
            Response from the Grafana API
        """
        payload = {
            'dashboard': dashboard,
            'overwrite': True,
        }
        
        if folder_id is not None:
            payload['folderId'] = folder_id
        
        response = requests.post(
            f'{self.base_url}/api/dashboards/db',
            headers=self.headers,
            json=payload,
        )
        
        response.raise_for_status()
        return response.json()
    
    def create_folder(self, title: str) -> Dict[str, Any]:
        """
        Create a folder.
        
        Args:
            title: Title of the folder
            
        Returns:
            Response from the Grafana API
        """
        payload = {
            'title': title,
        }
        
        response = requests.post(
            f'{self.base_url}/api/folders',
            headers=self.headers,
            json=payload,
        )
        
        # If folder already exists, return it
        if response.status_code == 412:
            # Get folder by title
            folders = requests.get(
                f'{self.base_url}/api/folders',
                headers=self.headers,
            ).json()
            
            for folder in folders:
                if folder['title'] == title:
                    return folder
        
        response.raise_for_status()
        return response.json()


def create_service_health_panel() -> Dict[str, Any]:
    """
    Create a panel for service health.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Service Health',
        'type': 'stat',
        'gridPos': {
            'h': 8,
            'w': 24,
            'x': 0,
            'y': 0,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'thresholds',
                },
                'mappings': [
                    {
                        'options': {
                            '0': {
                                'color': 'red',
                                'index': 0,
                                'text': 'Down',
                            },
                            '1': {
                                'color': 'green',
                                'index': 1,
                                'text': 'Up',
                            },
                        },
                        'type': 'value',
                    },
                ],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'red',
                            'value': None,
                        },
                        {
                            'color': 'green',
                            'value': 1,
                        },
                    ],
                },
            },
            'overrides': [],
        },
        'options': {
            'colorMode': 'background',
            'graphMode': 'none',
            'justifyMode': 'auto',
            'orientation': 'horizontal',
            'reduceOptions': {
                'calcs': ['lastNotNull'],
                'fields': '',
                'values': False,
            },
            'textMode': 'auto',
        },
        'pluginVersion': '9.5.2',
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'up{job=~"$service"}',
                'legendFormat': '{{job}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_error_rate_panel() -> Dict[str, Any]:
    """
    Create a panel for error rates.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Error Rate',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 0,
            'y': 8,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'palette-classic',
                },
                'custom': {
                    'axisCenteredZero': False,
                    'axisColorMode': 'text',
                    'axisLabel': '',
                    'axisPlacement': 'auto',
                    'barAlignment': 0,
                    'drawStyle': 'line',
                    'fillOpacity': 10,
                    'gradientMode': 'none',
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                    'lineInterpolation': 'linear',
                    'lineWidth': 1,
                    'pointSize': 5,
                    'scaleDistribution': {
                        'type': 'linear',
                    },
                    'showPoints': 'never',
                    'spanNulls': True,
                    'stacking': {
                        'group': 'A',
                        'mode': 'none',
                    },
                    'thresholdsStyle': {
                        'mode': 'area',
                    },
                },
                'mappings': [],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'green',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 0.01,
                        },
                        {
                            'color': 'red',
                            'value': 0.05,
                        },
                    ],
                },
                'unit': 'percentunit',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['mean', 'max'],
                'displayMode': 'table',
                'placement': 'bottom',
                'showLegend': True,
            },
            'tooltip': {
                'mode': 'multi',
                'sort': 'desc',
            },
        },
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(rate(http_requests_total{job=~"$service", status=~"5.."}[$__rate_interval])) by (job) / sum(rate(http_requests_total{job=~"$service"}[$__rate_interval])) by (job)',
                'legendFormat': '{{job}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_latency_panel() -> Dict[str, Any]:
    """
    Create a panel for latency metrics.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Latency (p95)',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 12,
            'y': 8,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'palette-classic',
                },
                'custom': {
                    'axisCenteredZero': False,
                    'axisColorMode': 'text',
                    'axisLabel': '',
                    'axisPlacement': 'auto',
                    'barAlignment': 0,
                    'drawStyle': 'line',
                    'fillOpacity': 10,
                    'gradientMode': 'none',
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                    'lineInterpolation': 'linear',
                    'lineWidth': 1,
                    'pointSize': 5,
                    'scaleDistribution': {
                        'type': 'linear',
                    },
                    'showPoints': 'never',
                    'spanNulls': True,
                    'stacking': {
                        'group': 'A',
                        'mode': 'none',
                    },
                    'thresholdsStyle': {
                        'mode': 'area',
                    },
                },
                'mappings': [],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'green',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 0.5,
                        },
                        {
                            'color': 'red',
                            'value': 1,
                        },
                    ],
                },
                'unit': 's',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['mean', 'max'],
                'displayMode': 'table',
                'placement': 'bottom',
                'showLegend': True,
            },
            'tooltip': {
                'mode': 'multi',
                'sort': 'desc',
            },
        },
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~"$service"}[$__rate_interval])) by (job, le))',
                'legendFormat': '{{job}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_resource_utilization_panel() -> Dict[str, Any]:
    """
    Create a panel for resource utilization.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Resource Utilization',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 24,
            'x': 0,
            'y': 16,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'palette-classic',
                },
                'custom': {
                    'axisCenteredZero': False,
                    'axisColorMode': 'text',
                    'axisLabel': '',
                    'axisPlacement': 'auto',
                    'barAlignment': 0,
                    'drawStyle': 'line',
                    'fillOpacity': 10,
                    'gradientMode': 'none',
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                    'lineInterpolation': 'linear',
                    'lineWidth': 1,
                    'pointSize': 5,
                    'scaleDistribution': {
                        'type': 'linear',
                    },
                    'showPoints': 'never',
                    'spanNulls': True,
                    'stacking': {
                        'group': 'A',
                        'mode': 'none',
                    },
                    'thresholdsStyle': {
                        'mode': 'area',
                    },
                },
                'mappings': [],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'green',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 0.7,
                        },
                        {
                            'color': 'red',
                            'value': 0.85,
                        },
                    ],
                },
                'unit': 'percentunit',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['mean', 'max'],
                'displayMode': 'table',
                'placement': 'bottom',
                'showLegend': True,
            },
            'tooltip': {
                'mode': 'multi',
                'sort': 'desc',
            },
        },
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(rate(container_cpu_usage_seconds_total{container!="", pod=~"$service.*"}[$__rate_interval])) by (pod) / sum(container_spec_cpu_quota{container!="", pod=~"$service.*"} / container_spec_cpu_period{container!="", pod=~"$service.*"}) by (pod)',
                'legendFormat': '{{pod}} - CPU',
                'range': True,
                'refId': 'A',
            },
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(container_memory_working_set_bytes{container!="", pod=~"$service.*"}) by (pod) / sum(container_spec_memory_limit_bytes{container!="", pod=~"$service.*"}) by (pod)',
                'legendFormat': '{{pod}} - Memory',
                'range': True,
                'refId': 'B',
            },
        ],
    }


def create_slo_panel() -> Dict[str, Any]:
    """
    Create a panel for SLO tracking.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'SLO Compliance',
        'type': 'gauge',
        'gridPos': {
            'h': 8,
            'w': 8,
            'x': 0,
            'y': 24,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'thresholds',
                },
                'mappings': [],
                'max': 100,
                'min': 0,
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'red',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 95,
                        },
                        {
                            'color': 'green',
                            'value': 99,
                        },
                    ],
                },
                'unit': 'percent',
            },
            'overrides': [],
        },
        'options': {
            'orientation': 'auto',
            'reduceOptions': {
                'calcs': ['lastNotNull'],
                'fields': '',
                'values': False,
            },
            'showThresholdLabels': False,
            'showThresholdMarkers': True,
        },
        'pluginVersion': '9.5.2',
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': '100 * (1 - (sum(rate(http_requests_total{job=~"$service", status=~"5.."}[$__rate_interval])) / sum(rate(http_requests_total{job=~"$service"}[$__rate_interval]))))',
                'legendFormat': 'Availability',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_error_budget_panel() -> Dict[str, Any]:
    """
    Create a panel for error budget.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Error Budget Remaining',
        'type': 'gauge',
        'gridPos': {
            'h': 8,
            'w': 8,
            'x': 8,
            'y': 24,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'thresholds',
                },
                'mappings': [],
                'max': 100,
                'min': 0,
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'red',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 30,
                        },
                        {
                            'color': 'green',
                            'value': 70,
                        },
                    ],
                },
                'unit': 'percent',
            },
            'overrides': [],
        },
        'options': {
            'orientation': 'auto',
            'reduceOptions': {
                'calcs': ['lastNotNull'],
                'fields': '',
                'values': False,
            },
            'showThresholdLabels': False,
            'showThresholdMarkers': True,
        },
        'pluginVersion': '9.5.2',
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': '100 * (1 - (sum(increase(http_requests_total{job=~"$service", status=~"5.."}[30d])) / (sum(increase(http_requests_total{job=~"$service"}[30d])) * 0.001)))',
                'legendFormat': 'Error Budget',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_alert_status_panel() -> Dict[str, Any]:
    """
    Create a panel for alert status.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Alert Status',
        'type': 'table',
        'gridPos': {
            'h': 8,
            'w': 8,
            'x': 16,
            'y': 24,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'thresholds',
                },
                'custom': {
                    'align': 'auto',
                    'cellOptions': {
                        'type': 'auto',
                    },
                    'filterable': False,
                    'inspect': False,
                },
                'mappings': [],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'green',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 1,
                        },
                        {
                            'color': 'red',
                            'value': 2,
                        },
                    ],
                },
            },
            'overrides': [
                {
                    'matcher': {
                        'id': 'byName',
                        'options': 'Value',
                    },
                    'properties': [
                        {
                            'id': 'mappings',
                            'value': [
                                {
                                    'options': {
                                        '0': {
                                            'color': 'green',
                                            'index': 0,
                                            'text': 'OK',
                                        },
                                        '1': {
                                            'color': 'orange',
                                            'index': 1,
                                            'text': 'Pending',
                                        },
                                        '2': {
                                            'color': 'red',
                                            'index': 2,
                                            'text': 'Firing',
                                        },
                                    },
                                    'type': 'value',
                                },
                            ],
                        },
                        {
                            'id': 'custom.cellOptions',
                            'value': {
                                'type': 'color-text',
                            },
                        },
                    ],
                },
            ],
        },
        'options': {
            'cellHeight': 'sm',
            'footer': {
                'countRows': False,
                'fields': '',
                'reducer': ['sum'],
                'show': False,
            },
            'showHeader': True,
        },
        'pluginVersion': '9.5.2',
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'ALERTS{job=~"$service"}',
                'format': 'table',
                'legendFormat': '__auto',
                'range': True,
                'refId': 'A',
            },
        ],
        'transformations': [
            {
                'id': 'organize',
                'options': {
                    'excludeByName': {
                        'Time': True,
                        '__name__': True,
                        'alertstate': True,
                        'instance': True,
                        'job': False,
                    },
                    'indexByName': {},
                    'renameByName': {
                        'alertname': 'Alert',
                        'job': 'Service',
                        'severity': 'Severity',
                        'Value': 'Status',
                    },
                },
            },
        ],
    }


def create_sre_dashboard() -> Dict[str, Any]:
    """
    Create a dashboard for SRE teams.
    
    Returns:
        Dashboard definition
    """
    return {
        'title': 'SRE Service Dashboard',
        'uid': 'sre-service-dashboard',
        'tags': ['sre', 'technical', 'service'],
        'timezone': 'browser',
        'editable': True,
        'fiscalYearStartMonth': 0,
        'graphTooltip': 0,
        'links': [],
        'liveNow': False,
        'panels': [
            create_service_health_panel(),
            create_error_rate_panel(),
            create_latency_panel(),
            create_resource_utilization_panel(),
            create_slo_panel(),
            create_error_budget_panel(),
            create_alert_status_panel(),
        ],
        'refresh': '10s',
        'schemaVersion': 38,
        'style': 'dark',
        'templating': {
            'list': [
                {
                    'current': {
                        'selected': False,
                        'text': 'Prometheus',
                        'value': 'Prometheus',
                    },
                    'hide': 0,
                    'includeAll': False,
                    'label': 'Data Source',
                    'multi': False,
                    'name': 'DS_PROMETHEUS',
                    'options': [],
                    'query': 'prometheus',
                    'refresh': 1,
                    'regex': '',
                    'skipUrlSync': False,
                    'type': 'datasource',
                },
                {
                    'current': {
                        'selected': True,
                        'text': 'All',
                        'value': '$__all',
                    },
                    'datasource': {
                        'type': 'prometheus',
                        'uid': '${DS_PROMETHEUS}',
                    },
                    'definition': 'label_values(up, job)',
                    'hide': 0,
                    'includeAll': True,
                    'label': 'Service',
                    'multi': True,
                    'name': 'service',
                    'options': [],
                    'query': {
                        'query': 'label_values(up, job)',
                        'refId': 'StandardVariableQuery',
                    },
                    'refresh': 1,
                    'regex': '',
                    'skipUrlSync': False,
                    'sort': 1,
                    'type': 'query',
                },
            ],
        },
        'time': {
            'from': 'now-1h',
            'to': 'now',
        },
        'timepicker': {
            'refresh_intervals': [
                '5s',
                '10s',
                '30s',
                '1m',
                '5m',
                '15m',
                '30m',
                '1h',
                '2h',
                '1d',
            ],
        },
        'weekStart': '',
    }


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Generate SRE Dashboard')
    parser.add_argument('--grafana-url', required=True, help='Grafana URL')
    parser.add_argument('--api-key', required=True, help='Grafana API key')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = create_sre_dashboard()
    
    # Save to file if output path is provided
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(dashboard, f, indent=2)
        print(f'Dashboard saved to {args.output}')
    
    # Upload to Grafana if URL and API key are provided
    if args.grafana_url and args.api_key:
        client = GrafanaClient(args.grafana_url, args.api_key)
        
        # Create folder
        folder = client.create_folder('SRE Dashboards')
        
        # Create dashboard
        result = client.create_or_update_dashboard(dashboard, folder['id'])
        print(f'Dashboard created: {result["url"]}')


if __name__ == '__main__':
    main()
