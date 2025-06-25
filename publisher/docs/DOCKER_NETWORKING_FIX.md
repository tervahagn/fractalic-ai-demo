# Docker Registry Deployment Issue: Frontend-Backend Connection

## Problem Analysis

When deploying from a locally running Fractalic instance to a Docker container, there's a networking configuration issue where the deployed container's frontend doesn't properly connect to its own internal backend services.

## Current Architecture

### Local Development
- Frontend: `localhost:3000` → Backend: `localhost:8000`
- AI Server: `localhost:8001` 
- MCP Manager: `localhost:5859`

### Deployed Container (Current Issue)
- **Host Access**: `localhost:3001` (mapped port)
- **Container Internal**: 
  - Frontend: port 3000 (internal)
  - Backend: port 8000 (internal) ✅
  - AI Server: port 8001 (internal) ✅
  - MCP Manager: port 5859 (internal) ✅

## Root Cause

The Docker Registry plugin correctly configures internal container networking, but there may be issues with:

1. **Frontend configuration not being applied correctly**
2. **Next.js rewrites not working as expected**
3. **Config.json not being served properly**
4. **Environment variables overriding container config**

## Solution: Enhanced Container Configuration

### 1. Fix Frontend Environment Variables

Update the docker-registry plugin to ensure proper environment variable configuration:

```python
def _fix_frontend_environment(self, container_name: str, config: Dict[str, Any]) -> None:
    """Set proper environment variables for container-internal networking"""
    
    # Create .env.local with INTERNAL container networking URLs
    env_content = '''# Container internal networking - DO NOT use host-mapped ports
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_AI_API_BASE_URL=http://localhost:8001  
NEXT_PUBLIC_MCP_API_BASE_URL=http://localhost:5859

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
        os.unlink(tmp_env_path)
```

### 2. Verify Service Startup Order

Ensure all services are running before declaring deployment complete:

```python
def _wait_for_services(self, container_name: str, config: Dict[str, Any], progress_callback=None) -> bool:
    """Wait for all services to be ready before completing deployment"""
    import time
    import requests
    
    services = {
        "backend": 8000,
        "ai_server": 8001, 
        "mcp_manager": 5859,
        "frontend": 3000
    }
    
    max_attempts = 30
    for attempt in range(max_attempts):
        all_ready = True
        
        for service, port in services.items():
            try:
                # Check if service is responding inside container
                result = self._run_command([
                    "docker", "exec", container_name,
                    "curl", "-sf", f"http://localhost:{port}/health"
                ], timeout=5)
                
                if result.returncode != 0:
                    all_ready = False
                    break
                    
            except Exception:
                all_ready = False
                break
        
        if all_ready:
            if progress_callback:
                progress_callback("✅ All services ready", "health_check", 95)
            return True
            
        if progress_callback and attempt % 5 == 0:
            progress_callback(f"⏳ Waiting for services... ({attempt}/{max_attempts})", "health_check", 85 + (attempt * 10 // max_attempts))
        
        time.sleep(2)
    
    return False
```

### 3. Enhanced Next.js Config Validation

Ensure the Next.js config is properly applied:

```python
def _validate_nextjs_config(self, container_name: str) -> bool:
    """Validate that Next.js config was applied correctly"""
    try:
        # Check if the config file exists and has correct content
        result = self._run_command([
            "docker", "exec", container_name,
            "cat", "/fractalic-ui/next.config.mjs"
        ])
        
        config_content = result.stdout
        required_patterns = [
            "async rewrites()",
            "source: '/list_directory'",
            "destination: 'http://localhost:8000",
            "source: '/mcp/:path*'",
            "destination: 'http://localhost:5859"
        ]
        
        for pattern in required_patterns:
            if pattern not in config_content:
                self.logger.error(f"Missing required pattern in next.config.mjs: {pattern}")
                return False
        
        self.logger.info("Next.js config validation passed")
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to validate Next.js config: {e}")
        return False
```

### 4. Force Frontend Restart

Restart the frontend service after configuration changes:

```python
def _restart_frontend_service(self, container_name: str, progress_callback=None) -> None:
    """Restart the frontend service to pick up new configuration"""
    
    if progress_callback:
        progress_callback("🔄 Restarting frontend with new config", "configuring", 75)
    
    try:
        # Kill the existing frontend process
        self._run_command([
            "docker", "exec", container_name,
            "supervisorctl", "stop", "frontend"
        ])
        
        # Wait a moment
        import time
        time.sleep(2)
        
        # Start frontend with new config
        self._run_command([
            "docker", "exec", container_name,
            "supervisorctl", "start", "frontend"
        ])
        
        # Wait for frontend to start
        time.sleep(5)
        
        if progress_callback:
            progress_callback("✅ Frontend restarted with new config", "configuring", 80)
            
        self.logger.info("Frontend service restarted successfully")
        
    except Exception as e:
        self.logger.error(f"Failed to restart frontend service: {e}")
        if progress_callback:
            progress_callback(f"⚠️ Frontend restart failed: {e}", "configuring", 80)
```

