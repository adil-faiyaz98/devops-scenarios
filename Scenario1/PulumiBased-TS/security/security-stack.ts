import * as pulumi from '@pulumi/pulumi';
import * as k8s from '@pulumi/kubernetes';
import * as eks from '@pulumi/eks';

export interface SecurityStackArgs {
    environment: string;
    clusters: eks.Cluster[];
    enableVault: boolean;
    enableNetworkPolicies: boolean;
}

export class SecurityStack extends pulumi.ComponentResource {
    public readonly vaultUrl?: pulumi.Output<string>;

    constructor(
        name: string,
        args: SecurityStackArgs,
        opts?: pulumi.ComponentResourceOptions
    ) {
        super('enterprise:security:SecurityStack', name, {}, opts);

        // Deploy security controls to each cluster
        for (let i = 0; i < args.clusters.length; i++) {
            const cluster = args.clusters[i];
            const isPrimary = i === 0; // First cluster is primary

            // Create a Kubernetes provider for this cluster
            const k8sProvider = new k8s.Provider(`${name}-k8s-provider-${i}`, {
                kubeconfig: cluster.kubeconfig,
            }, { parent: this });

            // Deploy network policies if enabled
            if (args.enableNetworkPolicies) {
                this.deployNetworkPolicies(
                    `${name}-network-policies-${i}`,
                    args,
                    k8sProvider
                );
            }

            // Deploy Vault only on the primary cluster if enabled
            if (isPrimary && args.enableVault) {
                const vault = this.deployVault(
                    `${name}-vault`,
                    args,
                    k8sProvider
                );
                this.vaultUrl = vault.url;
            }

            // Deploy Pod Security Policies
            this.deployPodSecurityPolicies(
                `${name}-pod-security-policies-${i}`,
                args,
                k8sProvider
            );

            // Deploy security scanning
            this.deploySecurityScanning(
                `${name}-security-scanning-${i}`,
                args,
                k8sProvider
            );
        }

        // Register outputs
        this.registerOutputs({
            vaultUrl: this.vaultUrl,
        });
    }

    /**
     * Deploy network policies to restrict communication between services
     */
    private deployNetworkPolicies(
        name: string,
        args: SecurityStackArgs,
        provider: k8s.Provider
    ): void {
        // Default deny all ingress traffic
        new k8s.networking.v1.NetworkPolicy(`${name}-default-deny-ingress`, {
            metadata: {
                name: 'default-deny-ingress',
                namespace: 'default',
            },
            spec: {
                podSelector: {},
                policyTypes: ['Ingress'],
            },
        }, { provider, parent: this });

        // Allow traffic within the same namespace
        new k8s.networking.v1.NetworkPolicy(`${name}-allow-same-namespace`, {
            metadata: {
                name: 'allow-same-namespace',
                namespace: 'default',
            },
            spec: {
                podSelector: {},
                ingress: [{
                    from: [{
                        podSelector: {},
                    }],
                }],
                policyTypes: ['Ingress'],
            },
        }, { provider, parent: this });

        // Allow traffic between specific microservices
        new k8s.networking.v1.NetworkPolicy(`${name}-allow-project1-microservice1`, {
            metadata: {
                name: 'allow-project1-microservice1',
                namespace: 'default',
            },
            spec: {
                podSelector: {
                    matchLabels: {
                        app: 'project1-microservice1',
                    },
                },
                ingress: [{
                    from: [{
                        podSelector: {
                            matchLabels: {
                                app: 'project1-microservice2',
                            },
                        },
                    }],
                    ports: [{
                        port: 8080,
                        protocol: 'TCP',
                    }],
                }],
                policyTypes: ['Ingress'],
            },
        }, { provider, parent: this });
    }

