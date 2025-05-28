# Fractalic Tools Documentation

This directory contains documentation for building and using tools in the Fractalic workflow system.

## Recommended Approach: Simple JSON Convention

**Start here for new tool development!** The Simple JSON Convention provides the fastest path from idea to working tool:

```python
#!/usr/bin/env python3
"""Tool description."""
import json, sys

def process_data(data):
    # Your tool logic here
    return {"result": "success"}

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '{"__test__": true}':
        print(json.dumps({"success": True, "_simple": True}))
        return
    
    try:
        params = json.loads(sys.argv[1])
        result = process_data(params)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__": main()
```

**Benefits**: 90% less code, automatic discovery, perfect LLM integration.

## Documents

### [Tool Plug-in & Auto-Discovery Guide](./tools.md)
**Overview document** covering the Fractalic tool system, including:
- **Simple JSON Convention** (top priority approach)
- Tool autodiscovery priority order
- Legacy approaches for backward compatibility
- Tool lifecycle and execution
- MCP server integration
- FAQ and troubleshooting

### [Autodiscoverable Tools Technical Specification Document (TSD)](./autodiscoverable-tools-tsd.md)
**Comprehensive technical specification** with implementation details:
- Simple JSON Convention requirements and examples
- Legacy pattern documentation
- Schema format specifications  
- Parameter types and validation
- Best practices and testing strategies
- Migration guidance

## Quick Start

1. **Use Simple JSON**: Copy the template above and implement your `process_data()` function
2. **Drop in tools/**: Save to `tools/my_tool.py` 
3. **Restart Fractalic**: Tool is automatically discovered and available to LLMs
4. **Optional**: Read [tools.md](./tools.md) for advanced features

## Key Concepts

- **Simple JSON Convention**: Top priority autodiscovery (recommended)
- **Auto-discovery priority**: Simple JSON → Schema dumps → Help text → ArgumentParser
- **Schema dumping**: Optional rich parameter definitions via `--fractalic-dump-schema`
- **OpenAI compatibility**: Tool schemas follow OpenAI function calling format
- **Language agnostic**: Python, Bash, or any CLI-compatible executable
