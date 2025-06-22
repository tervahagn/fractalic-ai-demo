#!/bin/bash

echo "Setting up Fractalic..."

# 1. Clone repositories if they don't exist
git clone https://github.com/fractalic-ai/fractalic.git
git clone https://github.com/fractalic-ai/fractalic-ui.git

# 2. Copy Docker files
cd fractalic
cp -a docker/. ..
cd ..

# 3. Build Docker image
echo "Building Docker image..."
docker build -t fractalic-app .

# 4. Check if container already exists and remove it
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