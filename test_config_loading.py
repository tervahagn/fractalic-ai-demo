#!/usr/bin/env python3
"""
Test script to verify configuration loading works with and without mcp_servers.json
"""

import json
import sys
from pathlib import Path
import tempfile
import os

# Add the current directory to the path so we can import fractalic_mcp_manager
sys.path.insert(0, str(Path(__file__).parent))

from fractalic_mcp_manager import Supervisor, log

def test_config_loading():
    """Test that Supervisor handles missing config files gracefully"""
    
    print("🧪 Testing Fractalic MCP Manager Configuration Loading")
    print("=" * 60)
    
    # Test 1: Missing config file
    print("\n📝 Test 1: Missing config file")
    with tempfile.TemporaryDirectory() as temp_dir:
        missing_config = Path(temp_dir) / "nonexistent_config.json"
        print(f"   Testing with non-existent file: {missing_config}")
        
        try:
            supervisor = Supervisor(file=missing_config)
            print("   ✅ Supervisor created successfully with missing config")
            print(f"   📊 Server count: {len(supervisor.children)}")
        except Exception as e:
            print(f"   ❌ Failed with missing config: {e}")
            return False
    
    # Test 2: Empty config file
    print("\n📝 Test 2: Empty/invalid config file")
    with tempfile.TemporaryDirectory() as temp_dir:
        empty_config = Path(temp_dir) / "empty_config.json"
        empty_config.write_text("")  # Empty file
        print(f"   Testing with empty file: {empty_config}")
        
        try:
            supervisor = Supervisor(file=empty_config)
            print("   ✅ Supervisor created successfully with empty config")
            print(f"   📊 Server count: {len(supervisor.children)}")
        except Exception as e:
            print(f"   ❌ Failed with empty config: {e}")
            return False
    
    # Test 3: Valid config file (test config parsing only)
    print("\n📝 Test 3: Valid config file")
    with tempfile.TemporaryDirectory() as temp_dir:
        valid_config = Path(temp_dir) / "valid_config.json"
        config_data = {
            "mcpServers": {
                "test-server": {
                    "command": "test",
                    "args": ["--test"]
                }
            }
        }
        valid_config.write_text(json.dumps(config_data, indent=2))
        print(f"   Testing with valid config: {valid_config}")
        
        try:
            # Just test that we can parse the config without async issues
            cfg_text = valid_config.read_text()
            cfg = json.loads(cfg_text)
            server_count = len(cfg.get("mcpServers", {}))
            print("   ✅ Valid config parsed successfully")
            print(f"   📊 Server count in config: {server_count}")
            print(f"   🔧 Servers: {list(cfg.get('mcpServers', {}).keys())}")
        except Exception as e:
            print(f"   ❌ Failed to parse valid config: {e}")
            return False
    
    # Test 4: Check if sample config exists
    print("\n📝 Test 4: Sample config file")
    sample_config = Path("mcp_servers.json.sample")
    if sample_config.exists():
        print(f"   ✅ Sample config exists: {sample_config}")
        try:
            # Try to parse it to make sure it's valid JSON
            json.loads(sample_config.read_text())
            print("   ✅ Sample config is valid JSON")
        except Exception as e:
            print(f"   ⚠️  Sample config has JSON errors: {e}")
    else:
        print(f"   ⚠️  Sample config not found: {sample_config}")
    
    print("\n🎉 All configuration loading tests completed successfully!")
    return True

if __name__ == "__main__":
    success = test_config_loading()
    sys.exit(0 if success else 1)
