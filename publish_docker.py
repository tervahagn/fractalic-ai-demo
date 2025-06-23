#!/usr/bin/env python3
"""
Fractalic Docker Publisher

This script is for EXISTING Fractalic installations (not fresh GitHub installs).
It creates a clean Docker deployment from your current working Fractalic repository,
including any custom tutorials, scripts, or content you've created.

For fresh GitHub installations, use docker_build_run.sh instead.

Usage:
    python publish_docker.py [--name container-name] [--port-offset 0] [--include-path path/to/custom/content]

Features:
- Creates temporary build directory (never pollutes your source repo)
- Copies current fractalic repo state with all your custom content
- Automatically detects and includes adjacent fractalic-ui (expects ../fractalic-ui)
- Optionally includes additional custom directories/files at the same level as fractalic
- Builds and runs Docker container with proper networking
- Cleans up temporary files automatically
- Supports custom container naming and port mapping

Expected Directory Structure:
    your-workspace/
    ├── fractalic/          (this repo with your custom content)
    ├── fractalic-ui/       (UI repo, automatically detected)
    └── my-custom-scripts/  (optional, can be included with --include-path)

The resulting Docker container will have:
    /app/
    ├── fractalic/          (your fractalic installation)
    ├── fractalic-ui/       (UI components)  
    └── my-custom-scripts/  (if --include-path was used)
"""

import os
import sys
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path
import json
import time

