# Fractalic Docker Publishing System

This system provides a clean way to publish the current working Fractalic repository to a Docker container without polluting the main development environment.

## Overview

The publishing system consists of several components:

1. **`publish_docker.py`** - Core Python script that handles the entire publishing process
2. **`publish_docker.sh`** - Simple bash wrapper for command-line usage
3. **`publish_api.py`** - FastAPI server that provides HTTP endpoints for UI integration
4. **`ui_integration_example.py`** - Example code showing how to integrate with the UI

## Key Features

- ✅ **Clean Publishing**: Uses temporary directories, doesn't modify source repo
- ✅ **Auto-Detection**: Automatically finds and includes adjacent `fractalic-ui` repository
- ✅ **Port Management**: Supports custom port offsets to avoid conflicts
- ✅ **Service Management**: Includes all Fractalic services (UI, Backend, AI Server, MCP Manager)
- ✅ **Container Management**: Start, stop, and manage published containers
- ✅ **UI Integration**: API endpoints ready for frontend integration

## Quick Usage

### Command Line

```bash
# Publish with default settings
./publish_docker.sh

# Publish with custom container name
./publish_docker.sh my-fractalic-container

# Publish with port offset (useful for multiple deployments)
./publish_docker.sh my-container 100
```

### Python Script

```bash
# Basic publish
python publish_docker.py

# Custom container name and port offset
python publish_docker.py --name my-container --port-offset 100

# Keep temporary files for debugging
python publish_docker.py --keep-temp
```

### API Server

```bash
# Start the API server
python publish_api.py

# API will be available at http://localhost:8080
# API docs at http://localhost:8080/docs
```

## How It Works

### 1. Preparation Phase
- Creates a temporary build directory
- Copies current Fractalic repository (excluding development files)
- Detects and copies adjacent `fractalic-ui` repository if present
- Creates minimal frontend placeholder if `fractalic-ui` is not found

### 2. Build Phase
- Copies Docker configuration files
- Modifies port mappings if port offset is specified
- Builds Docker image with all components

### 3. Deployment Phase
- Stops any existing container with the same name
- Starts new container with proper port mappings
- Verifies service availability
- Reports deployment status

### 4. Cleanup Phase
- Removes temporary build directory
- Preserves only the running Docker container

## Port Mappings

Default ports (offset 0):
- **Frontend UI**: 3000
- **Backend API**: 8000
- **AI Server**: 8001-8004
- **MCP Manager**: 5859

With port offset (e.g., offset 100):
- **Frontend UI**: 3100
- **Backend API**: 8100
- **AI Server**: 8101-8104
- **MCP Manager**: 5959

## API Endpoints

The publish API provides the following endpoints:

### Publishing Operations
- `POST /publish` - Start a new publish operation
- `GET /publish/status/{operation_id}` - Get status of a publish operation
- `GET /publish/operations` - List all publish operations
- `DELETE /publish/operations/{operation_id}` - Delete operation tracking

### Container Management
- `GET /containers` - List all Docker containers
- `POST /containers/{name}/stop` - Stop a container
- `POST /containers/{name}/remove` - Remove a container

### Utility
- `GET /health` - Health check

## Example API Usage

```python
import aiohttp
import asyncio

async def publish_example():
    async with aiohttp.ClientSession() as session:
        # Start publish operation
        payload = {
            "container_name": "my-fractalic-app",
            "port_offset": 0
        }
        
        async with session.post("http://localhost:8080/publish", json=payload) as response:
            result = await response.json()
            operation_id = result["operation_id"]
            
        # Poll for completion
        while True:
            async with session.get(f"http://localhost:8080/publish/status/{operation_id}") as response:
                status = await response.json()
                
                if status["status"] == "completed":
                    print(f"✅ Published successfully!")
                    print(f"Services available at ports: {status['ports']}")
                    break
                elif status["status"] == "failed":
                    print(f"❌ Publishing failed: {status.get('error', 'Unknown error')}")
                    break
                    
                await asyncio.sleep(2)

# Run the example
asyncio.run(publish_example())
```

## UI Integration

For integrating with the Fractalic UI, use the provided `ui_integration_example.py` as a reference. The key steps are:

1. **Start Publish API**: Run `publish_api.py` on a dedicated port (e.g., 8080)
2. **Create UI Components**: Add publish buttons and status displays to the UI
3. **Make API Calls**: Use the HTTP endpoints to start/monitor publishing operations
4. **Handle Results**: Display container information and service URLs to users

## Directory Structure

```
fractalic/
├── publish_docker.py          # Core publishing script
├── publish_docker.sh          # Bash wrapper
├── publish_api.py             # HTTP API server
├── ui_integration_example.py  # UI integration example
├── docker/
│   ├── Dockerfile            # Docker configuration
│   └── supervisord.conf      # Service management
└── ...
```

## Excluded Files

The publishing process automatically excludes development files:
- `.git/` - Git repository data
- `__pycache__/`, `*.pyc` - Python cache files
- `venv/`, `.venv/` - Virtual environments
- `node_modules/` - Node.js dependencies
- `.DS_Store` - macOS system files
- `*.log`, `logs/*` - Log files
- `.vscode/`, `.idea/` - Editor configurations

## Troubleshooting

### Common Issues

1. **Docker not available**
   - Ensure Docker is installed and running
   - Check with `docker --version`

2. **Port conflicts**
   - Use `--port-offset` to avoid conflicts with existing services
   - Check which ports are in use with `netstat -an | grep LISTEN`

3. **Missing fractalic-ui**
   - Place `fractalic-ui` repository adjacent to `fractalic` repository
   - Or accept the minimal frontend placeholder

4. **Build failures**
   - Check Docker logs with `docker logs <container-name>`
   - Use `--keep-temp` to inspect build directory

### Debug Mode

```bash
# Keep temporary files for inspection
python publish_docker.py --keep-temp

# Check container logs
docker logs fractalic-published

# Check running containers
docker ps

# Check all containers (including stopped)
docker ps -a
```

## Integration with Fractalic UI

To integrate this with the main Fractalic UI:

1. **Add Publish Button**: Add a "Publish to Docker" button in the UI
2. **Start API Server**: Run `publish_api.py` alongside the main UI server
3. **Handle Publishing**: Use the API to start publishing and show progress
4. **Display Results**: Show container information and service URLs
5. **Container Management**: Allow users to stop/restart published containers

The system is designed to be non-intrusive and can be easily integrated into the existing Fractalic UI workflow.
