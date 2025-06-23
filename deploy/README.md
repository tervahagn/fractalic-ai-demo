# Fractalic Deploy Scripts

This directory contains one-click deployment scripts and configurations for Fractalic.

## 🚀 Quick Deploy Options

### 1. Docker Desktop (Local)
```bash
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/deploy/docker-deploy.sh | bash
```

### 2. GitHub Codespaces (Cloud)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/fractalic-ai/fractalic?quickstart=1)

### 3. Plugin CLI (Advanced)
```bash
git clone https://github.com/fractalic-ai/fractalic.git
cd fractalic
python publisher_cli.py deploy local_docker --name my-app
```

## 📁 Files

- `docker-deploy.sh` - One-click Docker deployment script
- `codespaces-deploy.md` - GitHub Codespaces information  
- `../docs/deploy/index.html` - Web interface for deployment options

## 🔧 How It Works

The deployment scripts:
1. Check for required dependencies (Docker, Git)
2. Clone both `fractalic` and `fractalic-ui` repositories
3. Build and run the Docker container with proper port mapping
4. Provide access URLs for all services

## 🌐 Access URLs After Deployment

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000  
- **AI Server**: http://localhost:8001
- **MCP Manager**: http://localhost:5859

## 🛠️ Customization

### Custom Ports
```bash
curl -s https://raw.githubusercontent.com/fractalic-ai/fractalic/main/deploy/docker-deploy.sh | bash -s "my-app" "50"
```
This deploys with 50 port offset: 3050, 8050, 8051, 5909

### Plugin CLI with Options
```bash
python publisher_cli.py deploy local_docker \\
  --name my-app \\
  --ports "3100:3000,8100:8000,8101:8001,5960:5859"
```

## 🔮 Coming Soon

- Railway one-click deploy
- Render.com one-click deploy  
- Fly.io one-click deploy
- DigitalOcean App Platform deploy
- Heroku deployment (if Docker support returns)

## 🤝 Contributing

Want to add a new deployment platform? 

1. Create a new plugin in `../publisher/plugins/your_platform/`
2. Implement the `BasePublishPlugin` interface
3. Add deploy script in this directory
4. Update README badges

See `../PUBLISHER_ARCHITECTURE.md` for detailed plugin development guide.
