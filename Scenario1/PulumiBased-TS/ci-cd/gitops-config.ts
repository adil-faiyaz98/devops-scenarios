import * as pulumi from '@pulumi/pulumi';
import * as k8s from '@pulumi/kubernetes';
import * as eks from '@pulumi/eks';

export interface GitOpsConfigurationArgs {
    environment: string;
    clusters: eks.Cluster[];
    organization: string;
    repository: string;
}

export class GitOpsConfiguration extends pulumi.ComponentResource {
    constructor(
        name: string,
        args: GitOpsConfigurationArgs,
        opts?: pulumi.ComponentResourceOptions
    ) {
        super('enterprise:cicd:GitOpsConfiguration', name, {}, opts);

        // Deploy Flux to each cluster
        for (let i = 0; i < args.clusters.length; i++) {
            const cluster = args.clusters[i];
            const isPrimary = i === 0; // First cluster is primary

            // Create a Kubernetes provider for this cluster
            const k8sProvider = new k8s.Provider(`${name}-k8s-provider-${i}`, {
                kubeconfig: cluster.kubeconfig,
            }, { parent: this });

            // Deploy Flux
            this.deployFlux(
                `${name}-flux-${i}`,
                args,
                k8sProvider,
                isPrimary
            );
        }

        // Register outputs
        this.registerOutputs({});
    }

    /**
     * Deploy Flux CD for GitOps
     */
    private deployFlux(
        name: string,
        args: GitOpsConfigurationArgs,
        provider: k8s.Provider,
        isPrimary: boolean
    ): void {
        // Create a namespace for Flux
        new k8s.core.v1.Namespace(`${name}-namespace`, {
            metadata: {
                name: 'flux-system',
                labels: {
                    name: 'flux-system',
                    environment: args.environment,
                },
            },
        }, { provider, parent: this });

        // Create a service account for Flux
        new k8s.core.v1.ServiceAccount(`${name}-service-account`, {
            metadata: {
                name: 'flux',
                namespace: 'flux-system',
            },
        }, { provider, parent: this });

        // Create a cluster role binding for Flux
        new k8s.rbac.v1.ClusterRoleBinding(`${name}-cluster-role-binding`, {
            metadata: {
                name: 'flux-cluster-role-binding',
            },
            roleRef: {
                apiGroup: 'rbac.authorization.k8s.io',
                kind: 'ClusterRole',
                name: 'cluster-admin', // In a real implementation, we would use a more restricted role
            },
            subjects: [{
                kind: 'ServiceAccount',
                name: 'flux',
                namespace: 'flux-system',
            }],
        }, { provider, parent: this });

        // Create a secret for Flux to access the Git repository
        // In a real implementation, this would be a real secret
        new k8s.core.v1.Secret(`${name}-git-credentials`, {
            metadata: {
                name: 'flux-git-credentials',
                namespace: 'flux-system',
            },
            type: 'Opaque',
            stringData: {
                'identity': '...',
                'identity.pub': '...',
                'known_hosts': '...',
            },
        }, { provider, parent: this });

    }
}
