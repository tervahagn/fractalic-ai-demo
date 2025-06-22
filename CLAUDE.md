# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fractalic is an AI workflow orchestration platform that enables executable AI workflows through plain-language Markdown documents with embedded YAML operations. It's a "programmable AI system in natural language" that bridges documentation and automation.

## Technology Stack

- **Backend**: Python 3.11+ with FastAPI and Uvicorn
- **Frontend**: Node.js/React (separate repository: fractalic-ui)
- **AI Integration**: Multi-provider LLM support (Anthropic, OpenAI, Groq, Gemini, xAI, OpenRouter)
- **Document Processing**: Custom Markdown AST parser
- **Protocol**: Model Context Protocol (MCP) for tool integrations
- **Version Control**: Git-based session tracking

## Common Development Commands

### Backend Development
```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run backend server (port 8000)
./run_server.sh

# Run CLI directly
python fractalic.py <markdown-file>

# Run MCP manager (port 5859)
python fractalic_mcp_manager.py
```

### Frontend Development
Frontend is in separate repository `fractalic-ui`:
```bash
# Install frontend (in sibling directory)
git clone https://github.com/fractalic-ai/fractalic-ui.git
cd fractalic-ui
npm install
npm run dev  # Port 3000
```

### Docker Deployment
```bash
# Quick Docker setup
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/docker_build_run.sh | bash
```

## Architecture

### Core Components

1. **Main Entry Points**:
   - `fractalic.py` - CLI interface and core execution engine
   - `ai_server/fractalic_server.py` - HTTP API server
   - `fractalic_mcp_manager.py` - MCP service manager

2. **Core Engine** (`/core/`):
   - `ast_md/` - Markdown AST parser and node management
   - `operations/` - Operation handlers (@llm, @shell, @import, @run, @return, @goto)
   - `llm/` - Multi-provider LLM client system with streaming
   - `plugins/` - MCP and tool integration
   - `render/` - AST-to-Markdown conversion
   - `ui_server/` - Web UI backend server

3. **Operations System**:
   - `@llm` - AI model interactions with prompt management
   - `@shell` - System command execution
   - `@import` - Content inclusion from external files
   - `@run` - Sub-workflow execution
   - `@return` - Workflow result output
   - `@goto` - Context navigation

### Execution Model

1. **Document Parsing**: Markdown → AST with operation blocks
2. **Context Building**: Create hierarchical execution context tree
3. **Operation Execution**: Sequential processing of @operations
4. **State Management**: Git-based session tracking with automatic commits
5. **Output Generation**: Final AST → Markdown rendering

## Configuration

### settings.toml
Core configuration file containing:
- **Provider Settings**: API keys and model configurations for multiple LLM providers
- **Environment Variables**: External service tokens (TAVILY_API_KEY, REPLICATE_API_TOKEN, etc.)
- **Runtime Settings**: Operation visibility, MCP server endpoints
- **Default Behaviors**: Model selection, temperature settings

### mcp_servers.json
Tool integration configuration for MCP services (Zapier, HubSpot, Notion, etc.)

## Key Architectural Concepts

### Block References
- Simple: `section-name`
- Nested: `parent/child`
- Wildcard: `section/*` (includes all nested blocks)
- Arrays: YAML array syntax for multiple blocks

### Context Management
- **Hierarchical Addressing**: Block references use path-like syntax
- **Parameter Injection**: Dynamic content insertion between operations
- **State Persistence**: Git commits track execution state
- **Call Tree**: Execution trace for debugging workflows

### Multi-Provider AI
- Seamless switching between LLM providers in single workflow
- Per-operation model and provider overrides
- Centralized configuration with provider-specific settings

## Development Notes

- **No Test Framework**: Project currently has no dedicated test suite
- **Virtual Environment**: Always use `venv/` for Python dependencies
- **Server Architecture**: Backend on 8000, Frontend on 3000, MCP on 5859
- **Git Integration**: Sessions automatically tracked with git commits
- **Streaming Support**: Real-time output for long-running LLM operations
- **Tool Integration**: MCP protocol enables external tool connectivity

## Agent Development Guidelines

### Required Agent Location
**CRITICAL**: All agent development must be done in `/Users/marina/llexem-jan-25-deploy/llexem_deploy_2025/fractalic/agent_playground/cognition-v01/`

