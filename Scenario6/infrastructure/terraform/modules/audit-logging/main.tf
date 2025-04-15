resource "aws_cloudtrail" "audit_trail" {
  name                          = "govcloud-audit-trail"
  s3_bucket_name               = aws_s3_bucket.audit_logs.id
  include_global_service_events = true
  is_multi_region_trail        = true
  enable_logging               = true
  kms_key_id                  = aws_kms_key.audit_key.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws-us-gov:s3:::"]
    }
  }
}

resource "aws_config_configuration_recorder" "config" {
  name     = "govcloud-config-recorder"
  role_arn = aws_iam_role.config_role.arn

  recording_group {
    all_supported = true
    include_global_resources = true
  }
}

resource "aws_securityhub_account" "main" {
  enable_default_standards = true

  control_finding_generator = "SECURITY_CONTROL"
  
  standards_configuration {
    standard_arn = "arn:aws-us-gov:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0"
    enable_significantly_different_findings = true
    disable_notifications_for_findings = false
  }
}