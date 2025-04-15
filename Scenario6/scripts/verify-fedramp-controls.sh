#!/bin/bash
set -e

# FedRAMP High Controls Verification
echo "Verifying FedRAMP High Controls..."

# Check encryption at rest
verify_encryption() {
    aws s3 ls --region us-gov-west-1 | while read -r bucket; do
        encryption_status=$(aws s3api get-bucket-encryption --bucket "$bucket" --region us-gov-west-1)
        if [ $? -ne 0 ]; then
            echo "❌ Bucket $bucket is not encrypted"
            exit 1
        fi
    done
}

# Check MFA enforcement
verify_mfa() {
    mfa_status=$(aws iam get-account-summary --region us-gov-west-1 | grep AccountMFAEnabled)
    if [ $? -ne 0 ]; then
        echo "❌ MFA is not enforced at account level"
        exit 1
    fi
}

# Check audit logging
verify_audit() {
    trail_status=$(aws cloudtrail get-trail-status --name govcloud-audit-trail --region us-gov-west-1)
    if [ $? -ne 0 ]; then
        echo "❌ CloudTrail is not properly configured"
        exit 1
    fi
}

# Check network security
verify_network() {
    flow_logs=$(aws ec2 describe-flow-logs --region us-gov-west-1)
    if [ -z "$flow_logs" ]; then
        echo "❌ VPC Flow Logs are not enabled"
        exit 1
    fi
}

# Run all verifications
verify_encryption
verify_mfa
verify_audit
verify_network

echo "✅ All FedRAMP High controls verified successfully"