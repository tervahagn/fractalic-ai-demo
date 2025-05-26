# Fractalic Tools Documentation

This directory contains documentation for building and using tools in the Fractalic workflow system.

## Documents

### [Tool Plug-in & Auto-Discovery Guide](./tools.md)
**Overview document** covering the basics of the Fractalic tool system, including:
- Why tools are first-class citizens
- How the registry builds the master tool list  
- Comparison of explicit manifests vs auto-discovery
- Tool lifecycle and execution
- MCP server integration
- FAQ and troubleshooting

### [Autodiscoverable Tools Technical Specification Document (TSD)](./autodiscoverable-tools-tsd.md)
**Comprehensive technical specification** for building autodiscoverable tools, including:
- Detailed implementation requirements
- Schema format specifications
- Single-tool vs multi-tool patterns
- Parameter types and validation
- Complete implementation examples
- Best practices and testing strategies
- Advanced debugging techniques

## Quick Start

1. **Read the overview**: Start with [tools.md](./tools.md) to understand the system
2. **Follow the TSD**: Use [autodiscoverable-tools-tsd.md](./autodiscoverable-tools-tsd.md) for implementation details
3. **Study examples**: Reference `fractalic_generator.py` in the tools directory as a complete example

## Key Concepts

- **Auto-discovery**: Tools can register themselves without manual YAML manifests
- **Schema dumping**: Tools expose their parameter schema via `--fractalic-dump-schema`
- **Multi-tool support**: Single scripts can expose multiple tool functions
- **OpenAI compatibility**: Tool schemas follow OpenAI function calling format
- **Language agnostic**: Python, Bash, or any CLI-compatible executable
