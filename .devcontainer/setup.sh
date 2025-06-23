#!/bin/bash
# GitHub Codespaces setup script for Fractalic

echo "🚀 Setting up Fractalic in GitHub Codespaces..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Clone fractalic-ui in parent directory
echo "📥 Cloning fractalic-ui..."
cd ..
git clone https://github.com/fractalic-ai/fractalic-ui.git
cd fractalic-ui

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Return to fractalic directory
cd ../fractalic

echo "🎉 Setup complete!"
echo ""
echo "🚀 To start Fractalic:"
echo "1. Terminal 1: ./run_server.sh (Backend)"
echo "2. Terminal 2: cd ../fractalic-ui && npm run dev (Frontend)"
echo ""
echo "🌐 Access URLs will be automatically forwarded:"
echo "   - Frontend: http://localhost:3000"
echo "   - Backend: http://localhost:8000"
echo "   - AI Server: http://localhost:8001"
