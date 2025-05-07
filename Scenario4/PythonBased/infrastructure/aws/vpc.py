"""
VPC Module for the AI-driven Observability Pipeline.

This module creates a VPC with public and private subnets across multiple
availability zones, NAT gateways, and the necessary route tables.

The VPC is designed to be:
- Highly available: Resources spread across multiple AZs
- Secure: Private subnets for sensitive resources
- Cost-effective: Configurable NAT gateway options
"""

import pulumi
import pulumi_aws as aws
from typing import List, Dict, Any, Optional


class VpcResult:
    """Result object for VPC creation."""
    
    def __init__(
        self,
        vpc_id: pulumi.Output[str],
        private_subnet_ids: pulumi.Output[List[str]],
        public_subnet_ids: pulumi.Output[List[str]],
        nat_gateway_ids: pulumi.Output[List[str]],
        route_table_ids: pulumi.Output[List[str]],
    ):
        self.vpc_id = vpc_id
        self.private_subnet_ids = private_subnet_ids
        self.public_subnet_ids = public_subnet_ids
        self.nat_gateway_ids = nat_gateway_ids
        self.route_table_ids = route_table_ids


def create_vpc(
    name: str,
    cidr: str,
    azs: List[str],
    private_subnets: List[str],
    public_subnets: List[str],
    enable_nat_gateway: bool = True,
    single_nat_gateway: bool = False,
    tags: Optional[Dict[str, str]] = None,
) -> VpcResult:
    """
    Create a VPC with public and private subnets.
    
    Args:
        name: Name of the VPC
        cidr: CIDR block for the VPC
        azs: List of availability zones
        private_subnets: List of CIDR blocks for private subnets
        public_subnets: List of CIDR blocks for public subnets
        enable_nat_gateway: Whether to create NAT gateways
        single_nat_gateway: Whether to use a single NAT gateway for all AZs
        tags: Tags to apply to all resources
        
    Returns:
        VpcResult object with VPC details
    """
    if tags is None:
        tags = {}
    
    # Create VPC
    vpc = aws.ec2.Vpc(
        f"{name}",
        cidr_block=cidr,
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={**tags, "Name": name},
    )
    
    # Create Internet Gateway
    igw = aws.ec2.InternetGateway(
        f"{name}-igw",
        vpc_id=vpc.id,
        tags={**tags, "Name": f"{name}-igw"},
    )
    
    # Create public subnets
    public_subnet_resources = []
    for i, (az, cidr) in enumerate(zip(azs, public_subnets)):
        subnet = aws.ec2.Subnet(
            f"{name}-public-{i+1}",
            vpc_id=vpc.id,
            cidr_block=cidr,
            availability_zone=az,
            map_public_ip_on_launch=True,
            tags={
                **tags,
                "Name": f"{name}-public-{i+1}",
                "kubernetes.io/role/elb": "1",
            },
        )
        public_subnet_resources.append(subnet)
    
    # Create public route table
    public_route_table = aws.ec2.RouteTable(
        f"{name}-public-rt",
        vpc_id=vpc.id,
        tags={**tags, "Name": f"{name}-public-rt"},
    )
    
    # Create route to Internet Gateway
    aws.ec2.Route(
        f"{name}-public-route",
        route_table_id=public_route_table.id,
        destination_cidr_block="0.0.0.0/0",
        gateway_id=igw.id,
    )
    
    # Associate public subnets with public route table
    for i, subnet in enumerate(public_subnet_resources):
        aws.ec2.RouteTableAssociation(
            f"{name}-public-rta-{i+1}",
            subnet_id=subnet.id,
            route_table_id=public_route_table.id,
        )
    
    # Create NAT Gateways if enabled
    nat_gateway_resources = []
    if enable_nat_gateway:
        # Create Elastic IPs for NAT Gateways
        eips = []
        nat_count = 1 if single_nat_gateway else len(public_subnet_resources)
        
        for i in range(nat_count):
            eip = aws.ec2.Eip(
                f"{name}-eip-{i+1}",
                vpc=True,
                tags={**tags, "Name": f"{name}-eip-{i+1}"},
            )
            eips.append(eip)
        
        # Create NAT Gateways
        for i, eip in enumerate(eips):
            subnet = public_subnet_resources[i]
            nat_gateway = aws.ec2.NatGateway(
                f"{name}-nat-{i+1}",
                allocation_id=eip.id,
                subnet_id=subnet.id,
                tags={**tags, "Name": f"{name}-nat-{i+1}"},
            )
            nat_gateway_resources.append(nat_gateway)
    
    # Create private subnets
    private_subnet_resources = []
    for i, (az, cidr) in enumerate(zip(azs, private_subnets)):
        subnet = aws.ec2.Subnet(
            f"{name}-private-{i+1}",
            vpc_id=vpc.id,
            cidr_block=cidr,
            availability_zone=az,
            tags={
                **tags,
                "Name": f"{name}-private-{i+1}",
                "kubernetes.io/role/internal-elb": "1",
            },
        )
        private_subnet_resources.append(subnet)
    
    # Create private route tables
    private_route_table_resources = []
    for i, subnet in enumerate(private_subnet_resources):
        # Determine which NAT Gateway to use
        nat_index = 0 if single_nat_gateway else min(i, len(nat_gateway_resources) - 1)
        
        # Create route table
        route_table = aws.ec2.RouteTable(
            f"{name}-private-rt-{i+1}",
            vpc_id=vpc.id,
            tags={**tags, "Name": f"{name}-private-rt-{i+1}"},
        )
        private_route_table_resources.append(route_table)
        
        # Create route to NAT Gateway if available
        if nat_gateway_resources:
            aws.ec2.Route(
                f"{name}-private-route-{i+1}",
                route_table_id=route_table.id,
                destination_cidr_block="0.0.0.0/0",
                nat_gateway_id=nat_gateway_resources[nat_index].id,
            )
        
        # Associate private subnet with route table
        aws.ec2.RouteTableAssociation(
            f"{name}-private-rta-{i+1}",
            subnet_id=subnet.id,
            route_table_id=route_table.id,
        )
    
    # Return VPC details
    return VpcResult(
        vpc_id=vpc.id,
        private_subnet_ids=pulumi.Output.all(*[subnet.id for subnet in private_subnet_resources]),
        public_subnet_ids=pulumi.Output.all(*[subnet.id for subnet in public_subnet_resources]),
        nat_gateway_ids=pulumi.Output.all(*[nat.id for nat in nat_gateway_resources]) if nat_gateway_resources else pulumi.Output.from_input([]),
        route_table_ids=pulumi.Output.all(*[rt.id for rt in private_route_table_resources + [public_route_table]]),
    )