### 5. Updated Deployment Flow

Modify the main publish method to include all fixes:

```python
def publish(self, request: PublishRequest, progress_callback=None) -> PublishResponse:
    """Enhanced publish method with proper container networking"""
    try:
        # ... existing steps ...
        
        # After container starts and files are copied:
        
        # 1. Fix frontend environment variables
        if progress_callback:
            progress_callback("🔧 Configuring frontend environment", "configuring", 70)
        self._fix_frontend_environment(container_name, config)
        
        # 2. Apply Next.js configuration
        if progress_callback:
            progress_callback("🔧 Applying Next.js configuration", "configuring", 72)
        self._fix_nextjs_config(container_name, config)
        
        # 3. Validate configuration
        if progress_callback:
            progress_callback("✅ Validating configuration", "configuring", 74)
        config_valid = self._validate_nextjs_config(container_name)
        
        # 4. Restart frontend to pick up changes
        self._restart_frontend_service(container_name, progress_callback)
        
        # 5. Wait for all services to be ready
        if progress_callback:
            progress_callback("⏳ Waiting for services to start", "health_check", 85)
        services_ready = self._wait_for_services(container_name, config, progress_callback)
        
        # ... rest of method ...
        
        success = config_valid and services_ready and all(health_status.values())
        
        return PublishResponse(
            success=success,
            message=f"Deployment {'completed successfully' if success else 'completed with issues'}",
            endpoint_url=urls.get("frontend", ""),
            deployment_id=container_id[:12],
            metadata={
                "container_name": container_name,
                "container_id": container_id,
                "urls": urls,
                "config_valid": config_valid,
                "services_ready": services_ready,
                "health_status": health_status
            }
        )
```

## Debugging Tools

### 1. Container Network Inspection

Add debugging endpoints to verify internal networking:

```python
def _debug_container_networking(self, container_name: str) -> Dict[str, Any]:
    """Debug container networking configuration"""
    debug_info = {}
    
    try:
        # Check which ports are listening
        result = self._run_command([
            "docker", "exec", container_name,
            "netstat", "-tlnp"
        ])
        debug_info["listening_ports"] = result.stdout
        
        # Check if services respond internally
        for service, port in {"backend": 8000, "ai_server": 8001, "mcp_manager": 5859}.items():
            try:
                result = self._run_command([
                    "docker", "exec", container_name,
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    f"http://localhost:{port}/health"
                ])
                debug_info[f"{service}_status"] = result.stdout.strip()
            except:
                debug_info[f"{service}_status"] = "error"
        
        # Check frontend config
        try:
            result = self._run_command([
                "docker", "exec", container_name,
                "head", "-20", "/fractalic-ui/next.config.mjs"
            ])
            debug_info["nextjs_config"] = result.stdout
        except:
            debug_info["nextjs_config"] = "error reading config"
            
    except Exception as e:
        debug_info["error"] = str(e)
    
    return debug_info
```

### 2. UI Deployment Verification

Update the UI task to include verification steps:

```markdown
## Verification Steps

After deployment, the modal should verify:

1. **Container Health**: All services responding internally
2. **Frontend Config**: Next.js rewrites properly configured  
3. **API Connectivity**: Frontend can reach backend APIs
4. **External Access**: Host machine can access container UI

## Success Indicators

- ✅ Container running and all ports mapped
- ✅ Frontend loads without JavaScript errors
- ✅ Backend APIs responding (can load file tree, settings)
- ✅ MCP servers visible in UI
- ✅ Settings can be loaded and saved
- ✅ File operations work (create, edit, save files)

## Troubleshooting

If deployment succeeds but UI doesn't work:

1. Check browser console for API errors
2. Verify container logs: `docker logs [container-name]`
3. Test internal connectivity: `docker exec [container] curl localhost:8000/health`
4. Check Next.js config: `docker exec [container] cat /fractalic-ui/next.config.mjs`
5. Verify environment: `docker exec [container] cat /fractalic-ui/.env.local`
```

This comprehensive solution addresses the frontend-backend connection issues by:

1. **Ensuring proper environment variables** for container networking
2. **Validating configuration application** 
3. **Restarting services** to pick up changes
4. **Waiting for services** to be fully ready
5. **Providing debugging tools** for troubleshooting

The key insight is that the container networking should work correctly, but the configuration application and service startup timing need to be more robust.
