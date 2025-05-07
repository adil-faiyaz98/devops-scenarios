import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('error_rate');
const anomalyDetectionLatency = new Trend('anomaly_detection_latency');
const rootCauseAnalysisLatency = new Trend('root_cause_analysis_latency');
const predictiveAlertingLatency = new Trend('predictive_alerting_latency');
const dashboardLoadLatency = new Trend('dashboard_load_latency');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Test data
const services = [
  'product-service',
  'cart-service',
  'checkout-service',
  'payment-service',
  'inventory-service',
  'user-service',
  'search-service',
  'recommendation-service',
  'notification-service',
  'shipping-service'
];

const metricNames = [
  'cpu_usage',
  'memory_usage',
  'response_time',
  'error_rate',
  'request_count',
  'queue_length',
  'database_connections',
  'cache_hit_ratio',
  'throughput',
  'saturation'
];

// Helper functions
function generateMetricData(count = 10) {
  const metrics = [];
  const now = new Date().toISOString();
  
  for (let i = 0; i < count; i++) {
    metrics.push({
      timestamp: now,
      service: randomItem(services),
      metric_name: randomItem(metricNames),
      value: Math.random() * 100
    });
  }
  
  return metrics;
}

function generateAnomalyData() {
  const service = randomItem(services);
  const metricName = randomItem(metricNames);
  
  return {
    timestamp: new Date().toISOString(),
    service: service,
    metric_name: metricName,
    value: Math.random() * 100,
    expected_value: Math.random() * 50,
    is_anomaly: true,
    anomaly_score: Math.random(),
    anomaly_probability: Math.random()
  };
}

// Default options
export const options = {
  scenarios: {
    anomaly_detection: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 50,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 30 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 10 },
        { duration: '30s', target: 0 }
      ],
    },
    root_cause_analysis: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 5,
      maxVUs: 20,
      startTime: '30s'
    },
    predictive_alerting: {
      executor: 'per-vu-iterations',
      vus: 5,
      iterations: 10,
      maxDuration: '4m',
      startTime: '1m'
    },
    dashboard_load: {
      executor: 'constant-vus',
      vus: 10,
      duration: '5m',
      startTime: '0s'
    }
  },
  thresholds: {
    error_rate: ['rate<0.1'],  // Error rate should be less than 10%
    anomaly_detection_latency: ['p(95)<500'],  // 95% of requests should be under 500ms
    root_cause_analysis_latency: ['p(95)<1000'],  // 95% of requests should be under 1000ms
    predictive_alerting_latency: ['p(95)<2000'],  // 95% of requests should be under 2000ms
    dashboard_load_latency: ['p(95)<3000']  // 95% of requests should be under 3000ms
  }
};

// Test anomaly detection API
export function anomalyDetection() {
  const metrics = generateMetricData(20);
  
  const payload = JSON.stringify({
    metrics: metrics
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    }
  };
  
  const startTime = new Date();
  const response = http.post(`${BASE_URL}/api/v1/anomaly-detection/detect`, payload, params);
  const endTime = new Date();
  
  const duration = endTime - startTime;
  anomalyDetectionLatency.add(duration);
  
  const success = check(response, {
    'anomaly detection status is 200': (r) => r.status === 200,
    'anomaly detection response has results': (r) => r.json().hasOwnProperty('results')
  });
  
  errorRate.add(!success);
  
  sleep(1);
}

// Test root cause analysis API
export function rootCauseAnalysis() {
  const anomaly = generateAnomalyData();
  
  const payload = JSON.stringify({
    anomaly: anomaly
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    }
  };
  
  const startTime = new Date();
  const response = http.post(`${BASE_URL}/api/v1/root-cause-analysis/analyze`, payload, params);
  const endTime = new Date();
  
  const duration = endTime - startTime;
  rootCauseAnalysisLatency.add(duration);
  
  const success = check(response, {
    'root cause analysis status is 200': (r) => r.status === 200,
    'root cause analysis response has root_causes': (r) => r.json().hasOwnProperty('root_causes')
  });
  
  errorRate.add(!success);
  
  sleep(2);
}

// Test predictive alerting API
export function predictiveAlerting() {
  const metrics = generateMetricData(50);
  
  const payload = JSON.stringify({
    metrics: metrics,
    horizon_hours: 24
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    }
  };
  
  const startTime = new Date();
  const response = http.post(`${BASE_URL}/api/v1/predictive-alerting/predict`, payload, params);
  const endTime = new Date();
  
  const duration = endTime - startTime;
  predictiveAlertingLatency.add(duration);
  
  const success = check(response, {
    'predictive alerting status is 200': (r) => r.status === 200,
    'predictive alerting response has predictions': (r) => r.json().hasOwnProperty('predictions')
  });
  
  errorRate.add(!success);
  
  sleep(5);
}

// Test dashboard load
export function dashboardLoad() {
  const dashboardTypes = ['business', 'sre', 'developer'];
  const dashboardType = randomItem(dashboardTypes);
  
  const params = {
    headers: {
      'Authorization': `Bearer ${API_KEY}`
    }
  };
  
  const startTime = new Date();
  const response = http.get(`${BASE_URL}/api/v1/dashboards/${dashboardType}`, params);
  const endTime = new Date();
  
  const duration = endTime - startTime;
  dashboardLoadLatency.add(duration);
  
  const success = check(response, {
    'dashboard load status is 200': (r) => r.status === 200,
    'dashboard response has panels': (r) => r.json().hasOwnProperty('panels')
  });
  
  errorRate.add(!success);
  
  sleep(3);
}

// Main function
export default function() {
  const scenario = __ENV.SCENARIO || 'all';
  
  if (scenario === 'anomaly_detection' || scenario === 'all') {
    anomalyDetection();
  }
  
  if (scenario === 'root_cause_analysis' || scenario === 'all') {
    rootCauseAnalysis();
  }
  
  if (scenario === 'predictive_alerting' || scenario === 'all') {
    predictiveAlerting();
  }
  
  if (scenario === 'dashboard_load' || scenario === 'all') {
    dashboardLoad();
  }
}
