#!/usr/bin/env python3
"""
Debug script for deployment issues
Test each step of the deployment to identify where it hangs
"""

import subprocess
import time
import os
import tempfile
from pathlib import Path

def run_command(cmd, timeout=30):
    """Run command with timeout"""
    print(f"🔧 Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        print(f"✅ Exit code: {result.returncode}")
        if result.stdout:
            print(f"📤 stdout: {result.stdout[:200]}...")
        if result.stderr:
            print(f"📥 stderr: {result.stderr[:200]}...")
        return result
    except subprocess.TimeoutExpired:
        print(f"⏰ Command timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_docker_pull():
    """Test Docker image pull"""
    print("\n" + "="*50)
    print("🚀 Testing Docker image pull")
    print("="*50)
    
    image = "ghcr.io/fractalic-ai/fractalic:latest-production"
    platform = "linux/amd64"
    
    cmd = ["docker", "pull", "--platform", platform, image]
    result = run_command(cmd, timeout=120)  # 2 minutes for pull
    
    if result and result.returncode == 0:
        print("✅ Docker pull successful")
        return True
    else:
        print("❌ Docker pull failed")
        return False

def test_container_start():
    """Test container start"""
    print("\n" + "="*50)
    print("🐳 Testing container start")
    print("="*50)
    
    container_name = "fractalic-debug-test"
    image = "ghcr.io/fractalic-ai/fractalic:latest-production"
    
    # Clean up any existing container
    print("🧹 Cleaning up existing container...")
    run_command(["docker", "stop", container_name], timeout=10)
    run_command(["docker", "rm", container_name], timeout=10)
    
    # Start container
    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--platform", "linux/amd64",
        "-p", "8001:8001",
        image
    ]
    
    result = run_command(cmd, timeout=30)
    
    if result and result.returncode == 0:
        container_id = result.stdout.strip()
        print(f"✅ Container started: {container_id[:12]}")
        
        # Wait for container to initialize
        print("⏳ Waiting for container to initialize...")
        time.sleep(5)
        
        # Check container status
        status_result = run_command(["docker", "ps", "-f", f"name={container_name}"])
        if status_result:
            print("📊 Container status:")
            print(status_result.stdout)
        
        # Check logs
        logs_result = run_command(["docker", "logs", container_name], timeout=10)
        if logs_result:
            print("📝 Container logs:")
            print(logs_result.stdout[:500] + "..." if len(logs_result.stdout) > 500 else logs_result.stdout)
        
        return container_id
    else:
        print("❌ Container start failed")
        return None

def test_health_check(container_name):
    """Test health check"""
    print("\n" + "="*50)
    print("🏥 Testing health check")
    print("="*50)
    
    # Wait a bit for services to start
    print("⏳ Waiting for services to start...")
    time.sleep(10)
    
    # Test AI server health
    health_cmd = [
        "curl", "-s", "-f", "--max-time", "10",
        "http://localhost:8001/health"
    ]
    
    print("🩺 Testing AI server health...")
    result = run_command(health_cmd, timeout=15)
    
    if result and result.returncode == 0:
        print("✅ AI server health check passed")
        print(f"Response: {result.stdout}")
        return True
    else:
        print("❌ AI server health check failed")
        
        # Try to get more info from container
        print("🔍 Checking container processes...")
        run_command(["docker", "exec", container_name, "ps", "aux"], timeout=10)
        
        print("🔍 Checking container ports...")
        run_command(["docker", "exec", container_name, "netstat", "-tlnp"], timeout=10)
        
        return False

def cleanup_test_container():
    """Clean up test container"""
    print("\n" + "="*50)
    print("🧹 Cleaning up test container")
    print("="*50)
    
    container_name = "fractalic-debug-test"
    run_command(["docker", "stop", container_name], timeout=10)
    run_command(["docker", "rm", container_name], timeout=10)
    print("✅ Cleanup complete")

def main():
    """Run deployment debug tests"""
    print("🚀 Fractalic Deployment Debug")
    print("Testing each step to identify where deployment hangs")
    
    try:
        # Test 1: Docker pull
        if not test_docker_pull():
            print("❌ Stopping tests - Docker pull failed")
            return
        
        # Test 2: Container start
        container_id = test_container_start()
        if not container_id:
            print("❌ Stopping tests - Container start failed")
            return
            
        # Test 3: Health check
        if not test_health_check("fractalic-debug-test"):
            print("❌ Health check failed")
        else:
            print("✅ All tests passed!")
            
    finally:
        # Always cleanup
        cleanup_test_container()

if __name__ == "__main__":
    main()
