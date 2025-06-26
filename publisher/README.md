# Fractalic Publisher System

## Overview

The Fractalic Publisher System provides a plugin-based architecture for deploying Fractalic scripts to various cloud platforms and container registries. The system is designed for production-ready deployments with automatic port management, health checking, and configuration file handling.

## Architecture

### Core Components

- **Plugin Manager** (`plugin_manager.py`): Discovers and loads deployment plugins
- **Base Plugin** (`base_plugin.py`): Abstract base class for all deployment plugins  
- **Models** (`models.py`): Data structures for deployment configuration and results
- **Docker Registry Plugin** (`plugins/docker_registry_plugin.py`): Production deployment using pre-built Docker images

### Plugin System

The publisher uses a plugin-based architecture where each plugin handles deployment to a specific platform:

- **docker-registry**: Fast deployment using pre-built Docker images (primary plugin)
- **Future plugins**: Railway, Render, Fly.io, Vercel, etc.

## Production Deployment Flow

### 1. Image Strategy

The system uses pre-built Docker images for fast deployment:

```
ghcr.io/fractalic-ai/fractalic:latest-production -> AI server only (recommended)
ghcr.io/fractalic-ai/fractalic:latest -> Full version (UI + AI + Backend)
```

### 2. Port Management

- **AI Server**: External port (auto-detected starting from 8001)
- **Backend UI Server**: Internal port 8000 (container-only access)
- **MCP Manager**: Internal port 5859 (container-only access)

### 3. Configuration File Handling

The system automatically copies essential configuration files to containers:

- `settings.toml`: LLM provider settings and API keys
- `mcp_servers.json`: Model Context Protocol server configurations
- Files are copied to both `/fractalic/` and `/` for compatibility

### 4. Project Root Detection

The plugin uses intelligent project root detection that works regardless of working directory:

1. Walk up from `source_path` parameter to find `fractalic.py`
2. Walk up from current working directory to find `fractalic.py`  
3. Use plugin installation path (works regardless of cwd)
4. Fallback to current working directory

This ensures configuration files are found correctly whether deployed from CLI or UI.

## Usage

### CLI Deployment

```bash
python publisher_cli.py deploy docker-registry \
  --name "my-deployment" \
  --script-name "my-script" \
  --script-folder "path/to/scripts"
```

### UI Deployment

The UI server (`core/ui_server/server.py`) provides REST endpoints:

- `POST /api/deploy/docker-registry`: Standard deployment
- `POST /api/deploy/docker-registry/stream`: Deployment with real-time progress

### Expected Output

```bash
🎉 Fractalic AI Server deployed successfully!

📋 AI Server Access:
   • Host: http://localhost:8001
   • Health Check: http://localhost:8001/health
   • API Documentation: http://localhost:8001/docs

🗂️ Deployed Script:
   • File: /payload/my-script/my-script.md
   • Container: my-deployment

📝 Sample Usage:
   curl -X POST http://localhost:8001/execute \
     -H "Content-Type: application/json" \
     -d '{"filename": "payload/my-script/my-script.md"}'

🐳 Container Management:
   • View logs: docker logs my-deployment
   • Stop: docker stop my-deployment
   • Remove: docker rm my-deployment
```

## Development

### Plugin Development

To create a new deployment plugin:

1. Inherit from `BasePublishPlugin`
2. Implement required methods: `publish()`, `validate_config()`
3. Add plugin registration in `PluginManager._load_builtin_plugins()`

### Debugging

Use the debug script to test deployment steps:

```bash
python publisher/debug_deployment.py
```

This tests:
- Docker image pull
- Container startup
- Health checks
- Cleanup

### Development Notes

- **Module Caching**: The plugin manager includes `importlib.reload()` to handle Python module caching during development
- **Hot Reload**: If using `uvicorn --reload`, manually restart the server if plugin changes don't take effect
- **Working Directory**: The system works correctly regardless of the current working directory

## Configuration

### Deployment Configuration

```python
config = DeploymentConfig(
    plugin_name="docker-registry",
    script_name="my-script",
    script_folder="path/to/scripts",
    container_name="my-deployment",
    environment_vars={},
    port_mapping={},
    plugin_specific={
        "image_name": "ghcr.io/fractalic-ai/fractalic:latest-production"
    }
)
```

### Plugin Configuration

```python
plugin_config = {
    "script_name": "my-script",
    "script_folder": "path/to/scripts", 
    "container_name": "my-deployment",
    "registry_image": "ghcr.io/fractalic-ai/fractalic:latest-production",
    "platform": "linux/arm64",  # Auto-detected
    "ports": {"ai_server": 8001},
    "include_files": ["*"],
    "exclude_patterns": [".git", "__pycache__", "*.pyc"]
}
```

## Health Checking

The system performs comprehensive health checks:

1. **AI Server**: `GET /health` endpoint
2. **MCP Manager**: `GET /status` endpoint (internal)
3. **Container Status**: Docker container health status

## Security

- **Minimal Exposure**: Only AI server port exposed externally
- **Internal Services**: Backend UI and MCP manager remain internal
- **Configuration Isolation**: Each deployment gets isolated configuration

## Troubleshooting

### Common Issues

1. **"No model specified and no defaultProvider in settings.toml"**
   - **Cause**: Configuration files not copied to container
   - **Solution**: Check project root detection, restart UI server

2. **Port conflicts**
   - **Cause**: Default port 8001 already in use
   - **Solution**: Auto-port detection will find next available port

3. **Plugin changes not taking effect**
   - **Cause**: Python module caching
   - **Solution**: Manually restart the UI server

### Debug Steps

1. Check container status: `docker ps`
2. Check container logs: `docker logs <container-name>`
3. Test health endpoints manually: `curl http://localhost:8001/health`
4. Run debug script: `python publisher/debug_deployment.py`

## Future Enhancements

- Additional cloud platform plugins (Railway, Render, Fly.io)
- Multi-region deployment support
- Deployment scaling and load balancing
- Enhanced monitoring and logging
- Automated SSL certificate management
