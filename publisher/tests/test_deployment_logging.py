#!/usr/bin/env python3
"""
Quick test to see improved deployment logging
"""

import requests
import json
import tempfile
import time
from pathlib import Path

def test_deployment_logging():
    """Test deployment with improved logging"""
    
    # Create test script
    test_dir = tempfile.mkdtemp(prefix="fractalic_log_test_")
    script_path = Path(test_dir) / "test_script.py"
    script_path.write_text('print("Hello from improved deployment!")')
    
    try:
        payload = {
            "script_name": "log_test",
            "script_folder": test_dir,
            "image_name": "ghcr.io/fractalic-ai/fractalic:latest",
            "container_name": f"fractalic-log-test-{int(time.time())}"
        }
        
        print(f"🚀 Testing improved deployment logging...")
        print(f"📁 Script folder: {test_dir}")
        print(f"📦 Container: {payload['container_name']}")
        print("=" * 60)
        
        response = requests.post(
            "http://localhost:8000/api/deploy/docker-registry/stream",
            json=payload,
            stream=True,
            timeout=300
        )
        
        if response.status_code != 200:
            print(f"❌ Failed: {response.status_code}")
            return
            
        # Show all deployment messages
        for line in response.iter_lines():
            if line:
                try:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        event_json = line_text[6:]
                        event = json.loads(event_json)
                        message = event.get('message', '')
                        stage = event.get('stage', '')
                        progress = event.get('progress', 0)
                        
                        print(f"[{progress:3d}%] {message}")
                        
                        # Stop after deployment completes
                        if 'Deployment completed' in message:
                            break
                            
                except Exception as e:
                    print(f"Error parsing: {e}")
                    
        print("=" * 60)
        print("✅ Deployment logging test completed")
        
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree(test_dir)
        except:
            pass

if __name__ == "__main__":
    test_deployment_logging()
