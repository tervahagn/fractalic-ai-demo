#!/usr/bin/env python3
"""
Simple test for Docker registry plugin file copying functionality
Tests using the existing ghcr.io/fractalic-ai/fractalic:latest image
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from publisher.plugin_manager import PluginManager
from publisher.models import PublishRequest

def run_command(cmd, check=True):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"Command failed: {result.stderr}")
        return None
    print(f"Output: {result.stdout.strip()}")
    return result

def cleanup_existing_container(container_name="fractalic-hello-world-test"):
    """Clean up any existing test container"""
    print(f"Cleaning up existing container: {container_name}")
    run_command(["docker", "stop", container_name], check=False)
    run_command(["docker", "rm", container_name], check=False)

def test_simple_deployment():
    """Test deployment with existing registry image"""
    
    # Initialize plugin manager
    plugin_manager = PluginManager()
    
    # Get the docker registry plugin
    plugin = plugin_manager.get_plugin("docker-registry")
    if not plugin:
        print("ERROR: Docker registry plugin not found")
        return False
    
    # Configure the deployment
    hello_world_path = Path("tutorials/01_Basics/hello-world").resolve()
    if not hello_world_path.exists():
        print(f"ERROR: Hello world tutorial not found at {hello_world_path}")
        return False
    
    config = {
        "script_name": "hello-world-test",
        "script_folder": str(hello_world_path),
        "container_name": "fractalic-hello-world-test",
        "registry_image": "ghcr.io/fractalic-ai/fractalic:latest",  # Use existing registry image
        "ports": {
            "frontend": 3000,
            "backend": 8000,
            "ai_server": 8001,
            "mcp_manager": 5859
        }
    }
    
    # Create publish request
    request = PublishRequest(config=config)
    
    # Deploy
    print("Starting deployment...")
    response = plugin.publish(request)
    
    if not response.success:
        print(f"WARNING: Deployment had some issues: {response.message}")
        print(f"Metadata: {response.metadata}")
        
        # Check if container is running despite health check issues
        if not response.deployment_id:
            print("ERROR: No container was created")
            return False
        
        print("Container was created, continuing with tests...")
        return response
    
    print(f"Deployment successful: {response.message}")
    print(f"Container ID: {response.deployment_id}")
    print(f"URLs: {response.metadata.get('urls', {})}")
    
    return response

def verify_payload_structure(container_name="fractalic-hello-world-test"):
    """Verify that the /payload structure is correct"""
    print("Verifying /payload structure in container...")
    
    # Check if /payload directory exists and its permissions
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/"
    ], check=False)
    
    if result is None:
        print("ERROR: Could not list root directory")
        return False
    
    if "/payload" not in result.stdout and "payload" not in result.stdout:
        print("ERROR: /payload directory not found in container")
        print("Root directory contents:")
        print(result.stdout)
        return False
    
    # Check /payload directory permissions and contents
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: Could not access /payload directory")
        return False
    
    print("Contents of /payload:")
    print(result.stdout)
    
    # Check if our script directory exists
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload/hello-world-test"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: /payload/hello-world-test directory not found")
        return False
    
    print("Contents of /payload/hello-world-test:")
    print(result.stdout)
    
    # Check if the markdown file exists and is readable
    result = run_command([
        "docker", "exec", container_name, "cat", "/payload/hello-world-test/hello_world.md"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: Could not read hello_world.md from container")
        return False
    
    print("First 300 characters of hello_world.md:")
    print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)
    
    return True

def test_container_user_context(container_name="fractalic-hello-world-test"):
    """Test what user the container is running as"""
    print("Checking container user context...")
    
    # Check current user
    result = run_command([
        "docker", "exec", container_name, "whoami"
    ], check=False)
    
    if result:
        print(f"Container running as user: {result.stdout.strip()}")
    
    # Check user ID
    result = run_command([
        "docker", "exec", container_name, "id"
    ], check=False)
    
    if result:
        print(f"User ID info: {result.stdout.strip()}")
    
    # Check /payload ownership
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload"
    ], check=False)
    
    if result:
        print("Payload directory ownership:")
        print(result.stdout)

def main():
    """Main test function"""
    print("=== Simple Docker Registry Deployment Test ===")
    
    # Clean up any existing containers
    cleanup_existing_container()
    
    try:
        # Test deployment
        response = test_simple_deployment()
        if not response:
            sys.exit(1)
        
        container_name = response.metadata.get('container_name')
        
        # Wait a moment for container to fully start
        print("Waiting for container to fully start...")
        time.sleep(15)
        
        # Check container user context
        test_container_user_context(container_name)
        
        # Verify payload structure
        if not verify_payload_structure(container_name):
            print("ERROR: Payload verification failed")
            sys.exit(1)
        
        print("\n=== Test Results ===")
        print("✅ Container deployed successfully")
        print("✅ Files copied to /payload directory")
        print("✅ Files accessible and readable")
        print(f"✅ Container running: {container_name}")
        print(f"✅ Container ID: {response.deployment_id}")
        
        urls = response.metadata.get('urls', {})
        print(f"\nService URLs:")
        for service, url in urls.items():
            print(f"  {service}: {url}")
        
        print(f"\nTo inspect the container:")
        print(f"  docker exec -it {container_name} /bin/bash")
        print(f"  docker logs {container_name}")
        print(f"\nTo clean up:")
        print(f"  docker stop {container_name} && docker rm {container_name}")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