    /**
     * Deploy HashiCorp Vault for secret management
     */
    private deployVault(
        name: string,
        args: SecurityStackArgs,
        provider: k8s.Provider
    ): { url: pulumi.Output<string> } {
        // Create a namespace for Vault
        new k8s.core.v1.Namespace(`${name}-namespace`, {
            metadata: {
                name: 'vault',
                labels: {
                    name: 'vault',
                    environment: args.environment,
                },
            },
        }, { provider, parent: this });

        // Create a service account for Vault
        new k8s.core.v1.ServiceAccount(`${name}-service-account`, {
            metadata: {
                name: 'vault',
                namespace: 'vault',
            },
        }, { provider, parent: this });

        // Create a cluster role binding for Vault
        new k8s.rbac.v1.ClusterRoleBinding(`${name}-cluster-role-binding`, {
            metadata: {
                name: 'vault-server-binding',
            },
            roleRef: {
                apiGroup: 'rbac.authorization.k8s.io',
                kind: 'ClusterRole',
                name: 'system:auth-delegator',
            },
            subjects: [{
                kind: 'ServiceAccount',
                name: 'vault',
                namespace: 'vault',
            }],
        }, { provider, parent: this });

        // Deploy Vault using Helm
        const vaultRelease = new k8s.helm.v3.Release(`${name}-vault`, {
            chart: 'vault',
            repositoryOpts: {
                repo: 'https://helm.releases.hashicorp.com',
            },
            namespace: 'vault',
            values: {
                server: {
                    ha: {
                        enabled: true,
                        replicas: 3,
                        raft: {
                            enabled: true,
                            setNodeId: true,
                        },
                    },
                    affinity: {
                        podAntiAffinity: {
                            requiredDuringSchedulingIgnoredDuringExecution: [{
                                labelSelector: {
                                    matchLabels: {
                                        'app.kubernetes.io/name': 'vault',
                                        'component': 'server',
                                    },
                                },
                                topologyKey: 'kubernetes.io/hostname',
                            }],
                        },
                    },
                    resources: {
                        requests: {
                            memory: '256Mi',
                            cpu: '250m',
                        },
                        limits: {
                            memory: '512Mi',
                            cpu: '500m',
                        },
                    },
                    dataStorage: {
                        enabled: true,
                        size: '10Gi',
                        storageClass: 'gp2',
                    },
                    auditStorage: {
                        enabled: true,
                        size: '10Gi',
                        storageClass: 'gp2',
                    },
                    serviceAccount: {
                        create: false,
                        name: 'vault',
                    },
                },
                ui: {
                    enabled: true,
                    serviceType: 'ClusterIP',
                },
                injector: {
                    enabled: true,
                    resources: {
                        requests: {
                            memory: '256Mi',
                            cpu: '250m',
                        },
                        limits: {
                            memory: '512Mi',
                            cpu: '500m',
                        },
                    },
                },
            },
        }, { provider, parent: this });

        // Create an Ingress for Vault UI
        const vaultIngress = new k8s.networking.v1.Ingress(`${name}-ingress`, {
            metadata: {
                name: 'vault',
                namespace: 'vault',
                annotations: {
                    'kubernetes.io/ingress.class': 'nginx',
                    'cert-manager.io/cluster-issuer': 'letsencrypt-prod',
                    'nginx.ingress.kubernetes.io/backend-protocol': 'HTTPS',
                    'nginx.ingress.kubernetes.io/ssl-passthrough': 'true',
                },
            },
            spec: {
                tls: [{
                    hosts: [`vault.${args.environment}.example.com`],
                    secretName: 'vault-tls',
                }],
                rules: [{
                    host: `vault.${args.environment}.example.com`,
                    http: {
                        paths: [{
                            path: '/',
                            pathType: 'Prefix',
                            backend: {
                                service: {
                                    name: 'vault-ui',
                                    port: {
                                        number: 8200,
                                    },
                                },
                            },
                        }],
                    },
                }],
            },
        }, { provider, parent: this, dependsOn: vaultRelease });

        // Create a ConfigMap for Vault initialization script
        new k8s.core.v1.ConfigMap(`${name}-init-script`, {
            metadata: {
                name: 'vault-init-script',
                namespace: 'vault',
            },
            data: {
                'init.sh': `#!/bin/sh
                set -e
                
                # Check if Vault is initialized
                INITIALIZED=$(vault status -format=json | jq -r '.initialized')
                
                if [ "$INITIALIZED" = "false" ]; then
                    echo "Initializing Vault..."
                    # Initialize Vault and capture the unseal keys and root token
                    INIT_RESPONSE=$(vault operator init -format=json -recovery-shares=5 -recovery-threshold=3)
                    
                    # Store the keys in Kubernetes secrets
                    echo $INIT_RESPONSE | jq -r '.unseal_keys_b64[0]' > /tmp/unseal-key-0
                    echo $INIT_RESPONSE | jq -r '.unseal_keys_b64[1]' > /tmp/unseal-key-1
                    echo $INIT_RESPONSE | jq -r '.unseal_keys_b64[2]' > /tmp/unseal-key-2
                    echo $INIT_RESPONSE | jq -r '.root_token' > /tmp/root-token
                    
                    kubectl create secret generic vault-unseal-keys \
                        --from-file=/tmp/unseal-key-0 \
                        --from-file=/tmp/unseal-key-1 \
                        --from-file=/tmp/unseal-key-2 \
                        -n vault
                        
                    kubectl create secret generic vault-root-token \
                        --from-file=/tmp/root-token \
                        -n vault
                        
                    rm -f /tmp/unseal-key-0 /tmp/unseal-key-1 /tmp/unseal-key-2 /tmp/root-token
                    
                    echo "Vault has been initialized and keys stored as Kubernetes secrets"
                else
                    echo "Vault is already initialized"
                fi
                `,
            },
        }, { provider, parent: this });

        // Create a Job to initialize Vault
        new k8s.batch.v1.Job(`${name}-init-job`, {
            metadata: {
                name: 'vault-init',
                namespace: 'vault',
            },
            spec: {
                template: {
                    spec: {
                        serviceAccountName: 'vault',
                        containers: [{
                            name: 'vault-init',
                            image: 'hashicorp/vault:latest',
                            command: ['/bin/sh', '/scripts/init.sh'],
                            env: [{
                                name: 'VAULT_ADDR',
                                value: 'https://vault-0.vault-internal:8200',
                            }, {
                                name: 'VAULT_SKIP_VERIFY',
                                value: 'true',
                            }],
                            volumeMounts: [{
                                name: 'init-script',
                                mountPath: '/scripts',
                            }],
                        }],
                        restartPolicy: 'OnFailure',
                        volumes: [{
                            name: 'init-script',
                            configMap: {
                                name: 'vault-init-script',
                                defaultMode: 0o755,
                            },
                        }],
                    },
                },
                backoffLimit: 5,
            },
        }, { provider, parent: this, dependsOn: vaultRelease });

        // Return the Vault URL
        return {
            url: pulumi.interpolate`https://vault.${args.environment}.example.com`,
        };
    }

