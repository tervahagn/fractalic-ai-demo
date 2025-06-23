#!/bin/bash

# Fractalic Docker Build & Run Script
# This script is designed for fresh GitHub installations via:
# curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/docker_build_run.sh | bash
#
# It will clone both fractalic and fractalic-ui repositories and build/run them in Docker.
# For deploying existing local installations with custom content, use publish_docker.py instead.

echo "Setting up Fractalic from GitHub..."

# Safety check: Ensure we're in an empty or nearly empty directory
# This prevents accidentally polluting existing projects
CURRENT_FILES=$(ls -la | wc -l)
if [ $CURRENT_FILES -gt 3 ]; then  # . .. and maybe one other file
    echo "❌ ERROR: This directory is not empty!"
    echo "This script is designed for fresh installations in empty directories."
    echo ""
    echo "Current directory contents:"
    ls -la
    echo ""
    echo "If you want to deploy an existing Fractalic installation with custom content,"
    echo "use the publish_docker.py script instead:"
    echo "  python publish_docker.py --help"
    echo ""
    echo "If you want to continue anyway, create a new empty directory and run this script there."
    exit 1
fi

echo "✅ Directory is suitable for fresh installation"

# 1. Clone fractalic repository
echo "Cloning fractalic repository..."
git clone https://github.com/fractalic-ai/fractalic.git
cd fractalic

# 2. Clone fractalic-ui repository  
echo "Cloning fractalic-ui repository..."
cd ..
git clone https://github.com/fractalic-ai/fractalic-ui.git

# 3. Create temporary build directory
BUILD_DIR=$(mktemp -d -t fractalic-build-XXXXXX)
echo "Created temporary build directory: $BUILD_DIR"

# 4. Copy source repos to build directory
echo "Copying source repositories to build directory..."
cp -r fractalic "$BUILD_DIR/"
cp -r fractalic-ui "$BUILD_DIR/"

# 5. Copy Docker files to build directory
echo "Setting up Docker build context..."
cp -a fractalic/docker/. "$BUILD_DIR/"

# 6. Build Docker image from temporary directory
echo "Building Docker image..."
cd "$BUILD_DIR"
docker build -t fractalic-app .

# 7. Return to original directory and cleanup
ORIGINAL_DIR="$PWD"
cd - > /dev/null
echo "Cleaning up temporary build directory..."
rm -rf "$BUILD_DIR"
cd fractalic  # Move into fractalic directory for container management

# 7. Check if container already exists and remove it
if [ "$(docker ps -qa -f name=fractalic-app)" ]; then
  echo "Removing existing container..."
  docker stop fractalic-app >/dev/null 2>&1
  docker rm fractalic-app >/dev/null 2>&1
fi

# 5. Run the container
echo "Starting container..."
docker run -d \
  -p 8000:8000 \
  -p 3000:3000 \
  -p 8001:8001 \
  -p 8002:8002 \
  -p 8003:8003 \
  -p 8004:8004 \
  -p 5859:5859 \
  --name fractalic-app \
  fractalic-app

# 6. Wait for services to be ready
echo "Waiting for services to start (this may take a moment)..."
sleep 10

# 7. Check if services are running
if docker ps | grep -q fractalic-app; then
  echo "✅ Container is running"
  
  # Check if service is responding
  if curl -s http://localhost:8000 >/dev/null 2>&1; then
    echo "✅ Backend is available at: http://localhost:8000"
  else
    echo "⚠️ Backend may still be starting at: http://localhost:8000"
  fi
  
  # Check AI server
  if curl -s http://localhost:8001 >/dev/null 2>&1; then
    echo "✅ AI Server is available at: http://localhost:8001"
  else
    echo "⚠️ AI Server may still be starting at: http://localhost:8001"
  fi
  
  # Check MCP manager
  if curl -s http://localhost:5859 >/dev/null 2>&1; then
    echo "✅ MCP Manager is available at: http://localhost:5859"
  else
    echo "⚠️ MCP Manager may still be starting at: http://localhost:5859"
  fi
  
  echo "✅ UI should be available at: http://localhost:3000"
  echo ""
  echo "📋 All Services Summary:"
  echo "   • Frontend UI:    http://localhost:3000"
  echo "   • Backend API:    http://localhost:8000"
  echo "   • AI Server:      http://localhost:8001"
  echo "   • MCP Manager:    http://localhost:5859"
  echo ""
  echo "Setup complete! Container is ready."
else
  echo "❌ Container failed to start. Check logs with: docker logs fractalic-app"
fi