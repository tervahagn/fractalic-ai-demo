# Real-Time Docker Deployment Streaming Guide

## Overview

The Fractalic UI Server provides real-time Docker deployment progress streaming via Server-Sent Events (SSE). This allows the frontend to display detailed progress, logs, and results during the deployment process.

## API Endpoints

### Streaming Deployment
```http
POST /api/deploy/docker-registry/stream
Content-Type: application/json

{
  "script_name": "my-script",
  "script_folder": "/path/to/script/folder",
  "container_name": "fractalic-my-script",
  "registry_image": "ghcr.io/fractalic-ai/fractalic:latest",
  "platform": "linux/amd64",
  "ports": {
    "frontend": 3000,
    "backend": 8000,
    "ai_server": 8001,
    "mcp_manager": 5859
  },
  "env_vars": {
    "CUSTOM_VAR": "value"
  }
}
```

**Response:** Server-Sent Events stream

### Progress Polling (Alternative)
```http
GET /api/deploy/progress/{deployment_id}
```

## Required Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `script_name` | ✅ | Name of the script/project | - |
| `script_folder` | ✅ | Path to script folder | - |
| `container_name` | ❌ | Docker container name | `fractalic-{script_name}` |
| `registry_image` | ❌ | Base Docker image | `ghcr.io/fractalic-ai/fractalic:latest` |
| `platform` | ❌ | Target platform | Auto-detected |
| `ports` | ❌ | Port mappings | Default ports |
| `env_vars` | ❌ | Environment variables | `{}` |

## Frontend Integration

### JavaScript/TypeScript Example

```javascript
async function deployWithProgress(deploymentConfig) {
  const eventSource = new EventSource('/api/deploy/docker-registry/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(deploymentConfig)
  });

  return new Promise((resolve, reject) => {
    eventSource.onmessage = function(event) {
      const data = JSON.parse(event.data);
      
      // Update progress UI
      updateProgress(data.progress, data.message, data.stage);
      
      // Handle completion
      if (data.result) {
        eventSource.close();
        if (data.result.success) {
          resolve(data.result);
        } else {
          reject(new Error(data.result.message));
        }
      }
    };

    eventSource.onerror = function(event) {
      eventSource.close();
      reject(new Error('Deployment stream failed'));
    };
  });
}

function updateProgress(progress, message, stage) {
  // Update progress bar
  document.getElementById('progress-bar').style.width = `${progress}%`;
  document.getElementById('progress-text').textContent = `${progress}%`;
  
  // Add log message
  const logContainer = document.getElementById('logs');
  const logEntry = document.createElement('div');
  logEntry.className = `log-entry stage-${stage}`;
  logEntry.innerHTML = `
    <span class="timestamp">${new Date().toLocaleTimeString()}</span>
    <span class="message">${message}</span>
  `;
  logContainer.appendChild(logEntry);
  logContainer.scrollTop = logContainer.scrollHeight;
}
```

### React Hook Example

```typescript
import { useState, useEffect } from 'react';

interface DeploymentProgress {
  deploymentId: string;
  progress: number;
  message: string;
  stage: string;
  timestamp: string;
  result?: {
    success: boolean;
    message: string;
    endpoint_url: string;
    deployment_id: string;
    metadata: any;
  };
}

export function useDeploymentProgress() {
  const [progress, setProgress] = useState<DeploymentProgress[]>([]);
  const [isDeploying, setIsDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deploy = async (config: DeploymentConfig) => {
    setIsDeploying(true);
    setProgress([]);
    setError(null);

    try {
      const response = await fetch('/api/deploy/docker-registry/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (reader && isDeploying) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              setProgress(prev => [...prev, data]);
              
              if (data.result) {
                setIsDeploying(false);
                return data.result;
              }
            } catch (e) {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deployment failed');
      setIsDeploying(false);
    }
  };

  return { progress, isDeploying, error, deploy };
}
```

## Progress Stages

The deployment goes through these stages with corresponding progress percentages:

