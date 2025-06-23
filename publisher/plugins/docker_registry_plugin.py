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

from ..base_plugin import BasePlugin
from ..models import PublishRequest, PublishResponse, DeploymentStatus


class DockerRegistryPlugin(BasePlugin):
    """Plugin for deploying to pre-built Docker registry images"""
    
    plugin_name = "docker-registry"
    
    def __init__(self):
        super().__init__()
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
            "user_scripts": "/fractalic/user-scripts",
            "user_config": "/fractalic/user-config",
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
        for service, port in config["ports"].items():
            host_port = self._find_available_port(port)
            cmd.extend(["-p", f"{host_port}:{port}"])
            
        # Add volume mounts
        temp_path = Path(temp_dir)
        scripts_path = temp_path / "scripts"
        config_path = temp_path / "config"
        
        cmd.extend([
            "-v", f"{scripts_path}:{config['mount_paths']['user_scripts']}/{config['script_name']}:ro",
            "-v", f"{config_path}:{config['mount_paths']['user_config']}:ro",
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
        
    def _find_available_port(self, preferred_port: int) -> int:
        """Find an available port, starting with the preferred one"""
        import socket
        
        for port in range(preferred_port, preferred_port + 100):
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
                container_id = self._start_container(config, temp_dir.name)
                
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
