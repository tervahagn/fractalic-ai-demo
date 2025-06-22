#!/bin/bash

# Fractalic Docker Publisher - Bash Wrapper
# 
# Simple wrapper script for the Python publisher
# Usage: ./publish_docker.sh [container-name] [port-offset]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="${1:-fractalic-published}"
PORT_OFFSET="${2:-0}"

echo "🚀 Publishing Fractalic to Docker..."
echo "   Container name: $CONTAINER_NAME"
echo "   Port offset: $PORT_OFFSET"
echo ""

python3 "$SCRIPT_DIR/publish_docker.py" --name "$CONTAINER_NAME" --port-offset "$PORT_OFFSET"
