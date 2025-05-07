/**
 * Advanced error handling with retry and circuit breaker patterns
 * for resilient infrastructure deployments
 */

export interface ErrorHandlerOptions {
    maxRetries: number;
    retryDelay: number;
    circuitBreakerThreshold: number;
    resetTimeout: number;
    onError?: (error: Error) => void;
}

export class ErrorHandler {
    private options: ErrorHandlerOptions;
    private failureCount: Map<string, number> = new Map();
    private circuitOpen: Map<string, boolean> = new Map();
    private resetTimers: Map<string, NodeJS.Timeout> = new Map();

    constructor(options: ErrorHandlerOptions) {
        this.options = options;
    }

    /**
     * Handle an error with retry logic and circuit breaker pattern
     * @param error The error to handle
     * @param context Optional context for categorizing errors
     * @returns Promise that resolves when retries are exhausted or succeeds
     */
    async handleError(error: Error, context: string = 'default'): Promise<void> {
        // Call the onError callback if provided
        if (this.options.onError) {
            this.options.onError(error);
        }

        // Check if circuit breaker is open for this context
        if (this.circuitOpen.get(context)) {
            console.error(`Circuit breaker open for ${context}, not retrying`);
            throw new Error(`Circuit breaker open for ${context}: ${error.message}`);
        }

        // Increment failure count
        const currentFailures = (this.failureCount.get(context) || 0) + 1;
        this.failureCount.set(context, currentFailures);

        // Check if we should open the circuit breaker
        if (currentFailures >= this.options.circuitBreakerThreshold) {
            this.openCircuitBreaker(context);
            throw new Error(`Circuit breaker tripped for ${context} after ${currentFailures} failures: ${error.message}`);
        }

        // Implement retry logic
        if (currentFailures <= this.options.maxRetries) {
            console.warn(`Retrying operation for ${context} (attempt ${currentFailures} of ${this.options.maxRetries})`);
            await this.delay(this.options.retryDelay * currentFailures);
            return; // Allow retry
        }

        // If we've exhausted retries, rethrow the error
        throw new Error(`Max retries (${this.options.maxRetries}) exceeded for ${context}: ${error.message}`);
    }

    /**
     * Open the circuit breaker for a specific context
     * @param context The context to open the circuit breaker for
     */
    private openCircuitBreaker(context: string): void {
        console.error(`Opening circuit breaker for ${context}`);
        this.circuitOpen.set(context, true);

        // Set a timer to reset the circuit breaker
        const timer = setTimeout(() => {
            console.log(`Resetting circuit breaker for ${context}`);
            this.circuitOpen.set(context, false);
            this.failureCount.set(context, 0);
            this.resetTimers.delete(context);
        }, this.options.resetTimeout);

        // Store the timer so we can clear it if needed
        this.resetTimers.set(context, timer);
    }

    /**
     * Reset the circuit breaker for a specific context
     * @param context The context to reset
     */
    resetCircuitBreaker(context: string): void {
        const timer = this.resetTimers.get(context);
        if (timer) {
            clearTimeout(timer);
            this.resetTimers.delete(context);
        }

        this.circuitOpen.set(context, false);
        this.failureCount.set(context, 0);
    }

    /**
     * Reset all circuit breakers
     */
    resetAllCircuitBreakers(): void {
        for (const context of this.circuitOpen.keys()) {
            this.resetCircuitBreaker(context);
        }
    }

    /**
     * Helper method to create a delay
     * @param ms Milliseconds to delay
     * @returns Promise that resolves after the delay
     */
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
