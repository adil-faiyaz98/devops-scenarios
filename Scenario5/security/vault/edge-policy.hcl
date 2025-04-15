# Edge Device Policy
path "secret/data/edge-devices/{{identity.entity.aliases.auth_aws_iam.metadata.device_id}}/*" {
  capabilities = ["read"]
}

# Allow devices to generate short-lived tokens
path "auth/token/create/edge-device" {
  capabilities = ["create", "update"]
}

# Allow devices to renew their tokens
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow devices to rotate their certificates
path "pki/issue/edge-device" {
  capabilities = ["create", "update"]
}