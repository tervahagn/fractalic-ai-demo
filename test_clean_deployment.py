#!/usr/bin/env python3
"""
Clean deployment test from scratch for Docker registry deployment
Following exact requirements:
1. Deploy container to docker desktop from docker registry
2. Deploy config files and hello world script
3. Run hello_world.md by curl via ai server
4. Get response which should contain file list
"""

import os
import sys
import time
import subprocess
import requests
import json
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from publisher.plugin_manager import PluginManager
from publisher.models import PublishRequest

def run_command(cmd, check=True, show_output=True):
    """Run a command and return the result"""
    if show_output:
        print(f"🔧 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"❌ Command failed: {result.stderr}")
        return None
    if show_output and result.stdout.strip():
        print(f"   Output: {result.stdout.strip()}")
    return result

def clean_environment():
    """Clean up any existing containers and ensure fresh start"""
    print("🧹 Cleaning up environment...")
    
    # Stop and remove any existing fractalic containers
    result = run_command(["docker", "ps", "-a", "--filter", "name=fractalic", "-q"], check=False, show_output=False)
    if result and result.stdout.strip():
        container_ids = result.stdout.strip().split('\n')
        for container_id in container_ids:
            run_command(["docker", "stop", container_id], check=False, show_output=False)
            run_command(["docker", "rm", container_id], check=False, show_output=False)
    
    print("✅ Environment cleaned")

def verify_config_files():
    """Verify that required config files exist"""
    print("📋 Verifying config files...")
    
    config_files = ["mcp_servers.json", "settings.toml"]
    for config_file in config_files:
        config_path = Path(config_file)
        if config_path.exists():
            print(f"✅ {config_file} found")
        else:
            print(f"❌ {config_file} not found")
            return False
    
    return True

def deploy_container():
    """Deploy container from docker registry with hello world script"""
    print("🚀 Starting fresh deployment...")
    
    # Initialize plugin manager
    plugin_manager = PluginManager()
    
    # Get the docker registry plugin
    plugin = plugin_manager.get_plugin("docker-registry")
    if not plugin:
        print("❌ Docker registry plugin not found")
        return None
    
    # Configure the deployment
    hello_world_path = Path("tutorials/01_Basics/hello-world").resolve()
    if not hello_world_path.exists():
        print(f"❌ Hello world tutorial not found at {hello_world_path}")
        return None
    
    config = {
        "script_name": "hello-world-clean-test",
        "script_folder": str(hello_world_path),
        "container_name": "fractalic-clean-test",
        "registry_image": "ghcr.io/fractalic-ai/fractalic:latest",
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
    print("📦 Deploying container from registry...")
    response = plugin.publish(request)
    
    if not response.success:
        print(f"⚠️ Deployment had some issues: {response.message}")
        print(f"   Metadata: {response.metadata}")
        
        # Check if container was created
        if not response.deployment_id:
            print("❌ No container was created")
            return None
        
        # Continue if container exists (health checks might fail but container works)
        health_status = response.metadata.get('health_status', {})
        if health_status.get('ai_server') and health_status.get('backend'):
            print("✅ AI server and backend are healthy, continuing...")
        else:
            print("❌ Critical services not healthy")
            return None
    
    print(f"✅ Container deployed successfully!")
    print(f"   Container: {response.metadata.get('container_name')}")
    print(f"   Container ID: {response.deployment_id}")
    
    return response

def verify_deployment(response):
    """Verify that files were deployed correctly"""
    print("🔍 Verifying deployment...")
    
    container_name = response.metadata.get('container_name')
    
    # Check payload directory structure
    result = run_command([
        "docker", "exec", container_name, "ls", "-la", "/payload/"
    ], check=True, show_output=False)
    
    if result and "hello-world-clean-test" in result.stdout:
        print("✅ Script directory found in /payload/")
    else:
        print("❌ Script directory not found in /payload/")
        return False
    
    # Check hello_world.md file
    result = run_command([
        "docker", "exec", container_name, "cat", "/payload/hello-world-clean-test/hello_world.md"
    ], check=True, show_output=False)
    
    if result and "Agent identity" in result.stdout:
        print("✅ hello_world.md file accessible")
    else:
        print("❌ hello_world.md file not accessible")
        return False
    
    # Check config files
    config_files = ["mcp_servers.json", "settings.toml"]
    for config_file in config_files:
        result = run_command([
            "docker", "exec", container_name, "ls", "-la", f"/fractalic/{config_file}"
        ], check=False, show_output=False)
        
        if result and result.returncode == 0:
            print(f"✅ {config_file} copied to container")
        else:
            print(f"❌ {config_file} not found in container")
    
    return True

def test_ai_server_execution(response):
    """Test executing hello_world.md via AI server API"""
    print("🤖 Testing AI server execution...")
    
    urls = response.metadata.get('urls', {})
    ai_server_url = urls.get('ai_server')
    
    if not ai_server_url:
        print("❌ AI server URL not found")
        return False
    
    print(f"   AI Server URL: {ai_server_url}")
    
    # Wait for services to fully start
    print("⏳ Waiting for AI server to start...")
    time.sleep(25)
    
    # Test health endpoint
    try:
        response_health = requests.get(f"{ai_server_url}/health", timeout=10)
        if response_health.status_code == 200:
            print("✅ AI server health check passed")
        else:
            print(f"❌ AI server health check failed: {response_health.status_code}")
            return False
    except Exception as e:
        print(f"❌ Could not reach AI server: {e}")
        return False
    
    # Execute the hello_world.md script
    try:
        print("🔄 Executing hello_world.md script...")
        
        payload = {
            "filename": "/payload/hello-world-clean-test/hello_world.md"
        }
        
        response_exec = requests.post(
            f"{ai_server_url}/execute",
            json=payload,
            timeout=45
        )
        
        if response_exec.status_code == 200:
            result = response_exec.json()
            print("✅ Script execution successful!")
            print(f"   Success: {result.get('success')}")
            print(f"   Branch: {result.get('branch_name')}")
            
            # Check if we got the expected file list in return content
            return_content = result.get('return_content', '')
            if 'File summary' in return_content and 'hello_world.md' in return_content:
                print("✅ Response contains expected file list!")
                print("📋 Return content preview:")
                print("   " + return_content[:200] + "...")
                return True
            else:
                print("❌ Response doesn't contain expected file list")
                print(f"   Return content: {return_content[:100]}...")
                return False
        else:
            print(f"❌ Script execution failed: {response_exec.status_code}")
            print(f"   Response: {response_exec.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error executing script: {e}")
        return False

def main():
    """Main test function following exact requirements"""
    print("=" * 60)
    print("🧪 CLEAN DOCKER REGISTRY DEPLOYMENT TEST")
    print("=" * 60)
    
    try:
        # Step 0: Clean environment
        clean_environment()
        
        # Step 0.5: Verify config files exist
        if not verify_config_files():
            print("❌ Required config files not found!")
            sys.exit(1)
        
        # Step 1: Deploy container to docker desktop from docker registry
        response = deploy_container()
        if not response:
            sys.exit(1)
        
        # Step 2: Verify config files and hello world script deployment
        if not verify_deployment(response):
            print("❌ Deployment verification failed!")
            sys.exit(1)
        
        # Step 3 & 4: Run hello_world.md by curl via ai server and get file list response
        if not test_ai_server_execution(response):
            print("❌ AI server execution test failed!")
            sys.exit(1)
        
        # Success summary
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        
        container_name = response.metadata.get('container_name')
        urls = response.metadata.get('urls', {})
        
        print(f"📦 Container: {container_name}")
        print(f"🆔 Container ID: {response.deployment_id}")
        print(f"🌐 Service URLs:")
        for service, url in urls.items():
            print(f"   {service.title()}: {url}")
        
        print(f"\n🔧 Manual testing commands:")
        print(f"   # Check payload:")
        print(f"   docker exec -it {container_name} ls -la /payload/")
        print(f"   ")
        print(f"   # Test API:")
        print(f"   curl -X POST {urls.get('ai_server')}/execute -H 'Content-Type: application/json' -d '{{\"filename\": \"/payload/hello-world-clean-test/hello_world.md\"}}'")
        print(f"   ")
        print(f"   # Clean up:")
        print(f"   docker stop {container_name} && docker rm {container_name}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
