"""
Developer Technical Dashboard Generator.

This module generates Grafana dashboards for development teams to monitor
their services and applications in the e-commerce platform.

Key features:
- Service performance metrics
- Error tracking and debugging
- Endpoint-level metrics
- Dependency monitoring
- Deployment tracking
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


def create_request_rate_panel() -> Dict[str, Any]:
    """
    Create a panel for request rate.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Request Rate by Endpoint',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
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
                        'mode': 'off',
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
                    ],
                },
                'unit': 'reqps',
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
                'expr': 'sum(rate(http_requests_total{job="$service", handler!=""}[$__rate_interval])) by (handler)',
                'legendFormat': '{{handler}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_error_count_panel() -> Dict[str, Any]:
    """
    Create a panel for error count.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Error Count by Endpoint',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 12,
            'y': 0,
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
                    'drawStyle': 'bars',
                    'fillOpacity': 50,
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
                        'mode': 'normal',
                    },
                    'thresholdsStyle': {
                        'mode': 'off',
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
                    ],
                },
                'unit': 'short',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['sum'],
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
                'expr': 'sum(increase(http_requests_total{job="$service", status=~"5..", handler!=""}[$__interval])) by (handler)',
                'legendFormat': '{{handler}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_latency_by_endpoint_panel() -> Dict[str, Any]:
    """
    Create a panel for latency by endpoint.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Latency by Endpoint (p95)',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 24,
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
                'expr': 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="$service", handler!=""}[$__rate_interval])) by (handler, le))',
                'legendFormat': '{{handler}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_dependency_health_panel() -> Dict[str, Any]:
    """
    Create a panel for dependency health.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Dependency Health',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
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
                            'color': 'red',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 0.9,
                        },
                        {
                            'color': 'green',
                            'value': 0.99,
                        },
                    ],
                },
                'unit': 'percentunit',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['mean', 'min'],
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
                'expr': 'sum(rate(dependency_request_total{job="$service", status="success"}[$__rate_interval])) by (dependency) / sum(rate(dependency_request_total{job="$service"}[$__rate_interval])) by (dependency)',
                'legendFormat': '{{dependency}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_deployment_tracking_panel() -> Dict[str, Any]:
    """
    Create a panel for deployment tracking.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Deployments',
        'type': 'timeseries',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 12,
            'y': 16,
        },
        'datasource': {
            'type': 'prometheus',
            'uid': '${DS_PROMETHEUS}',
        },
        'fieldConfig': {
            'defaults': {
                'color': {
                    'mode': 'fixed',
                    'fixedColor': 'blue',
                },
                'custom': {
                    'axisCenteredZero': False,
                    'axisColorMode': 'text',
                    'axisLabel': '',
                    'axisPlacement': 'auto',
                    'barAlignment': 0,
                    'drawStyle': 'line',
                    'fillOpacity': 0,
                    'gradientMode': 'none',
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                    'lineInterpolation': 'linear',
                    'lineWidth': 1,
                    'pointSize': 10,
                    'scaleDistribution': {
                        'type': 'linear',
                    },
                    'showPoints': 'always',
                    'spanNulls': True,
                    'stacking': {
                        'group': 'A',
                        'mode': 'none',
                    },
                    'thresholdsStyle': {
                        'mode': 'off',
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
                    ],
                },
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': [],
                'displayMode': 'list',
                'placement': 'bottom',
                'showLegend': True,
            },
            'tooltip': {
                'mode': 'multi',
                'sort': 'none',
            },
        },
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'deployment_timestamp{job="$service"}',
                'legendFormat': 'Version {{version}}',
                'range': True,
                'refId': 'A',
            },
        ],
        'transformations': [
            {
                'id': 'configFromData',
                'options': {
                    'configRefId': 'A',
                    'mappings': [
                        {
                            'fieldName': 'version',
                            'handlerKey': 'color',
                            'reducerId': 'last',
                        },
                    ],
                },
            },
        ],
    }


def create_error_logs_panel() -> Dict[str, Any]:
    """
    Create a panel for error logs.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Error Logs',
        'type': 'logs',
        'gridPos': {
            'h': 8,
            'w': 24,
            'x': 0,
            'y': 24,
        },
        'datasource': {
            'type': 'loki',
            'uid': '${DS_LOKI}',
        },
        'options': {
            'dedupStrategy': 'none',
            'enableLogDetails': True,
            'prettifyLogMessage': False,
            'showCommonLabels': False,
            'showLabels': False,
            'showTime': True,
            'sortOrder': 'Descending',
            'wrapLogMessage': False,
        },
        'targets': [
            {
                'datasource': {
                    'type': 'loki',
                    'uid': '${DS_LOKI}',
                },
                'editorMode': 'code',
                'expr': '{job="$service"} |= "error" | json',
                'queryType': 'range',
                'refId': 'A',
            },
        ],
    }


def create_developer_dashboard() -> Dict[str, Any]:
    """
    Create a dashboard for developers.
    
    Returns:
        Dashboard definition
    """
    return {
        'title': 'Developer Service Dashboard',
        'uid': 'developer-service-dashboard',
        'tags': ['developer', 'technical', 'service'],
        'timezone': 'browser',
        'editable': True,
        'fiscalYearStartMonth': 0,
        'graphTooltip': 0,
        'links': [],
        'liveNow': False,
        'panels': [
            create_request_rate_panel(),
            create_error_count_panel(),
            create_latency_by_endpoint_panel(),
            create_dependency_health_panel(),
            create_deployment_tracking_panel(),
            create_error_logs_panel(),
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
                    'label': 'Prometheus',
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
                        'selected': False,
                        'text': 'Loki',
                        'value': 'Loki',
                    },
                    'hide': 0,
                    'includeAll': False,
                    'label': 'Loki',
                    'multi': False,
                    'name': 'DS_LOKI',
                    'options': [],
                    'query': 'loki',
                    'refresh': 1,
                    'regex': '',
                    'skipUrlSync': False,
                    'type': 'datasource',
                },
                {
                    'current': {
                        'selected': False,
                        'text': '',
                        'value': '',
                    },
                    'datasource': {
                        'type': 'prometheus',
                        'uid': '${DS_PROMETHEUS}',
                    },
                    'definition': 'label_values(up, job)',
                    'hide': 0,
                    'includeAll': False,
                    'label': 'Service',
                    'multi': False,
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
    parser = argparse.ArgumentParser(description='Generate Developer Dashboard')
    parser.add_argument('--grafana-url', required=True, help='Grafana URL')
    parser.add_argument('--api-key', required=True, help='Grafana API key')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = create_developer_dashboard()
    
    # Save to file if output path is provided
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(dashboard, f, indent=2)
        print(f'Dashboard saved to {args.output}')
    
    # Upload to Grafana if URL and API key are provided
    if args.grafana_url and args.api_key:
        client = GrafanaClient(args.grafana_url, args.api_key)
        
        # Create folder
        folder = client.create_folder('Developer Dashboards')
        
        # Create dashboard
        result = client.create_or_update_dashboard(dashboard, folder['id'])
        print(f'Dashboard created: {result["url"]}')


if __name__ == '__main__':
    main()
