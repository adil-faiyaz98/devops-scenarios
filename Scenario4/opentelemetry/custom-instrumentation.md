# Custom OpenTelemetry Instrumentation for E-commerce Services

This guide provides instructions for adding custom OpenTelemetry instrumentation to e-commerce microservices.

## Overview

Custom instrumentation allows us to capture business-specific metrics and traces that are important for e-commerce operations, such as:

- Order processing times
- Cart abandonment events
- Payment processing metrics
- Inventory updates
- User journey tracking
- Product search performance

## Implementation Examples

### Java (Spring Boot) Example

```java
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.metrics.LongCounter;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private final Tracer tracer;
    private final LongCounter orderCounter;
    private final LongCounter orderValueCounter;

    public OrderService() {
        // Get tracer
        tracer = GlobalOpenTelemetry.getTracer("com.ecommerce.order");
        
        // Get meter
        Meter meter = GlobalOpenTelemetry.getMeter("com.ecommerce.order");
        
        // Create counters
        orderCounter = meter.counterBuilder("orders.created")
                .setDescription("Number of orders created")
                .setUnit("1")
                .build();
        
        orderValueCounter = meter.counterBuilder("orders.value")
                .setDescription("Total value of orders")
                .setUnit("USD")
                .build();
    }

    public Order createOrder(Cart cart, User user) {
        // Create a span for order creation
        Span span = tracer.spanBuilder("createOrder")
                .setAttribute("user.id", user.getId())
                .setAttribute("cart.id", cart.getId())
                .setAttribute("cart.items", cart.getItemCount())
                .setAttribute("cart.value", cart.getTotalValue())
                .startSpan();
        
        try (Scope scope = span.makeCurrent()) {
            // Business logic to create order
            Order order = processOrder(cart, user);
            
            // Record metrics
            orderCounter.add(1, Attributes.builder()
                    .put("payment.method", order.getPaymentMethod())
                    .put("user.type", user.getType())
                    .put("order.type", order.getType())
                    .build());
            
            orderValueCounter.add(order.getTotalValue(), Attributes.builder()
                    .put("payment.method", order.getPaymentMethod())
                    .put("user.type", user.getType())
                    .build());
            
            // Add order result to span
            span.setAttribute("order.id", order.getId());
            span.setAttribute("order.status", order.getStatus());
            
            return order;
        } catch (Exception e) {
            span.recordException(e);
            span.setStatus(StatusCode.ERROR, e.getMessage());
            throw e;
        } finally {
            span.end();
        }
    }
}
```

### Node.js Example

```javascript
const { trace, metrics, context } = require('@opentelemetry/api');
const tracer = trace.getTracer('com.ecommerce.inventory');
const meter = metrics.getMeter('com.ecommerce.inventory');

// Create metrics
const stockLevelGauge = meter.createObservableGauge('inventory.stock.level', {
  description: 'Current stock level',
  unit: 'items',
});

const lowStockCounter = meter.createCounter('inventory.low.stock', {
  description: 'Number of low stock events',
  unit: 'events',
});

// Register callback for observable gauge
meter.addBatchObservableCallback(
  async (observableResult) => {
    // Get current inventory levels from database
    const inventoryLevels = await getInventoryLevels();
    
    // Record each product's inventory level
    for (const product of inventoryLevels) {
      observableResult.observe(
        stockLevelGauge,
        product.quantity,
        {
          'product.id': product.id,
          'product.category': product.category,
          'warehouse.id': product.warehouseId,
        }
      );
    }
  },
  [stockLevelGauge]
);

// Function with custom span
async function updateInventory(productId, quantity, operation) {
  const span = tracer.startSpan('updateInventory', {
    attributes: {
      'product.id': productId,
      'quantity': quantity,
      'operation': operation,
    },
  });
  
  // Set current span as active
  return context.with(trace.setSpan(context.active(), span), async () => {
    try {
      // Business logic
      const result = await performInventoryUpdate(productId, quantity, operation);
      
      // Check if stock is low after update
      if (result.newQuantity < result.threshold) {
        lowStockCounter.add(1, {
          'product.id': productId,
          'product.category': result.category,
          'warehouse.id': result.warehouseId,
        });
        
        // Create child span for low stock event
        const lowStockSpan = tracer.startSpan('lowStockDetected');
        lowStockSpan.setAttribute('product.id', productId);
        lowStockSpan.setAttribute('current.quantity', result.newQuantity);
        lowStockSpan.setAttribute('threshold', result.threshold);
        lowStockSpan.end();
      }
      
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (error) {
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: error.message,
      });
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}
```

