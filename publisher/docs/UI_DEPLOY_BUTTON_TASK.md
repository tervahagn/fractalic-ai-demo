# Deploy Button UI Implementation Task

## Overview
Implement a **Deploy** button in the Fractalic UI that allows users to deploy their current script to a Docker container using the existing Docker Registry deployment API. The button should be placed next to the Settings button and provide real-time progress feedback through a modal interface.

## Backend API Context
The backend server (`http://localhost:8003`) already provides fully functional deployment endpoints:

### Available Endpoints:
1. **Non-streaming**: `POST /api/deploy/docker-registry`
2. **Streaming (use this)**: `POST /api/deploy/docker-registry/stream`

### Required Request Payload:
```json
{
  "image_name": "ghcr.io/fractalic-ai/fractalic",
  "image_tag": "latest", 
  "script_name": "user-script-name",
  "script_folder": "/path/to/script/directory"
}
```

### Response Format (Server-Sent Events):
```json
{
  "deployment_id": "uuid",
  "timestamp": "2025-06-25T01:13:20.593431",
  "message": "🚀 Starting Docker registry deployment",
  "stage": "validating", 
  "progress": 5
}
```

### Deployment Stages:
- `validating` (5% progress)
- `pulling_image` (10-30% progress) 
- `preparing_files` (35% progress)
- `creating_container` (40-60% progress)
- `starting_container` (70-90% progress)
- `completed` (100% progress) with final results
- `error` (100% progress) with error details

## UI Implementation Requirements

### 1. Deploy Button Placement
**File**: `components/Header.tsx`

Add a **Deploy** button next to the existing Settings button:

```tsx
// Add this import
import { Rocket } from 'lucide-react'

// In the header buttons section, add:
<Button 
  variant="ghost" 
  size="sm" 
  onClick={() => setIsDeployOpen(true)}
  className="text-green-400 hover:text-green-300"
>
  <Rocket className="h-4 w-4 mr-2" />
  Deploy
</Button>
```

### 2. Deploy Modal Component
**File**: `components/DeployModal.tsx` (new file)

Create a comprehensive modal component that:

#### Props Interface:
```tsx
interface DeployModalProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  currentFilePath?: string;
  repoPath?: string;
}
```

#### Modal Sections:

1. **Header**: "Deploy to Docker Container"
2. **Script Info Display**:
   - Current script name (extracted from currentFilePath)
   - Script directory (parent directory of currentFilePath)
   - Container image: `ghcr.io/fractalic-ai/fractalic:latest`

3. **Deployment Progress Section**:
   - Progress bar (0-100%)
   - Current stage indicator
   - Real-time status messages
   - Deployment ID display

4. **Deployment Results Section** (shown after completion):
   - Success/failure status
   - Container information
   - Access URLs (if successful)
   - Error details (if failed)

5. **Action Buttons**:
   - "Deploy" button (start deployment)
   - "Close" button (available throughout)
   - "View Logs" button (optional, for detailed logs)

#### Key Features:
- **Real-time SSE streaming** from `/api/deploy/docker-registry/stream`
- **Progress visualization** with animated progress bar
- **Stage-based status icons** (spinner, checkmark, error)
- **Responsive error handling** with retry capability
- **Auto-scroll logs** for deployment messages

### 3. State Management Integration
**File**: `components/GitDiffViewer.tsx`

Add deploy modal state management:

```tsx
const [isDeployOpen, setIsDeployOpen] = useState(false);

// Pass to Header component:
<Header 
  // ...existing props
  isDeployOpen={isDeployOpen}
  setIsDeployOpen={setIsDeployOpen}
/>

// Add DeployModal at the end:
<DeployModal 
  isOpen={isDeployOpen}
  setIsOpen={setIsDeployOpen}
  currentFilePath={currentFilePath}
  repoPath={currentGitPath}
/>
```

### 4. Header Component Updates
**File**: `components/Header.tsx`

Update interface and add deploy button:

```tsx
interface HeaderProps {
  theme: 'dark' | 'light'
  setTheme: (theme: 'dark' | 'light') => void
  isSettingsOpen: boolean
  setIsSettingsOpen: (isOpen: boolean) => void
  isDeployOpen: boolean          // Add this
  setIsDeployOpen: (isOpen: boolean) => void  // Add this
}
```

### 5. Utility Functions
**File**: `utils/deployUtils.ts` (new file)

Create helper functions:

