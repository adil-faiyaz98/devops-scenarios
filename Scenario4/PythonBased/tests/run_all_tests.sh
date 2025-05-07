#!/bin/bash

# Script to run all tests for the AI-driven Observability Pipeline

# Default values
ENVIRONMENT=${ENVIRONMENT:-"dev"}
BASE_URL=${BASE_URL:-"http://localhost:8080"}
API_KEY=${API_KEY:-"test-api-key"}
ADMIN_API_KEY=${ADMIN_API_KEY:-"admin-api-key"}
OUTPUT_DIR=${OUTPUT_DIR:-"./test-results"}
NAMESPACE=${NAMESPACE:-"default"}
SERVICE=${SERVICE:-"observability-pipeline"}
DEPENDENCY=${DEPENDENCY:-"elasticsearch"}

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/unit"
mkdir -p "$OUTPUT_DIR/integration"
mkdir -p "$OUTPUT_DIR/performance"
mkdir -p "$OUTPUT_DIR/security"
mkdir -p "$OUTPUT_DIR/chaos"

# Print test configuration
echo "Running all tests with the following configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Base URL: $BASE_URL"
echo "  API Key: ${API_KEY:0:3}...${API_KEY: -3}"
echo "  Admin API Key: ${ADMIN_API_KEY:0:3}...${ADMIN_API_KEY: -3}"
echo "  Output Directory: $OUTPUT_DIR"
echo "  Namespace: $NAMESPACE"
echo "  Service: $SERVICE"
echo "  Dependency: $DEPENDENCY"
echo ""

# Function to run tests and track results
run_test() {
    local test_type=$1
    local test_command=$2
    local output_file=$3
    
    echo "Running $test_type tests..."
    echo "Command: $test_command"
    echo "Output: $output_file"
    
    # Run the test
    eval "$test_command" > "$output_file" 2>&1
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ $test_type tests PASSED"
    else
        echo "❌ $test_type tests FAILED (exit code: $exit_code)"
    fi
    
    echo ""
    
    return $exit_code
}

# Initialize result tracking
unit_result=0
integration_result=0
performance_result=0
security_result=0
chaos_result=0

# Run unit tests
unit_command="cd .. && python -m pytest tests/unit -v --junitxml=$OUTPUT_DIR/unit/junit.xml"
run_test "Unit" "$unit_command" "$OUTPUT_DIR/unit/output.log"
unit_result=$?

# Run integration tests
integration_command="cd .. && python -m pytest tests/integration -v --junitxml=$OUTPUT_DIR/integration/junit.xml"
run_test "Integration" "$integration_command" "$OUTPUT_DIR/integration/output.log"
integration_result=$?

# Run performance tests with k6
performance_command="cd performance/k6 && BASE_URL=$BASE_URL API_KEY=$API_KEY OUTPUT_DIR=$OUTPUT_DIR/performance ./run_tests.sh"
run_test "Performance" "$performance_command" "$OUTPUT_DIR/performance/output.log"
performance_result=$?

# Run security tests
security_command="cd .. && python -m tests.security.security_tests --base-url=$BASE_URL --api-key=$API_KEY --admin-api-key=$ADMIN_API_KEY --output=$OUTPUT_DIR/security/junit.xml"
run_test "Security" "$security_command" "$OUTPUT_DIR/security/output.log"
security_result=$?

# Run chaos tests
chaos_command="cd .. && python -m tests.chaos.chaos_tests --namespace=$NAMESPACE --service=$SERVICE --dependency=$DEPENDENCY --test-type=all --output=$OUTPUT_DIR/chaos/results.json"
run_test "Chaos" "$chaos_command" "$OUTPUT_DIR/chaos/output.log"
chaos_result=$?

# Generate summary report
echo "Generating summary report..."
cat > "$OUTPUT_DIR/summary.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Test Results Summary</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }
        h1, h2 {
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .summary {
            margin-bottom: 30px;
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
        .pass {
            color: green;
            font-weight: bold;
        }
        .fail {
            color: red;
            font-weight: bold;
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
        <h1>Test Results Summary</h1>
        
        <div class="summary">
            <h2>Summary</h2>
            <p>Report generated at: $(date '+%Y-%m-%d %H:%M:%S')</p>
            <p>Environment: $ENVIRONMENT</p>
        </div>
        
        <table>
            <tr>
                <th>Test Type</th>
                <th>Result</th>
                <th>Details</th>
            </tr>
            <tr>
                <td>Unit Tests</td>
                <td class="$([ $unit_result -eq 0 ] && echo 'pass' || echo 'fail')">$([ $unit_result -eq 0 ] && echo 'PASS' || echo 'FAIL')</td>
                <td><a href="unit/junit.xml">XML Report</a> | <a href="unit/output.log">Log</a></td>
            </tr>
            <tr>
                <td>Integration Tests</td>
                <td class="$([ $integration_result -eq 0 ] && echo 'pass' || echo 'fail')">$([ $integration_result -eq 0 ] && echo 'PASS' || echo 'FAIL')</td>
                <td><a href="integration/junit.xml">XML Report</a> | <a href="integration/output.log">Log</a></td>
            </tr>
            <tr>
                <td>Performance Tests</td>
                <td class="$([ $performance_result -eq 0 ] && echo 'pass' || echo 'fail')">$([ $performance_result -eq 0 ] && echo 'PASS' || echo 'FAIL')</td>
                <td><a href="performance/summary_report.html">HTML Report</a> | <a href="performance/output.log">Log</a></td>
            </tr>
            <tr>
                <td>Security Tests</td>
                <td class="$([ $security_result -eq 0 ] && echo 'pass' || echo 'fail')">$([ $security_result -eq 0 ] && echo 'PASS' || echo 'FAIL')</td>
                <td><a href="security/junit.xml">XML Report</a> | <a href="security/output.log">Log</a></td>
            </tr>
            <tr>
                <td>Chaos Tests</td>
                <td class="$([ $chaos_result -eq 0 ] && echo 'pass' || echo 'fail')">$([ $chaos_result -eq 0 ] && echo 'PASS' || echo 'FAIL')</td>
                <td><a href="chaos/results.json">JSON Report</a> | <a href="chaos/output.log">Log</a></td>
            </tr>
        </table>
        
        <div class="footer">
            <p>Generated by AI-driven Observability Pipeline Test Runner</p>
        </div>
    </div>
</body>
</html>
EOF

echo "Summary report generated: $OUTPUT_DIR/summary.html"

# Calculate overall result
overall_result=$(( $unit_result + $integration_result + $performance_result + $security_result + $chaos_result ))

if [ $overall_result -eq 0 ]; then
    echo "✅ All tests PASSED"
else
    echo "❌ Some tests FAILED"
fi

exit $overall_result
