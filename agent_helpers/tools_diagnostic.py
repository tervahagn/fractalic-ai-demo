#!/usr/bin/env python3
"""
Tools Diagnostic Script for Development Agent
Analyzes tools directory and provides specific fix recommendations
"""
import json
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

def test_tool_discovery(tool_path: Path) -> Dict[str, Any]:
    """Test a single tool for Simple JSON discovery compliance"""
    result = {
        "path": str(tool_path),
        "name": tool_path.stem,
        "status": "unknown",
        "response_time": None,
        "response": None,
        "error": None,
        "recommendations": []
    }
    
    try:
        start_time = time.time()
        proc = subprocess.run(
            [sys.executable, str(tool_path), '{"__test__": true}'],
            capture_output=True,
            text=True,
            timeout=1.0  # 1 second timeout for analysis
        )
        end_time = time.time()
        
        result["response_time"] = end_time - start_time
        
        if proc.returncode == 0:
            try:
                response_data = json.loads(proc.stdout)
                result["response"] = response_data
                
                if result["response_time"] > 0.2:
                    result["status"] = "slow"
                    result["recommendations"].append(f"Tool responds in {result['response_time']:.3f}s - optimize for <200ms")
                else:
                    result["status"] = "working"
                    
            except json.JSONDecodeError:
                result["status"] = "invalid_json"
                result["error"] = f"Non-JSON response: {proc.stdout[:100]}"
                result["recommendations"].append("Tool must return valid JSON response")
        else:
            result["status"] = "error"
            result["error"] = f"Exit code {proc.returncode}: {proc.stderr[:200]}"
            result["recommendations"].append("Tool must exit with code 0 and return JSON")
            
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["response_time"] = 1.0
        result["error"] = "Tool hangs during discovery test"
        result["recommendations"].extend([
            "Tool hangs - likely heavy imports or API calls at module level",
            "Move API imports inside process_data() function",
            "Avoid network calls during module initialization"
        ])
    except Exception as e:
        result["status"] = "exception"
        result["error"] = str(e)
        result["recommendations"].append(f"Execution failed: {str(e)}")
    
    return result

def analyze_tool_content(tool_path: Path) -> Dict[str, Any]:
    """Analyze tool source code for common issues"""
    analysis = {
        "file_size": 0,
        "is_empty": False,
        "has_simple_json_pattern": False,
        "has_discovery_test": False,
        "has_heavy_imports": False,
        "heavy_imports": [],
        "issues": [],
        "suggestions": []
    }
    
    try:
        content = tool_path.read_text(encoding='utf-8')
        analysis["file_size"] = len(content)
        
        if len(content.strip()) == 0:
            analysis["is_empty"] = True
            analysis["issues"].append("File is completely empty")
            analysis["suggestions"].append("Implement tool from scratch using Simple JSON template")
            return analysis
        
        lines = content.split('\n')
        
        # Check for Simple JSON pattern
        if 'sys.argv[1] == \'{"__test__": true}\'' in content:
            analysis["has_discovery_test"] = True
        if 'json.dumps' in content and 'json.loads' in content:
            analysis["has_simple_json_pattern"] = True
            
        # Check for problematic imports
        heavy_import_patterns = [
            'from hubspot_hub_helpers import',
            'import hubspot_hub_helpers',
            'from hubspot import',
            'import hubspot',
            'import requests',
            'import aiohttp'
        ]
        
        for i, line in enumerate(lines[:20]):  # Check first 20 lines for imports
            line_stripped = line.strip()
            for pattern in heavy_import_patterns:
                if line_stripped.startswith(pattern):
                    analysis["has_heavy_imports"] = True
                    analysis["heavy_imports"].append(f"Line {i+1}: {line_stripped}")
        
        # Analysis and recommendations
        if not analysis["has_discovery_test"]:
            analysis["issues"].append('Missing discovery test for \'{"__test__": true}\'')
            analysis["suggestions"].append("Add discovery test handler")
            
        if not analysis["has_simple_json_pattern"]:
            analysis["issues"].append("Not using Simple JSON pattern")
            analysis["suggestions"].append("Convert to Simple JSON I/O pattern")
            
        if analysis["has_heavy_imports"]:
            analysis["issues"].append("Heavy imports at module level")
            analysis["suggestions"].append("Move heavy imports inside process_data() function")
            
    except Exception as e:
        analysis["issues"].append(f"Could not read file: {str(e)}")
        
    return analysis

