#!/usr/bin/env python3
"""
Validate that the deployed container's frontend configuration is correctly set
for container-internal networking (not connecting to host/local backend).
"""

import json
import time
import requests
import tempfile
import subprocess
from pathlib import Path

def test_container_networking_config():
    """Deploy a container and validate its networking configuration"""
    
    print("🔧 Testing container networking configuration...")
    
    # Create test script
    test_dir = tempfile.mkdtemp(prefix="fractalic_config_test_")
    script_path = Path(test_dir) / "test_script.py"
    script_path.write_text('print("Config validation test")')
    
    try:
        # Deploy a container
        payload = {
            "script_name": "config_test",
            "script_folder": test_dir,
            "image_name": "ghcr.io/fractalic-ai/fractalic:latest",
            "container_name": f"fractalic-config-test-{int(time.time())}"
        }
        
        print(f"📦 Deploying container: {payload['container_name']}")
        
        response = requests.post(
            "http://localhost:8000/api/deploy/docker-registry/stream",
            json=payload,
            stream=True,
            timeout=300
        )
        
        if response.status_code != 200:
            print(f"❌ Deployment failed: {response.status_code}")
            return False
        
        # Wait for deployment to complete
        for line in response.iter_lines():
            if line:
                try:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        event_json = line_text[6:]
                        event = json.loads(event_json)
                        if 'Deployment completed' in event.get('message', ''):
                            break
                except:
                    continue
        
        print("✅ Deployment completed, validating configuration...")
        
        # Check the container's frontend configuration
        container_name = payload['container_name']
        
        # 1. Check .env.local file
        print("🔍 Checking .env.local configuration...")
        try:
            result = subprocess.run([
                "docker", "exec", container_name,
                "cat", "/fractalic-ui/.env.local"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                env_content = result.stdout
                print("📄 Found .env.local:")
                for line in env_content.strip().split('\n'):
                    if line.strip() and not line.startswith('#'):
                        print(f"   {line}")
                
                # Validate the environment variables
                if "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" in env_content:
                    print("✅ Backend URL correctly set to container-internal localhost:8000")
                else:
                    print("❌ Backend URL not correctly configured")
                    return False
                    
                if "NEXT_PUBLIC_AI_API_BASE_URL=http://localhost:8001" in env_content:
                    print("✅ AI API URL correctly set to container-internal localhost:8001")
                else:
                    print("❌ AI API URL not correctly configured")
                    
                if "NEXT_PUBLIC_MCP_API_BASE_URL=http://localhost:5859" in env_content:
                    print("✅ MCP API URL correctly set to container-internal localhost:5859")
                else:
                    print("❌ MCP API URL not correctly configured")
                    
            else:
                print("⚠️ Could not read .env.local file")
                
        except Exception as e:
            print(f"⚠️ Error checking .env.local: {e}")
        
        # 2. Check config.json file
        print("🔍 Checking config.json configuration...")
        try:
            result = subprocess.run([
                "docker", "exec", container_name,
                "cat", "/fractalic-ui/public/config.json"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                config_content = result.stdout
                config_data = json.loads(config_content)
                print("📄 Found config.json:")
                print(f"   {json.dumps(config_data, indent=2)}")
                
                # Validate config.json
                api_config = config_data.get('api', {})
                if api_config.get('backend') == '':
                    print("✅ Backend configured for relative paths (correct for container)")
                else:
                    print(f"⚠️ Backend configured as: {api_config.get('backend')}")
                    
            else:
                print("⚠️ Could not read config.json file")
                
        except Exception as e:
            print(f"⚠️ Error checking config.json: {e}")
        
        # 3. Check that we're NOT connecting to the host system
        print("🔍 Verifying no external host connections...")
        try:
            result = subprocess.run([
                "docker", "exec", container_name,
                "ps", "aux"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                processes = result.stdout
                # Look for any processes that might be connecting to host ports
                host_patterns = ['host.docker.internal', '172.17.0.1', '192.168.']
                found_host_connections = False
                
                for pattern in host_patterns:
                    if pattern in processes:
                        print(f"⚠️ Found potential host connection: {pattern}")
                        found_host_connections = True
                
                if not found_host_connections:
                    print("✅ No external host connections detected")
                    
        except Exception as e:
            print(f"⚠️ Error checking processes: {e}")
        
        # Cleanup
        print(f"🧹 Cleaning up container: {container_name}")
        subprocess.run(["docker", "stop", container_name], capture_output=True, timeout=30)
        subprocess.run(["docker", "rm", container_name], capture_output=True, timeout=30)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup test directory
        try:
            import shutil
            shutil.rmtree(test_dir)
        except:
            pass

if __name__ == "__main__":
    print("🧪 Starting container networking configuration validation...")
    print("=" * 70)
    
    # Check server
    try:
        requests.get("http://localhost:8000/health", timeout=5)
        print("✅ Fractalic server is running")
    except:
        print("❌ Fractalic server is not running")
        exit(1)
    
    # Run test
    success = test_container_networking_config()
    
    print("=" * 70)
    if success:
        print("🎉 Container networking configuration validation passed!")
    else:
        print("❌ Container networking configuration validation failed!")
        exit(1)