| Stage | Progress | Description |
|-------|----------|-------------|
| `validating` | 5% | Validating configuration |
| `pulling_image` | 10-30% | Pulling Docker image |
| `preparing_files` | 35-45% | Preparing user files |
| `starting_container` | 50-65% | Starting Docker container |
| `copying_files` | 70-85% | Copying files to container |
| `health_check` | 90-100% | Health checking services |
| `completed` | 100% | Deployment complete |
| `error` | 100% | Deployment failed |

## Response Format

### Progress Update
```json
{
  "deployment_id": "uuid-123",
  "timestamp": "2025-01-25T10:30:00.123456",
  "message": "📥 Pulling base image: ghcr.io/fractalic-ai/fractalic:latest",
  "stage": "pulling_image",
  "progress": 15
}
```

### Final Result
```json
{
  "deployment_id": "uuid-123",
  "timestamp": "2025-01-25T10:32:00.123456",
  "message": "Deployment completed",
  "stage": "completed",
  "progress": 100,
  "result": {
    "success": true,
    "message": "Deployment completed successfully",
    "endpoint_url": "http://localhost:32768",
    "deployment_id": "container_abc123",
    "metadata": {
      "urls": {
        "frontend": "http://localhost:32768",
        "backend": "http://localhost:32769",
        "ai_server": "http://localhost:32770",
        "mcp_manager": "http://localhost:32771"
      },
      "health_status": {
        "frontend": true,
        "backend": true,
        "ai_server": true,
        "mcp_manager": false
      }
    }
  }
}
```

### Error Response
```json
{
  "deployment_id": "uuid-123",
  "timestamp": "2025-01-25T10:31:00.123456",
  "message": "Deployment failed: Docker image not found",
  "stage": "error",
  "progress": 100,
  "error": "Docker image not found"
}
```

## Example UI Components

### Progress Bar Component
```css
.deployment-progress {
  max-width: 600px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background-color: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin: 10px 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #45a049);
  transition: width 0.3s ease;
}

.logs {
  max-height: 300px;
  overflow-y: auto;
  background: #1e1e1e;
  color: #ffffff;
  padding: 15px;
  border-radius: 5px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

.log-entry {
  margin: 2px 0;
  padding: 2px 0;
}

.log-entry .timestamp {
  color: #888;
  margin-right: 10px;
}

.stage-pulling_image { color: #3498db; }
.stage-preparing_files { color: #f39c12; }
.stage-starting_container { color: #9b59b6; }
.stage-copying_files { color: #e67e22; }
.stage-health_check { color: #2ecc71; }
.stage-completed { color: #27ae60; font-weight: bold; }
.stage-error { color: #e74c3c; font-weight: bold; }
```

## Testing

You can test the streaming deployment using curl:

```bash
curl -X POST http://localhost:8000/api/deploy/docker-registry/stream \
  -H "Content-Type: application/json" \
  -d '{
    "script_name": "test-script",
    "script_folder": "/path/to/your/script"
  }' \
  --no-buffer -N
```

Or open the included demo HTML file:
```
open docker-deployment-demo.html
```

## Error Handling

Always handle these potential errors:

1. **Network errors** - Connection lost during streaming
2. **Validation errors** - Invalid deployment configuration
3. **Docker errors** - Image not found, permission issues
4. **Resource errors** - Insufficient ports, disk space
5. **Timeout errors** - Long-running operations

## Best Practices

1. **Show visual progress** - Use progress bars and status indicators
2. **Display logs** - Show detailed progress messages to users
3. **Handle errors gracefully** - Provide clear error messages and recovery options
4. **Allow cancellation** - Provide a way to stop deployment if needed
5. **Persist state** - Save deployment status for page refreshes
6. **Test thoroughly** - Test with various deployment scenarios

## Advanced Features

### Custom Progress Callbacks
The Docker registry plugin supports custom progress callbacks that can be extended:

```python
def custom_progress_callback(message: str, stage: str, progress: int):
    # Custom logic for progress tracking
    # Could send to external monitoring systems
    # Could trigger webhooks
    # Could update database records
    pass
```

### WebSocket Alternative
For bidirectional communication or more advanced features, you could implement WebSocket support alongside SSE.

### Deployment History
Consider implementing deployment history tracking to show past deployments and their status.
