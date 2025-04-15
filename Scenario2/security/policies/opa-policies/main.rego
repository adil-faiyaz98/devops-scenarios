package fintech.security

# Default deny
default allow = false

# Allow only if all conditions are met
allow {
    authenticated
    authorized
    compliant
}

authenticated {
    input.user.authenticated == true
    input.user.mfa_verified == true
}

authorized {
    # Check if user has required role
    input.user.roles[_] == required_role
}

compliant {
    # Check PCI-DSS compliance
    input.request.encryption == "TLS1.3"
    input.request.data_classification != "PCI"
    not input.request.contains_pii
}

# Audit logging
audit[log] {
    log := {
        "timestamp": time.now_ns(),
        "user": input.user.id,
        "action": input.request.action,
        "resource": input.request.resource,
        "allowed": allow
    }
}