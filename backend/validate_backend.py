#!/usr/bin/env python3
"""
Backend validation script against architecture specification.

This script tests the FastAPI backend to verify it conforms to the architecture
and handles all specified cases correctly.

Usage:
    python validate_backend.py [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class ValidationReport:
    """Tracks test results and generates final report."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.findings = []
        self.architecture_issues = []
    
    def record_pass(self, test_name: str):
        """Record a passing test."""
        self.tests_run += 1
        self.tests_passed += 1
        print(f"{Colors.GREEN}âœ“ PASS{Colors.RESET}: {test_name}")
    
    def record_fail(self, test_name: str, expected: str, received: str, severity: str, hypothesis: str):
        """Record a failing test."""
        self.tests_run += 1
        self.tests_failed += 1
        print(f"{Colors.RED}âœ— FAIL{Colors.RESET}: {test_name}")
        self.findings.append({
            "test": test_name,
            "expected": expected,
            "received": received,
            "severity": severity,
            "hypothesis": hypothesis
        })
    
    def add_architecture_issue(self, issue: str):
        """Record an architecture conformance issue."""
        self.architecture_issues.append(issue)
        print(f"{Colors.YELLOW}âš  ARCHITECTURE{Colors.RESET}: {issue}")
    
    def print_summary(self):
        """Print final validation report."""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}VALIDATION REPORT{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
        
        # Summary
        print(f"{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Tests Run: {self.tests_run}")
        print(f"  {Colors.GREEN}Passed: {self.tests_passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {self.tests_failed}{Colors.RESET}")
        
        critical_failures = [f for f in self.findings if f["severity"] == "critical"]
        if critical_failures:
            print(f"  {Colors.RED}{Colors.BOLD}Critical Failures: {len(critical_failures)}{Colors.RESET}")
        
        # Findings
        if self.findings:
            print(f"\n{Colors.BOLD}Findings:{Colors.RESET}")
            for i, finding in enumerate(self.findings, 1):
                severity_color = Colors.RED if finding["severity"] == "critical" else Colors.YELLOW
                print(f"\n{i}. {Colors.BOLD}{finding['test']}{Colors.RESET}")
                print(f"   Severity: {severity_color}{finding['severity']}{Colors.RESET}")
                print(f"   Expected: {finding['expected']}")
                print(f"   Received: {finding['received']}")
                print(f"   Hypothesis: {finding['hypothesis']}")
        
        # Architecture conformance
        if self.architecture_issues:
            print(f"\n{Colors.BOLD}Architecture Conformance Issues:{Colors.RESET}")
            for issue in self.architecture_issues:
                print(f"  â€¢ {issue}")
        else:
            print(f"\n{Colors.GREEN}âœ“ No architecture conformance issues detected{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}\n")


async def check_server_reachable(base_url: str, report: ValidationReport) -> bool:
    """Check if server is reachable."""
    print(f"\n{Colors.BOLD}Setup Checks{Colors.RESET}")
    print(f"Testing server at: {base_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/v1/health", timeout=5.0)
            if response.status_code == 200:
                report.record_pass("Server reachable at /api/v1/health")
                return True
            else:
                report.record_fail(
                    "Server reachable",
                    "200 OK",
                    f"{response.status_code} {response.text}",
                    "critical",
                    "Server not responding correctly"
                )
                return False
    except Exception as e:
        print(f"{Colors.RED}âœ— CRITICAL{Colors.RESET}: Server unreachable - {e}")
        return False


async def check_openapi_schema(base_url: str, report: ValidationReport):
    """Validate OpenAPI schema against architecture."""
    print(f"\n{Colors.BOLD}OpenAPI Schema Validation{Colors.RESET}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/openapi.json", timeout=5.0)
            
            if response.status_code != 200:
                report.record_fail(
                    "OpenAPI schema accessible",
                    "200 OK",
                    f"{response.status_code}",
                    "major",
                    "OpenAPI endpoint not accessible"
                )
                return
            
            schema = response.json()
            
            # Check for required endpoint
            paths = schema.get("paths", {})
            if "/api/v1/process" not in paths:
                report.add_architecture_issue("Missing /api/v1/process endpoint")
            else:
                report.record_pass("Endpoint /api/v1/process exists")
            
            # List all routes
            print(f"\n{Colors.BLUE}Registered routes:{Colors.RESET}")
            for path in paths:
                methods = list(paths[path].keys())
                print(f"  {path}: {', '.join(methods).upper()}")
            
            # Check process endpoint schema
            if "/api/v1/process" in paths:
                process_schema = paths["/api/v1/process"].get("post", {})
                request_body = process_schema.get("requestBody", {})
                
                if not request_body:
                    report.add_architecture_issue("/api/v1/process missing request body schema")
                else:
                    report.record_pass("Process endpoint has request body schema")
            
    except Exception as e:
        report.record_fail(
            "OpenAPI schema validation",
            "Valid schema",
            str(e),
            "major",
            f"Failed to fetch or parse OpenAPI schema: {e}"
        )


async def test_happy_path_minimal(base_url: str, report: ValidationReport):
    """Test 1: Minimal valid DOM manipulation request."""
    print(f"\n{Colors.BOLD}Test 1: Happy Path - Minimal Request{Colors.RESET}")
    
    request_data = {
        "use_case": "dom_manipulation",
        "page_url": "https://example.com",
        "html": "<html><body><header><h1>Header</h1></header><main><p>Content</p></main><footer><p>Footer</p></footer></body></html>",
        "user_prompt": "move the footer to the top of the page",
        "params": {},
        "client_metadata": {}
    }
    
    print(f"Request: POST {base_url}/api/v1/process")
    print(f"Body: {json.dumps(request_data, indent=2)}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                json=request_data,
                timeout=30.0
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code != 200:
                report.record_fail(
                    "Minimal DOM manipulation request",
                    "200 OK",
                    f"{response.status_code}: {response.text}",
                    "critical",
                    "Basic request failed"
                )
                return
            
            data = response.json()
            
            # Validate envelope structure
            required_fields = ["trace_id", "use_case", "status"]
            for field in required_fields:
                if field not in data:
                    report.add_architecture_issue(f"Response missing required field: {field}")
            
            if data.get("status") != "ok":
                report.record_fail(
                    "Response status",
                    "ok",
                    data.get("status"),
                    "major",
                    "Request did not succeed"
                )
                return
            
            # Check result structure
            result = data.get("result")
            if not result:
                report.record_fail(
                    "Response has result",
                    "result object",
                    "None",
                    "critical",
                    "No result in successful response"
                )
                return
            
            # Check patches
            patches = result.get("patches", [])
            if not patches:
                report.record_fail(
                    "Response has patches",
                    "list of patch operations",
                    "empty list",
                    "major",
                    "No patches generated for valid prompt"
                )
            else:
                report.record_pass(f"Response contains {len(patches)} patch operations")
                
                # Validate patch operations
                valid_ops = ["move", "insert", "replace", "delete", "set_attr", "add_class", "remove_class", "wrap", "unwrap"]
                for i, patch in enumerate(patches):
                    op = patch.get("op")
                    if op not in valid_ops:
                        report.add_architecture_issue(f"Patch {i} has invalid op: {op}")
            
            # Check usage
            usage = data.get("usage")
            if usage:
                if usage.get("input_tokens", 0) > 0 and usage.get("output_tokens", 0) > 0:
                    report.record_pass("Usage tokens present and non-zero")
                else:
                    report.record_fail(
                        "Usage tokens",
                        "non-zero values",
                        f"input={usage.get('input_tokens')}, output={usage.get('output_tokens')}",
                        "minor",
                        "Token counts missing or zero"
                    )
            
            # Check timing
            timing = data.get("timing_ms")
            if timing:
                required_stages = ["preprocess_ms", "ai_ms", "postprocess_ms", "total_ms"]
                for stage in required_stages:
                    if stage not in timing or timing[stage] <= 0:
                        report.add_architecture_issue(f"Timing missing or invalid for stage: {stage}")
                    else:
                        report.record_pass(f"Timing for {stage}: {timing[stage]}ms")
            
    except Exception as e:
        report.record_fail(
            "Minimal DOM manipulation request",
            "Successful response",
            str(e),
            "critical",
            f"Request failed with exception: {e}"
        )


async def test_unknown_use_case(base_url: str, report: ValidationReport):
    """Test 5: Unknown use_case."""
    print(f"\n{Colors.BOLD}Test 5: Unknown use_case{Colors.RESET}")
    
    request_data = {
        "use_case": "banana",
        "page_url": "https://example.com",
        "html": "<html><body><p>Test</p></body></html>",
        "user_prompt": "do something",
        "params": {}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                json=request_data,
                timeout=10.0
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code >= 500:
                report.record_fail(
                    "Unknown use_case error handling",
                    "4xx error",
                    f"{response.status_code}",
                    "major",
                    "Server error instead of client error"
                )
                return
            
            if response.status_code in [400, 422]:
                data = response.json()
                if "error" in data or "detail" in data:
                    report.record_pass("Unknown use_case returns structured error")
                else:
                    report.record_fail(
                        "Error structure",
                        "Structured error with code/message",
                        json.dumps(data),
                        "minor",
                        "Error response not properly structured"
                    )
            else:
                report.record_fail(
                    "Unknown use_case status code",
                    "400 or 422",
                    f"{response.status_code}",
                    "minor",
                    "Unexpected status code for invalid use_case"
                )
    
    except Exception as e:
        report.record_fail(
            "Unknown use_case handling",
            "Graceful error",
            str(e),
            "major",
            f"Exception: {e}"
        )


async def test_unimplemented_use_case(base_url: str, report: ValidationReport):
    """Test 6: Registered but unimplemented use_case (qa)."""
    print(f"\n{Colors.BOLD}Test 6: Unimplemented use_case (qa){Colors.RESET}")
    
    request_data = {
        "use_case": "qa",
        "page_url": "https://example.com",
        "html": "<html><body><p>Test content</p></body></html>",
        "user_prompt": "What is this about?",
        "params": {}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                json=request_data,
                timeout=10.0
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "error":
                error = data.get("error", {})
                if "not.*implemented" in error.get("message", "").lower() or "not.*available" in error.get("message", "").lower():
                    report.record_pass("Unimplemented handler returns structured error")
                else:
                    report.record_fail(
                        "Unimplemented handler error message",
                        "Message indicating not implemented",
                        error.get("message"),
                        "minor",
                        "Error message unclear about implementation status"
                    )
            elif response.status_code >= 500:
                report.record_fail(
                    "Unimplemented handler",
                    "Structured error response",
                    f"500 error: {response.text}",
                    "major",
                    "Unimplemented handler crashes instead of returning error"
                )
            else:
                report.record_fail(
                    "Unimplemented handler response",
                    "Error status",
                    f"status={response.status_code}, body={response.text}",
                    "minor",
                    "Unexpected response for unimplemented handler"
                )
    
    except Exception as e:
        report.record_fail(
            "Unimplemented use_case handling",
            "Graceful error",
            str(e),
            "major",
            f"Exception: {e}"
        )


async def test_malformed_json(base_url: str, report: ValidationReport):
    """Test 7: Malformed JSON."""
    print(f"\n{Colors.BOLD}Test 7: Malformed JSON{Colors.RESET}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                content="{invalid json}",
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code in [400, 422]:
                report.record_pass("Malformed JSON returns 4xx error")
            else:
                report.record_fail(
                    "Malformed JSON handling",
                    "400 or 422",
                    f"{response.status_code}",
                    "minor",
                    "Unexpected status code for malformed JSON"
                )
    
    except Exception as e:
        report.record_fail(
            "Malformed JSON handling",
            "4xx error",
            str(e),
            "minor",
            f"Exception: {e}"
        )


async def test_missing_required_fields(base_url: str, report: ValidationReport):
    """Test 8: Missing required fields."""
    print(f"\n{Colors.BOLD}Test 8: Missing Required Fields{Colors.RESET}")
    
    test_cases = [
        ("missing html", {"use_case": "dom_manipulation", "page_url": "https://example.com", "user_prompt": "test"}),
        ("missing user_prompt", {"use_case": "dom_manipulation", "page_url": "https://example.com", "html": "<html></html>"}),
        ("missing page_url", {"use_case": "dom_manipulation", "html": "<html></html>", "user_prompt": "test"}),
    ]
    
    for test_name, request_data in test_cases:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/api/v1/process",
                    json=request_data,
                    timeout=10.0
                )
                
                print(f"\n{test_name}:")
                print(f"Status: {response.status_code}")
                
                if response.status_code == 422:
                    data = response.json()
                    if "detail" in data:
                        report.record_pass(f"Missing field validation: {test_name}")
                    else:
                        report.record_fail(
                            f"Missing field error structure: {test_name}",
                            "Pydantic validation error with detail",
                            json.dumps(data),
                            "minor",
                            "Error structure not Pydantic-shaped"
                        )
                else:
                    report.record_fail(
                        f"Missing field status: {test_name}",
                        "422",
                        f"{response.status_code}",
                        "minor",
                        "Wrong status code for missing required field"
                    )
        
        except Exception as e:
            report.record_fail(
                f"Missing field handling: {test_name}",
                "422 validation error",
                str(e),
                "minor",
                f"Exception: {e}"
            )


async def test_script_injection_safety(base_url: str, report: ValidationReport):
    """Test 10: Output sanitization - script injection."""
    print(f"\n{Colors.BOLD}Test 10: Script Injection Safety (CRITICAL){Colors.RESET}")
    
    request_data = {
        "use_case": "dom_manipulation",
        "page_url": "https://example.com",
        "html": "<html><body><div id='target'>Content</div></body></html>",
        "user_prompt": "insert a new div after the target div",
        "params": {}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/process",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                report.record_fail(
                    "Script injection test",
                    "200 OK",
                    f"{response.status_code}",
                    "major",
                    "Request failed"
                )
                return
            
            data = response.json()
            result = data.get("result", {})
            patches = result.get("patches", [])
            
            # Check all patches for dangerous content
            dangerous_patterns = ["<script", "onclick=", "onerror=", "javascript:", "<iframe"]
            found_dangerous = []
            
            for patch in patches:
                patch_str = json.dumps(patch).lower()
                for pattern in dangerous_patterns:
                    if pattern in patch_str:
                        found_dangerous.append((patch, pattern))
            
            if found_dangerous:
                report.record_fail(
                    "Output sanitization",
                    "No script tags or event handlers in patches",
                    f"Found dangerous patterns: {found_dangerous}",
                    "critical",
                    "Output sanitization not working - security vulnerability"
                )
            else:
                report.record_pass("Output sanitization: No dangerous content in patches")
    
    except Exception as e:
        report.record_fail(
            "Script injection safety test",
            "Safe output",
            str(e),
            "critical",
            f"Exception: {e}"
        )


async def test_trace_id_uniqueness(base_url: str, report: ValidationReport):
    """Test 12: Trace ID uniqueness."""
    print(f"\n{Colors.BOLD}Test 12: Trace ID Uniqueness{Colors.RESET}")
    
    request_data = {
        "use_case": "dom_manipulation",
        "page_url": "https://example.com",
        "html": "<html><body><p>Test</p></body></html>",
        "user_prompt": "add a class to the paragraph",
        "params": {}
    }
    
    try:
        trace_ids = []
        async with httpx.AsyncClient() as client:
            for i in range(3):
                response = await client.post(
                    f"{base_url}/api/v1/process",
                    json=request_data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    trace_id = data.get("trace_id")
                    if trace_id:
                        trace_ids.append(trace_id)
        
        if len(trace_ids) == 3 and len(set(trace_ids)) == 3:
            report.record_pass("Trace IDs are unique across requests")
        else:
            report.record_fail(
                "Trace ID uniqueness",
                "3 unique trace IDs",
                f"Got {len(set(trace_ids))} unique IDs from {len(trace_ids)} requests",
                "minor",
                "Trace IDs not unique"
            )
    
    except Exception as e:
        report.record_fail(
            "Trace ID uniqueness test",
            "Unique trace IDs",
            str(e),
            "minor",
            f"Exception: {e}"
        )


async def main():
    """Run all validation tests."""
    parser = argparse.ArgumentParser(description="Validate backend against architecture spec")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the backend")
    args = parser.parse_args()
    
    report = ValidationReport()
    
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}Backend Validation Against Architecture Specification{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
    
    # Setup checks
    if not await check_server_reachable(args.base_url, report):
        print(f"\n{Colors.RED}{Colors.BOLD}CRITICAL: Server unreachable. Stopping validation.{Colors.RESET}\n")
        return 1
    
    await check_openapi_schema(args.base_url, report)
    
    # Functional tests
    print(f"\n{Colors.BOLD}Functional Tests{Colors.RESET}")
    await test_happy_path_minimal(args.base_url, report)
    await test_unknown_use_case(args.base_url, report)
    await test_unimplemented_use_case(args.base_url, report)
    await test_malformed_json(args.base_url, report)
    await test_missing_required_fields(args.base_url, report)
    await test_script_injection_safety(args.base_url, report)
    await test_trace_id_uniqueness(args.base_url, report)
    
    # Print final report
    report.print_summary()
    
    return 0 if report.tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