- **Agents**: Place agent scripts in `agents/` subdirectory
- **Workflows**: Place orchestrator scripts in `workflows/` subdirectory
- **Testing**: Create test files within this structure
- **No Exception**: Never create agents or test files outside this folder structure

### Git Repository Management
**CRITICAL**: Git commits are managed by the Fractalic execution system, NOT manually

- **Execution Directory**: Fractalic creates branches and commits in the directory where the script runs (e.g., `agent_playground/cognition-v01/`)
- **Automatic Commits**: Each fractalic execution automatically commits `.ctx` and `.trc` files to the local git repository
- **Test Results**: All test execution results are automatically preserved in git history
- **Manual Commits**: NEVER manually commit files - let Fractalic handle all git operations
- **Branch Creation**: Fractalic automatically creates timestamped branches for each execution session

### Fractalic Syntax Requirements

#### YAML Block Formatting
```yaml
# CORRECT - No empty lines within YAML blocks
@llm
prompt: |
  Your prompt text here
  Continue on next line
use-header: "# Response Header"
tools: all

# INCORRECT - Empty lines break YAML parsing
@llm
prompt: |
  Your prompt text here
  
  Continue on next line  # This empty line breaks parsing
use-header: "# Response Header"
```

#### Header Quotation Rules
```yaml
# CORRECT - Always quote use-header values
use-header: "# Main Section"
use-header: "## Subsection"

# INCORRECT - Unquoted headers cause issues
use-header: # Main Section
use-header: ## Subsection
```

#### Block Hierarchy and Wildcards
```yaml
# CORRECT - Level 1 headings with wildcard returns
use-header: "# Research Findings"
@return
block: research-findings/*

# INCORRECT - Level 2 headings only capture first block
use-header: "## Research Findings"  # Only gets first child
@return
block: research-findings/*
```

#### Multi-line Prompts
```yaml
# CORRECT - Pipe syntax with no empty lines
prompt: |
  First line of prompt
  Second line continues
  Third line continues

# INCORRECT - Empty lines within prompt block
prompt: |
  First line of prompt
  
  Second line after empty line  # Breaks YAML parsing
```

#### File Path Requirements
```yaml
# CORRECT - Always include full file paths in fractalic_run calls
- file_path: "agent_playground/cognition-v01/agents/researcher.md"
- file_path: "agent_playground/cognition-v01/workflows/orchestrator.md"

# INCORRECT - Relative or incomplete paths
- file_path: "researcher.md"
- file_path: "agents/researcher.md"
```

#### Tool Collection and Enhanced Features
```yaml
# fractalic_run Enhanced Parameters
- block_uri: ["section-1/*", "section-2/*"]  # Collection support
- direct_context_output: true                # Direct insertion mode
- block_uri: "findings/*"                    # Wildcard patterns
- mode: "append"                             # append/prepend/replace
```

## Deep Architecture Knowledge

### AST (Abstract Syntax Tree) System

#### Core AST Structure (`/core/ast_md/`)

**Node Types and Hierarchy**:
- **NodeType Enum**: Defines HEADING, OPERATION, PARAGRAPH, CODEBLOCK, etc.
- **Node Class**: Base class with key attributes:
  - `id`: Block identifier (slugified from heading text)
  - `key`: Unique 8-character hex identifier for linking
  - `level`: Header level (1-6) for hierarchy
  - `content`: Full block content including headers
  - `prev/next`: Linked list pointers for sequential navigation
  - `enabled`: Boolean for conditional execution
  - `role`: "user" or "assistant" for conversation context

**Key Linking System**:
- Every node gets a unique `key` (e.g., "f3901472") for persistent references
- Keys survive AST modifications, enabling stable cross-references
- Parser (`parser.py`) generates keys during initial parsing
- Runner (`runner.py`) maintains key consistency during execution
- Renderer (`render.py`) preserves keys when converting AST back to Markdown

#### Block Reference Resolution (`ast.py`)

**Path Resolution Functions**:
- `get_ast_part_by_path()`: Main entry point for block lookups
- `_get_ast_part()`: Recursive traversal with hierarchy awareness
- `_find_node_by_id_or_key()`: Searches by both id and key
- `find_all_nodes_by_id()`: Handles wildcard patterns (e.g., "section/*")

