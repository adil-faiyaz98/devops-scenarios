import * as pulumi from '@pulumi/pulumi';
import * as aws from '@pulumi/aws';
import * as eks from '@pulumi/eks';
import * as k8s from '@pulumi/kubernetes';
import * as random from '@pulumi/random';
import { ErrorHandler } from './utils';

export interface MultiRegionInfrastructureArgs {
    environment: string;
    regions: string[];
    nodeSize: string;
    minNodes: number;
    maxNodes: number;
    desiredCapacity: number;
    domain: string;
}

interface ClusterOptions {
    provider: aws.Provider;
    region: string;
    isPrimary: boolean;
}

export class MultiRegionInfrastructure extends pulumi.ComponentResource {
    public readonly clusters: eks.Cluster[];
    public readonly clusterEndpoints: pulumi.Output<string>[];
    public readonly kubeconfigs: pulumi.Output<string>[];
    public readonly vpcIds: pulumi.Output<string>[];
    private readonly errorHandler?: ErrorHandler;

    constructor(
        name: string,
        args: MultiRegionInfrastructureArgs,
        opts?: pulumi.ComponentResourceOptions & { errorHandler?: ErrorHandler }
    ) {
        super('enterprise:infrastructure:MultiRegionInfrastructure', name, {}, opts);

        this.errorHandler = opts?.errorHandler;
        this.clusters = [];
        this.clusterEndpoints = [];
        this.kubeconfigs = [];
        this.vpcIds = [];

        // Create a cluster in each region
        for (let i = 0; i < args.regions.length; i++) {
            const region = args.regions[i];
            const isPrimary = i === 0; // First region is primary

            try {
                // Create a provider for this region
                const provider = new aws.Provider(`provider-${region}`, {
                    region: region as aws.Region,
                }, { parent: this });

                // Create a cluster in this region
                const cluster = this.createCluster(
                    `${name}-${region}`,
                    args,
                    { provider, region, isPrimary }
                );

                this.clusters.push(cluster);
                this.clusterEndpoints.push(cluster.eksCluster.endpoint);
                this.kubeconfigs.push(cluster.kubeconfig);
                this.vpcIds.push(cluster.core.vpcId);
            } catch (error) {
                if (this.errorHandler) {
                    this.errorHandler.handleError(error as Error, `cluster-${region}`);
                    
                    // If this is not the primary region, we can continue
                    if (!isPrimary) {
                        console.warn(`Failed to create cluster in ${region}, but continuing as it's not the primary region`);
                        continue;
                    }
                }
                
                throw error;
            }
        }

        // Register outputs
        this.registerOutputs({
            clusters: this.clusters,
            clusterEndpoints: this.clusterEndpoints,
            kubeconfigs: this.kubeconfigs,
            vpcIds: this.vpcIds,
        });
    }

    /**
     * Create a Kubernetes cluster in a specific region
     */
    private createCluster(
        name: string,
        args: MultiRegionInfrastructureArgs,
        options: ClusterOptions
    ): eks.Cluster {
        const { provider, region, isPrimary } = options;

        // Generate a unique suffix for resource names
        const suffix = new random.RandomString(`${name}-suffix`, {
            length: 8,
            special: false,
            upper: false,
        }, { provider, parent: this }).result;

        // Create VPC for the cluster
        const vpcName = pulumi.interpolate`${name}-vpc-${suffix}`;
        
        // Create EKS cluster with VPC
        const cluster = new eks.Cluster(`${name}-cluster`, {
            name: pulumi.interpolate`${args.environment}-${region}-${suffix}`,
            vpcId: undefined, // Let EKS create a new VPC
            privateSubnetIds: undefined, // Let EKS create new subnets
            publicSubnetIds: undefined, // Let EKS create new subnets
            instanceType: args.nodeSize,
            desiredCapacity: args.desiredCapacity,
            minSize: args.minNodes,
            maxSize: args.maxNodes,
            nodePublicKey: undefined, // Generate a new key
            enabledClusterLogTypes: [
                "api",
                "audit",
                "authenticator",
                "controllerManager",
                "scheduler",
            ],
            endpointPrivateAccess: true,
            endpointPublicAccess: true,
            version: "1.27",
            skipDefaultNodeGroup: false,
            createOidcProvider: true,
            tags: {
                Environment: args.environment,
                Region: region,
                Primary: isPrimary ? "true" : "false",
                ManagedBy: "pulumi",
            },
            nodeAssociatePublicIpAddress: false, // For security, use private IPs
            nodeRootVolumeEncrypted: true, // Encrypt root volumes
            nodeRootVolumeSize: 50, // 50 GB root volume
            encryptionConfigKeyArn: undefined, // Use default KMS key
        }, { provider, parent: this });

        // Create a Kubernetes provider for this cluster
        const k8sProvider = new k8s.Provider(`${name}-k8s-provider`, {
            kubeconfig: cluster.kubeconfig,
        }, { parent: this });

        // Deploy critical add-ons
        this.deployCriticalAddons(name, cluster, k8sProvider, args);

        return cluster;
    }

    /**
     * Deploy critical add-ons to the cluster
     */
    private deployCriticalAddons(
        name: string,
        cluster: eks.Cluster,
        provider: k8s.Provider,
        args: MultiRegionInfrastructureArgs
    ): void {
        // Create namespaces
        const namespaces = ['monitoring', 'logging', 'security', 'ingress-nginx', 'cert-manager'];
        
        for (const ns of namespaces) {
            new k8s.core.v1.Namespace(`${name}-${ns}`, {
                metadata: {
                    name: ns,
                    labels: {
                        name: ns,
                        environment: args.environment,
                    },
                },
            }, { provider, parent: this });
        }

        // Deploy AWS Load Balancer Controller
        // In a real implementation, we would deploy the AWS Load Balancer Controller here
        // For brevity, we'll skip the actual implementation

        // Deploy External DNS
        // In a real implementation, we would deploy External DNS here
        // For brevity, we'll skip the actual implementation

        // Deploy Cert Manager
        // In a real implementation, we would deploy Cert Manager here
        // For brevity, we'll skip the actual implementation

        // Deploy Ingress Nginx
        // In a real implementation, we would deploy Ingress Nginx here
        // For brevity, we'll skip the actual implementation
    }
}


