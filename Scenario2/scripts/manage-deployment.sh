#!/bin/bash
set -e

# Configuration
GITHUB_API="https://api.github.com"
WORKFLOW_ID="main-orchestrator.yml"

# Functions
trigger_deployment() {
    local env=$1
    local type=$2
    
    echo "Triggering deployment to $env environment..."
    gh workflow run $WORKFLOW_ID \
        -f environment=$env \
        -f deployment_type=$type
}

monitor_deployment() {
    local run_id=$1
    
    echo "Monitoring deployment progress..."
    while true; do
        status=$(gh run view $run_id --json status -q .status)
        if [[ $status == "completed" ]]; then
            break
        fi
        echo "Deployment status: $status"
        sleep 30
    done
}

rollback_deployment() {
    local env=$1
    
    echo "Initiating rollback for $env environment..."
    gh workflow run rollback.yml -f environment=$env
}

# Main
main() {
    case $1 in
        deploy)
            trigger_deployment $2 $3
            ;;
        monitor)
            monitor_deployment $2
            ;;
        rollback)
            rollback_deployment $2
            ;;
        *)
            echo "Usage: $0 {deploy|monitor|rollback} [environment] [type]"
            exit 1
            ;;
    esac
}

main "$@"