**Reference Types**:
- Simple: `"research-findings"` (matches id or key)
- Hierarchical: `"parent/child"` (path-based navigation)
- Wildcard: `"section/*"` (includes all nested blocks)
- Multi-block: `["block1", "block2"]` (array of references)

#### DirectAST Parsing (`DirectAST` class)

**Multi-Block Parsing**:
- Handles `__DIRECT_CONTEXT__` marker for dynamic content insertion
- Parses multiple top-level blocks from single content string
- Maintains proper node linking with prev/next pointers
- Preserves hierarchy and indentation levels
- Assigns unique keys to dynamically created nodes

### LLM Operation System (`/core/operations/llm_op.py`)

#### Message-Based Processing

**Tool Call Handling**:
- `process_tool_calls()`: Processes tool responses within LLM operations
- Detects `__DIRECT_CONTEXT__` marker in tool responses
- Extracts `direct_content` from JSON responses
- Triggers direct context insertion into current AST

**Direct Context Insertion**:
- `insert_direct_context()`: Merges new blocks into existing AST
- Updates node linking (prev/next pointers) after insertion
- Maintains AST consistency with proper key assignment
- Preserves execution flow and hierarchy

#### Context Building

**Message Context Assembly**:
- Converts AST nodes to conversation messages
- Handles role assignment (user/assistant)
- Maintains conversation flow for LLM context
- Supports streaming responses with proper message handling

### Tool Registry System (`/core/plugins/tool_registry.py`)

#### Dynamic AST Management

**Registry AST Updates**:
- Maintains global AST state for tool access
- `update_ast()`: Refreshes registry with modified AST
- `get_ast_part_by_path()`: Provides block lookup for tools
- Persistence issue: AST resets between fractalic_run calls

**Tool Integration**:
- Provides AST context to MCP tools
- Enables cross-agent context sharing
- Handles block URI resolution for tools
- Critical for fractalic_run tool functionality

### Execution Flow (`/core/operations/runner.py`)

#### Operation Processing

**Sequential Execution**:
- Processes nodes in linked-list order
- Maintains execution context throughout workflow
- Handles operation-specific logic (@llm, @return, @run, etc.)
- Updates AST with operation results

**Context Inheritance**:
- Git-based session tracking with automatic commits
- Branch creation for execution isolation
- Context file (.ctx) and trace file (.trc) generation
- Call tree tracking for hierarchical workflows

### Parser System (`/core/ast_md/parser.py`)

#### Markdown to AST Conversion

**Parsing Process**:
- Regex-based operation block detection
- YAML parameter parsing for operation blocks
- Header hierarchy analysis and id generation
- Node linking with prev/next pointers
- Key assignment for persistent references

**Operation Block Parsing**:
- Detects `@operation` syntax (e.g., `@llm`, `@return`)
- Extracts YAML parameters with proper validation
- Handles multi-line prompts and complex configurations
- Maintains indentation and formatting context

### Renderer System (`/core/render/render.py`)

#### AST to Markdown Conversion

**Rendering Process**:
- Converts AST nodes back to Markdown format
- Preserves operation blocks with YAML parameters
- Maintains header hierarchy and indentation
- Handles both content and response rendering

**Context File Generation**:
- Creates .ctx files with full execution context
- Includes both original content and LLM responses
- Maintains conversation flow and tool interactions
- Preserves AST structure for session continuity

### Testing Infrastructure

#### Cross-Agent Context Inheritance

**Test Directory**: `/agent_playground/cognition-v02-context/`
- Test files for sequential agent workflows
- Validation of direct context insertion
- Tool registry persistence verification
- Git-based session tracking validation

**Key Test Files**:
- `proper_direct_context_test.md` - Main orchestrator
- `agent1_researcher.md` - First agent with research output
- `agent2_synthesizer.md` - Second agent with context dependency
- Generated: `.ctx`, `.trc`, `call_tree.json` files

## File Structure Patterns

- **Tutorials**: `/tutorials/` contains working examples and learning materials
- **Documentation**: `/docs/` contains specifications and feature docs
- **Operations**: Core operation logic in `/core/operations/`
- **Providers**: LLM integrations in `/core/llm/`
- **Plugins**: Tool integrations in `/core/plugins/`
- **Agents**: `/agent_playground/cognition-v01/` for all agent development
- **Testing**: `/agent_playground/cognition-v02-context/` for cross-agent context inheritance tests