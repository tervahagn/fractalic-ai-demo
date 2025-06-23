# Fractalic Plugin-Based Publishing System 🚀

## 🎯 Architecture Overview

The Fractalic Publisher has been redesigned as a **plugin-based system** that supports deployment to multiple cloud platforms through discoverable plugins.

### 🏗️ Architecture Components

```
fractalic/
├── publisher/                    # Core publisher system
│   ├── models.py                # Data models (PluginInfo, DeploymentConfig, etc.)
│   ├── base_plugin.py           # Base plugin interface
│   ├── plugin_manager.py        # Plugin discovery and management
│   └── plugins/                 # Plugin directory
│       ├── local_docker/        # Local Docker Desktop plugin
│       ├── railway/             # Railway.app plugin (planned)
│       ├── render/              # Render.com plugin (planned)
│       └── fly_io/              # Fly.io plugin (planned)
├── publisher_cli.py             # Main CLI interface
├── publish_api.py               # HTTP API for UI integration
└── .github/workflows/           # CI/CD automation
    └── docker-build.yml         # GitHub Actions workflow
```

## 🔌 Plugin System Features

### **Plugin Capabilities**
- ✅ **One-Click Deploy**: Deploy with a single command
- ✅ **Git Integration**: Automatic deployment from Git repos
- ✅ **Custom Domains**: Support for custom domain configuration
- ✅ **Auto Scaling**: Automatic resource scaling
- ✅ **Free Tier**: Free hosting options available
- ✅ **Instant Preview**: Quick preview/testing deployment

### **Current Plugins**

#### 🐳 Local Docker Desktop
- **Best for**: Development, testing, local demos
- **Setup**: Easy (requires Docker Desktop)
- **Deploy Time**: 2-5 minutes
- **Cost**: Free (local resources)
- **Features**: Free Tier, Instant Preview, One-Click Deploy

#### 🚅 Railway (Planned)
- **Best for**: Production apps, hobby projects
- **Setup**: Easy (GitHub integration)
- **Deploy Time**: < 1 minute
- **Cost**: Free tier + usage-based
- **Features**: Git Integration, Auto Scaling, Custom Domains

#### 🎨 Render (Planned)
- **Best for**: Full-stack applications, APIs
- **Setup**: Easy (Git-based deployment)
- **Deploy Time**: 2-3 minutes  
- **Cost**: Free tier available
- **Features**: Auto HTTPS, Zero-downtime deploys

#### ✈️ Fly.io (Planned)
- **Best for**: Global applications, edge deployment
- **Setup**: Medium (CLI-based)
- **Deploy Time**: 1-2 minutes
- **Cost**: Pay-as-you-go
- **Features**: Global deployment, Auto scaling

## 🚀 Quick Start

### 1. List Available Plugins
```bash
python publisher_cli.py list
```

### 2. Get Plugin Details
```bash
python publisher_cli.py info local_docker
```

### 3. Deploy to Local Docker
```bash
python publisher_cli.py deploy local_docker --name my-fractalic-app
```

### 4. Deploy with Custom Configuration
```bash
python publisher_cli.py deploy local_docker \\
  --name my-app \\
  --ports "3100:3000,8100:8000" \\
  --env "API_KEY=secret" \\
  --env "DEBUG=true"
```

### 5. Generate README Badges
```bash
python publisher_cli.py badges
```

## 📋 CLI Commands

### **List Plugins**
```bash
python publisher_cli.py list
```
Shows all available plugins with their capabilities and features.

### **Plugin Information**
```bash
python publisher_cli.py info <plugin-name>
```
Shows detailed information about a specific plugin.

### **Deploy Application**
```bash
python publisher_cli.py deploy <plugin-name> --name <app-name> [options]
```

**Options:**
- `--name, -n`: Deployment name (required)
- `--ports, -p`: Port mapping (e.g., "3000:3000,8000:8000")
- `--env, -e`: Environment variables (e.g., "KEY=value")
- `--domain, -d`: Custom domain

### **Generate Deploy Buttons**
```bash
python publisher_cli.py badges
```
Generates markdown for README deploy buttons.

## 🔧 Plugin Development

### Creating a New Plugin

1. **Create plugin directory**:
```bash
mkdir publisher/plugins/my_platform
```

