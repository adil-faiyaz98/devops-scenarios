# Trace Correlation Guide

This guide explains how to correlate logs, metrics, and traces across services in the e-commerce platform.

## Overview

Correlation of telemetry data is essential for effective troubleshooting and performance analysis. This document outlines the approach for correlating different types of observability data across our 500+ microservices.

## Correlation Identifiers

The following identifiers are used for correlation:

1. **Trace ID**: Unique identifier for a request as it flows through the system
2. **Span ID**: Identifier for a specific operation within a trace
3. **Request ID**: Application-level identifier for a user request
4. **Session ID**: Identifier for a user session
5. **Order ID**: Business identifier for an order
6. **User ID**: Identifier for a user

## Implementation

### 1. Context Propagation

All services must propagate the trace context using W3C Trace Context headers:

- `traceparent`: Contains trace ID and parent span ID
- `tracestate`: Contains vendor-specific trace information

Example:
```
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
tracestate: congo=t61rcWkgMzE
```

### 2. Log Correlation

All log entries should include the trace ID and span ID:

```json
{
  "timestamp": "2023-05-15T08:12:34.567Z",
  "level": "INFO",
  "message": "Processing order",
  "service": "order-service",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b7ad6b7169203331",
  "order_id": "ORD-12345",
  "user_id": "USR-6789"
}
```

### 3. Metric Correlation

Metrics should include trace exemplars when possible:

```
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1",service="order-service",endpoint="/api/orders"} 24 # {trace_id="0af7651916cd43dd8448eb211c80319c"}
http_request_duration_seconds_bucket{le="0.5",service="order-service",endpoint="/api/orders"} 36 # {trace_id="0af7651916cd43dd8448eb211c80319c"}
http_request_duration_seconds_bucket{le="1",service="order-service",endpoint="/api/orders"} 37
http_request_duration_seconds_bucket{le="5",service="order-service",endpoint="/api/orders"} 37
http_request_duration_seconds_bucket{le="+Inf",service="order-service",endpoint="/api/orders"} 37
http_request_duration_seconds_sum{service="order-service",endpoint="/api/orders"} 8.312
http_request_duration_seconds_count{service="order-service",endpoint="/api/orders"} 37
```

### 4. Business Context

Add business context to spans as attributes:

```java
Span span = tracer.spanBuilder("processOrder")
    .setAttribute("order.id", orderId)
    .setAttribute("user.id", userId)
    .setAttribute("cart.value", cartValue)
    .setAttribute("payment.method", paymentMethod)
    .startSpan();
```

## Correlation in Practice

### Tracing a User Journey

1. **Start with a User Session**:
   - Identify the session ID from logs or metrics
   - Query Jaeger for traces containing this session ID

2. **Follow the Order Flow**:
   - From the checkout trace, identify the order ID
   - Query for all spans with this order ID across services

3. **Analyze Performance**:
   - Use Grafana to view metrics for the services involved
   - Look for exemplars matching the trace ID

4. **Investigate Errors**:
   - If errors occurred, check logs with the same trace ID
   - Analyze the span where the error occurred

## Correlation Tools

### Grafana Explore

Grafana Explore allows you to correlate logs, metrics, and traces:

1. Find a metric with high latency
2. Click on an exemplar to view the trace
3. From the trace view, find related logs

### Jaeger UI

Jaeger UI provides trace visualization and analysis:

1. Search for traces by service, operation, or tags
2. View the trace timeline and span details
3. See logs attached to spans

### Elasticsearch Queries

Query logs with trace IDs:

```
GET /logs-*/_search
{
  "query": {
    "match": {
      "trace_id": "0af7651916cd43dd8448eb211c80319c"
    }
  },
  "sort": [
    {
      "timestamp": {
        "order": "asc"
      }
    }
  ]
}
```

## Best Practices

1. **Consistent Naming**: Use consistent naming for services and operations
2. **Appropriate Sampling**: Use higher sampling rates for critical paths
3. **Business Context**: Always include business identifiers in spans
4. **Error Tagging**: Tag spans with error details when exceptions occur
5. **Baggage Items**: Use OpenTelemetry baggage for propagating business context

## Troubleshooting Common Issues

### Missing Correlation

If correlation is missing:

1. Check that the service is properly instrumented
2. Verify that context propagation is working
3. Ensure HTTP headers are being passed correctly

### Broken Traces

If traces appear broken:

1. Check for missing instrumentation in intermediary services
2. Verify that async operations properly propagate context
3. Check for sampling issues that might drop spans
