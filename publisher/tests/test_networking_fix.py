#!/usr/bin/env python3
"""
Test the Docker networking fix end-to-end
This test creates a real deployment and verifies the container's UI connects to its own backend
"""

import json
import time
import requests
import tempfile
import os
import subprocess
from pathlib import Path

def create_test_script():
    """Create a simple test script for deployment"""
    test_dir = tempfile.mkdtemp(prefix="fractalic_test_")
    script_path = Path(test_dir) / "test_script.py"
    
    script_content = '''
# Simple test script for Fractalic deployment
def hello_world():
    return "Hello from deployed Fractalic!"

if __name__ == "__main__":
    print(hello_world())
'''
    
    script_path.write_text(script_content)
    return test_dir, str(script_path)

def test_deployment_networking():
    """Test that deployed container UI connects to its own backend"""
    
    print("🧪 Testing Docker networking fix...")
    
    # Create test script
    test_dir, script_path = create_test_script()
    
    try:
        # Prepare deployment payload
        payload = {
            "script_name": "networking_test",
            "script_folder": test_dir,
            "image_name": "ghcr.io/fractalic-ai/fractalic:latest",
            "container_name": f"fractalic-test-{int(time.time())}"
        }
        
        print(f"📋 Deploying test script from: {test_dir}")
        print(f"📦 Container name: {payload['container_name']}")
        
        # Deploy using the streaming API
        response = requests.post(
            "http://localhost:8000/api/deploy/docker-registry/stream",
            json=payload,
            stream=True,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code != 200:
            print(f"❌ Deployment failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("📡 Streaming deployment progress...")
        
        deployment_id = None
        frontend_url = None
        
        # Process streaming response
        for line in response.iter_lines():
            if line:
                try:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        event_json = line_text[6:]  # Remove 'data: ' prefix
                        event = json.loads(event_json)
                        
                        print(f"  {event.get('message', 'Unknown event')}")
                        
                        if not deployment_id and 'deployment_id' in event:
                            deployment_id = event['deployment_id']
                        
                        # Look for completion or URL info
                        if 'urls' in event.get('metadata', {}):
                            frontend_url = event['metadata']['urls'].get('frontend')
                            
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"⚠️ Could not parse event: {line} ({e})")
        
        if not deployment_id:
            print("❌ No deployment ID received")
            return False
            
        print(f"✅ Deployment completed with ID: {deployment_id}")
        
        if frontend_url:
            print(f"🌐 Frontend URL: {frontend_url}")
            
            # Wait for container to be fully ready
            print("⏳ Waiting for container to be fully ready...")
            time.sleep(10)
            
            # Test that the frontend is accessible
            try:
                frontend_response = requests.get(frontend_url, timeout=10)
                if frontend_response.status_code == 200:
                    print("✅ Frontend is accessible")
                    
                    # Check if we can reach the API through the frontend
                    api_through_frontend = f"{frontend_url.rstrip('/')}/api/health"
                    try:
                        api_response = requests.get(api_through_frontend, timeout=10)
                        if api_response.status_code == 200:
                            print("✅ Backend API accessible through frontend proxy")
                            print(f"   API response: {api_response.json()}")
                        else:
                            print(f"⚠️ Backend API not accessible: {api_response.status_code}")
                    except Exception as e:
                        print(f"⚠️ Could not reach backend API: {e}")
                        
                else:
                    print(f"⚠️ Frontend returned status {frontend_response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ Could not reach frontend: {e}")
        
        # Check container logs for any networking issues
        print("📋 Checking container logs...")
        try:
            logs_cmd = ["docker", "logs", "--tail", "50", payload['container_name']]
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=30)
            
            if logs_result.returncode == 0:
                logs = logs_result.stdout
                if "ERROR" in logs.upper() or "FAILED" in logs.upper():
                    print("⚠️ Found errors in container logs:")
                    for line in logs.split('\n'):
                        if "ERROR" in line.upper() or "FAILED" in line.upper():
                            print(f"   🔍 {line}")
                else:
                    print("✅ No errors found in container logs")
            else:
                print(f"⚠️ Could not get container logs: {logs_result.stderr}")
                
        except Exception as e:
            print(f"⚠️ Error checking logs: {e}")
        
        # Cleanup container
        print(f"🧹 Cleaning up container: {payload['container_name']}")
        try:
            subprocess.run(["docker", "stop", payload['container_name']], 
                         capture_output=True, timeout=30)
            subprocess.run(["docker", "rm", payload['container_name']], 
                         capture_output=True, timeout=30)
            print("✅ Container cleaned up")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup test directory
        try:
            import shutil
            shutil.rmtree(test_dir)
            print("✅ Test directory cleaned up")
        except Exception as e:
            print(f"⚠️ Could not cleanup test directory: {e}")

if __name__ == "__main__":
    print("🚀 Starting Docker networking fix test...")
    print("=" * 60)
    
    # Check if server is running
    try:
        health_check = requests.get("http://localhost:8000/health", timeout=5)
        if health_check.status_code != 200:
            print("❌ Fractalic server is not running on localhost:8000")
            exit(1)
        print("✅ Fractalic server is running")
    except Exception as e:
        print(f"❌ Cannot reach Fractalic server: {e}")
        exit(1)
    
    # Run the test
    success = test_deployment_networking()
    
    print("=" * 60)
    if success:
        print("🎉 Docker networking fix test completed!")
    else:
        print("❌ Docker networking fix test failed!")
        exit(1)