### Python Example

```python
from opentelemetry import trace
from opentelemetry import metrics
from opentelemetry.trace.status import Status, StatusCode
import time

# Get tracer and meter
tracer = trace.get_tracer("com.ecommerce.search")
meter = metrics.get_meter("com.ecommerce.search")

# Create metrics
search_counter = meter.create_counter(
    name="search.requests",
    description="Number of search requests",
    unit="1",
)

search_latency = meter.create_histogram(
    name="search.latency",
    description="Search latency",
    unit="ms",
)

search_results = meter.create_histogram(
    name="search.results.count",
    description="Number of search results",
    unit="1",
)

def perform_product_search(query, filters=None, sort=None, page=1, page_size=20):
    # Start span for search operation
    with tracer.start_as_current_span("product_search") as span:
        # Add attributes to span
        span.set_attribute("search.query", query)
        span.set_attribute("search.page", page)
        span.set_attribute("search.page_size", page_size)
        
        if filters:
            span.set_attribute("search.filters", str(filters))
        if sort:
            span.set_attribute("search.sort", sort)
        
        # Record search request metric
        search_counter.add(1, {
            "search.type": "product",
            "search.has_filters": "true" if filters else "false",
        })
        
        try:
            # Record start time
            start_time = time.time()
            
            # Perform search
            with tracer.start_as_current_span("elasticsearch_query") as es_span:
                results = execute_search_query(query, filters, sort, page, page_size)
                es_span.set_attribute("elasticsearch.took", results.get("took", 0))
                es_span.set_attribute("elasticsearch.hits", len(results.get("hits", [])))
            
            # Calculate latency
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            # Record metrics
            search_latency.record(latency, {
                "search.type": "product",
                "search.has_filters": "true" if filters else "false",
            })
            
            search_results.record(len(results.get("hits", [])), {
                "search.type": "product",
                "search.query": query,
            })
            
            # Add result info to span
            span.set_attribute("search.results.count", len(results.get("hits", [])))
            span.set_attribute("search.latency", latency)
            
            # Set span status
            span.set_status(Status(StatusCode.OK))
            
            return results
        except Exception as e:
            # Record error
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
```

## Best Practices

1. **Consistent Naming**: Use a consistent naming convention for metrics and spans across all services
   - Format: `domain.entity.action` (e.g., `order.checkout.completed`, `product.search.latency`)

2. **Relevant Attributes**: Include business-relevant attributes with your telemetry data
   - User segments
   - Product categories
   - Payment methods
   - Geographic regions

3. **Performance Considerations**: 
   - Use sampling for high-volume services
   - Batch metrics when possible
   - Consider the overhead of excessive instrumentation

4. **Correlation IDs**:
   - Ensure proper propagation of trace context between services
   - Include business IDs (order ID, user ID) as span attributes for easier correlation

5. **Error Handling**:
   - Always record exceptions in spans
   - Set appropriate span status on error
   - Include error details as span attributes

## Custom Business Metrics

| Metric Name | Type | Description | Key Attributes |
|-------------|------|-------------|----------------|
| `order.checkout.started` | Counter | Number of checkout processes initiated | user_type, device_type |
| `order.checkout.completed` | Counter | Number of successful checkouts | payment_method, user_type |
| `order.checkout.abandoned` | Counter | Number of abandoned checkouts | step, user_type, cart_value |
| `order.value` | Counter | Total value of orders | product_category, payment_method |
| `product.view` | Counter | Number of product views | product_id, category, referrer |
| `product.add_to_cart` | Counter | Number of add-to-cart actions | product_id, category, price_range |
| `inventory.stock.level` | Gauge | Current stock level | product_id, warehouse |
| `search.latency` | Histogram | Search response time | query_complexity, filters_count |
| `payment.processing.time` | Histogram | Payment processing duration | payment_method, amount_range |
| `user.session.duration` | Histogram | User session length | user_type, device_type |
