#!/usr/bin/env python3
"""
Security Tests for the AI-driven Observability Pipeline.

This module implements security tests for the observability pipeline,
including API security, authentication, authorization, encryption,
and compliance with security best practices.
"""

import os
import sys
import json
import argparse
import logging
import requests
import subprocess
import unittest
from typing import Dict, List, Any, Optional


class SecurityTests(unittest.TestCase):
    """Security tests for the observability pipeline."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        cls.logger = logging.getLogger("security-tests")
        
        # Get configuration
        cls.base_url = os.environ.get('BASE_URL', 'http://localhost:8080')
        cls.api_key = os.environ.get('API_KEY', 'test-api-key')
        cls.admin_api_key = os.environ.get('ADMIN_API_KEY', 'admin-api-key')
        cls.invalid_api_key = 'invalid-api-key'
        
        # Set up headers
        cls.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {cls.api_key}'
        }
        
        cls.admin_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {cls.admin_api_key}'
        }
        
        cls.invalid_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {cls.invalid_api_key}'
        }
    
    def test_api_authentication(self):
        """Test API authentication."""
        # Test with valid API key
        response = requests.get(
            f"{self.base_url}/api/v1/health",
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200, "API should be accessible with valid API key")
        
        # Test with invalid API key
        response = requests.get(
            f"{self.base_url}/api/v1/health",
            headers=self.invalid_headers
        )
        self.assertEqual(response.status_code, 401, "API should reject invalid API key")
        
        # Test without API key
        response = requests.get(
            f"{self.base_url}/api/v1/health"
        )
        self.assertEqual(response.status_code, 401, "API should reject requests without API key")
    
    def test_api_authorization(self):
        """Test API authorization."""
        # Test admin endpoint with regular API key
        response = requests.get(
            f"{self.base_url}/api/v1/admin/users",
            headers=self.headers
        )
        self.assertEqual(response.status_code, 403, "Admin endpoint should reject regular API key")
        
        # Test admin endpoint with admin API key
        response = requests.get(
            f"{self.base_url}/api/v1/admin/users",
            headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 200, "Admin endpoint should accept admin API key")
    
    def test_ssl_tls_configuration(self):
        """Test SSL/TLS configuration."""
        # Skip if using localhost
        if self.base_url.startswith('http://localhost'):
            self.skipTest("Skipping SSL/TLS test for localhost")
        
        # Check if URL uses HTTPS
        self.assertTrue(
            self.base_url.startswith('https://'),
            "API should use HTTPS"
        )
        
        # Check SSL/TLS configuration using OpenSSL
        domain = self.base_url.split('//')[1].split('/')[0]
        result = subprocess.run(
            ['openssl', 's_client', '-connect', f'{domain}:443', '-tls1_2'],
            capture_output=True,
            text=True
        )
        
        # Check if TLS 1.2 is supported
        self.assertIn(
            'Protocol  : TLSv1.2',
            result.stdout,
            "API should support TLS 1.2"
        )
        
        # Check if weak ciphers are disabled
        weak_ciphers = ['RC4', 'MD5', 'SHA1', 'DES', '3DES', 'NULL']
        for cipher in weak_ciphers:
            self.assertNotIn(
                f'Cipher    : {cipher}',
                result.stdout,
                f"API should not use weak cipher {cipher}"
            )
    
    def test_content_security_policy(self):
        """Test Content Security Policy header."""
        response = requests.get(
            f"{self.base_url}/",
            headers=self.headers
        )
        
        self.assertIn(
            'Content-Security-Policy',
            response.headers,
            "API should include Content-Security-Policy header"
        )
        
        csp = response.headers.get('Content-Security-Policy', '')
        self.assertIn(
            "default-src 'self'",
            csp,
            "CSP should include default-src 'self'"
        )
    
    def test_xss_protection(self):
        """Test XSS protection headers."""
        response = requests.get(
            f"{self.base_url}/",
            headers=self.headers
        )
        
        self.assertIn(
            'X-XSS-Protection',
            response.headers,
            "API should include X-XSS-Protection header"
        )
        
        self.assertEqual(
            response.headers.get('X-XSS-Protection'),
            '1; mode=block',
            "X-XSS-Protection should be set to '1; mode=block'"
        )
    
    def test_csrf_protection(self):
        """Test CSRF protection."""
        # Get CSRF token
        response = requests.get(
            f"{self.base_url}/api/v1/csrf-token",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200, "CSRF token endpoint should be accessible")
        self.assertIn('csrf_token', response.json(), "Response should include CSRF token")
        
        csrf_token = response.json()['csrf_token']
        
        # Test API with CSRF token
        headers_with_csrf = self.headers.copy()
        headers_with_csrf['X-CSRF-Token'] = csrf_token
        
        response = requests.post(
            f"{self.base_url}/api/v1/dashboards",
            headers=headers_with_csrf,
            json={'name': 'Test Dashboard'}
        )
        
        self.assertNotEqual(response.status_code, 403, "API should accept request with valid CSRF token")
        
        # Test API without CSRF token
        response = requests.post(
            f"{self.base_url}/api/v1/dashboards",
            headers=self.headers,
            json={'name': 'Test Dashboard'}
        )
        
        self.assertEqual(response.status_code, 403, "API should reject request without CSRF token")
    
    def test_sql_injection(self):
        """Test SQL injection protection."""
        # Test with SQL injection payload
        sql_injection_payload = "' OR 1=1; --"
        
        response = requests.get(
            f"{self.base_url}/api/v1/users?username={sql_injection_payload}",
            headers=self.headers
        )
        
        self.assertNotEqual(response.status_code, 500, "API should handle SQL injection attempt")
        self.assertNotIn(
            'SQL syntax',
            response.text,
            "API should not expose SQL error messages"
        )
    
    def test_rate_limiting(self):
        """Test rate limiting."""
        # Make multiple requests in quick succession
        for _ in range(20):
            requests.get(
                f"{self.base_url}/api/v1/health",
                headers=self.headers
            )
        
        # Check if rate limiting is applied
        response = requests.get(
            f"{self.base_url}/api/v1/health",
            headers=self.headers
        )
        
        rate_limit_headers = [
            'X-RateLimit-Limit',
            'X-RateLimit-Remaining',
            'X-RateLimit-Reset'
        ]
        
        for header in rate_limit_headers:
            self.assertIn(
                header,
                response.headers,
                f"API should include {header} header"
            )
    
    def test_sensitive_data_exposure(self):
        """Test sensitive data exposure."""
        # Check if API returns sensitive data
        response = requests.get(
            f"{self.base_url}/api/v1/users/current",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200, "Current user endpoint should be accessible")
        
        user_data = response.json()
        sensitive_fields = ['password', 'password_hash', 'api_key', 'secret']
        
        for field in sensitive_fields:
            self.assertNotIn(
                field,
                user_data,
                f"API should not expose sensitive field {field}"
            )
    
    def test_security_headers(self):
        """Test security headers."""
        response = requests.get(
            f"{self.base_url}/",
            headers=self.headers
        )
        
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        
        for header, value in security_headers.items():
            self.assertIn(
                header,
                response.headers,
                f"API should include {header} header"
            )
            
            self.assertEqual(
                response.headers.get(header),
                value,
                f"{header} should be set to '{value}'"
            )
    
    def test_dependency_vulnerabilities(self):
        """Test for known vulnerabilities in dependencies."""
        # Run safety check on requirements.txt
        result = subprocess.run(
            ['safety', 'check', '-r', 'requirements.txt', '--json'],
            capture_output=True,
            text=True
        )
        
        # Parse JSON output
        try:
            vulnerabilities = json.loads(result.stdout)
            
            # Check if any vulnerabilities were found
            self.assertEqual(
                len(vulnerabilities),
                0,
                f"Found {len(vulnerabilities)} vulnerable dependencies"
            )
        except json.JSONDecodeError:
            self.fail("Failed to parse safety check output")
    
    def test_logging_and_monitoring(self):
        """Test logging and monitoring."""
        # Make a request that should be logged
        response = requests.post(
            f"{self.base_url}/api/v1/login",
            headers={'Content-Type': 'application/json'},
            json={'username': 'test', 'password': 'wrong-password'}
        )
        
        # Check if the request was logged
        logs_response = requests.get(
            f"{self.base_url}/api/v1/admin/logs?event=login_failure",
            headers=self.admin_headers
        )
        
        self.assertEqual(logs_response.status_code, 200, "Logs endpoint should be accessible")
        
        logs = logs_response.json()
        self.assertGreater(
            len(logs),
            0,
            "Failed login attempt should be logged"
        )
        
        # Check if the log contains the username but not the password
        latest_log = logs[0]
        self.assertIn(
            'test',
            json.dumps(latest_log),
            "Log should include username"
        )
        self.assertNotIn(
            'wrong-password',
            json.dumps(latest_log),
            "Log should not include password"
        )


def run_tests():
    """Run security tests."""
    parser = argparse.ArgumentParser(description='Run security tests')
    parser.add_argument('--base-url', help='Base URL of the API')
    parser.add_argument('--api-key', help='API key for authentication')
    parser.add_argument('--admin-api-key', help='Admin API key for authentication')
    parser.add_argument('--output', help='Output file for test results')
    
    args = parser.parse_args()
    
    # Set environment variables
    if args.base_url:
        os.environ['BASE_URL'] = args.base_url
    if args.api_key:
        os.environ['API_KEY'] = args.api_key
    if args.admin_api_key:
        os.environ['ADMIN_API_KEY'] = args.admin_api_key
    
    # Run tests
    if args.output:
        import xmlrunner
        with open(args.output, 'wb') as output:
            unittest.main(
                testRunner=xmlrunner.XMLTestRunner(output=output),
                argv=[sys.argv[0]]
            )
    else:
        unittest.main(argv=[sys.argv[0]])


if __name__ == '__main__':
    run_tests()
