# Tenant Guide: Enterprise Kubernetes Platform

## Introduction

Welcome to the Enterprise Kubernetes Platform! This guide will help you understand how to use the platform effectively, deploy applications, monitor resources, and manage costs.

## Getting Started

### Access and Authentication

1. **Platform Access**
   - Access is provided through Azure AD SSO
   - Your team's Azure AD group determines your permissions
   - MFA is required for all access

2. **Kubernetes Access**
   - Use `kubectl` with Azure AD authentication:
     ```bash
     az login
     az aks get-credentials --resource-group <resource-group> --name <cluster-name>
     kubectl get pods -n <your-namespace>
     ```

3. **ArgoCD Access**
   - URL: https://argocd.example.com
   - Authentication: Azure AD SSO
   - Your team has access to your tenant's ArgoCD project

### Namespace and Resources

Your tenant has been provisioned with:

- Dedicated namespace: `<tenant-name>`
- Resource quotas for CPU, memory, and pods
- Network policies for isolation
- Istio service mesh integration

## Deploying Applications

### GitOps Workflow

1. **Repository Structure**
   - Create Kubernetes manifests in your team's Git repository
   - Organize by environment (dev, qa, prod)
   - Use Kustomize or Helm for templating

2. **Deployment Process**
   - Commit changes to your repository
   - ArgoCD automatically syncs changes to the cluster
   - Monitor deployment status in ArgoCD UI

3. **Environment Promotion**
   - Use Git branches or paths for different environments
   - Promote changes through pull requests
   - Automated validation ensures compliance

### Example Repository Structure

```
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── overlays/
│   ├── dev/
│   │   ├── kustomization.yaml
│   │   └── config.yaml
│   ├── qa/
│   │   ├── kustomization.yaml
│   │   └── config.yaml
│   └── prod/
│       ├── kustomization.yaml
│       └── config.yaml
└── README.md
```

## Network Configuration

### Service Mesh

Your applications are automatically integrated with Istio service mesh:

- Service-to-service communication is encrypted with mTLS
- Traffic management for canary deployments
- Distributed tracing for request flows

### Ingress Configuration

To expose your service externally:

1. Create an Ingress resource:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: my-service-ingress
     namespace: <your-namespace>
     annotations:
       kubernetes.io/ingress.class: "nginx"
       nginx.ingress.kubernetes.io/ssl-redirect: "true"
   spec:
     rules:
     - host: <your-service>.<tenant>.example.com
       http:
         paths:
         - path: /
           pathType: Prefix
           backend:
             service:
               name: my-service
               port:
                 number: 80
   ```

2. DNS will be automatically configured for your domain

## Monitoring and Observability

### Dashboards

- **Grafana**: https://grafana.example.com
  - Tenant-specific dashboards
  - Resource utilization
  - Application metrics

- **Kubecost**: https://kubecost.example.com
  - Cost attribution
  - Resource utilization
  - Optimization recommendations

### Logging

- Centralized logging with Elasticsearch
- Query logs through Kibana: https://kibana.example.com
- Logs are retained for 30 days

### Alerting

- Configure alerts in Prometheus
- Integrate with your team's notification channels
- Default alerts for resource utilization

## Cost Management

### Cost Visibility

- View your tenant's costs in Kubecost
- Daily, weekly, and monthly reports
- Cost breakdown by workload

### Cost Optimization

- Right-size your resource requests
- Implement autoscaling for variable workloads
- Review idle resources regularly

## Security Best Practices

1. **Container Security**
   - Use minimal base images
   - Scan images for vulnerabilities
   - Don't run as root

2. **Secret Management**
   - Use Vault for secrets
   - Don't store secrets in Git
   - Rotate credentials regularly

3. **Network Security**
   - Implement network policies
   - Limit egress traffic
   - Use mTLS for service communication

## Support and Escalation

For platform support:

- Email: platform-support@company.com
- Slack: #platform-support
- Emergency: Call the on-call engineer at (555) 123-4567

## FAQ

**Q: How do I increase my resource quota?**
A: Submit a request through the platform portal with justification.

**Q: Can I access other tenants' services?**
A: No, tenants are isolated by default. Cross-tenant access requires explicit configuration.

**Q: How do I get access for a new team member?**
A: Add them to your team's Azure AD group.
