"""
Example UI Integration for Docker Publishing

This file shows how to integrate the Docker publishing functionality
into the Fractalic UI. This can be adapted for the actual UI implementation.
"""

import asyncio
import aiohttp
import json

class DockerPublishClient:
    """Client for interacting with the Docker Publish API"""
    
    def __init__(self, api_base_url="http://localhost:8080"):
        self.api_base_url = api_base_url
        
    async def start_publish(self, container_name="fractalic-published", port_offset=0):
        """Start a new publish operation"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "container_name": container_name,
                "port_offset": port_offset,
                "keep_temp": False
            }
            
            async with session.post(f"{self.api_base_url}/publish", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["operation_id"]
                else:
                    raise Exception(f"Failed to start publish: {response.status}")
    
    async def get_status(self, operation_id):
        """Get the status of a publish operation"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_base_url}/publish/status/{operation_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get status: {response.status}")
    
    async def wait_for_completion(self, operation_id, timeout=300):
        """Wait for a publish operation to complete"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            status = await self.get_status(operation_id)
            
            if status["status"] in ["completed", "failed"]:
                return status
                
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise Exception("Publish operation timed out")
                
            await asyncio.sleep(2)  # Poll every 2 seconds
    
    async def stop_container(self, container_name):
        """Stop a running container"""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_base_url}/containers/{container_name}/stop") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to stop container: {response.status}")
    
    async def list_containers(self):
        """List all Docker containers"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_base_url}/containers") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to list containers: {response.status}")

# Example usage functions that could be called from UI

async def publish_current_project():
    """Publish the current project to Docker - example UI function"""
    client = DockerPublishClient()
    
    try:
        # Start the publish operation
        print("🚀 Starting publish operation...")
        operation_id = await client.start_publish(
            container_name="fractalic-current-work",
            port_offset=0
        )
        print(f"   Operation ID: {operation_id}")
        
        # Wait for completion with progress updates
        print("⏳ Publishing in progress...")
        while True:
            status = await client.get_status(operation_id)
            print(f"   Status: {status['status']} - {status['message']}")
            
            if status["status"] == "completed":
                print("✅ Publish completed successfully!")
                print(f"   Container: {status['container_name']}")
                print("   Available services:")
                for service, port in status["ports"].items():
                    service_name = service.replace('_', ' ').title()
                    print(f"     • {service_name}: http://localhost:{port}")
                return status
                
            elif status["status"] == "failed":
                print("❌ Publish failed!")
                if status.get("error"):
                    print(f"   Error: {status['error']}")
                return status
                
            await asyncio.sleep(3)  # Update every 3 seconds
            
    except Exception as e:
        print(f"❌ Error during publish: {str(e)}")
        return None

async def list_published_containers():
    """List published containers - example UI function"""
    client = DockerPublishClient()
    
    try:
        result = await client.list_containers()
        containers = result["containers"]
        
        print("📦 Published Containers:")
        for container in containers:
            name = container.get("Names", "unknown")
            status = container.get("State", "unknown")
            ports = container.get("Ports", "")
            
            print(f"   • {name} - {status}")
            if ports:
                print(f"     Ports: {ports}")
                
        return containers
        
    except Exception as e:
        print(f"❌ Error listing containers: {str(e)}")
        return []

async def stop_published_container(container_name):
    """Stop a published container - example UI function"""
    client = DockerPublishClient()
    
    try:
        result = await client.stop_container(container_name)
        print(f"✅ Container {container_name} stopped")
        return True
        
    except Exception as e:
        print(f"❌ Error stopping container {container_name}: {str(e)}")
        return False

# Example CLI interface for testing
async def main():
    """Example CLI interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ui_integration_example.py <command>")
        print("Commands: publish, list, stop <container_name>")
        return
    
    command = sys.argv[1]
    
    if command == "publish":
        await publish_current_project()
    elif command == "list":
        await list_published_containers()
    elif command == "stop" and len(sys.argv) > 2:
        container_name = sys.argv[2]
        await stop_published_container(container_name)
    else:
        print("Unknown command")

if __name__ == "__main__":
    asyncio.run(main())
