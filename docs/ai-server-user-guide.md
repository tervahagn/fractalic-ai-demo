# Fractalic AI Server - User Guide

The Fractalic AI Server provides a RESTful API for executing Fractalic scripts programmatically. This allows you to integrate Fractalic functionality into web applications, automation workflows, and other systems.

## Quick Start

### Starting the Server

```bash
cd /path/to/fractalic
python ai_server/fractalic_server.py
```

The server will automatically find an available port (starting from 8001) and display:

```
🚀 Starting Fractalic AI Server on port 8001...
📍 Server will be available at: http://localhost:8001
📚 API docs: http://localhost:8001/docs
```

### Basic Usage

Execute a Fractalic script via HTTP POST:

```bash
curl -X POST "http://localhost:8001/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "/path/to/your/script.md"
  }'
```

## API Reference

### Base URL
- Development: `http://localhost:8001`
- The server automatically tries ports 8001-8004 if previous ports are in use

### Endpoints

#### `POST /execute`

Execute a Fractalic script.

**Request Body:**
```json
{
  "filename": "/path/to/script.md",
  "parameter_text": "Optional input parameters"
}
```

**Parameters:**
- `filename` (required): Absolute path to the Fractalic markdown script
- `parameter_text` (optional): Text content to inject as input parameters

**Response:**
```json
{
  "success": true,
  "explicit_return": true,
  "return_content": "Content returned by @return operation",
  "branch_name": "20241209123456_abcd1234_Script-execution",
  "ctx_file": null,
  "output": "Execution completed. Branch: ..., Context: ..."
}
```

**Response Fields:**
- `success`: Boolean indicating if execution completed successfully
- `explicit_return`: True if script used `@return` operation
- `return_content`: Content returned by `@return` operation (if any)
- `branch_name`: Git branch name created for this execution
- `ctx_file`: Context file path (for internal use)
- `output`: Human-readable execution summary

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

#### `GET /docs`

Interactive API documentation (Swagger UI).

## Usage Examples

### Simple Script Execution

**Script file (`hello.md`):**
```markdown
# Hello World Script

@llm
prompt: Say hello to the world!
use-header: "# Greeting"
```

**API Call:**
```bash
curl -X POST "http://localhost:8001/execute" \
  -H "Content-Type: application/json" \
  -d '{"filename": "/path/to/hello.md"}'
```

### Parameter Injection

**Script file (`analysis.md`):**
```markdown
# Data Analysis Script

@llm
prompt: Analyze the following data: {{ input-parameters }}
use-header: "# Analysis Result"

@return
block: analysis-result
```

**API Call with Parameters:**
```bash
curl -X POST "http://localhost:8001/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "/path/to/analysis.md",
    "parameter_text": "Sales data for Q4: Revenue $1.2M, Growth 15%"
  }'
```

The `parameter_text` will be injected as:
```markdown
# Input Parameters {id=input-parameters}

Sales data for Q4: Revenue $1.2M, Growth 15%
```

### Using Return Values

Scripts with `@return` operations will have their returned content available in the `return_content` field:

```json
{
  "success": true,
  "explicit_return": true,
  "return_content": "# Analysis Result\nThe Q4 data shows strong performance...",
  "branch_name": "20241209123456_abcd1234_Analysis-execution",
  "output": "Execution completed..."
}
```

## Configuration

The server uses the same `settings.toml` configuration as the CLI tool:

```toml
defaultProvider = "openrouter/anthropic/claude-sonnet-4"
defaultOperation = "append"

[settings.openrouter/anthropic/claude-sonnet-4]
model = "openrouter/anthropic/claude-sonnet-4"
apiKey = "your-api-key-here"
```

## Error Handling

### Common Error Responses

**File Not Found:**
```json
{
  "success": false,
  "error": "File not found: /path/to/nonexistent.md",
  "explicit_return": false,
  "return_content": null,
  "branch_name": null
}
```

**Configuration Error:**
```json
{
  "success": false,
  "error": "No model specified and no defaultProvider in settings.toml",
  "explicit_return": false,
  "return_content": null,
  "branch_name": null
}
```

**Execution Error:**
```json
{
  "success": false,
  "error": "Block 'nonexistent-block' not found",
  "explicit_return": false,
  "return_content": null,
  "branch_name": null
}
```

## Best Practices

### 1. File Path Management
- Always use absolute paths for script files
- Ensure the server process has read access to script files
- Scripts will execute in their containing directory for proper git tracking

### 2. Parameter Injection
- Keep parameter text concise and well-structured
- Parameters are injected as `# Input Parameters {id=input-parameters}`
- Reference parameters in scripts using `{{ input-parameters }}`

### 3. Error Handling
- Always check the `success` field in responses
- Handle network timeouts gracefully (LLM operations can take time)
- Log `error` field contents for debugging

### 4. Git Integration
- Each execution creates a new git branch for tracking
- Context and trace files are automatically committed
- Clean up old branches periodically if needed

## Integration Examples

### Python Client

```python
import requests
import json

def execute_fractalic_script(filename, parameters=None):
    url = "http://localhost:8001/execute"
    payload = {"filename": filename}
    if parameters:
        payload["parameter_text"] = parameters
    
    response = requests.post(url, json=payload)
    return response.json()

# Usage
result = execute_fractalic_script(
    "/path/to/script.md",
    "Analyze sales data for Q4 2024"
)

if result["success"]:
    print("Execution successful!")
    if result["explicit_return"]:
        print("Returned content:", result["return_content"])
else:
    print("Error:", result["error"])
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

async function executeFractalicScript(filename, parameters = null) {
    const payload = { filename };
    if (parameters) {
        payload.parameter_text = parameters;
    }
    
    try {
        const response = await axios.post('http://localhost:8001/execute', payload);
        return response.data;
    } catch (error) {
        throw new Error(`Server request failed: ${error.message}`);
    }
}

// Usage
executeFractalicScript('/path/to/script.md', 'Input data here')
    .then(result => {
        if (result.success) {
            console.log('Execution successful!');
            if (result.explicit_return) {
                console.log('Returned content:', result.return_content);
            }
        } else {
            console.error('Error:', result.error);
        }
    })
    .catch(error => console.error('Request failed:', error));
```

## Troubleshooting

### Server Won't Start
1. Check if the port is already in use: `lsof -i :8001`
2. Verify Python environment has required dependencies
3. Ensure `settings.toml` is properly configured

### Execution Fails
1. Verify the script file exists and is readable
2. Check `settings.toml` has valid API keys
3. Review script syntax for errors
4. Check server logs for detailed error messages

### Performance Issues
1. LLM operations can take 5-30 seconds depending on complexity
2. Increase client timeout settings appropriately
3. Consider breaking large scripts into smaller chunks

## Security Considerations

- The server executes scripts with the same permissions as the server process
- Only run scripts from trusted sources
- Consider running the server in a containerized environment for production use
- API keys are loaded from `settings.toml` - protect this file appropriately
- The server does not implement authentication - add a reverse proxy if needed
