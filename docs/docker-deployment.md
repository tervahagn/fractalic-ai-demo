# Fractalic Docker Deployment & Publishing Guide

This comprehensive guide covers Fractalic Docker deployment scenarios and the publishing system architecture.

## 🚀 Deployment Scenarios

Fractalic supports TWO different deployment approaches:

### 🆕 Fresh Installation from GitHub (New Users)

Perfect for users who want to try Fractalic without any existing setup:

```bash
# Create empty directory and run
mkdir my-fractalic && cd my-fractalic
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/docker_build_run.sh | bash
```

**What this does:**
- Checks for empty directory (safety)
- Clones fractalic and fractalic-ui from GitHub
- Creates temporary build context
- Builds and runs Docker container
- Cleans up temporary files

### 🔧 Deploy Existing Installation (Developers/Custom Content)

For developers with existing Fractalic installations containing custom tutorials, scripts, or modifications:

```bash
# From your existing fractalic directory
python publish_docker.py
```

**What this does:**
- Uses your current installation with all customizations
- Includes your tutorials, scripts, and modifications
- Deploys to Docker with proper networking
- Supports additional content inclusion

---

## 📁 Expected Directory Structure

### For Existing Installation Deployment

```
your-workspace/
├── fractalic/              (your main fractalic repo with custom content)
├── fractalic-ui/           (UI repo - automatically detected)
└── my-custom-tutorials/    (optional additional content)
```

### Prerequisites

- Existing Fractalic installation with custom content
- fractalic-ui repository at `../fractalic-ui` (one level up)
- Docker Desktop installed and running
- Python 3.11+ with required dependencies

---

## 🛠 Publishing System Architecture

The publishing system provides a clean way to publish your working Fractalic repository to Docker without polluting your development environment.

### Core Components

1. **`publish_docker.py`** - Core Python script handling the entire publishing process
2. **`publish_docker.sh`** - Simple bash wrapper for command-line usage
3. **`publish_api.py`** - FastAPI server providing HTTP endpoints for UI integration
4. **`ui_integration_example.py`** - Example code for UI integration

### Key Features

- ✅ **Clean Publishing**: Uses temporary directories, doesn't modify source repo
- ✅ **Auto-Detection**: Automatically finds and includes adjacent `fractalic-ui` repository
- ✅ **Port Management**: Supports custom port offsets to avoid conflicts
- ✅ **Service Management**: Includes all Fractalic services (UI, Backend, AI Server, MCP Manager)
- ✅ **Container Management**: Start, stop, and manage published containers
- ✅ **UI Integration**: API endpoints ready for frontend integration

---

## 🚀 Quick Usage

### Command Line Publishing

```bash
# Publish with default settings
./publish_docker.sh

# Publish with custom container name
./publish_docker.sh my-fractalic-container

# Publish with port offset (useful for multiple deployments)
./publish_docker.sh my-container 100
```

### Python Script Publishing

```bash
# Basic publish
python publish_docker.py

# Custom container name and port offset
python publish_docker.py --name my-container --port-offset 100

# Keep temporary files for debugging
python publish_docker.py --keep-temp
```

### API Publishing

```bash
# Start the publishing API server
python publish_api.py

# Then use HTTP endpoints:
# POST /publish - Start publishing
# GET /status/{container_name} - Check status
# POST /stop/{container_name} - Stop container
```

---

## 📋 Step-by-Step Deployment Process

### Step 1: Project Structure Verification

First, verify that your project structure is correct:

```bash
# Check tutorials directory exists
ls -la /path/to/fractalic/tutorials/

# Expected output:
# 01_Basics/
# 02_tutorial_yahoofinance_tavily_stocks_news_analytics/

# Check hello world tutorial
ls -la /path/to/fractalic/tutorials/01_Basics/hello-world/

# Expected output:
# .git/
# hello_world.md
```

### Step 2: Build and Deploy

#### Using Shell Script (Fresh Install)
```bash
mkdir my-fractalic && cd my-fractalic
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/docker_build_run.sh | bash
```

#### Using Python Script (Existing Installation)
```bash
cd /path/to/fractalic
python publish_docker.py
```

**Expected Build Output:**
```
✅ Container is running
✅ Backend is available at: http://localhost:8000
✅ AI Server is available at: http://localhost:8001
⚠️ MCP Manager may still be starting at: http://localhost:5859
✅ UI should be available at: http://localhost:3000

📋 All Services Summary:
   • Frontend UI:    http://localhost:3000
   • Backend API:    http://localhost:8000
   • AI Server:      http://localhost:8001
   • MCP Manager:    http://localhost:5859

Setup complete! Container is ready.
```

### Step 3: Verify Container and Content

Check that the container is running:

```bash
docker ps
```

Verify tutorials are present in the container:

```bash
docker exec -it fractalic-app ls -la /app/tutorials/
```

### Step 4: Test AI Server Functionality

Execute the hello world tutorial using the AI server:

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{"filename": "tutorials/01_Basics/hello-world/hello_world.md"}' \
  | jq
