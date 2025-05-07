"""
Unit tests for the VPC module.

These tests verify that the VPC module creates the expected resources
with the correct configuration.
"""

import unittest
import pulumi
from infrastructure.aws.vpc import create_vpc


class MockResourceMonitor(pulumi.runtime.Mocks):
    """Mock resource monitor for Pulumi testing."""
    
    def new_resource(self, type_, name, inputs, provider, id_):
        """Create a new mock resource."""
        return [f"{name}_id", inputs]
    
    def call(self, token, args, provider):
        """Mock a function call."""
        return {}


class TestVpc(unittest.TestCase):
    """Test cases for the VPC module."""
    
    @pulumi.runtime.test
    def test_vpc_creation(self):
        """Test that the VPC is created with the correct configuration."""
        # Set up the Pulumi mocks
        pulumi.runtime.set_mocks(MockResourceMonitor())
        
        # Define test inputs
        name = "test-vpc"
        cidr = "10.0.0.0/16"
        azs = ["us-east-1a", "us-east-1b", "us-east-1c"]
        private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
        public_subnets = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
        enable_nat_gateway = True
        single_nat_gateway = False
        tags = {"Environment": "test", "Project": "test-project"}
        
        # Create the VPC
        vpc = create_vpc(
            name=name,
            cidr=cidr,
            azs=azs,
            private_subnets=private_subnets,
            public_subnets=public_subnets,
            enable_nat_gateway=enable_nat_gateway,
            single_nat_gateway=single_nat_gateway,
            tags=tags,
        )
        
        # Verify that the VPC ID is set
        def check_vpc_id(vpc_id):
            self.assertIsNotNone(vpc_id)
            self.assertTrue(vpc_id.endswith("_id"))
        
        pulumi.Output.all(vpc.vpc_id).apply(lambda args: check_vpc_id(args[0]))
        
        # Verify that the subnet IDs are set
        def check_subnet_ids(private_subnet_ids, public_subnet_ids):
            self.assertEqual(len(private_subnet_ids), len(private_subnets))
            self.assertEqual(len(public_subnet_ids), len(public_subnets))
            
            for subnet_id in private_subnet_ids + public_subnet_ids:
                self.assertIsNotNone(subnet_id)
                self.assertTrue(subnet_id.endswith("_id"))
        
        pulumi.Output.all(vpc.private_subnet_ids, vpc.public_subnet_ids).apply(
            lambda args: check_subnet_ids(args[0], args[1])
        )
        
        # Verify that the NAT gateway IDs are set
        def check_nat_gateway_ids(nat_gateway_ids):
            self.assertEqual(len(nat_gateway_ids), len(azs) if not single_nat_gateway else 1)
            
            for nat_gateway_id in nat_gateway_ids:
                self.assertIsNotNone(nat_gateway_id)
                self.assertTrue(nat_gateway_id.endswith("_id"))
        
        pulumi.Output.all(vpc.nat_gateway_ids).apply(
            lambda args: check_nat_gateway_ids(args[0])
        )
        
        # Verify that the route table IDs are set
        def check_route_table_ids(route_table_ids):
            # One route table per private subnet plus one for public subnets
            self.assertEqual(len(route_table_ids), len(private_subnets) + 1)
            
            for route_table_id in route_table_ids:
                self.assertIsNotNone(route_table_id)
                self.assertTrue(route_table_id.endswith("_id"))
        
        pulumi.Output.all(vpc.route_table_ids).apply(
            lambda args: check_route_table_ids(args[0])
        )
    
    @pulumi.runtime.test
    def test_vpc_without_nat_gateway(self):
        """Test that the VPC can be created without NAT gateways."""
        # Set up the Pulumi mocks
        pulumi.runtime.set_mocks(MockResourceMonitor())
        
        # Define test inputs
        name = "test-vpc"
        cidr = "10.0.0.0/16"
        azs = ["us-east-1a", "us-east-1b"]
        private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
        public_subnets = ["10.0.101.0/24", "10.0.102.0/24"]
        enable_nat_gateway = False
        tags = {"Environment": "test", "Project": "test-project"}
        
        # Create the VPC
        vpc = create_vpc(
            name=name,
            cidr=cidr,
            azs=azs,
            private_subnets=private_subnets,
            public_subnets=public_subnets,
            enable_nat_gateway=enable_nat_gateway,
            tags=tags,
        )
        
        # Verify that no NAT gateway IDs are set
        def check_nat_gateway_ids(nat_gateway_ids):
            self.assertEqual(len(nat_gateway_ids), 0)
        
        pulumi.Output.all(vpc.nat_gateway_ids).apply(
            lambda args: check_nat_gateway_ids(args[0])
        )
    
    @pulumi.runtime.test
    def test_vpc_with_single_nat_gateway(self):
        """Test that the VPC can be created with a single NAT gateway."""
        # Set up the Pulumi mocks
        pulumi.runtime.set_mocks(MockResourceMonitor())
        
        # Define test inputs
        name = "test-vpc"
        cidr = "10.0.0.0/16"
        azs = ["us-east-1a", "us-east-1b", "us-east-1c"]
        private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
        public_subnets = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
        enable_nat_gateway = True
        single_nat_gateway = True
        tags = {"Environment": "test", "Project": "test-project"}
        
        # Create the VPC
        vpc = create_vpc(
            name=name,
            cidr=cidr,
            azs=azs,
            private_subnets=private_subnets,
            public_subnets=public_subnets,
            enable_nat_gateway=enable_nat_gateway,
            single_nat_gateway=single_nat_gateway,
            tags=tags,
        )
        
        # Verify that only one NAT gateway ID is set
        def check_nat_gateway_ids(nat_gateway_ids):
            self.assertEqual(len(nat_gateway_ids), 1)
            self.assertIsNotNone(nat_gateway_ids[0])
            self.assertTrue(nat_gateway_ids[0].endswith("_id"))
        
        pulumi.Output.all(vpc.nat_gateway_ids).apply(
            lambda args: check_nat_gateway_ids(args[0])
        )


if __name__ == "__main__":
    unittest.main()