    /**
     * Deploy Pod Security Policies
     */
    private deployPodSecurityPolicies(
        name: string,
        args: SecurityStackArgs,
        provider: k8s.Provider
    ): void {
        // Create a namespace for security policies
        new k8s.core.v1.Namespace(`${name}-namespace`, {
            metadata: {
                name: 'security-policies',
                labels: {
                    name: 'security-policies',
                    environment: args.environment,
                },
            },
        }, { provider, parent: this });

        // Create a restricted PSP
        new k8s.policy.v1beta1.PodSecurityPolicy(`${name}-restricted`, {
            metadata: {
                name: 'restricted',
                annotations: {
                    'seccomp.security.alpha.kubernetes.io/allowedProfileNames': 'docker/default,runtime/default',
                    'apparmor.security.beta.kubernetes.io/allowedProfileNames': 'runtime/default',
                    'seccomp.security.alpha.kubernetes.io/defaultProfileName': 'runtime/default',
                    'apparmor.security.beta.kubernetes.io/defaultProfileName': 'runtime/default',
                },
            },
            spec: {
                privileged: false,
                allowPrivilegeEscalation: false,
                requiredDropCapabilities: ['ALL'],
                volumes: [
                    'configMap',
                    'emptyDir',
                    'projected',
                    'secret',
                    'downwardAPI',
                    'persistentVolumeClaim',
                ],
                hostNetwork: false,
                hostIPC: false,
                hostPID: false,
                runAsUser: {
                    rule: 'MustRunAsNonRoot',
                },
                seLinux: {
                    rule: 'RunAsAny',
                },
                supplementalGroups: {
                    rule: 'MustRunAs',
                    ranges: [{
                        min: 1,
                        max: 65535,
                    }],
                },
                fsGroup: {
                    rule: 'MustRunAs',
                    ranges: [{
                        min: 1,
                        max: 65535,
                    }],
                },
                readOnlyRootFilesystem: true,
            },
        }, { provider, parent: this });

        // Create a role for using the restricted PSP
        new k8s.rbac.v1.ClusterRole(`${name}-restricted-psp-user`, {
            metadata: {
                name: 'restricted-psp-user',
            },
            rules: [{
                apiGroups: ['policy'],
                resources: ['podsecuritypolicies'],
                verbs: ['use'],
                resourceNames: ['restricted'],
            }],
        }, { provider, parent: this });

        // Bind the PSP role to all authenticated users
        new k8s.rbac.v1.ClusterRoleBinding(`${name}-restricted-psp-user`, {
            metadata: {
                name: 'restricted-psp-user',
            },
            roleRef: {
                apiGroup: 'rbac.authorization.k8s.io',
                kind: 'ClusterRole',
                name: 'restricted-psp-user',
            },
            subjects: [{
                kind: 'Group',
                apiGroup: 'rbac.authorization.k8s.io',
                name: 'system:authenticated',
            }],
        }, { provider, parent: this });
    }