```

**Expected Success Response:**
```json
{
  "success": true,
  "explicit_return": true,
  "return_content": "# File summary\nHere's a summary of the files and directories...",
  "branch_name": "20250623154202_0338efda_Testing-git-operations",
  "ctx_file": null,
  "output": "Execution completed. Branch: ..., Context: ..."
}
```

---

## 🌐 Service Endpoints

Once deployed, Fractalic provides these endpoints:

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **AI Server**: http://localhost:8001
- **MCP Manager**: http://localhost:5859

With port offset (e.g., `--port-offset 100`):
- **Frontend UI**: http://localhost:3100
- **Backend API**: http://localhost:8100
- **AI Server**: http://localhost:8101
- **MCP Manager**: http://localhost:5959

---

## 🔧 Advanced Configuration

### Port Management

```bash
# Deploy with custom ports (adds offset to all services)
python publish_docker.py --port-offset 100 --name fractalic-dev

# This creates:
# Frontend: 3100, Backend: 8100, AI Server: 8101, MCP Manager: 5959
```

### Container Management

```bash
# List running containers
docker ps

# View container logs
docker logs fractalic-app

# Stop container
docker stop fractalic-app

# Remove container
docker rm fractalic-app

# Remove image
docker rmi fractalic-app
```

### Multiple Deployments

```bash
# Deploy multiple instances with different ports
python publish_docker.py --name fractalic-dev --port-offset 0
python publish_docker.py --name fractalic-staging --port-offset 100
python publish_docker.py --name fractalic-prod --port-offset 200
```

---

## 🐛 Troubleshooting

### Common Issues

1. **Container fails to start**
   - Check Docker Desktop is running
   - Ensure ports are not in use: `lsof -i :3000 -i :8000 -i :8001 -i :5859`
   - Check container logs: `docker logs fractalic-app`

2. **Services not responding**
   - Wait 30-60 seconds for services to fully start
   - Check individual service logs in container
   - Verify firewall/network settings

3. **fractalic-ui not found**
   - Ensure `fractalic-ui` is at `../fractalic-ui` relative to fractalic directory
   - Clone it manually: `git clone https://github.com/fractalic-ai/fractalic-ui.git`
   - Place `fractalic-ui` repository adjacent to `fractalic` repository

4. **Build failures**
   - Check Docker logs with `docker logs <container-name>`
   - Use `--keep-temp` to inspect build directory
   - Ensure sufficient disk space and memory

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

# Inspect container filesystem
docker exec -it fractalic-app bash
```

### Tutorials Missing

If tutorials are missing:
1. Verify the tutorials directory exists in source
2. Check Dockerfile includes `COPY fractalic/tutorials/ /app/tutorials/`
3. Rebuild the image
4. Verify with: `docker exec -it fractalic-app ls -la /app/tutorials/`

---

## 🔌 UI Integration

To integrate the publishing system with the main Fractalic UI:

### 1. Start Publishing API

```bash
# Start the API server alongside main UI
python publish_api.py
```

### 2. Add UI Components

```javascript
// Example: Add publish button to UI
const publishToDocker = async () => {
  const response = await fetch('/api/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      container_name: 'my-fractalic',
      port_offset: 0
    })
  });
  
  const result = await response.json();
  console.log('Published:', result);
};
```

### 3. API Endpoints

- `POST /publish` - Start publishing process
- `GET /status/{container_name}` - Check container status
- `POST /stop/{container_name}` - Stop container
- `GET /containers` - List all published containers

The system is designed to be non-intrusive and can be easily integrated into the existing Fractalic UI workflow.

---

## 📊 What Deployment Demonstrates

A successful deployment confirms:

1. **Successful Build**: Docker image built with all components
2. **Content Inclusion**: Tutorials and custom content properly copied
3. **Service Integration**: All services (UI, Backend, AI Server, MCP Manager) running
4. **AI Server Functionality**: Can execute tutorial scripts via API
5. **Network Configuration**: Proper port mapping and service communication
6. **Tutorial Execution**: Demonstrates:
   - Shell command execution (`ls -la`)
   - LLM integration for analysis
   - Formatted output generation
   - Git branch tracking for operations

---

## 🔒 Key Files and Safety

### Modified Files
1. **docker/Dockerfile**: Updated with proper build context paths
2. **docker/supervisord.conf**: Fixed working directories and command syntax
3. **docker_build_run.sh**: Enhanced with safety checks for fresh installs
4. **publish_docker.py**: Enhanced with safety checks for existing installations

### Safety Features
- **Empty Directory Check**: Shell script only runs in empty directories
- **Path Validation**: Python script validates all paths to prevent repo pollution
- **Temporary Directories**: All builds use temporary directories, never modify source
- **Auto Cleanup**: Automatic cleanup of temporary files after build
- **.gitignore Protection**: Prevents accidental commit of build artifacts

---

## 🎯 Summary

The Fractalic Docker deployment system provides:

- **Two deployment paths**: Fresh installs vs. existing installations
- **Safety-first approach**: Never pollutes source repositories
- **Flexible configuration**: Custom ports, names, and content inclusion
- **Complete service stack**: UI, Backend, AI Server, and MCP Manager
- **Developer-friendly**: Easy debugging and troubleshooting
- **UI integration ready**: API endpoints for frontend integration

Whether you're a new user trying Fractalic or a developer deploying custom content, the system provides a clean, safe, and powerful way to run Fractalic in Docker containers.
