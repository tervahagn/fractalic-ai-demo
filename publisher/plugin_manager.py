"""
Plugin Manager for Fractalic Publisher System
"""
import os
import sys
import importlib
import importlib.util
from typing import Dict, List, Optional
import logging
from pathlib import Path

try:
    from .base_plugin import BasePublishPlugin
    from .models import PluginInfo, DeploymentConfig
except ImportError:
    from base_plugin import BasePublishPlugin
    from models import PluginInfo, DeploymentConfig


class PluginManager:
    """Manages discovery and loading of publish plugins"""
    
    def __init__(self, plugins_dir: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.plugins_dir = plugins_dir or os.path.join(os.path.dirname(__file__), "plugins")
        self.plugins: Dict[str, BasePublishPlugin] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        
        # Load built-in plugins
        self._load_builtin_plugins()
        
    def _load_builtin_plugins(self):
        """Load built-in plugins that don't require separate plugin files"""
        try:
            # Load Docker Registry plugin
            from .plugins.docker_registry_plugin import DockerRegistryPlugin
            docker_plugin = DockerRegistryPlugin()
            self.plugins["docker-registry"] = docker_plugin
            
            # Create plugin info for Docker Registry plugin
            from .models import PluginInfo, PluginCapability
            docker_info = PluginInfo(
                name="docker-registry",
                display_name="Docker Registry",
                description="Fast deployment using pre-built Docker images from registry",
                version="1.0.0",
                homepage_url="https://github.com/yourusername/fractalic",
                documentation_url="https://github.com/yourusername/fractalic/docs",
                capabilities=[
                    PluginCapability.ONE_CLICK_DEPLOY,
                    PluginCapability.INSTANT_PREVIEW
                ],
                pricing_info="Free (uses your own Docker registry)",
                setup_difficulty="easy",
                deploy_time_estimate="< 1 min",
                free_tier_limits="Unlimited (local deployment)"
            )
            self.plugin_info["docker-registry"] = docker_info
            
            self.logger.info("Loaded built-in Docker Registry plugin")
            
        except Exception as e:
            self.logger.error(f"Failed to load built-in plugins: {e}")
    
    def discover_plugins(self) -> List[str]:
        """Discover all available plugins"""
        discovered = []
        plugins_path = Path(self.plugins_dir)
        
        if not plugins_path.exists():
            self.logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return discovered
            
        for plugin_dir in plugins_path.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('.'):
                plugin_file = plugin_dir / "plugin.py"
                if plugin_file.exists():
                    discovered.append(plugin_dir.name)
                    self.logger.info(f"Discovered plugin: {plugin_dir.name}")
                    
        return discovered
    
    def load_plugin(self, plugin_name: str) -> Optional[BasePublishPlugin]:
        """Load a specific plugin"""
        if plugin_name in self.plugins:
            return self.plugins[plugin_name]
            
        plugin_path = Path(self.plugins_dir) / plugin_name / "plugin.py"
        if not plugin_path.exists():
            self.logger.error(f"Plugin file not found: {plugin_path}")
            return None
            
        try:
            # Add the plugin directory and publisher directory to sys.path temporarily
            plugin_dir = str(plugin_path.parent)
            publisher_dir = str(Path(self.plugins_dir).parent)
            
            original_path = sys.path.copy()
            sys.path.insert(0, publisher_dir)
            sys.path.insert(0, plugin_dir)
            
            try:
                # Load the plugin module
                spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", plugin_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find the plugin class
                plugin_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '__bases__') and
                        any('BasePublishPlugin' in str(base) for base in attr.__bases__) and
                        attr_name != 'BasePublishPlugin'):
                        plugin_class = attr
                        break
                        
                if not plugin_class:
                    self.logger.error(f"No plugin class found in {plugin_name}")
                    return None
                    
                # Instantiate the plugin
                plugin_instance = plugin_class()
                self.plugins[plugin_name] = plugin_instance
                self.plugin_info[plugin_name] = plugin_instance.get_info()
                
                self.logger.info(f"Loaded plugin: {plugin_name}")
                return plugin_instance
                
            finally:
                # Restore original sys.path
                sys.path[:] = original_path
                
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return None
    
    def load_all_plugins(self) -> List[str]:
        """Load all discovered plugins"""
        discovered = self.discover_plugins()
        loaded = []
        
        for plugin_name in discovered:
            if self.load_plugin(plugin_name):
                loaded.append(plugin_name)
                
        return loaded
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePublishPlugin]:
        """Get a loaded plugin by name"""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List all loaded plugin names"""
        return list(self.plugins.keys())
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get information about a plugin"""
        return self.plugin_info.get(plugin_name)
    
    def get_plugins_by_capability(self, capability: str) -> List[str]:
        """Get plugins that support a specific capability"""
        matching = []
        for name, plugin in self.plugins.items():
            if plugin.supports_capability(capability):
                matching.append(name)
        return matching
    
    def get_one_click_plugins(self) -> List[str]:
        """Get plugins that support one-click deployment"""
        return self.get_plugins_by_capability("one-click-deploy")
    
    def validate_config(self, plugin_name: str, config: DeploymentConfig) -> tuple[bool, Optional[str]]:
        """Validate configuration for a specific plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return False, f"Plugin '{plugin_name}' not found"
            
        return plugin.validate_config(config)