2. **Create plugin.py**:
```python
from base_plugin import BasePublishPlugin
from models import PluginInfo, PluginCapability

class MyPlatformPlugin(BasePublishPlugin):
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="my_platform",
            display_name="My Platform",
            description="Deploy to My Platform",
            version="1.0.0",
            homepage_url="https://myplatform.com",
            documentation_url="https://docs.myplatform.com",
            capabilities=[PluginCapability.ONE_CLICK_DEPLOY],
            pricing_info="Free tier available",
            setup_difficulty="easy",
            deploy_time_estimate="< 1 minute",
            free_tier_limits="500MB RAM, 1GB storage"
        )
    
    def validate_config(self, config):
        return True, None
    
    def publish(self, source_path, config, progress_callback=None):
        # Implement deployment logic
        pass
    
    # Implement other required methods...
```

3. **Test the plugin**:
```bash
python publisher_cli.py list
python publisher_cli.py info my_platform
```

## 🤖 GitHub Actions Integration

The system includes automatic CI/CD with GitHub Actions:

### **Features**
- ✅ **Automatic Testing**: Tests on every commit/PR
- ✅ **Docker Build**: Builds and tests Docker containers
- ✅ **Container Registry**: Publishes to GitHub Container Registry
- ✅ **Deploy Badges**: Auto-generates deployment information

### **Workflow Triggers**
- **Push to main/develop**: Full build and test
- **Pull Requests**: Build and test with deploy info comments
- **Releases**: Build, test, and publish to registry

### **Manual GitHub Container Registry Deploy**
```bash
# After GitHub Actions builds the image
docker run -p 3000:3000 -p 8000:8000 -p 8001:8001 \\
  ghcr.io/your-username/fractalic:main
```

## 📝 README Deploy Buttons

Add one-click deploy buttons to your README:

### Local Docker Desktop
[![Deploy to Docker Desktop](https://img.shields.io/badge/Deploy-Docker%20Desktop-2496ED?logo=docker)](docker://localhost/fractalic)

### Railway (Coming Soon)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/docker)

### Render (Coming Soon)  
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### DigitalOcean (Coming Soon)
[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new)

## 🔮 Planned Features

### **New Plugins**
- 🚅 **Railway**: One-click deployment with GitHub integration
- 🎨 **Render**: Zero-downtime deployments with free SSL
- ✈️ **Fly.io**: Global edge deployment
- 🌊 **DigitalOcean App Platform**: Scalable container hosting

### **Enhanced Features**
- 📊 **Deployment Dashboard**: Web UI for managing deployments
- 🔄 **Auto-Updates**: Automatic redeployment on git changes
- 📈 **Resource Monitoring**: Real-time resource usage tracking
- 🔐 **Secrets Management**: Secure environment variable handling
- 📱 **Mobile-Friendly CLI**: Progressive web app interface

### **Integration Features**
- 🔗 **Webhook Support**: Deploy via webhooks
- 📧 **Notification System**: Email/Slack deployment notifications
- 🏷️ **Deployment Tags**: Version tagging and rollback support
- 🔍 **Deployment Analytics**: Usage and performance metrics

## 💡 Use Cases

### **Development Workflow**
1. **Local Development**: Use `local_docker` plugin for testing
2. **Staging**: Deploy to Railway/Render for team review
3. **Production**: Deploy to Fly.io or DigitalOcean for scale

### **Demo Scenarios**
1. **Client Presentations**: Quick local Docker deployment
2. **Conference Demos**: One-click cloud deployment links
3. **Open Source**: README badges for instant try-it experience

### **CI/CD Integration**
1. **PR Previews**: Automatic preview deployments
2. **Release Automation**: Auto-deploy on version tags
3. **Multi-Environment**: Deploy to dev/staging/prod automatically

## 🛠️ Technical Details

### **Plugin Interface**
Each plugin implements the `BasePublishPlugin` interface with these methods:
- `get_info()`: Plugin metadata and capabilities
- `validate_config()`: Configuration validation
- `publish()`: Main deployment logic
- `get_deployment_info()`: Deployment status
- `list_deployments()`: List managed deployments
- `stop_deployment()`: Stop running deployment
- `delete_deployment()`: Remove deployment
- `get_logs()`: Retrieve deployment logs

### **Configuration System**
Deployments use standardized `DeploymentConfig`:
- `plugin_name`: Target plugin
- `container_name`: Deployment identifier
- `environment_vars`: Environment variables
- `port_mapping`: Port configuration
- `custom_domain`: Domain settings
- `plugin_specific`: Plugin-specific options

### **Progress Tracking**
Real-time deployment progress with callback system:
```python
def progress_callback(message: str, percentage: int):
    print(f"[{percentage:3d}%] {message}")
```

This plugin-based architecture makes Fractalic extremely flexible and extensible for deployment to any cloud platform! 🚀
