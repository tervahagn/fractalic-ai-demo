# Fractalic Tools Documentation

This directory contains documentation for building and using tools in the Fractalic workflow system.

## Simple JSON Convention - The ONLY Supported Approach

**All tools must implement the Simple JSON Convention for automatic discovery:**

```python
#!/usr/bin/env python3
"""Tool description."""
import json, sys

def process_data(data):
    # Your tool logic here
    action = data.get("action")
    if action == "example":
        return {"result": "success"}
    return {"error": f"Unknown action: {action}"}

def main():
    # Discovery test - REQUIRED
    if len(sys.argv) == 2 and sys.argv[1] == '{"__test__": true}':
        print(json.dumps({"success": True}))
        return
    
    # Process JSON input - REQUIRED
    try:
        params = json.loads(sys.argv[1])
        result = process_data(params)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__": 
    main()
```

**Key Requirements:**
- ✅ Respond to `'{"__test__": true}'` within 200ms
- ✅ Accept JSON as single argument, return JSON to stdout
- ✅ Handle errors gracefully with JSON error responses

## Documents

### [Tool Plug-in & Auto-Discovery Guide](./tools.md)
**Overview document** covering the Fractalic Simple JSON tool system:
- Simple JSON Convention requirements
- Tool discovery process
- Implementation templates
- Error handling and best practices

### [Simple JSON Tools Technical Specification Document (TSD)](./autodiscoverable-tools-tsd.md)
**Comprehensive technical specification** with implementation details:
- Complete Simple JSON requirements
- Schema format specifications  
- Parameter types and validation
- Implementation examples and best practices
- Testing and troubleshooting

## Quick Start

1. **Copy the template**: Use the Simple JSON template above
2. **Implement your logic**: Add your tool functionality in `process_data()`
3. **Drop in tools/**: Save to `tools/my_tool.py` 
4. **Restart Fractalic**: Tool is automatically discovered and available to LLMs

## Key Benefits

- **Fast discovery**: Tools respond in <200ms, no hanging on problematic files
- **Error-resistant**: Only valid tools are registered, helpers are skipped
- **Simple protocol**: JSON in, JSON out - clean LLM integration
- **Zero configuration**: No YAML files needed for basic tools
- **Language agnostic**: Works with any language that can handle CLI arguments

## Migration from Legacy Approaches

If you have existing tools using argparse or help text parsing, convert them to Simple JSON:

1. **Replace argparse** with JSON parameter parsing
2. **Add discovery test** that responds to `'{"__test__": true}'`
3. **Return JSON** instead of plain text output
4. **Test quickly**: Ensure response time is <200ms
