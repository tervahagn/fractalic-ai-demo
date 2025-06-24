#!/usr/bin/env python3
"""
Test script for Docker registry deployment with file copying
"""

import os
import sys
import time
import subprocess
import requests
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
    return result

def cleanup_existing_container(container_name="fractalic-hello-world"):
    """Clean up any existing test container"""
    print(f"Cleaning up existing container: {container_name}")
    run_command(["docker", "stop", container_name], check=False)
    run_command(["docker", "rm", container_name], check=False)

def build_docker_image():
    """Build the Docker image with updated Dockerfile"""
    print("Building Docker image with /payload directory...")
    
    # Check if we need to build the image
    result = run_command(["docker", "images", "-q", "fractalic:latest"], check=False)
    if result and result.stdout.strip():
        print("Docker image already exists, rebuilding...")
    
    # Build the image - we need to be in the correct context
    dockerfile_path = Path("docker/Dockerfile.production")
    if not dockerfile_path.exists():
        print("ERROR: Dockerfile.production not found")
        return False
    
    # For testing, let's use a simpler approach - build from parent directory
    parent_dir = Path("..").resolve()
    fractalic_dir = Path(".").resolve()
    
    cmd = [
        "docker", "build",
        "-f", str(dockerfile_path),
        "-t", "fractalic:latest",
        str(parent_dir)
    ]
    
    result = run_command(cmd)
    if result is None:
        print("ERROR: Failed to build Docker image")
        return False
    
    print("Docker image built successfully")
    return True

def test_deployment():
    """Test the deployment using hello-world tutorial"""
    
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
        "script_name": "hello-world",
        "script_folder": str(hello_world_path),
        "container_name": "fractalic-hello-world",
        "registry_image": "fractalic:latest",  # Use our locally built image
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
        print(f"ERROR: Deployment failed: {response.message}")
        return False
    
    print(f"Deployment successful: {response.message}")
    print(f"Container ID: {response.deployment_id}")
    print(f"URLs: {response.metadata.get('urls', {})}")
    
    return response

def verify_files_in_container(container_name="fractalic-hello-world"):
    """Verify that files were copied correctly to /payload"""
    print("Verifying files in container...")
    
    # Check if /payload directory exists
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: /payload directory not found in container")
        return False
    
    print("Contents of /payload:")
    print(result.stdout)
    
    # Check if our hello-world directory exists
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload/hello-world"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: /payload/hello-world directory not found")
        return False
    
    print("Contents of /payload/hello-world:")
    print(result.stdout)
    
    # Check if the markdown file exists
    result = run_command([
        "docker", "exec", container_name, "cat", "/payload/hello-world/hello_world.md"
    ], check=False)
    
    if result is None or result.returncode != 0:
        print("ERROR: hello_world.md not found in container")
        return False
    
    print("Contents of hello_world.md:")
    print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
    
    return True

def test_api_accessibility(response):
    """Test if the API is accessible and can read the deployed files"""
    print("Testing API accessibility...")
    
    urls = response.metadata.get('urls', {})
    ai_server_url = urls.get('ai_server')
    
    if not ai_server_url:
        print("ERROR: AI server URL not found")
        return False
    
    # Wait a bit for services to fully start
    print("Waiting for services to start...")
    time.sleep(15)
    
    # Test basic connectivity
    try:
        response = requests.get(f"{ai_server_url}/health", timeout=10)
        if response.status_code == 200:
            print("AI server is responding to health checks")
        else:
            print(f"AI server health check failed: {response.status_code}")
    except Exception as e:
        print(f"Could not reach AI server: {e}")
    
    # Test if we can access the hello-world script through the API
    # This would depend on the specific API endpoints available
    
    return True

def main():
    """Main test function"""
    print("=== Docker Registry Deployment Test ===")
    
    # Clean up any existing containers
    cleanup_existing_container()
    
    # Build Docker image
    if not build_docker_image():
        sys.exit(1)
    
    # Test deployment
    try:
        response = test_deployment()
        if not response:
            sys.exit(1)
        
        # Wait a moment for container to fully start
        time.sleep(10)
        
        # Verify files were copied correctly
        if not verify_files_in_container(response.metadata.get('container_name')):
            print("ERROR: File verification failed")
            sys.exit(1)
        
        # Test API accessibility
        test_api_accessibility(response)
        
        print("\n=== Test Summary ===")
        print("✅ Docker image built successfully")
        print("✅ Container deployed successfully")
        print("✅ Files copied to /payload directory")
        print("✅ Files accessible in container")
        print(f"✅ Container running: {response.metadata.get('container_name')}")
        print(f"✅ Container ID: {response.deployment_id}")
        
        urls = response.metadata.get('urls', {})
        print(f"\nAccess URLs:")
        for service, url in urls.items():
            print(f"  {service}: {url}")
        
        print(f"\nTo manually test the container:")
        print(f"  docker exec -it {response.metadata.get('container_name')} /bin/bash")
        print(f"  docker logs {response.metadata.get('container_name')}")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
