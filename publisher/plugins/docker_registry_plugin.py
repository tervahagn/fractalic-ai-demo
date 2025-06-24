"""
Docker Registry Plugin for Fractalic Publisher
Deploys user scripts using pre-built Docker images from registry
"""

import os
import json
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..base_plugin import BasePublishPlugin
from ..models import PublishRequest, PublishResponse, DeploymentStatus, PluginInfo, DeploymentInfo, PluginInfo, PluginCapability


class DockerRegistryPlugin(BasePublishPlugin):
    """Plugin for deploying to pre-built Docker registry images"""
    
    plugin_name = "docker-registry"
    
    def __init__(self):
        super().__init__()
        import logging
        self.logger = logging.getLogger(__name__)
        self.default_registry = "ghcr.io/fractalic-ai/fractalic"
        self.default_ports = {
            "frontend": 3000,
            "backend": 8000,
            "ai_server": 8001,
            "mcp_manager": 5859
        }
        
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize plugin configuration"""
        validated = {}
        
        # Required fields
        validated["script_name"] = config.get("script_name", "").strip()
        if not validated["script_name"]:
            raise ValueError("script_name is required")
            
        validated["script_folder"] = config.get("script_folder", "").strip()
        if not validated["script_folder"]:
            raise ValueError("script_folder is required")
            
        # Optional fields with defaults
        validated["container_name"] = config.get("container_name", f"fractalic-{validated['script_name']}")
        validated["registry_image"] = config.get("registry_image", f"{self.default_registry}:latest")
        validated["platform"] = config.get("platform", self._detect_platform())
        
        # Port mappings
        validated["ports"] = {**self.default_ports, **config.get("ports", {})}
        
        # File handling
        validated["include_files"] = config.get("include_files", ["*"])
        validated["exclude_patterns"] = config.get("exclude_patterns", [
            ".git", ".gitignore", "__pycache__", "*.pyc", ".DS_Store",
            "node_modules", ".next", ".vscode", "*.log"
        ])
        
        # Configuration files
        validated["config_files"] = config.get("config_files", [
            "settings.toml", "mcp_servers.json", ".env", "requirements.txt"
        ])
        
        # Environment variables
        validated["env_vars"] = config.get("env_vars", {})
        
        # Mount paths
        validated["mount_paths"] = config.get("mount_paths", {
            "user_scripts": "/payload",
            "logs": "/fractalic/logs"
        })
        
        return validated
        
    def _detect_platform(self) -> str:
        """Auto-detect the target platform"""
        machine = platform.machine().lower()
        if machine in ['arm64', 'aarch64']:
            return "linux/arm64"
        elif machine in ['x86_64', 'amd64']:
            return "linux/amd64"
        else:
            # Default to amd64 for unknown architectures
            return "linux/amd64"
            
    def _run_command(self, cmd: List[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\nError: {e.stderr}")
            
    def _pull_base_image(self, config: Dict[str, Any]) -> None:
        """Pull the pre-built base image from registry"""
        image = config["registry_image"]
        platform = config["platform"]
        
        self.logger.info(f"Pulling base image: {image} ({platform})")
        
        # Pull the image for the specific platform
        cmd = ["docker", "pull", "--platform", platform, image]
        self._run_command(cmd)
        
        self.logger.info(f"Successfully pulled {image}")
        
    def _prepare_user_files(self, config: Dict[str, Any]) -> tempfile.TemporaryDirectory:
        """Prepare user files for copying to container"""
        script_folder = Path(config["script_folder"]).resolve()
        if not script_folder.exists():
            raise FileNotFoundError(f"Script folder not found: {script_folder}")
            
        # Create temporary directory for prepared files
        temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(temp_dir.name)
        
        # Create subdirectories
        scripts_dir = temp_path / "scripts"
        config_dir = temp_path / "config"
        scripts_dir.mkdir()
        config_dir.mkdir()
        
        # Copy script files (excluding patterns)
        self._copy_filtered_files(script_folder, scripts_dir, config["exclude_patterns"])
        
        # Copy configuration files
        self._copy_config_files(script_folder, config_dir, config["config_files"])
        
        return temp_dir
        
    def _copy_filtered_files(self, src_dir: Path, dst_dir: Path, exclude_patterns: List[str]) -> None:
        """Copy files from source to destination, excluding patterns"""
        import fnmatch
        
        for root, dirs, files in os.walk(src_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in exclude_patterns)]
            
            rel_root = Path(root).relative_to(src_dir)
            dst_root = dst_dir / rel_root
            dst_root.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                # Skip files matching exclude patterns
                if any(fnmatch.fnmatch(file, pattern) for pattern in exclude_patterns):
                    continue
                    
                src_file = Path(root) / file
                dst_file = dst_root / file
                shutil.copy2(src_file, dst_file)
                
    def _copy_config_files(self, src_dir: Path, dst_dir: Path, config_files: List[str]) -> None:
        """Copy configuration files if they exist"""
        for config_file in config_files:
            src_file = src_dir / config_file
            if src_file.exists():
                dst_file = dst_dir / config_file
                shutil.copy2(src_file, dst_file)
                self.logger.info(f"Copied config file: {config_file}")
                
    def _start_container(self, config: Dict[str, Any], temp_dir: str) -> str:
        """Start the Docker container with user files mounted"""
        container_name = config["container_name"]
        image = config["registry_image"]
        platform = config["platform"]
        
        # Stop and remove existing container if it exists
        self._cleanup_container(container_name)
        
        # Build docker run command
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--platform", platform
        ]
        
        # Add port mappings
        used_ports = set()
        for service, port in config["ports"].items():
            host_port = self._find_available_port(port, used_ports)
            used_ports.add(host_port)
            cmd.extend(["-p", f"{host_port}:{port}"])
            
        # Add volume mounts (logs only - user scripts will be copied)
        cmd.extend([
            "-v", f"{os.getcwd()}/logs:/fractalic/logs"
        ])
        
        # Add environment variables
        for key, value in config["env_vars"].items():
            cmd.extend(["-e", f"{key}={value}"])
            
        # Add the image
        cmd.append(image)
        
        # Run the container
        result = self._run_command(cmd)
        container_id = result.stdout.strip()
        
        self.logger.info(f"Started container: {container_name} ({container_id[:12]})")
        return container_id
        
    def _find_available_port(self, preferred_port: int, used_ports: set = None) -> int:
        """Find an available port, starting with the preferred one"""
        import socket
        
        if used_ports is None:
            used_ports = set()
        
        for port in range(preferred_port, preferred_port + 100):
            if port in used_ports:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"No available ports found near {preferred_port}")
        
    def _cleanup_container(self, container_name: str) -> None:
        """Stop and remove existing container"""
        try:
            # Stop container
            self._run_command(["docker", "stop", container_name])
            self.logger.info(f"Stopped container: {container_name}")
        except RuntimeError:
            pass  # Container might not exist
            
        try:
            # Remove container
            self._run_command(["docker", "rm", container_name])
            self.logger.info(f"Removed container: {container_name}")
        except RuntimeError:
            pass  # Container might not exist
            
    def _health_check(self, config: Dict[str, Any]) -> Dict[str, bool]:
        """Check if all services in the container are healthy"""
        import time
        import requests
        
        container_name = config["container_name"]
        health_status = {}
        
        # Wait for container to start
        time.sleep(10)
        
        # Get container port mappings
        try:
            result = self._run_command([
                "docker", "port", container_name
            ])
            port_mappings = self._parse_port_mappings(result.stdout)
        except RuntimeError:
            return {"container": False}
            
        # Check each service
        services_to_check = {
            "frontend": 3000,
            "backend": 8000,
            "ai_server": 8001,
            "mcp_manager": 5859
        }
        
        for service, container_port in services_to_check.items():
            host_port = port_mappings.get(container_port)
            if host_port:
                try:
                    response = requests.get(f"http://localhost:{host_port}", timeout=5)
                    health_status[service] = response.status_code in [200, 404]  # 404 is OK for some endpoints
                except:
                    health_status[service] = False
            else:
                health_status[service] = False
                
        return health_status
        
    def _parse_port_mappings(self, port_output: str) -> Dict[int, int]:
        """Parse docker port command output"""
        mappings = {}
        for line in port_output.strip().split('\n'):
            if '->' in line:
                # Format: "3000/tcp -> 0.0.0.0:32768"
                parts = line.split(' -> ')
                if len(parts) == 2:
                    container_port = int(parts[0].split('/')[0])
                    host_port = int(parts[1].split(':')[-1])
                    mappings[container_port] = host_port
        return mappings
        
    def publish(self, request: PublishRequest) -> PublishResponse:
        """Main publish method"""
        try:
            self.logger.info(f"Starting Docker registry deployment: {request.config.get('script_name')}")
            
            # Validate configuration
            config = self.validate_config(request.config)
            
            # Pull base image
            self._pull_base_image(config)
            
            # Prepare user files
            with self._prepare_user_files(config) as temp_dir:
                # Start container
                container_id = self._start_container(config, temp_dir)
                
                # Copy files into container (cloud-ready approach)
                self._copy_files_to_container(config["container_name"], temp_dir, config)
                
                # Health check
                health_status = self._health_check(config)
                
                # Get port mappings for response
                result = self._run_command(["docker", "port", config["container_name"]])
                port_mappings = self._parse_port_mappings(result.stdout)
                
                # Build URLs
                urls = {}
                service_ports = {
                    "frontend": 3000,
                    "backend": 8000,
                    "ai_server": 8001,
                    "mcp_manager": 5859
                }
                
                for service, container_port in service_ports.items():
                    host_port = port_mappings.get(container_port)
                    if host_port:
                        urls[service] = f"http://localhost:{host_port}"
                
                success = all(health_status.values())
                
                return PublishResponse(
                    success=success,
                    message=f"Deployment {'completed successfully' if success else 'completed with some issues'}",
                    endpoint_url=urls.get("frontend", ""),
                    deployment_id=container_id[:12],
                    metadata={
                        "container_name": config["container_name"],
                        "container_id": container_id,
                        "urls": urls,
                        "health_status": health_status,
                        "platform": config["platform"],
                        "deployed_at": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Deployment failed: {str(e)}", exc_info=True)
            return PublishResponse(
                success=False,
                message=f"Deployment failed: {str(e)}",
                endpoint_url="",
                deployment_id="",
                metadata={"error": str(e)}
            )
            
    def get_status(self, deployment_id: str) -> DeploymentStatus:
        """Get deployment status"""
        try:
            # Get container info
            result = self._run_command([
                "docker", "inspect", deployment_id, "--format", "{{.State.Status}}"
            ])
            container_status = result.stdout.strip()
            
            is_running = container_status == "running"
            
            return DeploymentStatus(
                deployment_id=deployment_id,
                status="running" if is_running else container_status,
                is_healthy=is_running,
                last_updated=datetime.now().isoformat()
            )
            
        except RuntimeError:
            return DeploymentStatus(
                deployment_id=deployment_id,
                status="not_found",
                is_healthy=False,
                last_updated=datetime.now().isoformat()
            )
            
    def cleanup(self, deployment_id: str) -> bool:
        """Clean up deployment"""
        try:
            self._cleanup_container(deployment_id)
            return True
        except Exception as e:
            self.logger.error(f"Cleanup failed for {deployment_id}: {str(e)}")
            return False
        
    def get_info(self) -> PluginInfo:
        """Get plugin information"""
        return PluginInfo(
            name=self.plugin_name,
            display_name="Docker Registry",
            description="Deploy using pre-built Docker images from registry",
            version="1.0.0",
            homepage_url="https://github.com/fractalic-ai/fractalic",
            documentation_url="https://github.com/fractalic-ai/fractalic/docs",
            capabilities=[PluginCapability.INSTANT_PREVIEW],
            pricing_info="Free",
            setup_difficulty="easy",
            deploy_time_estimate="< 1 min",
            free_tier_limits="Unlimited local deployments"
        )

    def get_deployment_info(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get information about a specific deployment"""
        from ..models import DeploymentInfo
        # For now, return basic info based on container status
        try:
            cmd = ["docker", "inspect", deployment_id]
            result = self._run_command(cmd)
            if result.returncode == 0:
                return DeploymentInfo(
                    deployment_id=deployment_id,
                    status=self.get_status(deployment_id),
                    plugin_name=self.plugin_name,
                    container_name=deployment_id
                )
        except Exception:
            pass
        return None

    def list_deployments(self) -> List[DeploymentInfo]:
        """List all deployments managed by this plugin"""
        from ..models import DeploymentInfo
        deployments = []
        try:
            # List containers with our label/tag
            cmd = ["docker", "ps", "-a", "--filter", "label=fractalic-deploy", "--format", "{{.Names}}"]
            result = self._run_command(cmd)
            if result.returncode == 0:
                container_names = result.stdout.strip().split('\n')
                for name in container_names:
                    if name:
                        info = self.get_deployment_info(name)
                        if info:
                            deployments.append(info)
        except Exception:
            pass
        return deployments

    def stop_deployment(self, deployment_id: str) -> bool:
        """Stop a deployment"""
        try:
            cmd = ["docker", "stop", deployment_id]
            result = self._run_command(cmd)
            return result.returncode == 0
        except Exception:
            return False

    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment"""
        try:
            # Stop first, then remove
            self.stop_deployment(deployment_id)
            cmd = ["docker", "rm", deployment_id]
            result = self._run_command(cmd)
            return result.returncode == 0
        except Exception:
            return False

    def get_logs(self, deployment_id: str, lines: int = 100) -> Optional[str]:
        """Get deployment logs"""
        try:
            cmd = ["docker", "logs", "--tail", str(lines), deployment_id]
            result = self._run_command(cmd)
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
        return None

    def _copy_files_to_container(self, container_name: str, temp_dir: str, config: Dict[str, Any]) -> None:
        """Copy prepared files directly into the running container"""
        temp_path = Path(temp_dir)
        scripts_path = temp_path / "scripts"
        config_path = temp_path / "config"
        
        # Ensure payload directory exists in container (run as root)
        payload_base = config['mount_paths']['user_scripts']
        payload_path = f"{payload_base}/{config['script_name']}"
        
        # Create the base payload directory as root if it doesn't exist
        self._run_command([
            "docker", "exec", "--user", "root", container_name, 
            "mkdir", "-p", payload_base
        ])
        
        # Create the script-specific directory as root
        self._run_command([
            "docker", "exec", "--user", "root", container_name, 
            "mkdir", "-p", payload_path
        ])
        
        # Copy all files from scripts directory to container
        if scripts_path.exists():
            for item in scripts_path.iterdir():
                if item.is_file():
                    # Copy individual files
                    self._run_command([
                        "docker", "cp", str(item), 
                        f"{container_name}:{payload_path}/{item.name}"
                    ])
                    self.logger.info(f"Copied {item.name} to container {payload_path}")
                elif item.is_dir():
                    # Copy directories recursively
                    self._run_command([
                        "docker", "cp", str(item), 
                        f"{container_name}:{payload_path}/"
                    ])
                    self.logger.info(f"Copied directory {item.name} to container {payload_path}")

        # Copy configuration files from main directory to /fractalic
        main_config_files = ["mcp_servers.json", "settings.toml"]
        current_dir = Path.cwd()
        
        for config_file in main_config_files:
            config_file_path = current_dir / config_file
            if config_file_path.exists():
                self._run_command([
                    "docker", "cp", str(config_file_path), 
                    f"{container_name}:/fractalic/{config_file}"
                ])
                self.logger.info(f"Copied main config file {config_file} to /fractalic/")
                
                # For settings.toml, also copy to root directory where backend expects it
                if config_file == "settings.toml":
                    self._run_command([
                        "docker", "cp", str(config_file_path), 
                        f"{container_name}:/{config_file}"
                    ])
                    self.logger.info(f"Copied {config_file} to root directory for backend compatibility")
        
        # Also copy configuration files from temp directory if they exist
        if config_path.exists():
            for config_file in config_path.iterdir():
                if config_file.is_file():
                    self._run_command([
                        "docker", "cp", str(config_file), 
                        f"{container_name}:/fractalic/{config_file.name}"
                    ])
                    self.logger.info(f"Copied config file {config_file.name} to /fractalic/")
        
        # Create symlink from /fractalic/payload to /payload so UI can see deployed scripts
        self._run_command([
            "docker", "exec", "--user", "root", container_name,
            "ln", "-sf", "/payload", "/fractalic/payload"
        ])
        self.logger.info("Created symlink from /fractalic/payload to /payload for UI visibility")

        # Set proper ownership for copied files (run as root)
        self._run_command([
            "docker", "exec", "--user", "root", container_name,
            "chown", "-R", "appuser:appuser", payload_base
        ])
        
        # Set proper ownership for config files if they exist (run as root)
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic/mcp_servers.json"
            ])
        except RuntimeError:
            pass  # File might not exist
            
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic/settings.toml"
            ])
        except RuntimeError:
            pass  # File might not exist
            
        # Also fix ownership for root settings.toml file
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/settings.toml"
            ])
        except RuntimeError:
            pass  # File might not exist
        
        # Fix the frontend config.json to have correct API endpoints
        self._fix_frontend_config(container_name, config)
        
        # Fix the Next.js config for proper API rewrites
        self._fix_nextjs_config(container_name, config)
        
        self.logger.info(f"Successfully copied all files to {payload_path} and config files to /fractalic/")
        
    def _fix_frontend_config(self, container_name: str, config: Dict[str, Any]) -> None:
        """Fix the frontend config.json to have correct API endpoints for single-container deployment"""
        
        # Create the correct config for single-container deployment
        # Use relative paths that will go through Next.js rewrites
        correct_config = {
            "api": {
                "backend": "",  # Relative path - will use Next.js rewrites
                "ai_server": "/ai",  # Will rewrite to http://localhost:8001
                "mcp_manager": "/mcp"  # Will rewrite to http://localhost:5859 - this is the key fix!
            },
            "container": {
                "internal_ports": {
                    "frontend": 3000,
                    "backend": 8000,
                    "ai_server": 8001,
                    "mcp_manager": 5859
                },
                "host_ports": config.get("ports", self.default_ports)
            },
            "deployment": {
                "type": "docker",
                "container_name": container_name,
                "build_timestamp": datetime.now().timestamp()
            },
            "paths": {
                "default_git_path": "/payload"  # Fix: point to our payload directory
            }
        }
        
        # Write the corrected config to a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(correct_config, tmp_file, indent=2)
            tmp_config_path = tmp_file.name
        
        try:
            # Copy the corrected config.json to the container
            self._run_command([
                "docker", "cp", tmp_config_path, 
                f"{container_name}:/fractalic-ui/public/config.json"
            ])
            
            # Fix ownership and permissions so the frontend can serve it
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic-ui/public/config.json"
            ])
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chmod", "644", "/fractalic-ui/public/config.json"
            ])
            
            self.logger.info("Fixed frontend config.json with correct API endpoints and permissions")
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_config_path)
            except OSError:
                pass

    def _fix_nextjs_config(self, container_name: str, config: Dict[str, Any]) -> None:
        """Fix the Next.js config to include proper API rewrites for single-container deployment"""
        
        # Create the correct Next.js config with rewrites for all API endpoints
        nextjs_config = '''/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  trailingSlash: false,
  
  // Docker deployment: Use rewrites to proxy API calls to internal services
  async rewrites() {
    return [
      // Backend API rewrites
      {
        source: '/list_directory',
        destination: 'http://localhost:8000/list_directory',
      },
      {
        source: '/branches_and_commits',
        destination: 'http://localhost:8000/branches_and_commits',
      },
      {
        source: '/get_file_content_disk',
        destination: 'http://localhost:8000/get_file_content_disk',
      },
      {
        source: '/create_file',
        destination: 'http://localhost:8000/create_file',
      },
      {
        source: '/create_folder',
        destination: 'http://localhost:8000/create_folder',
      },
      {
        source: '/get_file_content',
        destination: 'http://localhost:8000/get_file_content',
      },
      {
        source: '/save_file',
        destination: 'http://localhost:8000/save_file',
      },
      {
        source: '/delete_item',
        destination: 'http://localhost:8000/delete_item',
      },
      {
        source: '/rename_item',
        destination: 'http://localhost:8000/rename_item',
      },
      {
        source: '/load_settings',
        destination: 'http://localhost:8000/load_settings',
      },
      {
        source: '/save_settings',
        destination: 'http://localhost:8000/save_settings',
      },
      // MCP Manager API rewrites - this is the key fix!
      {
        source: '/mcp/:path*',
        destination: 'http://localhost:5859/:path*',
      },
      // AI Server API rewrites
      {
        source: '/ai/:path*',
        destination: 'http://localhost:8001/:path*',
      },
    ];
  },
  
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
'''
        
        # Write the corrected config to a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', delete=False) as tmp_file:
            tmp_file.write(nextjs_config)
            tmp_config_path = tmp_file.name
        
        try:
            # Copy the corrected next.config.mjs to the container
            self._run_command([
                "docker", "cp", tmp_config_path, 
                f"{container_name}:/fractalic-ui/next.config.mjs"
            ])
            
            # Fix ownership and permissions
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic-ui/next.config.mjs"
            ])
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chmod", "644", "/fractalic-ui/next.config.mjs"
            ])
            
            self.logger.info("Fixed Next.js config with API rewrites for proper port routing")
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_config_path)
            except OSError:
                pass