```tsx
export interface DeploymentStatus {
  deployment_id: string;
  stage: string;
  progress: number;
  message: string;
  timestamp: string;
  error?: string;
  result?: {
    success: boolean;
    deployment_id: string;
    endpoint_url: string;
    metadata: any;
  };
}

export function parseDeploymentEvent(data: string): DeploymentStatus | null;
export function getScriptNameFromPath(filePath: string): string;
export function getScriptDirectory(filePath: string): string;
export function createDeploymentPayload(filePath: string, repoPath: string): object;
```

## Technical Implementation Details

### 1. Server-Sent Events (SSE) Handling

```tsx
const eventSource = new EventSource('/api/deploy/docker-registry/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(payload)
});

eventSource.onmessage = (event) => {
  const data = parseDeploymentEvent(event.data);
  if (data) {
    setDeploymentStatus(data);
    updateProgress(data.progress);
    addLogMessage(data.message);
  }
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  handleDeploymentError(error);
};
```

### 2. Progress Animation

Use Framer Motion or CSS transitions for smooth progress bar updates:

```tsx
<div className="w-full bg-gray-200 rounded-full h-2.5">
  <div 
    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
    style={{ width: `${progress}%` }}
  />
</div>
```

### 3. Stage Icons and Messages

```tsx
const getStageIcon = (stage: string, isActive: boolean) => {
  switch (stage) {
    case 'validating': return <CheckCircle className={isActive ? 'animate-spin' : ''} />;
    case 'pulling_image': return <Download className={isActive ? 'animate-bounce' : ''} />;
    case 'preparing_files': return <FileText className={isActive ? 'animate-pulse' : ''} />;
    case 'creating_container': return <Box className={isActive ? 'animate-spin' : ''} />;
    case 'starting_container': return <Play className={isActive ? 'animate-pulse' : ''} />;
    case 'completed': return <CheckCircle className="text-green-500" />;
    case 'error': return <AlertCircle className="text-red-500" />;
    default: return <Clock />;
  }
};
```

### 4. Error Handling

```tsx
const handleDeploymentError = (error: any) => {
  setDeploymentStatus(prev => ({
    ...prev,
    stage: 'error',
    progress: 100,
    error: error.message || 'Deployment failed',
    message: `❌ Deployment failed: ${error.message}`
  }));
  setIsDeploying(false);
};
```

## File Structure
```
fractalic-ui/
├── components/
│   ├── Header.tsx                 (modified)
│   ├── GitDiffViewer.tsx         (modified)
│   ├── DeployModal.tsx           (new)
│   └── ui/
│       ├── progress.tsx          (use existing)
│       └── dialog.tsx            (use existing)
├── utils/
│   └── deployUtils.ts            (new)
└── hooks/
    └── useDeployment.ts          (new, optional)
```

## Success Criteria

1. **Deploy button visible** next to Settings button
2. **Modal opens** when Deploy button is clicked
3. **Real-time progress** updates during deployment
4. **Proper error handling** for failed deployments
5. **Success state** shows deployment results and access URLs
6. **Responsive design** works on different screen sizes
7. **Accessibility** - proper ARIA labels and keyboard navigation

## Additional Considerations

1. **Current File Detection**: Extract script name from `currentFilePath` state
2. **Directory Validation**: Ensure script directory exists before deployment
3. **Default Values**: Use sensible defaults for image name/tag
4. **Connection Status**: Handle network disconnection gracefully
5. **Modal Persistence**: Keep modal open during deployment process
6. **User Feedback**: Clear visual indicators for each deployment stage

## Testing Scenarios

1. **Happy Path**: Deploy a valid script successfully
2. **Invalid Script**: Handle missing script folder error
3. **Network Error**: Handle connection issues during deployment
4. **Server Error**: Handle backend validation errors
5. **Long Deployment**: Test progress updates over time
6. **Multiple Deployments**: Ensure modal resets properly between uses

## Dependencies

The following UI components and utilities should already be available:
- Button, Dialog, Progress components from `@/components/ui/`
- Lucide React icons
- Tailwind CSS for styling
- TypeScript interfaces and types
- `useAppConfig` hook for API configuration

## API Integration Notes

- Use the **streaming endpoint** (`/api/deploy/docker-registry/stream`) for real-time updates
- Server runs on `http://localhost:8003` (configurable via `useAppConfig`)
- Handle HTTP 400 errors for validation failures
- Handle HTTP 500 errors for server issues
- Parse Server-Sent Events data as JSON
- Maintain deployment state throughout the process
