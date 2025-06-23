"""
Base plugin interface for Fractalic Publisher System
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

try:
    from .models import PluginInfo, DeploymentConfig, PublishResult, DeploymentInfo, ProgressCallback
except ImportError:
    from models import PluginInfo, DeploymentConfig, PublishResult, DeploymentInfo, ProgressCallback


class BasePublishPlugin(ABC):
    """Base class for all publish plugins"""
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Get plugin information and capabilities"""
        pass
    
    @abstractmethod
    def validate_config(self, config: DeploymentConfig) -> tuple[bool, Optional[str]]:
        """
        Validate deployment configuration
        Returns: (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def publish(self, source_path: str, config: DeploymentConfig, progress_callback: Optional[ProgressCallback] = None) -> PublishResult:
        """
        Publish the application
        
        Args:
            source_path: Path to the Fractalic source code
            config: Deployment configuration
            progress_callback: Optional callback for progress updates
            
        Returns:
            PublishResult with deployment information
        """
        pass
    
    @abstractmethod
    def get_deployment_info(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get information about a specific deployment"""
        pass
    
    @abstractmethod
    def list_deployments(self) -> List[DeploymentInfo]:
        """List all deployments managed by this plugin"""
        pass
    
    @abstractmethod
    def stop_deployment(self, deployment_id: str) -> bool:
        """Stop a deployment"""
        pass
    
    @abstractmethod
    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment"""
        pass
    
    @abstractmethod
    def get_logs(self, deployment_id: str, lines: int = 100) -> Optional[str]:
        """Get deployment logs"""
        pass
    
    def supports_capability(self, capability: str) -> bool:
        """Check if plugin supports a specific capability"""
        info = self.get_info()
        return any(cap.value == capability for cap in info.capabilities)
    
    def get_deploy_button_markdown(self, config: DeploymentConfig) -> str:
        """
        Generate Markdown for a deploy button that can be added to README.
        Should return a clickable badge/button that triggers deployment.
        """
        info = self.get_info()
        if not info.badge_url:
            return ""
        
        # Generate deploy URL with parameters
        deploy_url = self.generate_deploy_url(config)
        
        return f"[![Deploy to {info.display_name}]({info.badge_url})]({deploy_url})"
    
    def generate_deploy_url(self, config: DeploymentConfig) -> str:
        """
        Generate a URL that can trigger deployment.
        For local plugins, this might be a script or command.
        For cloud platforms, this would be their one-click deploy URL.
        """
        return "#"  # Default placeholder
