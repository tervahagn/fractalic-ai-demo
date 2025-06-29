"""
Docker Registry Plugin for Fractalic Publisher
Deploys user scripts using pre-built Docker images from registry
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root to path for utils import
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import publishing utilities
sys.path.insert(0, os.path.dirname(project_root))  # Add parent to import publish_docker
from publish_docker import find_available_ai_server_port, generate_ai_server_info
from ..base_plugin import BasePublishPlugin
from ..models import PublishRequest, PublishResponse, DeploymentStatus, PluginInfo, DeploymentInfo, PluginInfo, PluginCapability, DeploymentConfig, PublishResult, ProgressCallback


class DockerRegistryPlugin(BasePublishPlugin):
    """Plugin for deploying to pre-built Docker registry images"""
    
    plugin_name = "docker-registry"
    
    def __init__(self):
        super().__init__()
        import logging
        self.logger = logging.getLogger(__name__)
        self.default_registry = "ghcr.io/fractalic-ai/fractalic"
        self.default_ports = {
            "backend": 8000,  # Internal only
            "ai_server": 8001,  # External - main service
            "mcp_manager": 5859  # Internal only
        }
        
    def validate_config(self, config: DeploymentConfig) -> tuple[bool, Optional[str]]:
        """
        Validate deployment configuration
        Returns: (is_valid, error_message)
        """
        try:
            # Convert DeploymentConfig to dict for internal processing
            config_dict = {
                "script_name": getattr(config, 'script_name', ''),
                "script_folder": getattr(config, 'script_folder', ''),
                "container_name": getattr(config, 'container_name', ''),
                "registry_image": getattr(config, 'registry_image', ''),
                "platform": getattr(config, 'platform', ''),
                "ports": getattr(config, 'port_mapping', {}),
                "include_files": getattr(config, 'include_files', ["*"]),
                "exclude_patterns": getattr(config, 'exclude_patterns', [
                    ".git", ".gitignore", "__pycache__", "*.pyc", ".DS_Store",
                    "node_modules", ".next", ".vscode", "*.log"
                ])
            }
            
            # For CLI deployments, we need to prompt for missing required fields
            if not config_dict["script_name"]:
                return False, "script_name is required. Please provide --script-name parameter."
                
            if not config_dict["script_folder"]:
                return False, "script_folder is required. Please provide --script-folder parameter."
            
            return True, None
            
        except Exception as e:
            return False, f"Configuration validation error: {str(e)}"
        
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
    
    def _run_command_with_output(self, cmd: List[str], cwd: Optional[str] = None, progress_callback=None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Run a shell command with real-time output display and optional timeout"""
        try:
            if progress_callback:
                progress_callback(f"🔧 Running: {' '.join(cmd)}", 0)
            
            print(f"📝 Executing: {' '.join(cmd)}")
            
            # Run with real-time output
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            import time
            start_time = time.time()
            output_lines = []
            
            while True:
                # Check for timeout only if specified
                if timeout is not None:
                    current_time = time.time()
                    if current_time - start_time > timeout:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise RuntimeError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
                
                # Read output
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                    
                if output:
                    output_lines.append(output.strip())
                    print(f"   {output.strip()}")
                    
                    # For docker pull, show progress updates
                    if 'docker pull' in ' '.join(cmd) and ('Downloading' in output or 'Extracting' in output or 'Pull complete' in output):
                        if progress_callback:
                            elapsed = time.time() - start_time
                            progress_callback(f"📥 Downloading layers... ({elapsed:.0f}s)", 20)
                
                # Sleep briefly to prevent busy waiting
                time.sleep(0.1)
            
            return_code = process.poll()
            if return_code != 0:
                raise RuntimeError(f"Command failed with return code {return_code}: {' '.join(cmd)}")
                
            # Create a result object similar to subprocess.run
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=return_code,
                stdout='\n'.join(output_lines),
                stderr=''
            )
            return result
            
        except Exception as e:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\nError: {str(e)}")
            
    def _pull_base_image(self, config: Dict[str, Any], progress_callback=None) -> None:
        """Pull the pre-built base image from registry"""
        image = config["registry_image"]
        platform = config["platform"]
        
        if progress_callback:
            progress_callback("🚀 Starting deployment", 10)
            progress_callback(f" Pulling base image: {image} ({platform})", 15)
        
        print(f"\n🐳 Checking/pulling Docker image: {image}")
        print(f"🏗️  Platform: {platform}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        self.logger.info(f"Pulling base image: {image} ({platform})")
        
        # Docker pull will automatically check if image exists and only download if needed
        cmd = ["docker", "pull", "--platform", platform, image]
        self._run_command_with_output(cmd, progress_callback=progress_callback, timeout=None)
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if progress_callback:
            progress_callback(f"✅ Image ready: {image}", 30)
        
        print(f"✅ Image ready: {image}\n")
        self.logger.info(f"Image ready: {image}")
        
    def _prepare_user_files(self, config: Dict[str, Any], progress_callback=None) -> tempfile.TemporaryDirectory:
        """Prepare user files for copying to container"""
        if progress_callback:
            progress_callback("📁 Preparing user files", 35)
            
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
        
        if progress_callback:
            progress_callback("🔄 Copying script files", 40)
        
        # Copy script files (excluding patterns)
        self._copy_filtered_files(script_folder, scripts_dir, config["exclude_patterns"])
        
        # Copy configuration files
        self._copy_config_files(script_folder, config_dir, config["config_files"])
        
        if progress_callback:
            progress_callback("✅ User files prepared", 45)
        
        return temp_dir
        
    def _find_main_script_file(self, script_name: str, script_folder: str) -> str:
        """Find the main script file with proper extension"""
        script_dir = Path(script_folder)
        possible_extensions = ['.md', '.py', '.sh', '.txt', '']
        
        # Look for script_name with various extensions
        for ext in possible_extensions:
            script_file = script_dir / f"{script_name}{ext}"
            if script_file.exists():
                return f"/payload/{script_name}/{script_name}{ext}"
        
        # If no exact match, look for any file that starts with script_name
        for file in script_dir.glob(f"{script_name}.*"):
            if file.is_file():
                return f"/payload/{script_name}/{file.name}"
        
        # Default fallback
        return f"/payload/{script_name}/{script_name}"

    def _copy_filtered_files(self, src_dir: Path, dst_dir: Path, exclude_patterns: List[str]) -> None:
        """Copy files from source to destination, excluding patterns and problematic files"""
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
                
                # Skip problematic files that can't be copied (sockets, devices, etc.)
                try:
                    if src_file.is_socket() or src_file.is_fifo() or src_file.is_block_device() or src_file.is_char_device():
                        continue
                    if not src_file.is_file():
                        continue
                    shutil.copy2(src_file, dst_file)
                except (OSError, PermissionError) as e:
                    # Skip files that can't be read or copied
                    self.logger.warning(f"Skipping file {src_file}: {e}")
                    continue
                
    def _copy_config_files(self, src_dir: Path, dst_dir: Path, config_files: List[str]) -> None:
        """Copy configuration files if they exist"""
        for config_file in config_files:
            src_file = src_dir / config_file
            if src_file.exists():
                dst_file = dst_dir / config_file
                shutil.copy2(src_file, dst_file)
                self.logger.info(f"Copied config file: {config_file}")
                
    def _start_container(self, config: Dict[str, Any], temp_dir: str, progress_callback=None) -> str:
        """Start the Docker container with automatic port detection"""
        container_name = config["container_name"]
        image = config["registry_image"]
        platform = config["platform"]
        
        if progress_callback:
            progress_callback(f"🐳 Starting container: {container_name}", 50)
        
        # Stop and remove existing container if it exists
        self._cleanup_container(container_name)
        
        # Find available AI server port (main external service)
        ai_port, conflict_info = find_available_ai_server_port(config["ports"]["ai_server"])
        
        if conflict_info:
            if progress_callback:
                if conflict_info.get('type') == 'docker_container':
                    port = conflict_info.get('port', 'unknown')
                    container = conflict_info.get('container', 'unknown')
                    progress_callback(f"⚠️ Port {port} in use by container {container}, using port {ai_port}", 52)
                elif conflict_info.get('type') == 'port_in_use':
                    port = conflict_info.get('port', 'unknown')
                    progress_callback(f"⚠️ Port {port} in use, using port {ai_port}", 52)
                elif conflict_info.get('type') == 'preferred_port_unavailable':
                    preferred_port = conflict_info.get('preferred_port', 'unknown')
                    progress_callback(f"⚠️ Preferred port {preferred_port} unavailable, using port {ai_port}", 52)
                else:
                    progress_callback(f"⚠️ Port conflict detected, using port {ai_port}", 52)
        
        # Store the actual ports used
        config["actual_ports"] = {
            "ai_server": ai_port,
            "backend": 8000,  # Internal only, no mapping needed
            "mcp_manager": 5859  # Internal only, no mapping needed
        }
        
        # Build docker run command
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--platform", platform
        ]
        
        # Add port mappings - only expose AI server externally
        cmd.extend(["-p", f"{ai_port}:8001"])  # AI server (main service)
        
        port_mappings = [f"AI Server: {ai_port}→8001 (external)", "Backend: 8000 (internal)", "MCP Manager: 5859 (internal)"]
            
        if progress_callback:
            progress_callback(f"🔌 Port mappings: {', '.join(port_mappings)}", 55)
            
        print(f"\n🐳 Starting Fractalic container:")
        print(f"📦 Container name: {container_name}")
        print(f"🏗️  Image: {image}")
        print(f"🔌 AI Server port: {ai_port} → 8001")
        print(f"🔌 Backend (internal): 8000")
        print(f"🔌 MCP Manager (internal): 5859")
        
        # Add volume mounts (logs only - user scripts will be copied)
        cmd.extend([
            "-v", f"{os.getcwd()}/logs:/fractalic/logs"
        ])
        
        # Add environment variables
        for key, value in config["env_vars"].items():
            cmd.extend(["-e", f"{key}={value}"])
            
        # Add the image
        cmd.append(image)
        
        if progress_callback:
            progress_callback("🚀 Launching container", 60)
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Run the container with output
        result = self._run_command_with_output(cmd, progress_callback=progress_callback)
        container_id = result.stdout.strip().split('\n')[-1]  # Get the last line which should be the container ID
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if progress_callback:
            progress_callback(f"✅ Container started: {container_id[:12]}", 65)
        
        print(f"✅ Container started: {container_id[:12]}")
        print(f"🔍 Container logs: docker logs {container_name}")
        print(f"🛑 Stop container: docker stop {container_name}\n")
        
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
            
    def _health_check(self, config: Dict[str, Any], progress_callback=None) -> Dict[str, bool]:
        """Check if AI server and backend services are healthy (production mode)"""
        import time
        import requests
        
        container_name = config["container_name"]
        health_status = {}
        
        if progress_callback:
            progress_callback("🔍 Performing health checks", 90)
        
        print(f"\n🔍 Performing health checks for container: {container_name}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Wait for container to start
        print("⏳ Waiting 10 seconds for services to initialize...")
        time.sleep(10)
        
        # Check AI server (external service)
        ai_port = config["actual_ports"]["ai_server"]
        if progress_callback:
            progress_callback(f"🩺 Checking AI server on port {ai_port}", 92)
            
        print(f"\n🩺 Testing AI Server on port {ai_port}:")
        print(f"   URL: http://localhost:{ai_port}/health")
        
        try:
            response = requests.get(f"http://localhost:{ai_port}/health", timeout=10)
            health_status["ai_server"] = response.status_code == 200
            if health_status["ai_server"]:
                print(f"   ✅ AI server is healthy (HTTP {response.status_code})")
                if progress_callback:
                    progress_callback(f"✅ AI server is healthy (port {ai_port})", 94)
            else:
                print(f"   ❌ AI server unhealthy (HTTP {response.status_code})")
                if progress_callback:
                    progress_callback(f"❌ AI server unhealthy (HTTP {response.status_code})", 94)
        except Exception as e:
            health_status["ai_server"] = False
            print(f"   ❌ AI server connection failed: {str(e)}")
            if progress_callback:
                progress_callback(f"❌ AI server connection failed: {str(e)}", 94)
        
        # Check backend (internal service via container exec) - only for full images
        is_production = "production" in config.get("registry_image", "")
        if not is_production:
            if progress_callback:
                progress_callback("🩺 Checking backend (internal)", 96)
                
            print(f"\n🩺 Testing Backend (internal service):")
            print(f"   URL: http://localhost:8000/health (inside container)")
            
            try:
                result = self._run_command([
                    "docker", "exec", container_name, "curl", "-f", "http://localhost:8000/health"
                ])
                health_status["backend"] = True
                print(f"   ✅ Backend is healthy (internal port 8000)")
                if progress_callback:
                    progress_callback("✅ Backend is healthy (internal port 8000)", 98)
            except RuntimeError as e:
                health_status["backend"] = False
                print(f"   ❌ Backend health check failed: {str(e)}")
                if progress_callback:
                    progress_callback(f"❌ Backend health check failed: {str(e)}", 98)
        else:
            # For production, check MCP manager instead of backend
            if progress_callback:
                progress_callback("🩺 Checking MCP manager (production)", 96)
                
            print(f"\n🩺 Testing MCP Manager (production service):")
            print(f"   URL: http://localhost:5859/status (inside container)")
            
            # Retry MCP manager check with backoff (it takes longer to start)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = self._run_command([
                        "docker", "exec", container_name, "curl", "-f", "http://localhost:5859/status"
                    ])
                    health_status["mcp_manager"] = True
                    print(f"   ✅ MCP manager is healthy (internal port 5859)")
                    if progress_callback:
                        progress_callback("✅ MCP manager is healthy (internal port 5859)", 98)
                    break
                except RuntimeError as e:
                    if attempt < max_retries - 1:
                        print(f"   ⏳ MCP manager not ready, retrying in 5 seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(5)
                    else:
                        health_status["mcp_manager"] = False
                        print(f"   ❌ MCP manager health check failed after {max_retries} attempts: {str(e)}")
                        if progress_callback:
                            progress_callback(f"❌ MCP manager health check failed: {str(e)}", 98)
        
        # Summary
        healthy_count = sum(health_status.values())
        total_count = len(health_status)
        
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📊 Health check summary: {healthy_count}/{total_count} services healthy")
        
        if progress_callback:
            progress_callback(f"✅ Health check complete: {healthy_count}/{total_count} services healthy", 100)
                
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
        
    def publish(self, source_path: str, config: DeploymentConfig, progress_callback: Optional[ProgressCallback] = None) -> PublishResult:
        """
        Publish the application using Docker registry
        
        Args:
            source_path: Path to the Fractalic source code
            config: Deployment configuration
            progress_callback: Optional callback for progress updates
            
        Returns:
            PublishResult with deployment information
        """
        try:
            if progress_callback:
                progress_callback("🚀 Starting Docker registry deployment", 5)
                
            self.logger.info(f"Starting Docker registry deployment: {config.script_name}")
            
            # Store source_path for use in file copying operations
            self._source_path = source_path
            
            # Validate configuration
            is_valid, error_msg = self.validate_config(config)
            if not is_valid:
                return PublishResult(
                    success=False,
                    deployment_id="",
                    message="Configuration validation failed",
                    error=error_msg
                )
            
            # Convert DeploymentConfig to internal config dict
            # Get image name from plugin_specific config or use default
            image_name = f"{self.default_registry}:latest-production"
            if config.plugin_specific and "image_name" in config.plugin_specific:
                image_name = config.plugin_specific["image_name"]
                # Force production image for deployments
                if "fractalic-ai/fractalic" in image_name:
                    if image_name.endswith(":latest"):
                        image_name = image_name.replace(":latest", ":latest-production")
                    elif not image_name.endswith("-production"):
                        # Add production tag if no tag specified
                        if ":" not in image_name.split("/")[-1]:
                            image_name = f"{image_name}:latest-production"
                        else:
                            image_name = f"{image_name}-production"
            
            config_dict = {
                "script_name": config.script_name,
                "script_folder": config.script_folder,
                "container_name": config.container_name,
                "registry_image": image_name,
                "platform": self._detect_platform(),
                "ports": self.default_ports,
                "include_files": ["*"],
                "exclude_patterns": [
                    ".git", ".gitignore", "__pycache__", "*.pyc", ".DS_Store",
                    "node_modules", ".next", ".vscode", "*.log"
                ],
                "config_files": ["config.json", "settings.toml", ".env"],
                "env_vars": {},
                "mount_paths": {
                    "user_scripts": "/payload",
                    "logs": "/fractalic/logs"
                }
            }
            
            # Pull base image
            self._pull_base_image(config_dict, progress_callback)
            
            # Prepare user files
            with self._prepare_user_files(config_dict, progress_callback) as temp_dir:
                # Start container
                container_id = self._start_container(config_dict, temp_dir, progress_callback)
                
                # Copy files into container (cloud-ready approach)
                self._copy_files_to_container(config_dict["container_name"], temp_dir, config_dict, progress_callback)
                
                # Health check
                health_status = self._health_check(config_dict, progress_callback)
                
                # Generate AI server information with actual script path
                ai_port = config_dict["actual_ports"]["ai_server"]
                script_path = self._find_main_script_file(config_dict['script_name'], config_dict['script_folder'])
                ai_server_info = generate_ai_server_info(ai_port, config_dict["container_name"], script_path)
                
                # Build URLs (focused on AI server as main service)
                urls = {
                    "ai_server": ai_server_info["url"]
                }
                
                # Determine success criteria based on deployment type
                is_production = "production" in config_dict.get("registry_image", "")
                if is_production:
                    # For production: AI server + MCP manager
                    success = health_status.get("ai_server", False) and health_status.get("mcp_manager", False)
                    service_status = f"AI Server: {'✅' if health_status.get('ai_server') else '❌'}, MCP Manager: {'✅' if health_status.get('mcp_manager') else '❌'}"
                else:
                    # For full: AI server + backend
                    success = health_status.get("ai_server", False) and health_status.get("backend", False)
                    service_status = f"AI Server: {'✅' if health_status.get('ai_server') else '❌'}, Backend: {'✅' if health_status.get('backend') else '❌'}"
                
                # Generate deployment summary message
                if success:
                    message = f"🎉 Fractalic AI Server deployed successfully!\n\n"
                    message += f"📋 AI Server Access:\n"
                    message += f"   • Host: http://localhost:{ai_port}\n"
                    message += f"   • Endpoint: /execute\n"
                    message += f"   • Health Check: {ai_server_info['health_url']}\n"
                    message += f"   • API Docs: {ai_server_info['docs_url']}\n\n"
                    message += f"� Deployed Script:\n"
                    message += f"   • File: {script_path}\n"
                    message += f"   • Container: {config_dict['container_name']}\n\n"
                    message += f"📝 Sample Usage:\n"
                    message += f"   {ai_server_info['sample_curl']}\n\n"
                    message += f"� Container Management:\n"
                    message += f"   • View logs: {ai_server_info['logs_command']}\n"
                    message += f"   • Stop: {ai_server_info['stop_command']}\n"
                    message += f"   • Remove: {ai_server_info['remove_command']}"
                    if is_production:
                        message += f"\n\n🔧 MCP Manager: http://localhost:5859/status (internal)"
                else:
                    message = f"⚠️ Deployment completed with issues. {service_status}"
                
                return PublishResult(
                    success=success,
                    deployment_id=container_id[:12],
                    message=message,
                    url=ai_server_info["url"],
                    admin_url=None,
                    build_time=None,
                    error=None if success else "Health check failed",
                    metadata={
                        "ai_server": {
                            "host": ai_server_info["url"],
                            "port": ai_server_info["port"],
                            "health_url": ai_server_info["health_url"],
                            "docs_url": ai_server_info["docs_url"]
                        },
                        "deployment": {
                            "script_name": config_dict["script_name"],
                            "script_path": script_path,
                            "container_name": config_dict["container_name"],
                            "container_id": container_id[:12]
                        },
                        "api": {
                            "endpoint": "/execute",
                            "sample_curl": ai_server_info["sample_curl"],
                            "example_payload": {
                                "filename": script_path,
                                "parameter_text": "optional context or parameters"
                            }
                        },
                        "container": {
                            "logs_command": ai_server_info["logs_command"],
                            "stop_command": ai_server_info["stop_command"],
                            "remove_command": ai_server_info["remove_command"]
                        },
                        "services": {
                            "ai_server": "healthy" if ai_server_info else "unhealthy",
                            "mcp_manager": "healthy (internal)" if is_production else "healthy"
                        }
                    }
                )
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Deployment failed: {str(e)}", 100)
            self.logger.error(f"Deployment failed: {str(e)}", exc_info=True)
            return PublishResult(
                success=False,
                deployment_id="",
                message=f"Deployment failed: {str(e)}",
                error=str(e)
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

    def _copy_files_to_container(self, container_name: str, temp_dir: str, config: Dict[str, Any], progress_callback=None) -> None:
        """Copy prepared files directly into the running container"""
        temp_path = Path(temp_dir)
        scripts_path = temp_path / "scripts"
        config_path = temp_path / "config"
        
        if progress_callback:
            progress_callback("📂 Setting up container directories", 70)
        
        print(f"\n📂 Setting up directories in container:")
        
        # Ensure payload directory exists in container (run as root)
        payload_base = config['mount_paths']['user_scripts']
        payload_path = f"{payload_base}/{config['script_name']}"
        
        print(f"📁 Creating payload directory: {payload_path}")
        
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
        
        if progress_callback:
            progress_callback("📄 Copying user scripts to container", 75)
        
        print(f"📄 Copying user scripts to container:")
        
        # Copy all files from scripts directory to container
        file_count = 0
        copied_files = []
        if scripts_path.exists():
            for item in scripts_path.iterdir():
                if item.is_file():
                    # Copy individual files
                    self._run_command([
                        "docker", "cp", str(item), 
                        f"{container_name}:{payload_path}/{item.name}"
                    ])
                    self.logger.info(f"Copied {item.name} to container {payload_path}")
                    copied_files.append(item.name)
                    file_count += 1
                elif item.is_dir():
                    # Copy directories recursively
                    self._run_command([
                        "docker", "cp", str(item), 
                        f"{container_name}:{payload_path}/"
                    ])
                    
                    # Count files in directory for accurate reporting
                    dir_file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                    self.logger.info(f"Copied directory {item.name} to container {payload_path} ({dir_file_count} files inside)")
                    copied_files.append(f"{item.name}/ ({dir_file_count} files)")
                    file_count += dir_file_count

        if progress_callback:
            file_list = ", ".join(copied_files[:5])  # Show first 5 files
            if len(copied_files) > 5:
                file_list += f" (and {len(copied_files) - 5} more)"
            progress_callback(f"📄 Copied {file_count} user files: {file_list}", 78)

        if progress_callback:
            progress_callback(f"⚙️ Copying configuration files ({file_count} items copied)", 80)

        # Copy configuration files from main directory to /fractalic
        main_config_files = ["mcp_servers.json", "settings.toml"]
        
        # Determine the fractalic project root directory 
        # Priority: 1) use source_path if it contains config files or is part of fractalic project
        #          2) find fractalic.py from current directory up the tree
        #          3) find fractalic.py from source_path up the tree
        #          4) fallback to current working directory
        project_root = None
        
        # First: try to find fractalic.py starting from source_path if provided
        if hasattr(self, '_source_path') and self._source_path:
            source_path = Path(self._source_path).resolve()
            # Walk up from source_path to find fractalic.py (project root indicator)
            for parent in [source_path] + list(source_path.parents):
                if (parent / "fractalic.py").exists():
                    project_root = parent
                    self.logger.info(f"Found fractalic.py in source path hierarchy: {project_root}")
                    break
        
        # Second: try to find fractalic.py starting from current working directory
        if not project_root:
            cwd = Path.cwd().resolve()
            for parent in [cwd] + list(cwd.parents):
                if (parent / "fractalic.py").exists():
                    project_root = parent
                    self.logger.info(f"Found fractalic.py from current directory: {project_root}")
                    break
        
        # Third: try common locations where fractalic might be installed
        if not project_root:
            # Check if we're in a subdirectory of a fractalic installation
            possible_paths = [
                Path(__file__).parent.parent.parent,  # Go up from publisher/plugins/
            ]
            for path in possible_paths:
                if (path / "fractalic.py").exists():
                    project_root = path
                    self.logger.info(f"Found fractalic.py via plugin path: {project_root}")
                    break
        
        # Fallback to current working directory if nothing else works
        if not project_root:
            project_root = Path.cwd()
            self.logger.warning(f"Could not locate fractalic.py, using current directory: {project_root}")
            
        self.logger.info(f"Using project root for config files: {project_root}")
        
        for config_file in main_config_files:
            config_file_path = project_root / config_file
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
        
        if progress_callback:
            progress_callback("✅ All files copied successfully", 85)
        
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
        
        # Set proper permissions for user files
        self._run_command([
            "docker", "exec", "--user", "root", container_name,
            "chmod", "-R", "755", payload_base
        ])
        
        # Set proper ownership for config files if they exist (run as root)
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic/mcp_servers.json"
            ])
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chmod", "664", "/fractalic/mcp_servers.json"
            ])
        except RuntimeError:
            pass  # File might not exist
            
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic/settings.toml"
            ])
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chmod", "664", "/fractalic/settings.toml"
            ])
        except RuntimeError:
            pass  # File might not exist
            
        # Also fix ownership for root settings.toml file
        try:
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/settings.toml"
            ])
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chmod", "664", "/settings.toml"
            ])
        except RuntimeError:
            pass  # File might not exist
        
        # Fix the frontend config.json to have correct API endpoints (only for full images)
        if "production" not in config.get("registry_image", ""):
            if progress_callback:
                progress_callback("⚙️ Configuring frontend for container networking", 82)
            self._fix_frontend_config(container_name, config)
            
            # Fix the Next.js config for proper API rewrites
            if progress_callback:
                progress_callback("⚙️ Setting up Next.js API rewrites", 84)
            self._fix_nextjs_config(container_name, config)
            
            # Fix frontend environment variables for container networking
            if progress_callback:
                progress_callback("⚙️ Setting frontend environment variables", 86)
            self._fix_frontend_environment(container_name, config)
            
            # Restart frontend service to apply new configuration
            self._restart_frontend_service(container_name, progress_callback)
        else:
            if progress_callback:
                progress_callback("⚙️ Production image - skipping frontend config", 82)
        
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
      // Backend API rewrites with query parameter support
      {
        source: '/list_directory/:path*',
        destination: 'http://localhost:8000/list_directory/:path*',
      },
      {
        source: '/list_directory',
        destination: 'http://localhost:8000/list_directory/',
      },
      {
        source: '/branches_and_commits/:path*',
        destination: 'http://localhost:8000/branches_and_commits/:path*',
      },
      {
        source: '/branches_and_commits',
        destination: 'http://localhost:8000/branches_and_commits',
      },
      {
        source: '/get_file_content_disk/:path*',
        destination: 'http://localhost:8000/get_file_content_disk/:path*',
      },
      {
        source: '/get_file_content_disk',
        destination: 'http://localhost:8000/get_file_content_disk',
      },
      {
        source: '/create_file/:path*',
        destination: 'http://localhost:8000/create_file/:path*',
      },
      {
        source: '/create_file',
        destination: 'http://localhost:8000/create_file',
      },
      {
        source: '/create_folder/:path*',
        destination: 'http://localhost:8000/create_folder/:path*',
      },
      {
        source: '/create_folder',
        destination: 'http://localhost:8000/create_folder',
      },
      {
        source: '/get_file_content/:path*',
        destination: 'http://localhost:8000/get_file_content/:path*',
      },
      {
        source: '/get_file_content',
        destination: 'http://localhost:8000/get_file_content',
      },
      {
        source: '/save_file/:path*',
        destination: 'http://localhost:8000/save_file/:path*',
      },
      {
        source: '/save_file',
        destination: 'http://localhost:8000/save_file',
      },
      {
        source: '/delete_item/:path*',
        destination: 'http://localhost:8000/delete_item/:path*',
      },
      {
        source: '/delete_item',
        destination: 'http://localhost:8000/delete_item',
      },
      {
        source: '/rename_item/:path*',
        destination: 'http://localhost:8000/rename_item/:path*',
      },
      {
        source: '/rename_item',
        destination: 'http://localhost:8000/rename_item',
      },
      {
        source: '/load_settings/:path*',
        destination: 'http://localhost:8000/load_settings/:path*',
      },
      {
        source: '/load_settings',
        destination: 'http://localhost:8000/load_settings',
      },
      {
        source: '/save_settings/:path*',
        destination: 'http://localhost:8000/save_settings/:path*',
      },
      {
        source: '/save_settings',
        destination: 'http://localhost:8000/save_settings',
      },
      // MCP Manager API rewrites
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

    def _fix_frontend_environment(self, container_name: str, config: Dict[str, Any]) -> None:
        """Set proper environment variables for container-internal networking"""
        
        # Create .env.local with relative URLs for container networking
        # Using empty strings to force relative URLs that work with Next.js rewrites
        env_content = '''# Container internal networking - use relative URLs with Next.js rewrites
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_AI_API_BASE_URL=/ai  
NEXT_PUBLIC_MCP_API_BASE_URL=/mcp

# Disable external config fetching
NEXT_PUBLIC_USE_INTERNAL_CONFIG=true
'''
        
        # Write environment file to container
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as tmp_file:
            tmp_file.write(env_content)
            tmp_env_path = tmp_file.name
        
        try:
            # Copy environment file to container
            self._run_command([
                "docker", "cp", tmp_env_path, 
                f"{container_name}:/fractalic-ui/.env.local"
            ])
            
            # Fix ownership
            self._run_command([
                "docker", "exec", "--user", "root", container_name,
                "chown", "appuser:appuser", "/fractalic-ui/.env.local"
            ])
            
            self.logger.info("Set frontend environment variables for container networking")
        finally:
            try:
                os.unlink(tmp_env_path)
            except OSError:
                pass

    def _restart_frontend_service(self, container_name: str, progress_callback=None) -> None:
        """Restart the frontend service to pick up new configuration"""
        
        if progress_callback:
            progress_callback("🔄 Restarting frontend with new config", 75)
        
        try:
            # Method 1: Try supervisorctl (if available)
            try:
                self._run_command([
                    "docker", "exec", container_name,
                    "supervisorctl", "restart", "frontend"
                ])
                if progress_callback:
                    progress_callback("✅ Frontend restarted via supervisor", 80)
                self.logger.info("Frontend service restarted via supervisor")
                return
            except RuntimeError:
                # Supervisor might not be configured properly, try manual approach
                pass
            
            # Method 2: Manual process management
            import time
            
            # Kill any existing Node.js processes (frontend)
            try:
                self._run_command([
                    "docker", "exec", container_name,
                    "pkill", "-f", "npm.*dev"
                ])
                time.sleep(2)
            except RuntimeError:
                pass  # Process might not be running
            
            try:
                self._run_command([
                    "docker", "exec", container_name,
                    "pkill", "-f", "next-server"
                ])
                time.sleep(2)
            except RuntimeError:
                pass  # Process might not be running
            
            # Start frontend in background
            self._run_command([
                "docker", "exec", "-d", container_name,
                "sh", "-c", "cd /fractalic-ui && npm run dev > /tmp/frontend.log 2>&1 &"
            ])
            
            # Wait for frontend to start
            time.sleep(8)
            
            if progress_callback:
                progress_callback("✅ Frontend restarted manually", 80)
                
            self.logger.info("Frontend service restarted manually")
            
        except Exception as e:
            self.logger.error(f"Failed to restart frontend service: {e}")
            if progress_callback:
                progress_callback(f"⚠️ Frontend restart failed: {e}", 80)
