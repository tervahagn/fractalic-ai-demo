#!/usr/bin/env python3
"""
Test script to demonstrate the streaming deployment functionality.

This script tests the Docker registry streaming deployment endpoint and shows
how the real-time progress updates work.
"""

import requests
import json
import time
from typing import Dict, Any


def test_streaming_deployment():
    """Test the streaming deployment endpoint with a mock deployment."""
    
    # Test deployment configuration
    deployment_data = {
        "script_name": "test-streaming-app",
        "script_folder": "/tmp/test-app",  # This would be a real path in production
        "plugin_config": {
            "registry_url": "docker.io",
            "image_name": "python",  # Use a real image that exists
            "image_tag": "3.9-slim"
        },
        "user_files": {
            "app.py": "print('Hello from streaming deployment!')",
            "requirements.txt": "flask==2.3.0"
        },
        "config": {
            "port": 3000,
            "environment": "test"
        }
    }
    
    print("🚀 Testing Fractalic Docker Registry Streaming Deployment")
    print("=" * 60)
    print(f"Script Name: {deployment_data['script_name']}")
    print(f"Image: {deployment_data['plugin_config']['registry_url']}/{deployment_data['plugin_config']['image_name']}:{deployment_data['plugin_config']['image_tag']}")
    print("=" * 60)
    
    try:
        # Make streaming request
        url = "http://localhost:8000/api/deploy/docker-registry/stream"
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        print(f"Connecting to: {url}")
        response = requests.post(url, json=deployment_data, headers=headers, stream=True)
        
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        print("✅ Connected to streaming endpoint")
        print("📡 Receiving deployment progress:")
        print("-" * 60)
        
        # Process streaming response
        deployment_id = None
        final_result = None
        
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    
                    # Store deployment ID and result
                    if 'deployment_id' in data and not deployment_id:
                        deployment_id = data['deployment_id']
                    
                    if 'result' in data:
                        final_result = data['result']
                    
                    # Format and display progress
                    timestamp = data.get('timestamp', '').split('.')[0].replace('T', ' ')
                    stage = data.get('stage', 'unknown').upper()
                    message = data.get('message', '')
                    progress = data.get('progress', 0)
                    
                    # Add emoji based on stage
                    stage_emoji = {
                        'VALIDATING': '🔍',
                        'PULLING': '⬇️',
                        'COPYING': '📁',
                        'STARTING': '🚀',
                        'HEALTH_CHECK': '❤️',
                        'COMPLETED': '✅',
                        'ERROR': '❌'
                    }.get(stage, '📋')
                    
                    print(f"{stage_emoji} [{timestamp}] {stage}: {message} ({progress}%)")
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  Failed to parse JSON: {e}")
                    print(f"Raw line: {line}")
        
        print("-" * 60)
        print("🏁 Deployment stream completed")
        
        if final_result:
            print("\n📋 Final Result:")
            print(f"   Success: {final_result.get('success', False)}")
            print(f"   Message: {final_result.get('message', 'N/A')}")
            
            if final_result.get('success'):
                print(f"   Deployment ID: {final_result.get('deployment_id', 'N/A')}")
                print(f"   Endpoint URL: {final_result.get('endpoint_url', 'N/A')}")
            else:
                error_details = final_result.get('metadata', {})
                if error_details:
                    print(f"   Error Details: {error_details}")
        
        if deployment_id:
            print(f"\n🆔 Deployment ID: {deployment_id}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the server. Make sure it's running on localhost:8000")
        print("   Try running: uvicorn core.ui_server.server:app --host 0.0.0.0 --port 8000 --reload")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def test_server_health():
    """Test if the server is running and responsive."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Server is running and healthy")
            print(f"   UI Server: {health_data.get('ui_server', 'unknown')}")
            print(f"   MCP Manager: {health_data.get('mcp_manager', {}).get('status', 'unknown')}")
            return True
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running or not accessible")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


if __name__ == "__main__":
    print("Fractalic Streaming Deployment Test")
    print("====================================\n")
    
    # First check if server is running
    print("1. Checking server health...")
    if test_server_health():
        print("\n2. Testing streaming deployment...")
        test_streaming_deployment()
    else:
        print("\n❌ Cannot proceed with deployment test - server is not running")
        print("\nTo start the server, run:")
        print("   cd /path/to/fractalic")
        print("   uvicorn core.ui_server.server:app --host 0.0.0.0 --port 8000 --reload")