class FractalicDockerPublisher:
    def __init__(self, container_name="fractalic-published", port_offset=0):
        self.container_name = container_name
        self.port_offset = port_offset
        self.temp_dir = None
        self.current_dir = Path(__file__).parent.absolute()
        
        # Host port mappings (internal ports stay fixed)
        # Internal container ports remain: 3000, 8000, 8001, 5859
        # Only host-side ports are shifted to avoid conflicts
        self.host_ports = {
            'frontend': 3000 + port_offset,
            'backend': 8000 + port_offset,
            'ai_server': 8001 + port_offset,
            'mcp_manager': 5859 + port_offset
        }
        
        # Internal container ports (never change these)
        self.container_ports = {
            'frontend': 3000,
            'backend': 8000,
            'ai_server': 8001,
            'mcp_manager': 5859
        }
        
    def log(self, message, level="INFO"):
        """Log message with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅ ",
            "WARNING": "⚠️ ",
            "ERROR": "❌ ",
            "BUILD": "🏗️ ",
            "STEP": "📋 "
        }.get(level, "ℹ️ ")
        print(f"[{timestamp}] {prefix}{message}")
        
    def log_step(self, step_num, total_steps, description):
        """Log a build step with progress"""
        self.log(f"Step {step_num}/{total_steps}: {description}", "STEP")
        
    def check_dependencies(self):
        """Check if Docker is available"""
        try:
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
            self.log("Docker is available")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("Docker is not available or not installed", "ERROR")
            return False
            
    def find_fractalic_ui(self):
        """Find fractalic-ui repository relative to current fractalic repo"""
        # Check common locations relative to current directory
        possible_paths = [
            self.current_dir.parent / "fractalic-ui",             # ../fractalic-ui (new structure)
            self.current_dir / "fractalic-ui",                    # ./fractalic-ui
            Path.cwd().parent / "fractalic-ui",                   # ../fractalic-ui from cwd
            self.current_dir.parent / "fractalic-ui" / "my-app",  # ../fractalic-ui/my-app (legacy)
            self.current_dir / "fractalic-ui" / "my-app",         # ./fractalic-ui/my-app (legacy)
            Path.cwd().parent / "fractalic-ui" / "my-app",        # ../fractalic-ui/my-app from cwd (legacy)
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "package.json").exists():
                self.log(f"Found fractalic-ui at: {path}")
                return path
                
        self.log("fractalic-ui not found - this is FATAL, cannot proceed without UI", "ERROR")
        self.log("Expected locations checked:", "ERROR")
        for path in possible_paths:
            exists = "✓" if path.exists() else "✗"
            pkg_json = "✓" if (path / "package.json").exists() else "✗"
            self.log(f"  {exists} {pkg_json} {path}", "ERROR")
        return None
        
    def create_temp_build_dir(self):
        """Create temporary build directory"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fractalic_publish_"))
        self.log(f"Created temporary build directory: {self.temp_dir}", "SUCCESS")
        
        # CRITICAL: Ensure temp directory is NOT inside the main repo
        # This prevents accidentally polluting the source repository
        if self.current_dir in self.temp_dir.parents or self.temp_dir == self.current_dir:
            raise RuntimeError(f"FATAL: Temporary directory {self.temp_dir} is inside source repo {self.current_dir}! This would pollute the source.")
        
        return self.temp_dir
        
    def get_directory_size(self, path):
        """Get directory size in MB"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size / (1024 * 1024)  # Convert to MB
        
    def copy_fractalic_repo(self, build_dir):
        """Copy current fractalic repository to build directory"""
        fractalic_dest = build_dir / "fractalic"
        
        # CRITICAL SAFETY CHECK: Ensure we're not copying into our own repo
        if fractalic_dest.resolve() == self.current_dir.resolve():
            raise RuntimeError(f"FATAL: Attempting to copy repo into itself! Source: {self.current_dir}, Dest: {fractalic_dest}")
        if self.current_dir in fractalic_dest.parents:
            raise RuntimeError(f"FATAL: Destination {fractalic_dest} is inside source repo {self.current_dir}!")
        
        self.log("Copying fractalic repository...", "BUILD")
        
        # Copy the entire fractalic directory but exclude some development files
        exclude_patterns = {
            '.git', '__pycache__', '*.pyc', '.pytest_cache', 
            'venv', '.venv', 'node_modules', '.DS_Store',
            '*.log', 'logs/*', '.vscode', '.idea'
        }
        
        start_time = time.time()
        shutil.copytree(
            self.current_dir, 
            fractalic_dest, 
            ignore=shutil.ignore_patterns(*exclude_patterns)
        )
        copy_time = time.time() - start_time
        
        # Report size and timing
        size_mb = self.get_directory_size(fractalic_dest)
        self.log(f"Copied fractalic ({size_mb:.1f} MB) in {copy_time:.2f}s", "SUCCESS")
        
        # Ensure critical files are present
        critical_files = [
            'fractalic.py', 'requirements.txt', 'settings.toml', 
            'mcp_servers.json', 'fractalic_mcp_manager.py'
        ]
        
        missing_files = []
        for file in critical_files:
            if not (fractalic_dest / file).exists():
                missing_files.append(file)
                
        if missing_files:
            self.log(f"Warning: Missing critical files: {missing_files}", "WARNING")
            
        # Fix MCP manager to bind to all interfaces for Docker deployment
        self.fix_mcp_manager_binding(fractalic_dest / "fractalic_mcp_manager.py")
            
        self.log("Fractalic repository setup complete", "SUCCESS")
        return fractalic_dest
        
    def fix_mcp_manager_binding(self, mcp_manager_path):
        """Fix MCP manager to bind to all interfaces (0.0.0.0) for Docker deployment"""
        if not mcp_manager_path.exists():
            return
            
        self.log("Fixing MCP manager to bind to all interfaces for Docker deployment")
        
        with open(mcp_manager_path, 'r') as f:
            content = f.read()
        
        # Replace localhost binding with all interfaces binding
        # This allows external access through Docker port mapping
        content = content.replace(
            'site   = web.TCPSite(runner, "127.0.0.1", port)',
            'site   = web.TCPSite(runner, "0.0.0.0", port)'
        )
        
        # Update the log message to reflect the change
        content = content.replace(
            'log(f"API http://127.0.0.1:{port}  – Ctrl-C to quit")',
            'log(f"API http://0.0.0.0:{port}  – Ctrl-C to quit")'
        )
        
        with open(mcp_manager_path, 'w') as f:
            f.write(content)
            
        self.log("Fixed MCP manager binding to accept external connections")
        
    def copy_or_create_frontend(self, build_dir):
        """Copy fractalic-ui - FATAL if not found"""
        ui_source = self.find_fractalic_ui()
        ui_dest = build_dir / "fractalic-ui"
        
        if not ui_source:
            self.log("fractalic-ui is required but not found - cannot proceed", "ERROR")
            raise FileNotFoundError("fractalic-ui not found - this is a fatal error")
        
        # CRITICAL SAFETY CHECK: Ensure we're not copying into the main repo
        if self.current_dir in ui_dest.parents:
            raise RuntimeError(f"FATAL: UI destination {ui_dest} is inside source repo {self.current_dir}!")
        if ui_dest.resolve() == self.current_dir.resolve():
            raise RuntimeError(f"FATAL: Attempting to copy UI into main repo directory!")
            
        self.log("Copying fractalic-ui repository...", "BUILD")
        start_time = time.time()
        
        shutil.copytree(
            ui_source, 
            ui_dest,
            ignore=shutil.ignore_patterns('node_modules', '.git', '.DS_Store', '__pycache__', '.next', '*.tsbuildinfo')
        )
        
        copy_time = time.time() - start_time
        size_mb = self.get_directory_size(ui_dest)
        self.log(f"Copied fractalic-ui ({size_mb:.1f} MB) in {copy_time:.2f}s", "SUCCESS")
        
        # Verify package.json exists in destination
        if not (ui_dest / "package.json").exists():
            self.log("package.json not found in copied fractalic-ui", "ERROR")
            raise FileNotFoundError("Invalid fractalic-ui structure - package.json missing")
            
        # Fix API URLs for Docker container networking
        self.fix_frontend_api_urls(ui_dest)
            
        return ui_dest
        
    def fix_frontend_api_urls(self, ui_dest):
        """Fix hardcoded API URLs in frontend for Docker container networking"""
        self.log("Fixing frontend API URLs for container networking...")
        
        # Update next.config.mjs to use host-mapped ports for Docker deployment
        next_config_path = ui_dest / "next.config.mjs"
        if next_config_path.exists():
            with open(next_config_path, 'r') as f:
                content = f.read()
            
            # For Docker deployment, disable rewrites and let frontend directly access host-mapped ports
            # This ensures browser requests go to the correct host-mapped backend ports
            docker_config = f'''/** @type {{import('next').NextConfig}} */
const nextConfig = {{
  output: 'standalone',
  trailingSlash: false,
  
  // Docker deployment: Direct API access via host-mapped ports
  // No rewrites needed - frontend uses NEXT_PUBLIC_API_BASE_URL
  
  async rewrites() {{
    return [];
  }},
  
  async headers() {{
    return [
      {{
        source: '/:path*',
        headers: [
          {{
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          }},
        ],
      }},
    ];
  }},
}};

export default nextConfig;
'''
            
            with open(next_config_path, 'w') as f:
                f.write(docker_config)
            self.log("Updated next.config.mjs for Docker deployment with host-mapped ports")
        
        # Create environment file for API base URL
        # CRITICAL: Browser needs to access backend through host-mapped ports
        # Frontend runs on host:3050 -> container:3000
        # Backend runs on host:8050 -> container:8000
        # Browser accesses via host ports, not container ports
        env_local_path = ui_dest / ".env.local"
        with open(env_local_path, 'w') as f:
            f.write("# Docker container networking - browser accesses via host-mapped ports\n")
            f.write(f"NEXT_PUBLIC_API_BASE_URL=http://localhost:{self.host_ports['backend']}\n")
            f.write(f"NEXT_PUBLIC_AI_API_BASE_URL=http://localhost:{self.host_ports['ai_server']}\n")
            f.write(f"NEXT_PUBLIC_MCP_API_BASE_URL=http://localhost:{self.host_ports['mcp_manager']}\n")
        self.log(f"Created .env.local with host-mapped API URLs (backend: {self.host_ports['backend']})")
        
        # Create runtime configuration JSON file
        self.create_runtime_config(ui_dest)
        
        # Skip automatic component updates since UI is already fixed manually
        # Components now use the useAppConfig hook and getApiUrl functions
        self.log("Skipping automatic component updates - UI already uses configuration system")
        
        # Create runtime configuration
        self.create_runtime_config(ui_dest)
        
    def create_runtime_config(self, ui_dest):
        """Create runtime configuration JSON file for the UI"""
        config = {
            "api": {
                "backend": f"http://localhost:{self.host_ports['backend']}",
                "ai_server": f"http://localhost:{self.host_ports['ai_server']}",
                "mcp_manager": f"http://localhost:{self.host_ports['mcp_manager']}"
            },
            "container": {
                "internal_ports": self.container_ports,
                "host_ports": self.host_ports
            },
            "deployment": {
                "type": "docker",
                "container_name": self.container_name,
                "build_timestamp": time.time()
            },
            "paths": {
                "default_git_path": "/app/fractalic"
            }
        }
        
        # Create the public directory if it doesn't exist
        public_dir = ui_dest / "public"
        public_dir.mkdir(exist_ok=True)
        
        # Write config.json to public directory so it's accessible at runtime
        config_file = public_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.log(f"Created runtime config.json with API URLs: {config['api']}")
        
    def create_config_hook(self, ui_dest):
        """Create a React hook for accessing configuration"""
        hooks_dir = ui_dest / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        hook_content = '''import { useEffect, useState } from 'react';

export interface ApiConfig {
  backend: string;
  ai_server: string;
  mcp_manager: string;
}

export interface AppConfig {
  api: ApiConfig;
  container: {
    internal_ports: Record<string, number>;
    host_ports: Record<string, number>;
  };
  deployment: {
    type: string;
    container_name: string;
    build_timestamp: number;
  };
  paths: {
    default_git_path: string;
  };
}

let cachedConfig: AppConfig | null = null;

export function useAppConfig(): { config: AppConfig | null; loading: boolean; error: string | null } {
  const [config, setConfig] = useState<AppConfig | null>(cachedConfig);
  const [loading, setLoading] = useState(!cachedConfig);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cachedConfig) {
      setConfig(cachedConfig);
      setLoading(false);
      return;
    }

    const fetchConfig = async () => {
      try {
        const response = await fetch('/config.json');
        if (!response.ok) {
          throw new Error(`Failed to load config: ${response.statusText}`);
        }
        const configData: AppConfig = await response.json();
        
        // Cache the config
        cachedConfig = configData;
        setConfig(configData);
        setError(null);
      } catch (err) {
        console.error('Failed to load app config:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
        
        // Fallback to environment variables
        const fallbackConfig: AppConfig = {
          api: {
            backend: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
            ai_server: process.env.NEXT_PUBLIC_AI_API_BASE_URL || 'http://localhost:8001',
            mcp_manager: process.env.NEXT_PUBLIC_MCP_API_BASE_URL || 'http://localhost:5859'
          },
          container: {
            internal_ports: { frontend: 3000, backend: 8000, ai_server: 8001, mcp_manager: 5859 },
            host_ports: { frontend: 3000, backend: 8000, ai_server: 8001, mcp_manager: 5859 }
          },
          deployment: {
            type: 'development',
            container_name: 'fractalic-dev',
            build_timestamp: Date.now()
          },
          paths: {
            default_git_path: '/'
          }
        };
        
        cachedConfig = fallbackConfig;
        setConfig(fallbackConfig);
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, []);

  return { config, loading, error };
}

// Utility function to get specific API URLs
export function getApiUrl(service: keyof ApiConfig, config?: AppConfig | null): string {
  if (config?.api?.[service]) {
    return config.api[service];
  }
  
  // Fallback to environment variables
  switch (service) {
    case 'backend':
      return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    case 'ai_server':
      return process.env.NEXT_PUBLIC_AI_API_BASE_URL || 'http://localhost:8001';
    case 'mcp_manager':
      return process.env.NEXT_PUBLIC_MCP_API_BASE_URL || 'http://localhost:5859';
    default:
      return 'http://localhost:8000';
  }
}
'''
        
        hook_file = hooks_dir / "use-app-config.ts"
        with open(hook_file, 'w') as f:
            f.write(hook_content)
        
        self.log("Created useAppConfig hook for runtime configuration")
        
    def update_component_config_usage(self, ui_dest):
        """Update component files to use the new configuration system instead of hardcoded URLs"""
        self.log("Updating components to use configuration system...")
        
        # Create the config hook
        self.create_config_hook(ui_dest)
        
        # Update MCPManager.tsx to use the config hook
        self.update_mcp_manager_config(ui_dest)
        
        # Update other components as needed
        self.update_other_components_config(ui_dest)
    
    def update_mcp_manager_config(self, ui_dest):
        """Update MCPManager.tsx to use the configuration system"""
        mcp_manager_file = ui_dest / "components" / "MCPManager.tsx"
        if not mcp_manager_file.exists():
            self.log("MCPManager.tsx not found, skipping update", "WARNING")
            return
            
        self.log("Updating MCPManager.tsx to use configuration system")
        
        try:
            with open(mcp_manager_file, 'r') as f:
                content = f.read()
            
            # Add import for the config hook if not already present
            if "useAppConfig" not in content:
                # Find the imports section and add our hook
                import_match = content.find("import React,")
                if import_match != -1:
                    # Find the end of the React import line
                    end_match = content.find("\n", import_match)
                    if end_match != -1:
                        insert_pos = end_match + 1
                        config_import = "import { useAppConfig, getApiUrl } from '@/hooks/use-app-config';\n"
                        content = content[:insert_pos] + config_import + content[insert_pos:]
            
            # Add config hook usage at the beginning of the component
            component_start = content.find("const MCPManager: React.FC")
            if component_start != -1:
                # Find the opening brace of the component
                brace_pos = content.find("{", component_start)
                if brace_pos != -1:
                    insert_pos = brace_pos + 1
                    config_usage = "\n  const { config } = useAppConfig();"
                    content = content[:insert_pos] + config_usage + content[insert_pos:]
            
            # Replace hardcoded URLs with config-based URLs
            replacements = [
                ("'http://127.0.0.1:5859/", "${getApiUrl('mcp_manager', config)}/"),
                ("'http://localhost:8000/", "${getApiUrl('backend', config)}/"),
                ('"http://127.0.0.1:5859/', "${getApiUrl('mcp_manager', config)}/"),
                ('"http://localhost:8000/', "${getApiUrl('backend', config)}/"),
            ]
            
            for old_url, new_url in replacements:
                content = content.replace(old_url, f"`{new_url}")
                # Also handle the closing quote/backtick
                content = content.replace(f"`{new_url}'", f"`{new_url}`")
                content = content.replace(f"`{new_url}\"", f"`{new_url}`")
            
            with open(mcp_manager_file, 'w') as f:
                f.write(content)
                
            self.log("Successfully updated MCPManager.tsx to use configuration system")
            
        except Exception as e:
            self.log(f"Failed to update MCPManager.tsx: {e}", "WARNING")
    
    def update_other_components_config(self, ui_dest):
        """Update other component files to use the configuration system"""
        component_files = [
            "Console.tsx",
            "GitDiffViewer.tsx", 
            "Editor.tsx",
            "SettingsModal.tsx",
            "ToolsManager.tsx"
        ]
        
        for component_file in component_files:
            file_path = ui_dest / "components" / component_file
            if file_path.exists():
                try:
                    self.update_component_file_config(file_path)
                    
                    # Special handling for GitDiffViewer paths
                    if component_file == "GitDiffViewer.tsx":
                        self.fix_git_diff_viewer_paths(file_path)
                        
                except Exception as e:
                    self.log(f"Failed to update {component_file}: {e}", "WARNING")
    
    def fix_git_diff_viewer_paths(self, file_path):
        """Fix GitDiffViewer initial paths for containerized deployment"""
        self.log("Fixing GitDiffViewer paths for containerized deployment")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add import for the config hook if not already present
        if "useAppConfig" not in content:
            # Find the imports section and add our hook
            import_match = content.find("import React,")
            if import_match != -1:
                # Find the end of the React import line
                end_match = content.find("\n", import_match)
                if end_match != -1:
                    insert_pos = end_match + 1
                    config_import = "import { useAppConfig } from '@/hooks/use-app-config';\n"
                    content = content[:insert_pos] + config_import + content[insert_pos:]
        
        # Add config hook usage at the beginning of the component
        component_start = content.find("const GitDiffViewer")
        if component_start != -1:
            # Find the opening brace of the component
            brace_pos = content.find("{", component_start)
            if brace_pos != -1:
                insert_pos = brace_pos + 1
                config_usage = "\n  const { config } = useAppConfig();"
                content = content[:insert_pos] + config_usage + content[insert_pos:]
        
        # Replace hardcoded paths with config-based paths
        import re
        
        # Use config for default path
        path_replacements = [
            (r"useState<string>\('/'?\)", "useState<string>(config?.paths?.default_git_path || '/app/fractalic')"),
            (r"setCurrentGitPath\(\'\/\'\)", "setCurrentGitPath(config?.paths?.default_git_path || '/app/fractalic')"),
            (r"setCurrentEditPath\(\'\/\'\)", "setCurrentEditPath(config?.paths?.default_git_path || '/app/fractalic')")
        ]
        
        for pattern, replacement in path_replacements:
            content = re.sub(pattern, replacement, content)
        
        with open(file_path, 'w') as f:
            f.write(content)
    
    def update_component_file_config(self, file_path):
        """Update a single component file to use configuration system"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check if this file has hardcoded URLs that need updating
        has_urls = any(url in content for url in [
            'http://localhost:8000',
            'http://localhost:5859', 
            'http://127.0.0.1:8000',
            'http://127.0.0.1:5859'
        ])
        
        if not has_urls:
            return
            
        self.log(f"Updating {file_path.name} to use configuration system")
        
        # Add import for the config hook if not already present
        if "useAppConfig" not in content and "getApiUrl" not in content:
            # Find the imports section and add our hook
            import_match = content.find("import React,")
            if import_match == -1:
                import_match = content.find("import {")
            
            if import_match != -1:
                # Find a good place to insert the import
                newline_pos = content.find("\\n", import_match)
                if newline_pos != -1:
                    config_import = "import { getApiUrl, useAppConfig } from '@/hooks/use-app-config';\\n"
                    content = content[:newline_pos+1] + config_import + content[newline_pos+1:]
        
        # Replace hardcoded URLs - be very conservative to avoid breaking template literals
        simple_replacements = [
            ("'http://localhost:8000'", "getApiUrl('backend')"),
            ("'http://localhost:5859'", "getApiUrl('mcp_manager')"), 
            ("'http://127.0.0.1:8000'", "getApiUrl('backend')"),
            ("'http://127.0.0.1:5859'", "getApiUrl('mcp_manager')"),
            ('"http://localhost:8000"', "getApiUrl('backend')"),
            ('"http://localhost:5859"', "getApiUrl('mcp_manager')"),
            ('"http://127.0.0.1:8000"', "getApiUrl('backend')"),
            ('"http://127.0.0.1:5859"', "getApiUrl('mcp_manager')")
        ]
        
        for old_url, new_url in simple_replacements:
            if old_url in content:
                content = content.replace(old_url, new_url)
        
        # Handle template literal cases more carefully
        import re
        # Only replace URLs in fetch calls - much safer than general replacement
        content = re.sub(
            r"fetch\(\s*['\"]http://localhost:8000([^'\"]*)['\"]",
            r"fetch(`${getApiUrl('backend')}\\1`",
            content
        )
        content = re.sub(
            r"fetch\(\s*['\"]http://localhost:5859([^'\"]*)['\"]",
            r"fetch(`${getApiUrl('mcp_manager')}\\1`",
            content
        )
        content = re.sub(
            r"fetch\(\s*['\"]http://127\.0\.0\.1:8000([^'\"]*)['\"]",
            r"fetch(`${getApiUrl('backend')}\\1`",  
            content
        )
        content = re.sub(
            r"fetch\(\s*['\"]http://127\.0\.0\.1:5859([^'\"]*)['\"]",
            r"fetch(`${getApiUrl('mcp_manager')}\\1`",
            content
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        
    def copy_docker_config(self, build_dir):
        """Copy and potentially modify Docker configuration"""
        docker_src = self.current_dir / "docker"
        docker_dest = build_dir
        
        # Copy Dockerfile, supervisord.conf, and next.config.docker.mjs to build root
        if docker_src.exists():
            for file in ["Dockerfile", "supervisord.conf", "next.config.docker.mjs"]:
                src_file = docker_src / file
                if src_file.exists():
                    shutil.copy2(src_file, docker_dest / file)
                    self.log(f"Copied {file}")
                    
        # Fix MCP manager command syntax in supervisord.conf
        self.fix_supervisor_mcp_command(build_dir / "supervisord.conf")
            
    def fix_supervisor_mcp_command(self, supervisor_conf):
        """Fix MCP manager command syntax in supervisor configuration"""
        if not supervisor_conf.exists():
            return
            
        self.log("Fixing MCP manager command syntax in supervisord.conf")
        
        with open(supervisor_conf, 'r') as f:
            content = f.read()
        
        # Fix the MCP manager command - port argument must come BEFORE the serve command
        # Wrong: python fractalic_mcp_manager.py serve --port 5859
        # Correct: python fractalic_mcp_manager.py --port 5859 serve
        content = content.replace(
            "command=python fractalic_mcp_manager.py serve --port 5859",
            "command=python fractalic_mcp_manager.py --port 5859 serve"
        )
        
        with open(supervisor_conf, 'w') as f:
            f.write(content)
            
        self.log("Fixed MCP manager command syntax")
            
    def build_docker_image(self, build_dir):
        """Build Docker image with live output and progress tracking"""
        image_name = f"{self.container_name}:latest"
        
        # Report build context size
        total_size = self.get_directory_size(build_dir)
        self.log(f"Build context size: {total_size:.1f} MB", "BUILD")
        
        self.log(f"Building Docker image: {image_name}", "BUILD")
        
        # Show what's in the build directory
        self.log("Build directory contents:", "BUILD")
        for item in build_dir.iterdir():
            if item.is_dir():
                size = self.get_directory_size(item)
                self.log(f"  📁 {item.name}/ ({size:.1f} MB)")
            else:
                size = item.stat().st_size / 1024  # KB
                self.log(f"  📄 {item.name} ({size:.1f} KB)")
        
        self.log("=== DOCKER BUILD OUTPUT ===", "BUILD")
        
        cmd = ["docker", "build", "-t", image_name, str(build_dir)]
        start_time = time.time()
        
        # Stream output in real-time with step tracking
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        step_count = 0
        # Print output line by line as it comes
        for line in process.stdout:
            line = line.rstrip()
            if "Step " in line and "/" in line:
                step_count += 1
                # Highlight Docker steps
                self.log(f"🏗️  {line}", "BUILD")
            elif "-->" in line or "sha256:" in line:
                # Highlight important progress lines
                print(f"    ✅ {line}")
            elif "RUN " in line or "COPY " in line or "WORKDIR " in line:
                # Highlight commands
                print(f"    ⚡ {line}")
            else:
                # Regular output
                print(f"    {line}")
        
        # Wait for process to complete
        return_code = process.wait()
        build_time = time.time() - start_time
        
        self.log("=== END DOCKER BUILD OUTPUT ===", "BUILD")
        
        if return_code == 0:
            self.log(f"Docker image built successfully in {build_time:.1f}s", "SUCCESS")
            self.log(f"Image: {image_name}", "SUCCESS")
            return image_name
        else:
            self.log(f"Docker build failed with return code: {return_code}", "ERROR")
            return None
            
    def stop_existing_container(self):
        """Stop and remove existing container with same name"""
        self.log(f"Checking for existing container: {self.container_name}")
        
        # Check if container exists
        check_cmd = ["docker", "ps", "-qa", "-f", f"name={self.container_name}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if result.stdout.strip():
            self.log("Stopping existing container...")
            subprocess.run(["docker", "stop", self.container_name], capture_output=True)
            
            self.log("Removing existing container...")
            subprocess.run(["docker", "rm", self.container_name], capture_output=True)
            
    def run_container(self, image_name):
        """Run the Docker container with detailed progress"""
        self.log(f"Starting container: {self.container_name}", "BUILD")
        
        # Build port mapping arguments (host:container)
        port_args = []
        self.log("Configuring port mappings:", "BUILD")
        
        for service in self.host_ports.keys():
            host_port = self.host_ports[service]
            container_port = self.container_ports[service]
            port_args.extend(["-p", f"{host_port}:{container_port}"])
            self.log(f"  {service}: localhost:{host_port} -> container:{container_port}")
                
        # Also map additional AI server ports (8002, 8003, 8004)
        self.log("  Additional AI server ports:")
        for i in range(2, 5):  # 8002, 8003, 8004
            host_ai_port = 8000 + i + self.port_offset
            container_ai_port = 8000 + i
            port_args.extend(["-p", f"{host_ai_port}:{container_ai_port}"])
            self.log(f"    AI server {i}: localhost:{host_ai_port} -> container:{container_ai_port}")
        
        cmd = [
            "docker", "run", "-d",
            "--name", self.container_name
        ] + port_args + [image_name]
        
        self.log("Executing: " + " ".join(cmd[:6]) + " ... " + image_name, "BUILD")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            container_id = result.stdout.strip()[:12]  # First 12 chars of container ID
            self.log(f"Container started successfully (ID: {container_id})", "SUCCESS")
            return True
        else:
            self.log(f"Failed to start container: {result.stderr}", "ERROR")
            return False
            
    def wait_for_services(self):
        """Wait for services to be ready with progressive checking"""
        self.log("Waiting for services to start...", "BUILD")
        
        # Give initial startup time
        for i in range(10, 0, -1):
            self.log(f"Initial startup wait: {i}s remaining...")
            time.sleep(1)
        
        # Check service availability progressively
        services_status = {}
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            self.log(f"Service check attempt {attempt}/{max_attempts}", "BUILD")
            
            for service in self.host_ports.keys():
                if service in services_status and "✅" in services_status[service]:
                    continue  # Skip already confirmed services
                    
                host_port = self.host_ports[service]
                try:
                    import urllib.request
                    url = f"http://localhost:{host_port}"
                    urllib.request.urlopen(url, timeout=3)
                    services_status[service] = "✅ Available"
                    self.log(f"   {service}: Available on port {host_port}", "SUCCESS")
                except Exception as e:
                    services_status[service] = f"⚠️ Starting (attempt {attempt})"
                    self.log(f"   {service}: Not yet ready on port {host_port}")
            
            # Check if all services are ready
            ready_count = sum(1 for status in services_status.values() if "✅" in status)
            total_count = len(self.host_ports)
            self.log(f"Services ready: {ready_count}/{total_count}")
            
            if ready_count == total_count:
                break
            
            if attempt < max_attempts:
                self.log("Waiting 5s before next check...")
                time.sleep(5)
        
        # Final status for any remaining services
        for service in services_status:
            if "⚠️" in services_status[service]:
                services_status[service] = "⚠️ May need more time"
                
        return services_status
        
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and self.temp_dir.exists():
            # SAFETY CHECK: Only delete if it's actually a temp directory
            if "fractalic_publish_" in str(self.temp_dir) and "/tmp/" in str(self.temp_dir):
                self.log(f"Cleaning up temporary files: {self.temp_dir}")
                try:
                    shutil.rmtree(self.temp_dir)
                    self.log("Temporary files cleaned up successfully")
                except Exception as e:
                    self.log(f"Warning: Failed to clean up temp dir: {e}", "WARNING")
            else:
                self.log(f"WARNING: Skipping cleanup of suspicious directory: {self.temp_dir}", "WARNING")
            
    def publish(self):
        """Main publish process with step-by-step progress tracking"""
        total_steps = 8
        
        try:
            self.log("🚀 Starting Fractalic Docker deployment", "BUILD")
            self.log(f"Container: {self.container_name}", "BUILD")
            self.log(f"Port offset: {self.port_offset}", "BUILD")
            self.log("")
            
            # Step 1: Check dependencies
            self.log_step(1, total_steps, "Checking Docker availability")
            if not self.check_dependencies():
                return False
            
            # Step 2: Create build directory
            self.log_step(2, total_steps, "Creating temporary build directory")
            build_dir = self.create_temp_build_dir()
            
            # Step 3: Copy source files
            self.log_step(3, total_steps, "Copying Fractalic backend")
            self.copy_fractalic_repo(build_dir)
            
            self.log_step(4, total_steps, "Copying Fractalic UI frontend")
            self.copy_or_create_frontend(build_dir)
            
            self.log_step(5, total_steps, "Copying Docker configuration")
            self.copy_docker_config(build_dir)
            
            # Step 6: Stop existing container
            self.log_step(6, total_steps, "Stopping existing containers")
            self.stop_existing_container()
            
            # Step 7: Build Docker image
            self.log_step(7, total_steps, "Building Docker image")
            image_name = self.build_docker_image(build_dir)
            
            if not image_name:
                return False
            
            # Step 8: Run container and verify services
            self.log_step(8, total_steps, "Starting container and verifying services")
            if not self.run_container(image_name):
                return False
                
            # Check services
            services_status = self.wait_for_services()
            
            # Report success
            self.log("")
            self.log("🎉 Publication completed successfully!", "SUCCESS")
            self.log("")
            self.log("📋 Services Summary:", "SUCCESS")
            for service, status in services_status.items():
                service_name = service.replace('_', ' ').title()
                host_port = self.host_ports[service]
                container_port = self.container_ports[service]
                self.log(f"   • {service_name}: http://localhost:{host_port} -> container:{container_port} - {status}")
                
            self.log("")
            self.log(f"Container name: {self.container_name}", "SUCCESS")
            self.log(f"Use 'docker logs {self.container_name}' to view logs")
            self.log(f"Use 'docker stop {self.container_name}' to stop")
            
            return True
            
        except Exception as e:
            self.log(f"Publication failed: {str(e)}", "ERROR")
            import traceback
            self.log(f"Error details: {traceback.format_exc()}", "ERROR")
            return False
        finally:
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Publish Fractalic to Docker")
    parser.add_argument("--name", default="fractalic-published", 
                       help="Container name (default: fractalic-published)")
    parser.add_argument("--port-offset", type=int, default=0,
                       help="Port offset for all services (default: 0)")
    parser.add_argument("--keep-temp", action="store_true",
                       help="Keep temporary build directory for debugging")
    
    args = parser.parse_args()
    
    publisher = FractalicDockerPublisher(
        container_name=args.name,
        port_offset=args.port_offset
    )
    
    if args.keep_temp:
        # Override cleanup for debugging
        publisher.cleanup = lambda: None
    
    success = publisher.publish()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
