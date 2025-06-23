# Fractalic Docker Deployment Guide

This guide covers TWO different deployment scenarios:

## 🆕 Fresh Installation from GitHub (New Users)

Use the shell script for clean installations from GitHub:

```bash
# Create empty directory and run
mkdir my-fractalic && cd my-fractalic
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/docker_build_run.sh | bash
```

## 🔧 Deploy Existing Installation (Developers/Custom Content)

Use the Python script to deploy your existing Fractalic installation with custom tutorials, scripts, or modifications:

```bash
# From your existing fractalic directory
python publish_docker.py
```

---

This guide documents the **existing installation deployment** process using the Python publish script.

## Prerequisites for Existing Installation Deployment

- Existing Fractalic installation with custom content
- fractalic-ui repository at `../fractalic-ui` (one level up)
- Docker Desktop installed and running
- Python 3.11+ with required dependencies

## Expected Directory Structure

```
your-workspace/
├── fractalic/              (your main fractalic repo with custom content)
├── fractalic-ui/           (UI repo - automatically detected)
└── my-custom-tutorials/    (optional additional content)
```

## Step 1: Project Structure Verification

First, verify that the tutorials directory exists in the project:

```bash
ls -la /path/to/fractalic/tutorials/
```

Expected output:
```
01_Basics/
02_tutorial_yahoofinance_tavily_stocks_news_analytics/
```

Check the hello world tutorial:
```bash
ls -la /path/to/fractalic/tutorials/01_Basics/hello-world/
```

Expected output:
```
.git/
hello_world.md
```

## Step 2: Dockerfile Configuration

Ensure the Dockerfile includes the tutorials directory. The following line should be present:

```dockerfile
COPY tutorials/ /app/tutorials/
```

This was added to both `Dockerfile` and `Dockerfile.ci` to ensure tutorial scripts are included in the Docker image.

## Step 3: Build and Run with Deploy Script

Navigate to the fractalic directory and execute the custom deploy script:

```bash
cd /path/to/fractalic
./docker_build_run.sh
```

### Build Process Output

The script will:
1. Set up Fractalic environment
2. Use existing fractalic-ui from the parent directory
3. Build the Docker image with all dependencies
4. Remove any existing container
5. Start the new container

Expected final output:
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

## Step 4: Verify Container and Tutorials

Check that the container is running:

```bash
docker ps
```

Expected output:
```
CONTAINER ID   IMAGE           COMMAND                  CREATED         STATUS         PORTS                                                                              NAMES
d36813bc199a   fractalic-app   "supervisord -c /etc…"   X seconds ago   Up X seconds   0.0.0.0:3000->3000/tcp, 0.0.0.0:5859->5859/tcp, 0.0.0.0:8000-8004->8000-8004/tcp   fractalic-app
```

Verify tutorials are present in the container:

```bash
docker exec -it fractalic-app ls -la /app/tutorials/
```

Expected output:
```
total 32
drwxr-xr-x 1 appuser appuser 4096 Jun 13 16:20 .
drwxr-xr-x 1 appuser appuser 4096 Jun 23 15:41 ..
drwxr-xr-x 1 appuser appuser 4096 Jun  9 00:16 01_Basics
drwxr-xr-x 1 appuser appuser 4096 Jun 12 13:42 02_tutorial_yahoofinance_tavily_stocks_news_analytics
```

Confirm hello world tutorial is accessible:

```bash
docker exec -it fractalic-app ls -la /app/tutorials/01_Basics/hello-world/
```

Expected output:
```
total 28
drwxr-xr-x 1 appuser appuser 4096 Jun 22 23:33 .
drwxr-xr-x 1 appuser appuser 4096 Jun  9 00:16 ..
drwxr-xr-x 1 appuser appuser 4096 Jun 22 22:49 .git
-rw-r--r-- 1 appuser appuser  267 Jun 22 22:49 hello_world.md
```

## Step 5: Test AI Server with Hello World Tutorial

Execute the hello world tutorial using curl to call the AI server's `/execute` endpoint:

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{"filename": "tutorials/01_Basics/hello-world/hello_world.md"}' \
  | jq
```

### Hello World Tutorial Content

The `hello_world.md` tutorial contains:

```markdown
# Agent identity
Your name is Fractalic and your goal is to help user with their requests

@shell
prompt: ls -la

@llm
prompt: Please abalyze file list and give me nice summary. Format list as Markdown table
use-header: "# File summary"

@return
block: file-summary/*
```

### Successful Execution Result

```json
{
  "success": true,
  "explicit_return": true,
  "return_content": "# File summary\nHere's a summary of the files and directories in your current location:\n\nThis directory appears to be a Git repository, indicated by the presence of the `.git` directory and the `.gitignore` file. It also contains a Markdown document named `hello_world.md`. All listed items are owned by `appuser`.\n\n### File List Summary\n\n| Name             | Type      | Permissions | Size (bytes) | Last Modified     |\n| :--------------- | :-------- | :---------- | :----------- | :---------------- |\n| `.`              | Directory | `drwxr-xr-x`| 4096         | Jun 23 15:42      |\n| `..`             | Directory | `drwxr-xr-x`| 4096         | Jun 9 00:16       |\n| `.git`           | Directory | `drwxr-xr-x`| 4096         | Jun 23 15:42      |\n| `.gitignore`     | File      | `-rw-r--r--`| 45           | Jun 23 15:42      |\n| `hello_world.md` | File      | `-rw-r--r--`| 267          | Jun 22 22:49      |\n\n",
  "branch_name": "20250623154202_0338efda_Testing-git-operations",
  "ctx_file": null,
  "output": "Execution completed. Branch: 20250623154202_0338efda_Testing-git-operations, Context: 708c3d69b040ad966a07d0ec0b193fb22a03f2d6"
}
```

## What the Test Demonstrates

1. **Successful Build**: The Docker image built successfully with all required components
2. **Tutorials Included**: The tutorials directory is properly copied into the container
3. **AI Server Running**: The AI server is accessible on port 8001
4. **Tutorial Execution**: The hello world tutorial executes properly, demonstrating:
   - Shell command execution (`ls -la`)
   - LLM integration for analysis
   - Formatted output generation
   - Git branch tracking for operations

## Service Endpoints

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **AI Server**: http://localhost:8001
- **MCP Manager**: http://localhost:5859

## Key Files Modified

1. **Dockerfile**: Added `COPY tutorials/ /app/tutorials/`
2. **Dockerfile.ci**: Added `COPY tutorials/ /app/tutorials/`

## Troubleshooting

If the container doesn't start properly:
1. Check Docker Desktop is running
2. Ensure no other services are using the required ports
3. Run `docker logs fractalic-app` to check container logs

If tutorials are missing:
1. Verify the COPY command is present in the Dockerfile
2. Rebuild the image with `./docker_build_run.sh`

## Summary

This deployment successfully demonstrates:
- Building Fractalic Docker image with custom deploy script
- Including tutorials directory in the container
- Running the container with all services
- Testing AI server functionality with the hello world tutorial
- Complete end-to-end workflow from build to execution

The hello world tutorial execution confirms that the Fractalic AI server can successfully:
- Process tutorial scripts
- Execute shell commands
- Integrate with LLM for content analysis
- Return formatted results
- Track operations with Git branching
