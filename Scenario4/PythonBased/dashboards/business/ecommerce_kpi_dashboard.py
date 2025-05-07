"""
E-commerce Business KPI Dashboard Generator.

This module generates Grafana dashboards for business KPIs in the e-commerce platform.
It uses the Grafana API to create and update dashboards programmatically.

Key features:
- Revenue and order metrics
- Conversion funnel visualization
- Customer behavior analysis
- Product performance metrics
- Real-time sales monitoring
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


def create_revenue_panel() -> Dict[str, Any]:
    """
    Create a panel for revenue metrics.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Revenue Metrics',
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
                    'lineInterpolation': 'smooth',
                    'lineWidth': 2,
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
                'unit': 'currencyUSD',
            },
            'overrides': [],
        },
        'options': {
            'legend': {
                'calcs': ['mean', 'lastNotNull', 'max'],
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
                'expr': 'sum(rate(ecommerce_revenue_total[$__rate_interval])) by (product_category)',
                'legendFormat': '{{product_category}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_conversion_funnel_panel() -> Dict[str, Any]:
    """
    Create a panel for conversion funnel.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Conversion Funnel',
        'type': 'barchart',
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
                    'fillOpacity': 80,
                    'gradientMode': 'none',
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                    'lineWidth': 1,
                    'scaleDistribution': {
                        'type': 'linear',
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
            'barWidth': 0.5,
            'groupWidth': 0.7,
            'legend': {
                'calcs': [],
                'displayMode': 'list',
                'placement': 'bottom',
                'showLegend': False,
            },
            'orientation': 'auto',
            'showValue': 'auto',
            'stacking': 'none',
            'tooltip': {
                'mode': 'single',
                'sort': 'none',
            },
            'xTickLabelRotation': 0,
            'xTickLabelSpacing': 0,
        },
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_page_views_total)',
                'legendFormat': 'Page Views',
                'range': True,
                'refId': 'A',
            },
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_product_views_total)',
                'legendFormat': 'Product Views',
                'range': True,
                'refId': 'B',
            },
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_cart_adds_total)',
                'legendFormat': 'Add to Cart',
                'range': True,
                'refId': 'C',
            },
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_checkout_starts_total)',
                'legendFormat': 'Checkout Started',
                'range': True,
                'refId': 'D',
            },
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_orders_total)',
                'legendFormat': 'Orders Completed',
                'range': True,
                'refId': 'E',
            },
        ],
    }


def create_customer_metrics_panel() -> Dict[str, Any]:
    """
    Create a panel for customer metrics.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Customer Metrics',
        'type': 'stat',
        'gridPos': {
            'h': 4,
            'w': 8,
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
                    'mode': 'thresholds',
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
                            'value': 1,
                        },
                        {
                            'color': 'green',
                            'value': 2,
                        },
                    ],
                },
                'unit': 'percent',
            },
            'overrides': [],
        },
        'options': {
            'colorMode': 'value',
            'graphMode': 'area',
            'justifyMode': 'auto',
            'orientation': 'auto',
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
                'expr': 'ecommerce_conversion_rate',
                'legendFormat': 'Conversion Rate',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_cart_abandonment_panel() -> Dict[str, Any]:
    """
    Create a panel for cart abandonment rate.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Cart Abandonment Rate',
        'type': 'stat',
        'gridPos': {
            'h': 4,
            'w': 8,
            'x': 8,
            'y': 8,
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
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'green',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 50,
                        },
                        {
                            'color': 'red',
                            'value': 70,
                        },
                    ],
                },
                'unit': 'percent',
            },
            'overrides': [],
        },
        'options': {
            'colorMode': 'value',
            'graphMode': 'area',
            'justifyMode': 'auto',
            'orientation': 'auto',
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
                'expr': 'ecommerce_cart_abandonment_rate',
                'legendFormat': 'Cart Abandonment Rate',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_average_order_value_panel() -> Dict[str, Any]:
    """
    Create a panel for average order value.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Average Order Value',
        'type': 'stat',
        'gridPos': {
            'h': 4,
            'w': 8,
            'x': 16,
            'y': 8,
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
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [
                        {
                            'color': 'red',
                            'value': None,
                        },
                        {
                            'color': 'orange',
                            'value': 50,
                        },
                        {
                            'color': 'green',
                            'value': 100,
                        },
                    ],
                },
                'unit': 'currencyUSD',
            },
            'overrides': [],
        },
        'options': {
            'colorMode': 'value',
            'graphMode': 'area',
            'justifyMode': 'auto',
            'orientation': 'auto',
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
                'expr': 'ecommerce_average_order_value',
                'legendFormat': 'Average Order Value',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_top_products_panel() -> Dict[str, Any]:
    """
    Create a panel for top products.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Top Products by Revenue',
        'type': 'table',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 0,
            'y': 12,
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
                    'filterable': True,
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
                            'id': 'unit',
                            'value': 'currencyUSD',
                        },
                        {
                            'id': 'custom.width',
                            'value': 150,
                        },
                    ],
                },
                {
                    'matcher': {
                        'id': 'byName',
                        'options': 'product_name',
                    },
                    'properties': [
                        {
                            'id': 'custom.width',
                            'value': 300,
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
                'expr': 'topk(10, sum(ecommerce_product_revenue_total) by (product_name))',
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
                    },
                    'indexByName': {},
                    'renameByName': {},
                },
            },
            {
                'id': 'sortBy',
                'options': {
                    'fields': {},
                    'sort': [
                        {
                            'field': 'Value',
                            'order': 'desc',
                        },
                    ],
                },
            },
        ],
    }


def create_customer_segments_panel() -> Dict[str, Any]:
    """
    Create a panel for customer segments.
    
    Returns:
        Panel definition
    """
    return {
        'title': 'Revenue by Customer Segment',
        'type': 'piechart',
        'gridPos': {
            'h': 8,
            'w': 12,
            'x': 12,
            'y': 12,
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
                    'hideFrom': {
                        'legend': False,
                        'tooltip': False,
                        'viz': False,
                    },
                },
                'mappings': [],
                'unit': 'currencyUSD',
            },
            'overrides': [],
        },
        'options': {
            'displayLabels': ['percent'],
            'legend': {
                'displayMode': 'table',
                'placement': 'right',
                'showLegend': True,
                'values': ['value'],
            },
            'pieType': 'pie',
            'reduceOptions': {
                'calcs': ['lastNotNull'],
                'fields': '',
                'values': False,
            },
            'tooltip': {
                'mode': 'single',
                'sort': 'none',
            },
        },
        'pluginVersion': '9.5.2',
        'targets': [
            {
                'datasource': {
                    'type': 'prometheus',
                    'uid': '${DS_PROMETHEUS}',
                },
                'editorMode': 'code',
                'expr': 'sum(ecommerce_revenue_by_segment_total) by (customer_segment)',
                'legendFormat': '{{customer_segment}}',
                'range': True,
                'refId': 'A',
            },
        ],
    }


def create_ecommerce_kpi_dashboard() -> Dict[str, Any]:
    """
    Create a dashboard for e-commerce KPIs.
    
    Returns:
        Dashboard definition
    """
    return {
        'title': 'E-commerce Business KPIs',
        'uid': 'ecommerce-business-kpis',
        'tags': ['business', 'e-commerce', 'kpi'],
        'timezone': 'browser',
        'editable': True,
        'fiscalYearStartMonth': 0,
        'graphTooltip': 0,
        'links': [],
        'liveNow': False,
        'panels': [
            create_revenue_panel(),
            create_conversion_funnel_panel(),
            create_customer_metrics_panel(),
            create_cart_abandonment_panel(),
            create_average_order_value_panel(),
            create_top_products_panel(),
            create_customer_segments_panel(),
        ],
        'refresh': '5m',
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
                        'text': ['Last 24 hours'],
                        'value': ['now-24h'],
                    },
                    'hide': 0,
                    'includeAll': False,
                    'label': 'Time Range',
                    'multi': True,
                    'name': 'timeRange',
                    'options': [
                        {
                            'selected': True,
                            'text': 'Last 24 hours',
                            'value': 'now-24h',
                        },
                        {
                            'selected': False,
                            'text': 'Last 7 days',
                            'value': 'now-7d',
                        },
                        {
                            'selected': False,
                            'text': 'Last 30 days',
                            'value': 'now-30d',
                        },
                        {
                            'selected': False,
                            'text': 'Last 90 days',
                            'value': 'now-90d',
                        },
                    ],
                    'query': 'now-24h, now-7d, now-30d, now-90d',
                    'queryValue': '',
                    'skipUrlSync': False,
                    'type': 'custom',
                },
            ],
        },
        'time': {
            'from': 'now-24h',
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
    parser = argparse.ArgumentParser(description='Generate E-commerce KPI Dashboard')
    parser.add_argument('--grafana-url', required=True, help='Grafana URL')
    parser.add_argument('--api-key', required=True, help='Grafana API key')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = create_ecommerce_kpi_dashboard()
    
    # Save to file if output path is provided
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(dashboard, f, indent=2)
        print(f'Dashboard saved to {args.output}')
    
    # Upload to Grafana if URL and API key are provided
    if args.grafana_url and args.api_key:
        client = GrafanaClient(args.grafana_url, args.api_key)
        
        # Create folder
        folder = client.create_folder('Business KPIs')
        
        # Create dashboard
        result = client.create_or_update_dashboard(dashboard, folder['id'])
        print(f'Dashboard created: {result["url"]}')


if __name__ == '__main__':
    main()
