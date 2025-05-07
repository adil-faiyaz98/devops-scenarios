import * as pulumi from '@pulumi/pulumi';
import { MultiRegionInfrastructure } from './infrastructure/multi-region';
import { MonitoringStack } from './monitoring/monitoring-stack';
import { SecurityStack } from './security/security-stack';
import { GitOpsConfiguration } from './ci-cd/gitops-config';
import { ErrorHandler, Logger } from './infrastructure/utils';

/**
 * Enterprise Multi-Project CI/CD Pipeline
 * 
 * This Pulumi program deploys a comprehensive CI/CD infrastructure for 5 projects with 10 microservices.
 * It includes multi-region Kubernetes clusters, monitoring, security, and GitOps configuration.
 * 
 * Features:
 * - Multi-region Kubernetes clusters for high availability
 * - Comprehensive monitoring with Prometheus, Grafana, and ELK stack
 * - Security controls including network policies, secret management, and vulnerability scanning
 * - GitOps-based deployment with Flux CD
 * - Advanced error handling and resilience patterns
 * - Automated verification and compliance checks
 */

// Initialize logger
const logger = new Logger('enterprise-cicd');

// Load configuration
const config = new pulumi.Config();
const environment = config.require('environment');
const clusterName = config.require('clusterName');
const regions = config.requireObject<string[]>('regions');
const enableMonitoring = config.requireBoolean('enableMonitoring');
const enableTracing = config.requireBoolean('enableTracing');
const enableLogging = config.requireBoolean('enableLogging');
const enableVault = config.requireBoolean('enableVault');
const enableNetworkPolicies = config.requireBoolean('enableNetworkPolicies');
const domain = config.require('domain');
const alertingEmail = config.require('alertingEmail');
const slackWebhook = config.requireSecret('slackWebhook');

// Initialize error handler with retry and circuit breaker patterns
const errorHandler = new ErrorHandler({
    maxRetries: 3,
    retryDelay: 5000,
    circuitBreakerThreshold: 5,
    resetTimeout: 30000,
    onError: (error) => {
        logger.error(`Deployment error: ${error.message}`, { error });
        
        // Send alert for critical errors
        if (environment === 'prod') {
            // In a real implementation, this would send an alert
            logger.warn('Would send alert to PagerDuty for production error');
        }
    }
});

// Deploy multi-region infrastructure with error handling
let infrastructure: MultiRegionInfrastructure;
try {
    logger.info(`Deploying infrastructure for ${environment} environment in ${regions.join(', ')} regions`);
    
    infrastructure = new MultiRegionInfrastructure(clusterName, {
        environment,
        regions,
        nodeSize: config.require('nodeSize'),
        minNodes: config.requireNumber('minNodes'),
        maxNodes: config.requireNumber('maxNodes'),
        desiredCapacity: config.requireNumber('desiredCapacity'),
        domain,
    }, { errorHandler });
    
    logger.info('Infrastructure deployment successful');
} catch (error) {
    errorHandler.handleError(error as Error);
    throw error;
}

// Deploy monitoring stack if enabled
let monitoring: MonitoringStack | undefined;
if (enableMonitoring) {
    try {
        logger.info('Deploying monitoring stack');
        
        monitoring = new MonitoringStack('monitoring', {
            environment,
            clusters: infrastructure.clusters,
            enableTracing,
            enableLogging,
            alertingEmail,
            slackWebhook,
        }, { dependsOn: infrastructure.clusters });
        
        logger.info('Monitoring stack deployment successful');
    } catch (error) {
        errorHandler.handleError(error as Error);
        // Continue deployment even if monitoring fails
        logger.warn('Continuing deployment despite monitoring setup failure');
    }
}

// Deploy security stack if enabled
let security: SecurityStack | undefined;
if (enableVault || enableNetworkPolicies) {
    try {
        logger.info('Deploying security stack');
        
        security = new SecurityStack('security', {
            environment,
            clusters: infrastructure.clusters,
            enableVault,
            enableNetworkPolicies,
        }, { dependsOn: infrastructure.clusters });
        
        logger.info('Security stack deployment successful');
    } catch (error) {
        errorHandler.handleError(error as Error);
        // Continue deployment even if security fails, but log a critical warning
        logger.error('Security stack deployment failed, continuing with reduced security posture');
    }
}

// Configure GitOps with Flux CD
try {
    logger.info('Configuring GitOps with Flux CD');
    
    const gitOps = new GitOpsConfiguration('gitops', {
        environment,
        clusters: infrastructure.clusters,
        organization: config.require('organization'),
        repository: config.require('gitops:repository'),
    }, { 
        dependsOn: [
            infrastructure.clusters,
            ...(monitoring ? [monitoring] : []),
            ...(security ? [security] : []),
        ] 
    });
    
    logger.info('GitOps configuration successful');
} catch (error) {
    errorHandler.handleError(error as Error);
    throw error; // GitOps is critical, so we fail the deployment if it fails
}

// Export outputs
export const clusterEndpoints = infrastructure.clusterEndpoints;
export const kubeconfigs = infrastructure.kubeconfigs;
export const monitoringUrls = monitoring ? monitoring.dashboardUrls : undefined;
export const loggingUrl = monitoring && enableLogging ? monitoring.loggingUrl : undefined;
export const tracingUrl = monitoring && enableTracing ? monitoring.tracingUrl : undefined;
export const vaultUrl = security && enableVault ? security.vaultUrl : undefined;