    /**
     * Deploy security scanning tools
     */
    private deploySecurityScanning(
        name: string,
        args: SecurityStackArgs,
        provider: k8s.Provider
    ): void {
        // Create namespace for security tools
        new k8s.core.v1.Namespace(`${name}-namespace`, {
            metadata: {
                name: 'security-scanning',
                labels: {
                    name: 'security-scanning',
                    environment: args.environment,
                },
            },
        }, { provider, parent: this });

        // Deploy Trivy for vulnerability scanning
        new k8s.helm.v3.Release(`${name}-trivy`, {
            chart: 'trivy-operator',
            repositoryOpts: {
                repo: 'https://aquasecurity.github.io/helm-charts',
            },
            namespace: 'security-scanning',
            values: {
                trivy: {
                    ignoreUnfixed: true,
                    severity: 'CRITICAL,HIGH',
                    timeout: '10m0s',
                },
                serviceAccount: {
                    create: true,
                    annotations: {
                        'eks.amazonaws.com/role-arn': `arn:aws:iam::account-id:role/trivy-${args.environment}`,
                    },
                },
            },
        }, { provider, parent: this });

        // Deploy Falco for runtime security
        new k8s.helm.v3.Release(`${name}-falco`, {
            chart: 'falco',
            repositoryOpts: {
                repo: 'https://falcosecurity.github.io/charts',
            },
            namespace: 'security-scanning',
            values: {
                falco: {
                    jsonOutput: true,
                    priority: 'debug',
                    k8sAuditRules: true,
                },
                ebpf: {
                    enabled: true,
                },
                integrations: {
                    syslogOutput: {
                        enabled: true,
                    },
                },
                serviceAccount: {
                    create: true,
                    annotations: {
                        'eks.amazonaws.com/role-arn': `arn:aws:iam::account-id:role/falco-${args.environment}`,
                    },
                },
            },
        }, { provider, parent: this });

        // Deploy Kube-bench for CIS benchmark scanning
        new k8s.apps.v1.CronJob(`${name}-kube-bench`, {
            metadata: {
                name: 'kube-bench',
                namespace: 'security-scanning',
            },
            spec: {
                schedule: '0 0 * * *', // Run daily at midnight
                jobTemplate: {
                    spec: {
                        template: {
                            spec: {
                                serviceAccountName: 'kube-bench',
                                containers: [{
                                    name: 'kube-bench',
                                    image: 'aquasec/kube-bench:latest',
                                    command: ['kube-bench', '--json'],
                                    volumeMounts: [{
                                        name: 'var-lib-kubelet',
                                        mountPath: '/var/lib/kubelet',
                                        readOnly: true,
                                    }, {
                                        name: 'etc-systemd',
                                        mountPath: '/etc/systemd',
                                        readOnly: true,
                                    }, {
                                        name: 'etc-kubernetes',
                                        mountPath: '/etc/kubernetes',
                                        readOnly: true,
                                    }],
                                }],
                                restartPolicy: 'Never',
                                volumes: [{
                                    name: 'var-lib-kubelet',
                                    hostPath: {
                                        path: '/var/lib/kubelet',
                                    },
                                }, {
                                    name: 'etc-systemd',
                                    hostPath: {
                                        path: '/etc/systemd',
                                    },
                                }, {
                                    name: 'etc-kubernetes',
                                    hostPath: {
                                        path: '/etc/kubernetes',
                                    },
                                }],
                            },
                        },
                    },
                },
            },
        }, { provider, parent: this });

        // Create service account for kube-bench
        new k8s.core.v1.ServiceAccount(`${name}-kube-bench-sa`, {
            metadata: {
                name: 'kube-bench',
                namespace: 'security-scanning',
            },
        }, { provider, parent: this });

        // Create cluster role for kube-bench
        new k8s.rbac.v1.ClusterRole(`${name}-kube-bench-role`, {
            metadata: {
                name: 'kube-bench',
            },
            rules: [{
                apiGroups: [''],
                resources: ['nodes'],
                verbs: ['get', 'list'],
            }],
        }, { provider, parent: this });

        // Bind the role to the service account
        new k8s.rbac.v1.ClusterRoleBinding(`${name}-kube-bench-binding`, {
            metadata: {
                name: 'kube-bench',
            },
            roleRef: {
                apiGroup: 'rbac.authorization.k8s.io',
                kind: 'ClusterRole',
                name: 'kube-bench',
            },
            subjects: [{
                kind: 'ServiceAccount',
                name: 'kube-bench',
                namespace: 'security-scanning',
            }],
        }, { provider, parent: this });
    }
}


