#!/bin/bash

# Script to run k6 performance tests for the AI-driven Observability Pipeline

# Default values
BASE_URL=${BASE_URL:-"http://localhost:8080"}
API_KEY=${API_KEY:-"test-api-key"}
OUTPUT_DIR=${OUTPUT_DIR:-"./results"}
SCENARIO=${SCENARIO:-"all"}

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Print test configuration
echo "Running k6 performance tests with the following configuration:"
echo "  Base URL: $BASE_URL"
echo "  API Key: ${API_KEY:0:3}...${API_KEY: -3}"
echo "  Output Directory: $OUTPUT_DIR"
echo "  Scenario: $SCENARIO"
echo ""

# Function to run a test
run_test() {
    local scenario=$1
    local output_file="$OUTPUT_DIR/k6-$scenario-$(date +%Y%m%d-%H%M%S).json"
    
    echo "Running $scenario test..."
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --env SCENARIO="$scenario" \
        --out json="$output_file" \
        load_test.js
    
    echo "Test completed. Results saved to $output_file"
    echo ""
}

# Run tests based on scenario
case "$SCENARIO" in
    "anomaly_detection")
        run_test "anomaly_detection"
        ;;
    "root_cause_analysis")
        run_test "root_cause_analysis"
        ;;
    "predictive_alerting")
        run_test "predictive_alerting"
        ;;
    "dashboard_load")
        run_test "dashboard_load"
        ;;
    "all")
        echo "Running all tests sequentially..."
        run_test "anomaly_detection"
        run_test "root_cause_analysis"
        run_test "predictive_alerting"
        run_test "dashboard_load"
        ;;
    *)
        echo "Error: Unknown scenario '$SCENARIO'"
        echo "Available scenarios: anomaly_detection, root_cause_analysis, predictive_alerting, dashboard_load, all"
        exit 1
        ;;
esac

# Generate summary report
echo "Generating summary report..."
python3 generate_report.py --input-dir "$OUTPUT_DIR" --output-file "$OUTPUT_DIR/summary_report.html"

echo "Performance testing completed!"