def generate_fix_template(tool_name: str, original_content: str = None) -> str:
    """Generate a fix template for a problematic tool"""
    template = f'''#!/usr/bin/env python3
"""
{tool_name.replace('_', ' ').title()} - Fixed for Simple JSON Discovery
TODO: Add description of what this tool does
"""
import json
import sys

def process_data(data):
    """
    Main processing function for {tool_name}
    TODO: Implement your tool logic here
    """
    action = data.get("action")
    
    # TODO: Add your actions here
    if action == "example":
        # TODO: Replace with actual logic
        return {{"result": "success", "tool": "{tool_name}"}}
    else:
        return {{"error": f"Unknown action: {{action}}"}}

def main():
    # REQUIRED: Discovery test - must respond within 200ms
    if len(sys.argv) == 2 and sys.argv[1] == '{{"__test__": true}}':
        print(json.dumps({{"success": True}}))
        return
    
    # OPTIONAL: Schema dump for rich LLM integration
    if len(sys.argv) == 2 and sys.argv[1] == "--fractalic-dump-schema":
        schema = {{
            "description": "TODO: Add tool description",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "action": {{
                        "type": "string",
                        "enum": ["example"],  # TODO: Add your actions
                        "description": "Action to perform"
                    }}
                }},
                "required": ["action"]
            }}
        }}
        print(json.dumps(schema, ensure_ascii=False))
        return
    
    # REQUIRED: Process JSON input
    try:
        if len(sys.argv) != 2:
            raise ValueError("Expected exactly one JSON argument")
        
        params = json.loads(sys.argv[1])
        result = process_data(params)
        print(json.dumps(result, ensure_ascii=False))
        
    except json.JSONDecodeError as e:
        print(json.dumps({{"error": f"Invalid JSON input: {{str(e)}}"}}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({{"error": str(e)}}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    return template

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 tools_diagnostic.py <tools_directory>")
        sys.exit(1)
    
    tools_dir = Path(sys.argv[1])
    if not tools_dir.exists():
        print(f"Directory not found: {tools_dir}")
        sys.exit(1)
    
    print(f"Analyzing tools in: {tools_dir}")
    print("=" * 80)
    
    # Find all Python files
    python_files = list(tools_dir.glob("*.py"))
    
    working_tools = []
    problematic_tools = []
    
    for tool_path in sorted(python_files):
        print(f"\\nAnalyzing: {tool_path.name}")
        print("-" * 40)
        
        # Test discovery
        discovery_result = test_tool_discovery(tool_path)
        print(f"Discovery Status: {discovery_result['status']}")
        
        if discovery_result['response_time']:
            print(f"Response Time: {discovery_result['response_time']:.3f}s")
        
        if discovery_result['error']:
            print(f"Error: {discovery_result['error']}")
        
        # Analyze content
        content_analysis = analyze_tool_content(tool_path)
        
        if content_analysis['is_empty']:
            print("📝 EMPTY FILE - Needs implementation")
        elif content_analysis['has_heavy_imports']:
            print("⚠️  HEAVY IMPORTS - Likely cause of hanging")
            for imp in content_analysis['heavy_imports']:
                print(f"   {imp}")
        
        # Recommendations
        if discovery_result['recommendations'] or content_analysis['suggestions']:
            print("\\n🔧 Recommendations:")
            for rec in discovery_result['recommendations'] + content_analysis['suggestions']:
                print(f"   • {rec}")
        
        # Categorize
        if discovery_result['status'] == 'working':
            working_tools.append(tool_path.name)
        else:
            problematic_tools.append({
                'name': tool_path.name,
                'status': discovery_result['status'],
                'issues': content_analysis['issues'],
                'suggestions': content_analysis['suggestions']
            })
    
    # Summary Report
    print("\\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    print(f"\\n✅ Working Tools ({len(working_tools)}):")
    for tool in working_tools:
        print(f"   • {tool}")
    
    print(f"\\n❌ Problematic Tools ({len(problematic_tools)}):")
    for tool in problematic_tools:
        print(f"   • {tool['name']} ({tool['status']})")
    
    # Detailed Fix Instructions
    print(f"\\n🔧 DETAILED FIX INSTRUCTIONS")
    print("=" * 80)
    
    for tool in problematic_tools:
        print(f"\\n{tool['name']}:")
        print(f"  Status: {tool['status']}")
        if tool['issues']:
            print("  Issues:")
            for issue in tool['issues']:
                print(f"    - {issue}")
        if tool['suggestions']:
            print("  Fixes:")
            for suggestion in tool['suggestions']:
                print(f"    - {suggestion}")
        
        # Generate fix template file
        template_content = generate_fix_template(tool['name'].replace('.py', ''))
        template_path = tools_dir / f"{tool['name']}.template"
        template_path.write_text(template_content)
        print(f"  📝 Fix template generated: {template_path}")
    
    print(f"\\n📊 STATISTICS")
    print("=" * 80)
    total_tools = len(python_files)
    success_rate = (len(working_tools) / total_tools) * 100 if total_tools > 0 else 0
    print(f"Total tools: {total_tools}")
    print(f"Working: {len(working_tools)} ({success_rate:.1f}%)")
    print(f"Problematic: {len(problematic_tools)} ({100-success_rate:.1f}%)")
    
    if success_rate < 90:
        print(f"\\n⚠️  Success rate is {success_rate:.1f}% - Target is 90%+")
        print("Priority: Fix problematic tools to improve discovery reliability")

if __name__ == "__main__":
    main()
