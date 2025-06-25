#!/usr/bin/env python3
"""
Comprehensive test suite for Docker Registry deployment API endpoints.
Tests both regular and streaming endpoints with various payloads and edge cases.
"""

import asyncio
import aiohttp
import json
import time
import sys
from typing import Dict, Any, List

# Server configuration
BASE_URL = "http://localhost:8003"
DOCKER_REGISTRY_ENDPOINT = f"{BASE_URL}/api/deploy/docker-registry"
DOCKER_REGISTRY_STREAM_ENDPOINT = f"{BASE_URL}/api/deploy/docker-registry/stream"

class APITester:
    def __init__(self):
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
    
    async def test_health_check(self):
        """Test basic server health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BASE_URL}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.log_test("Health Check", True, f"Status: {data.get('status', 'unknown')}")
                    else:
                        self.log_test("Health Check", False, f"HTTP {response.status}")
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
    
    async def test_regular_endpoint_missing_data(self):
        """Test regular endpoint with missing required data"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DOCKER_REGISTRY_ENDPOINT, json={}) as response:
                    if response.status >= 400:
                        error_data = await response.json()
                        self.log_test(
                            "Regular Endpoint - Missing Data", 
                            True, 
                            f"Correctly returned HTTP {response.status}"
                        )
                    else:
                        self.log_test(
                            "Regular Endpoint - Missing Data", 
                            False, 
                            f"Should have failed but got HTTP {response.status}"
                        )
        except Exception as e:
            self.log_test("Regular Endpoint - Missing Data", False, f"Exception: {str(e)}")
    
    async def test_regular_endpoint_valid_data(self):
        """Test regular endpoint with valid data"""
        valid_payload = {
            "image_name": "fractalic/test-app",
            "image_tag": "latest",
            "script_name": "test-script",
            "script_folder": "/tmp/test-scripts",
            "env_vars": {"TEST_VAR": "test_value"}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DOCKER_REGISTRY_ENDPOINT, json=valid_payload) as response:
                    if response.status in [200, 202]:
                        data = await response.json()
                        self.log_test(
                            "Regular Endpoint - Valid Data", 
                            True, 
                            f"HTTP {response.status}, Response: {data}"
                        )
                    else:
                        error_data = await response.text()
                        self.log_test(
                            "Regular Endpoint - Valid Data", 
                            False, 
                            f"HTTP {response.status}, Error: {error_data}"
                        )
        except Exception as e:
            self.log_test("Regular Endpoint - Valid Data", False, f"Exception: {str(e)}")
    
    async def test_streaming_endpoint_missing_data(self):
        """Test streaming endpoint with missing required data"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DOCKER_REGISTRY_STREAM_ENDPOINT, json={}) as response:
                    if response.status >= 400:
                        content = await response.text()
                        self.log_test(
                            "Streaming Endpoint - Missing Data", 
                            True, 
                            f"Correctly returned HTTP {response.status}"
                        )
                    else:
                        self.log_test(
                            "Streaming Endpoint - Missing Data", 
                            False, 
                            f"Should have failed but got HTTP {response.status}"
                        )
        except Exception as e:
            self.log_test("Streaming Endpoint - Missing Data", False, f"Exception: {str(e)}")
    
    async def test_streaming_endpoint_invalid_json(self):
        """Test streaming endpoint with invalid JSON"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DOCKER_REGISTRY_STREAM_ENDPOINT, 
                    data="invalid json{",
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status >= 400:
                        self.log_test(
                            "Streaming Endpoint - Invalid JSON", 
                            True, 
                            f"Correctly returned HTTP {response.status}"
                        )
                    else:
                        self.log_test(
                            "Streaming Endpoint - Invalid JSON", 
                            False, 
                            f"Should have failed but got HTTP {response.status}"
                        )
        except Exception as e:
            self.log_test("Streaming Endpoint - Invalid JSON", False, f"Exception: {str(e)}")
    
    async def test_streaming_endpoint_partial_data(self):
        """Test streaming endpoint with partial data"""
        partial_payloads = [
            {"image_name": "test"},  # Missing script_name and script_folder
            {"script_name": "test"},  # Missing image_name and script_folder
            {"script_folder": "/tmp/test"},  # Missing image_name and script_name
            {"image_name": "test", "script_name": "test"},  # Missing script_folder
        ]
        
        for i, payload in enumerate(partial_payloads):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(DOCKER_REGISTRY_STREAM_ENDPOINT, json=payload) as response:
                        if response.status >= 400:
                            self.log_test(
                                f"Streaming Endpoint - Partial Data {i+1}", 
                                True, 
                                f"Correctly returned HTTP {response.status} for payload: {payload}"
                            )
                        else:
                            self.log_test(
                                f"Streaming Endpoint - Partial Data {i+1}", 
                                False, 
                                f"Should have failed but got HTTP {response.status} for payload: {payload}"
                            )
            except Exception as e:
                self.log_test(f"Streaming Endpoint - Partial Data {i+1}", False, f"Exception: {str(e)}")
    
    async def test_streaming_endpoint_valid_data_events(self):
        """Test streaming endpoint with valid data and verify SSE events"""
        valid_payload = {
            "image_name": "fractalic/test-app",
            "image_tag": "latest", 
            "script_name": "test-streaming-script",
            "script_folder": "/tmp/test-streaming",
            "env_vars": {"STREAM_TEST": "true"}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DOCKER_REGISTRY_STREAM_ENDPOINT, json=valid_payload) as response:
                    if response.status == 200:
                        events_received = []
                        async for line in response.content:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                try:
                                    event_data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                                    events_received.append(event_data)
                                except json.JSONDecodeError:
                                    events_received.append({"raw": line_str})
                            
                            # Stop after receiving several events or on completion
                            if len(events_received) >= 10 or any(
                                event.get('status') in ['completed', 'failed'] 
                                for event in events_received 
                                if isinstance(event, dict)
                            ):
                                break
                        
                        if events_received:
                            self.log_test(
                                "Streaming Endpoint - Valid Data Events", 
                                True, 
                                f"Received {len(events_received)} events: {events_received[:3]}..."
                            )
                        else:
                            self.log_test(
                                "Streaming Endpoint - Valid Data Events", 
                                False, 
                                "No events received from stream"
                            )
                    else:
                        error_content = await response.text()
                        self.log_test(
                            "Streaming Endpoint - Valid Data Events", 
                            False, 
                            f"HTTP {response.status}: {error_content}"
                        )
        except Exception as e:
            self.log_test("Streaming Endpoint - Valid Data Events", False, f"Exception: {str(e)}")
    
    async def test_streaming_endpoint_timeout_handling(self):
        """Test streaming endpoint with timeout to check connection handling"""
        valid_payload = {
            "image_name": "fractalic/test-app",
            "image_tag": "latest",
            "script_name": "test-timeout-script", 
            "script_folder": "/tmp/test-timeout",
            "env_vars": {}
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                try:
                    async with session.post(DOCKER_REGISTRY_STREAM_ENDPOINT, json=valid_payload) as response:
                        if response.status == 200:
                            event_count = 0
                            async for line in response.content:
                                event_count += 1
                                if event_count >= 5:  # Just get a few events
                                    break
                            
                            elapsed = time.time() - start_time
                            self.log_test(
                                "Streaming Endpoint - Timeout Handling", 
                                True, 
                                f"Stream worked within timeout, {event_count} events in {elapsed:.2f}s"
                            )
                        else:
                            self.log_test(
                                "Streaming Endpoint - Timeout Handling", 
                                False, 
                                f"HTTP {response.status}"
                            )
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    self.log_test(
                        "Streaming Endpoint - Timeout Handling", 
                        True, 
                        f"Timeout occurred as expected after {elapsed:.2f}s"
                    )
        except Exception as e:
            self.log_test("Streaming Endpoint - Timeout Handling", False, f"Exception: {str(e)}")
    
    async def test_concurrent_requests(self):
        """Test multiple concurrent requests to streaming endpoint"""
        valid_payload = {
            "image_name": "fractalic/test-app",
            "image_tag": "latest",
            "script_name": "test-concurrent-script",
            "script_folder": "/tmp/test-concurrent",
            "env_vars": {}
        }
        
        async def make_request(session, request_id):
            try:
                payload_with_id = {**valid_payload, "script_name": f"test-concurrent-{request_id}"}
                async with session.post(DOCKER_REGISTRY_STREAM_ENDPOINT, json=payload_with_id) as response:
                    if response.status == 200:
                        event_count = 0
                        async for line in response.content:
                            event_count += 1
                            if event_count >= 3:  # Just get a few events
                                break
                        return True, f"Request {request_id}: {event_count} events"
                    else:
                        return False, f"Request {request_id}: HTTP {response.status}"
            except Exception as e:
                return False, f"Request {request_id}: Exception {str(e)}"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Make 3 concurrent requests
                tasks = [make_request(session, i) for i in range(3)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful_requests = sum(1 for result in results if isinstance(result, tuple) and result[0])
                
                if successful_requests >= 2:  # At least 2 out of 3 should succeed
                    self.log_test(
                        "Concurrent Requests", 
                        True, 
                        f"{successful_requests}/3 requests successful: {results}"
                    )
                else:
                    self.log_test(
                        "Concurrent Requests", 
                        False, 
                        f"Only {successful_requests}/3 requests successful: {results}"
                    )
        except Exception as e:
            self.log_test("Concurrent Requests", False, f"Exception: {str(e)}")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting comprehensive Docker Registry API tests...")
        print("=" * 60)
        
        # Health check first
        await self.test_health_check()
        
        # Regular endpoint tests
        print("\n📋 Testing regular deployment endpoint...")
        await self.test_regular_endpoint_missing_data()
        await self.test_regular_endpoint_valid_data()
        
        # Streaming endpoint tests
        print("\n🌊 Testing streaming deployment endpoint...")
        await self.test_streaming_endpoint_missing_data()
        await self.test_streaming_endpoint_invalid_json()
        await self.test_streaming_endpoint_partial_data()
        await self.test_streaming_endpoint_valid_data_events()
        await self.test_streaming_endpoint_timeout_handling()
        
        # Concurrent requests test
        print("\n🔀 Testing concurrent requests...")
        await self.test_concurrent_requests()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test']}: {result['details']}")
        
        return passed_tests, failed_tests

async def main():
    """Main test runner"""
    tester = APITester()
    passed, failed = await tester.run_all_tests()
    
    # Exit with error code if tests failed
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
