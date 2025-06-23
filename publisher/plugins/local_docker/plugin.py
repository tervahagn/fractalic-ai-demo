"""
Local Docker Plugin - Full Implementation

This plugin handles local Docker Desktop deployment of Fractalic applications.
It includes all the functionality from the original publish_docker.py script,
refactored into the plugin architecture.
"""
import sys
import os
import shutil
import tempfile
import subprocess
import json
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add publisher to path if needed
publisher_path = os.path.join(os.path.dirname(__file__), '..', '..')
if publisher_path not in sys.path:
    sys.path.insert(0, publisher_path)

from base_plugin import BasePublishPlugin
from models import PluginInfo, PluginCapability, DeploymentConfig, PublishResult, DeploymentInfo, DeploymentStatus


class LocalDockerPlugin(BasePublishPlugin):
    """Plugin for local Docker Desktop deployment"""
    
    def __init__(self):
        self.temp_dir = None
        self.active_deployments = {}
        
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="local_docker",
            display_name="Local Docker Desktop",
            description="Deploy to local Docker Desktop for development and testing",
            version="1.0.0",
            homepage_url="https://www.docker.com/products/docker-desktop/",
            documentation_url="https://docs.docker.com/",
            capabilities=[PluginCapability.FREE_TIER, PluginCapability.INSTANT_PREVIEW, PluginCapability.ONE_CLICK_DEPLOY],
            pricing_info="Free (requires Docker Desktop)",
            setup_difficulty="easy",
            deploy_time_estimate="2-5 minutes",
            free_tier_limits="Unlimited (local resources)",
            badge_url="https://img.shields.io/badge/Deploy-Docker%20Desktop-2496ED?logo=docker",
            deploy_button_url="docker://localhost/fractalic"
        )
    
    def validate_config(self, config: DeploymentConfig) -> tuple[bool, str]:
        """Validate Docker deployment configuration"""
        # Check if Docker is available
        try:
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False, "Docker is not available or not installed. Please install Docker Desktop."
        
        # Validate port configuration
        if hasattr(config, 'port_offset') and config.port_offset < 0:
            return False, "Port offset must be non-negative"
            
        return True, None
    
    def publish(self, source_path: str, config: DeploymentConfig, progress_callback=None) -> PublishResult:
        """Deploy Fractalic to local Docker"""
        deployment_id = f"fractalic-{int(time.time())}"
        
        try:
            self._log("Starting local Docker deployment...", progress_callback, 5)
            
            # Extract configuration
            container_name = getattr(config, 'container_name', deployment_id)
            port_offset = getattr(config, 'port_offset', 0)
            
            # Set up port mappings - use custom port mapping if provided
            if hasattr(config, 'port_mapping') and config.port_mapping:
                # Extract host ports from port_mapping (keys are host ports, values are container ports)
                host_ports = {}
                container_ports = {}
                port_map = config.port_mapping
                
                # Map standard services to their container ports
                service_container_ports = {3000: 'frontend', 8000: 'backend', 8001: 'ai_server', 5859: 'mcp_manager'}
                
                for host_port, container_port in port_map.items():
                    if container_port in service_container_ports:
                        service = service_container_ports[container_port]
                        host_ports[service] = host_port
                        container_ports[service] = container_port
                
                # Fill in any missing services with defaults + offset
                if 'frontend' not in host_ports:
                    host_ports['frontend'] = 3000 + port_offset
                    container_ports['frontend'] = 3000
                if 'backend' not in host_ports:
                    host_ports['backend'] = 8000 + port_offset
                    container_ports['backend'] = 8000
                if 'ai_server' not in host_ports:
                    host_ports['ai_server'] = 8001 + port_offset
                    container_ports['ai_server'] = 8001
                if 'mcp_manager' not in host_ports:
                    host_ports['mcp_manager'] = 5859 + port_offset
                    container_ports['mcp_manager'] = 5859
            else:
                # Use default port mapping with offset
                host_ports = {
                    'frontend': 3000 + port_offset,
                    'backend': 8000 + port_offset,
                    'ai_server': 8001 + port_offset,
                    'mcp_manager': 5859 + port_offset
                }
                
                container_ports = {
                    'frontend': 3000,
                    'backend': 8000,
                    'ai_server': 8001,
                    'mcp_manager': 5859
                }
            
            # Create temporary build directory
            self._log("Creating build directory...", progress_callback, 10)
            self.temp_dir = Path(tempfile.mkdtemp(prefix="fractalic_publish_"))
            
            # Copy and prepare source files
            self._log("Copying source files...", progress_callback, 20)
            source_path = Path(source_path)
            fractalic_dest = self._copy_fractalic_repo(source_path, self.temp_dir)
            ui_dest = self._copy_or_create_frontend(source_path, self.temp_dir, host_ports)
            self._copy_docker_config(source_path, self.temp_dir)
            
            # Stop existing container if it exists
            self._log("Stopping existing container...", progress_callback, 40)
            self._stop_existing_container(container_name)
            
            # Build Docker image
            self._log("Building Docker image...", progress_callback, 50)
            image_name = self._build_docker_image(self.temp_dir, container_name)
            
            if not image_name:
                return PublishResult(
                    success=False,
                    deployment_id=deployment_id,
                    message="Failed to build Docker image"
                )
            
            # Run container
            self._log("Starting container...", progress_callback, 70)
            if not self._run_container(image_name, container_name, host_ports, container_ports, port_offset):
                return PublishResult(
                    success=False,
                    deployment_id=deployment_id,
                    message="Failed to start container"
                )
            
            # Wait for services to be ready
            self._log("Waiting for services to start...", progress_callback, 90)
            time.sleep(10)
            services_status = self._check_services(host_ports)
            
            # Store deployment info
            self.active_deployments[deployment_id] = {
                'container_name': container_name,
                'host_ports': host_ports,
                'container_ports': container_ports,
                'image_name': image_name,
                'started_at': time.time(),
                'services_status': services_status
            }
            
            # Generate success message
            message = self._generate_success_message(container_name, host_ports, services_status)
            
            self._log("Deployment complete!", progress_callback, 100)
            
            return PublishResult(
                success=True,
                deployment_id=deployment_id,
                message=message,
                url=f"http://localhost:{host_ports['frontend']}"
            )
            
        except Exception as e:
            self._log(f"Deployment failed: {str(e)}", progress_callback, 0)
            return PublishResult(
                success=False,
                deployment_id=deployment_id,
                message=f"Deployment failed: {str(e)}"
            )
        finally:
            # Clean up temporary files
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
    
    def get_deployment_info(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get information about a deployment"""
        if deployment_id not in self.active_deployments:
            return None
            
        deployment = self.active_deployments[deployment_id]
        
        # Check if container is still running
        try:
            result = subprocess.run([
                'docker', 'inspect', '--format={{.State.Status}}', 
                deployment['container_name']
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                container_status = result.stdout.strip()
                if container_status == 'running':
                    status = DeploymentStatus.RUNNING
                elif container_status in ['exited', 'dead']:
                    status = DeploymentStatus.STOPPED
                else:
                    status = DeploymentStatus.UNKNOWN
            else:
                status = DeploymentStatus.NOT_FOUND
        except:
            status = DeploymentStatus.UNKNOWN
        
        return DeploymentInfo(
            deployment_id=deployment_id,
            status=status,
            url=f"http://localhost:{deployment['host_ports']['frontend']}",
            created_at=deployment['started_at'],
            metadata={
                'container_name': deployment['container_name'],
                'host_ports': deployment['host_ports'],
                'services_status': deployment['services_status']
            }
        )
    
    def list_deployments(self) -> List[DeploymentInfo]:
        """List all active deployments"""
        deployments = []
        for deployment_id in list(self.active_deployments.keys()):
            info = self.get_deployment_info(deployment_id)
            if info:
                deployments.append(info)
            else:
                # Clean up inactive deployments
                del self.active_deployments[deployment_id]
        return deployments
    
    def stop_deployment(self, deployment_id: str) -> bool:
        """Stop a running deployment"""
        if deployment_id not in self.active_deployments:
            return False
            
        container_name = self.active_deployments[deployment_id]['container_name']
        return self._stop_existing_container(container_name)
    
    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment completely"""
        if deployment_id not in self.active_deployments:
            return False
            
        container_name = self.active_deployments[deployment_id]['container_name']
        
        # Stop and remove container
        try:
            subprocess.run(['docker', 'stop', container_name], capture_output=True)
            subprocess.run(['docker', 'rm', container_name], capture_output=True)
            
            # Remove from active deployments
            del self.active_deployments[deployment_id]
            return True
        except:
            return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        """Get logs for a deployment"""
        if deployment_id not in self.active_deployments:
            return "Deployment not found"
            
        container_name = self.active_deployments[deployment_id]['container_name']
        
        try:
            result = subprocess.run([
                'docker', 'logs', '--tail', str(lines), container_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Failed to get logs: {result.stderr}"
        except Exception as e:
            return f"Error getting logs: {str(e)}"
    
    def _log(self, message: str, progress_callback=None, percentage: int = 0):
        """Log message with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        if progress_callback:
            progress_callback(message, percentage)
    
    def _find_fractalic_ui(self, source_path: Path) -> Optional[Path]:
        """Find fractalic-ui repository relative to source path"""
        possible_paths = [
            source_path.parent / "fractalic-ui" / "my-app",
            source_path.parent / "fractalic-ui",
            source_path / "fractalic-ui" / "my-app",
            source_path / "fractalic-ui"
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "package.json").exists():
                return path
                
        return None
    
    def _copy_fractalic_repo(self, source_path: Path, build_dir: Path) -> Path:
        """Copy Fractalic repository to build directory"""
        fractalic_dest = build_dir / "fractalic"
        
        # Exclude patterns for copying
        exclude_patterns = {
            '.git', '__pycache__', '*.pyc', '.pytest_cache',
            'venv', '.venv', 'node_modules', '.DS_Store',
            '*.log', 'logs/*', '.vscode', '.idea'
        }
        
        shutil.copytree(
            source_path,
            fractalic_dest,
            ignore=shutil.ignore_patterns(*exclude_patterns)
        )
        
        # Fix MCP manager to bind to all interfaces for Docker
        self._fix_mcp_manager_binding(fractalic_dest / "fractalic_mcp_manager.py")
        
        return fractalic_dest
    
    def _fix_mcp_manager_binding(self, mcp_manager_path: Path):
        """Fix MCP manager to bind to all interfaces for Docker deployment"""
        if not mcp_manager_path.exists():
            return
            
        with open(mcp_manager_path, 'r') as f:
            content = f.read()
        
        # Replace localhost binding with all interfaces binding
        content = content.replace(
            'site   = web.TCPSite(runner, "127.0.0.1", port)',
            'site   = web.TCPSite(runner, "0.0.0.0", port)'
        )
        
        content = content.replace(
            'log(f"API http://127.0.0.1:{port}  – Ctrl-C to quit")',
            'log(f"API http://0.0.0.0:{port}  – Ctrl-C to quit")'
        )
        
        with open(mcp_manager_path, 'w') as f:
            f.write(content)
    
    def _copy_or_create_frontend(self, source_path: Path, build_dir: Path, host_ports: Dict[str, int]) -> Path:
        """Copy fractalic-ui to build directory"""
        ui_source = self._find_fractalic_ui(source_path)
        if not ui_source:
            raise FileNotFoundError("fractalic-ui not found - this is required for deployment")
            
        ui_dest = build_dir / "fractalic-ui"
        shutil.copytree(
            ui_source,
            ui_dest,
            ignore=shutil.ignore_patterns('node_modules', '.git', '.DS_Store', '__pycache__')
        )
        
        # Fix frontend configuration for Docker deployment
        self._fix_frontend_config(ui_dest, host_ports)
        
        return ui_dest
    
    def _fix_frontend_config(self, ui_dest: Path, host_ports: Dict[str, int]):
        """Configure frontend for Docker deployment"""
        # Create .env.local with host-mapped API URLs
        env_local_path = ui_dest / ".env.local"
        with open(env_local_path, 'w') as f:
            f.write("# Docker container networking - browser accesses via host-mapped ports\n")
            f.write(f"NEXT_PUBLIC_API_BASE_URL=http://localhost:{host_ports['backend']}\n")
            f.write(f"NEXT_PUBLIC_AI_API_BASE_URL=http://localhost:{host_ports['ai_server']}\n")
            f.write(f"NEXT_PUBLIC_MCP_API_BASE_URL=http://localhost:{host_ports['mcp_manager']}\n")
        
        # Create runtime config.json
        config = {
            "api": {
                "backend": f"http://localhost:{host_ports['backend']}",
                "ai_server": f"http://localhost:{host_ports['ai_server']}",
                "mcp_manager": f"http://localhost:{host_ports['mcp_manager']}"
            },
            "deployment": {
                "type": "docker",
                "build_timestamp": time.time()
            },
            "paths": {
                "default_git_path": "/app/fractalic"
            }
        }
        
        public_dir = ui_dest / "public"
        public_dir.mkdir(exist_ok=True)
        
        config_file = public_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def _copy_docker_config(self, source_path: Path, build_dir: Path):
        """Copy Docker configuration files"""
        docker_src = source_path / "docker"
        if docker_src.exists():
            shutil.copytree(docker_src, build_dir / "docker")
        
        # Also copy supervisord.conf to the root of build directory
        supervisord_src = source_path / "docker" / "supervisord.conf"
        if supervisord_src.exists():
            shutil.copy2(supervisord_src, build_dir / "supervisord.conf")
    
    def _stop_existing_container(self, container_name: str) -> bool:
        """Stop and remove existing container"""
        try:
            # Stop container
            subprocess.run(['docker', 'stop', container_name], capture_output=True)
            # Remove container
            subprocess.run(['docker', 'rm', container_name], capture_output=True)
            return True
        except:
            return True  # Return True even if container doesn't exist
    
    def _build_docker_image(self, build_dir: Path, container_name: str) -> Optional[str]:
        """Build Docker image"""
        image_name = f"{container_name}-image"
        
        # Build command
        cmd = [
            "docker", "build",
            "-f", str(build_dir / "docker" / "Dockerfile"),
            "-t", image_name,
            str(build_dir)
        ]
        
        print(f"Building Docker image with command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Docker build successful!")
            return image_name
        else:
            print(f"Docker build failed with return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return None
    
    def _run_container(self, image_name: str, container_name: str, host_ports: Dict[str, int], 
                      container_ports: Dict[str, int], port_offset: int) -> bool:
        """Run Docker container"""
        # Build port mapping arguments
        port_args = []
        for service in host_ports.keys():
            host_port = host_ports[service]
            container_port = container_ports[service]
            port_args.extend(["-p", f"{host_port}:{container_port}"])
        
        # Map additional AI server ports
        for i in range(2, 5):  # 8002, 8003, 8004
            host_ai_port = 8000 + i + port_offset
            container_ai_port = 8000 + i
            port_args.extend(["-p", f"{host_ai_port}:{container_ai_port}"])
        
        cmd = [
            "docker", "run", "-d",
            "--name", container_name
        ] + port_args + [image_name]
        
        print(f"Running container with command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Container started successfully with ID: {result.stdout.strip()}")
            return True
        else:
            print(f"Container start failed with return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
    
    def _check_services(self, host_ports: Dict[str, int]) -> Dict[str, str]:
        """Check if services are available"""
        services_status = {}
        
        for service, host_port in host_ports.items():
            try:
                url = f"http://localhost:{host_port}"
                urllib.request.urlopen(url, timeout=5)
                services_status[service] = "✅ Available"
            except:
                services_status[service] = "⚠️ Starting"
                
        return services_status
    
    def _generate_success_message(self, container_name: str, host_ports: Dict[str, int], 
                                 services_status: Dict[str, str]) -> str:
        """Generate success message with service details"""
        message = "🎉 Docker deployment completed successfully!\n\n"
        message += "📋 Services Summary:\n"
        
        for service, status in services_status.items():
            service_name = service.replace('_', ' ').title()
            host_port = host_ports[service]
            message += f"   • {service_name}: http://localhost:{host_port} - {status}\n"
        
        message += f"\n🐳 Container: {container_name}\n"
        message += f"📊 Frontend: http://localhost:{host_ports['frontend']}\n"
        message += f"⚙️  Backend API: http://localhost:{host_ports['backend']}\n"
        message += f"🤖 AI Server: http://localhost:{host_ports['ai_server']}\n"
        
        return message
    
    def generate_deploy_url(self, config: DeploymentConfig) -> str:
        """Generate deployment URL for Local Docker"""
        # For local Docker, we'll create a simple install script
        base_url = "https://raw.githubusercontent.com/fractalic-ai/fractalic/main"
        script_url = f"{base_url}/deploy/docker-deploy.sh"
        
        # Create URL with parameters
        params = []
        if config.container_name != "fractalic-app":
            params.append(f"name={config.container_name}")
        if hasattr(config, 'port_offset') and config.port_offset != 0:
            params.append(f"port_offset={config.port_offset}")
        
        param_string = "&".join(params)
        if param_string:
            return f"{script_url}?{param_string}"
        return script_url


# Make sure the plugin class is available for discovery
__all__ = ['LocalDockerPlugin']
