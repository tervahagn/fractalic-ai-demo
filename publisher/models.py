"""
Data models for the Fractalic Publisher Plugin System
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class DeploymentStatus(Enum):
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class PluginCapability(Enum):
    ONE_CLICK_DEPLOY = "one-click-deploy"
    GIT_INTEGRATION = "git-integration"
    CUSTOM_DOMAINS = "custom-domains"
    AUTO_SCALING = "auto-scaling"
    FREE_TIER = "free-tier"
    INSTANT_PREVIEW = "instant-preview"


@dataclass
class PluginInfo:
    """Information about a deployment plugin"""
    name: str
    display_name: str
    description: str
    version: str
    homepage_url: str
    documentation_url: str
    capabilities: List[PluginCapability]
    pricing_info: str
    setup_difficulty: str  # "easy", "medium", "advanced"
    deploy_time_estimate: str  # "< 1 min", "2-5 min", etc.
    free_tier_limits: str
    badge_url: Optional[str] = None  # For README badges
    deploy_button_url: Optional[str] = None  # One-click deploy URL


@dataclass
class DeploymentConfig:
    """Configuration for a deployment"""
    plugin_name: str
    container_name: str
    environment_vars: Dict[str, str]
    port_mapping: Dict[int, int]
    custom_domain: Optional[str] = None
    scaling_config: Optional[Dict[str, Any]] = None
    plugin_specific: Optional[Dict[str, Any]] = None  # Plugin-specific config
    port_offset: int = 0  # Port offset for avoiding conflicts


@dataclass
class PublishResult:
    """Result of a publish operation"""
    success: bool
    deployment_id: str
    message: str = ""
    url: Optional[str] = None
    admin_url: Optional[str] = None
    logs_url: Optional[str] = None
    build_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DeploymentInfo:
    """Information about a deployed application"""
    deployment_id: str
    status: DeploymentStatus
    url: Optional[str] = None
    created_at: Optional[float] = None  # Unix timestamp
    last_updated: Optional[float] = None  # Unix timestamp
    plugin_name: Optional[str] = None
    container_name: Optional[str] = None
    resource_usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PublishRequest:
    """Request for publishing/deployment"""
    config: Dict[str, Any]
    script_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PublishResponse:
    """Response from publishing/deployment"""
    success: bool
    message: str
    endpoint_url: str
    deployment_id: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DeploymentStatusInfo:
    """Detailed deployment status information"""
    deployment_id: str
    status: str
    is_healthy: bool
    last_updated: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DockerRegistryDeploymentConfig:
    """Configuration for Docker Registry Plugin deployment"""
    image_name: str
    container_name: str
    ports: Dict[str, int]  # service_name -> port_number
    environment_vars: Dict[str, str]
    script_content: str
    volumes: Optional[Dict[str, str]] = None  # host_path -> container_path
    network_mode: Optional[str] = None
    restart_policy: str = "unless-stopped"


@dataclass 
class DeploymentResult:
    """Result of a deployment operation"""
    success: bool
    container_id: Optional[str] = None
    ports: Optional[Dict[str, int]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


ProgressCallback = Callable[[str, int], None]  # message, percentage
