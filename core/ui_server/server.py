# server.py
import asyncio
import sys
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import git
from pathlib import Path
import json
import os
import toml
from fastapi.responses import FileResponse, Response
import logging
import subprocess
import signal
import aiohttp
import time
from typing import Optional, Dict, Any, List

# --- Robust import for ToolRegistry regardless of working directory ---
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from core.plugins.tool_registry import ToolRegistry

logging.getLogger("git").setLevel(logging.CRITICAL)
logging.getLogger("git.cmd").setLevel(logging.CRITICAL)

app = FastAPI()

current_repo_path = ""

# MCP Manager process management
mcp_manager_process: Optional[subprocess.Popen] = None
mcp_manager_port = 5859
mcp_manager_url = f"http://localhost:{mcp_manager_port}"

# Set BASE_DIR to the root directory to allow navigation to parent directories
BASE_DIR = Path('/').resolve()

# Mount static files (HTML, CSS, JS)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Enable CORS for static files
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins since everything is local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the settings file path
SETTINGS_FILE_PATH = '../../settings.toml'

def set_repo_path(path: str):
    """Set the current repository path globally"""
    global current_repo_path
    current_repo_path = path

# MCP Manager process management functions
async def start_mcp_manager():
    """Start the MCP manager process"""
    global mcp_manager_process
    
    if mcp_manager_process and mcp_manager_process.poll() is None:
        return {"status": "already_running", "pid": mcp_manager_process.pid}
    
    try:
        # Path to the MCP manager script
        mcp_manager_script = Path(project_root) / "fractalic_mcp_manager.py"
        
        if not mcp_manager_script.exists():
            raise HTTPException(status_code=500, detail=f"MCP manager script not found at {mcp_manager_script}")
          # Start the MCP manager process
        mcp_manager_process = subprocess.Popen(
            [sys.executable, str(mcp_manager_script), "--port", str(mcp_manager_port), "serve"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        await asyncio.sleep(2)
        
        # Check if process is still running
        if mcp_manager_process.poll() is not None:
            # Process died, read error output
            stdout, stderr = mcp_manager_process.communicate()
            error_msg = f"MCP manager failed to start. stdout: {stdout}, stderr: {stderr}"
            mcp_manager_process = None
            raise HTTPException(status_code=500, detail=error_msg)
        
        return {"status": "started", "pid": mcp_manager_process.pid, "port": mcp_manager_port}
        
    except Exception as e:
        mcp_manager_process = None
        raise HTTPException(status_code=500, detail=f"Failed to start MCP manager: {str(e)}")

async def stop_mcp_manager():
    """Stop the MCP manager process"""
    global mcp_manager_process
    
    if not mcp_manager_process or mcp_manager_process.poll() is not None:
        return {"status": "not_running"}
    
    try:
        # First, try to gracefully shutdown via API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{mcp_manager_url}/kill") as response:
                    if response.status == 200:
                        # Wait for process to terminate
                        for _ in range(10):  # Wait up to 10 seconds
                            if mcp_manager_process.poll() is not None:
                                break
                            await asyncio.sleep(1)
        except:
            pass  # Graceful shutdown failed, continue with forceful termination
        
        # If still running, force terminate
        if mcp_manager_process.poll() is None:
            mcp_manager_process.terminate()
            
            # Wait for termination
            for _ in range(5):  # Wait up to 5 seconds
                if mcp_manager_process.poll() is not None:
                    break
                await asyncio.sleep(1)
            
            # If still running, kill forcefully
            if mcp_manager_process.poll() is None:
                mcp_manager_process.kill()
                mcp_manager_process.wait()
        
        pid = mcp_manager_process.pid
        mcp_manager_process = None
        return {"status": "stopped", "pid": pid}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def get_mcp_manager_status():
    """Get the status of the MCP manager process"""
    global mcp_manager_process
    
    if not mcp_manager_process:
        return {"status": "not_started", "running": False, "api_responsive": False}
    
    poll_result = mcp_manager_process.poll()
    if poll_result is not None:
        # Process has terminated
        pid = mcp_manager_process.pid if mcp_manager_process else None
        mcp_manager_process = None
        return {
            "status": "terminated", 
            "running": False, 
            "api_responsive": False,
            "exit_code": poll_result,
            "last_pid": pid
        }
    
    # Process is running, try to connect to API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{mcp_manager_url}/status", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "running",
                        "running": True,
                        "pid": mcp_manager_process.pid,
                        "port": mcp_manager_port,
                        "api_responsive": True,
                        "servers": data
                    }
                else:
                    return {
                        "status": "running_not_responsive",
                        "running": True,
                        "pid": mcp_manager_process.pid,
                        "port": mcp_manager_port,
                        "api_responsive": False,
                        "http_status": response.status
                    }
    except Exception as e:
        return {
            "status": "running_not_responsive",
            "running": True,
            "pid": mcp_manager_process.pid,
            "port": mcp_manager_port,
            "api_responsive": False,
            "connection_error": str(e)
        }

# Cleanup function for graceful shutdown
async def cleanup_mcp_manager():
    """Cleanup MCP manager process on shutdown"""
    if mcp_manager_process and mcp_manager_process.poll() is None:
        try:
            await stop_mcp_manager()
        except:
            pass

# Helper functions
def get_repo(repo_path: str):
    resolved_path = Path(repo_path).resolve()
    if not resolved_path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid repository path")
    try:
        repo = git.Repo(resolved_path)
        set_repo_path(resolved_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing git repository: {e}")
    return repo

def get_file_content(repo, commit_hash, filepath):
    try:
        file_content = repo.git.show(f'{commit_hash}:{filepath}')
        return file_content
    except Exception as e:
        print(f"Error fetching '{filepath}' at commit '{commit_hash}': {e}")
        return ""

def ensure_empty_lines_before_symbols(text):
    lines = text.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        if line.startswith('#') or line.startswith('@'):
            if i > 0 and lines[i - 1].strip() != '':
                new_lines.append('')
        new_lines.append(line)
    return '\n'.join(new_lines)

def enrich_call_tree(node, repo):
    operation_src_list = node.get('operation_src', [])
    if operation_src_list and isinstance(operation_src_list[0], str):
        operation_src = operation_src_list[0]
    else:
        operation_src = "No Operation Source"

    filename = node.get('filename')
    ctx_file = node.get('ctx_file')
    trc_file = node.get('trc_file')  # Add this line to get trc_file
    md_commit_hash = node.get('md_commit_hash')
    ctx_commit_hash = node.get('ctx_commit_hash')
    trc_commit_hash = node.get('trc_commit_hash')  # Add this line to get trc_commit_hash

    source_content = get_file_content(repo, md_commit_hash, filename)
    target_content = get_file_content(repo, ctx_commit_hash, ctx_file)
    trace_content = get_file_content(repo, trc_commit_hash, trc_file)
      
    node['source_content'] = ensure_empty_lines_before_symbols(source_content)
    node['target_content'] = ensure_empty_lines_before_symbols(target_content)
    node['trace_content'] = trace_content  # Add trace_content to node
    node['operation_src'] = operation_src

    children = node.get('children', [])
    enriched_children = []
    for child in children:
        enriched_child = enrich_call_tree(child, repo)
        enriched_children.append(enriched_child)
    node['children'] = enriched_children

    return node

@app.get("/serve_image/")
async def serve_image(path: str = Query(...)):
    """
    Serves an image file from a path relative to the current repository path
    that was set during get_repo call.
    """
    if not current_repo_path:
        raise HTTPException(
            status_code=400, 
            detail="Repository path not set. Call get_repo first."
        )
    
    image_path = os.path.join(current_repo_path, path)
    
    if not os.path.isfile(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    response = FileResponse(image_path)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/list_directory/")
async def list_directory(path: str = Query("")):
    resolved_path = Path(path).resolve()
    if not resolved_path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    items = []
    for item in resolved_path.iterdir():
        is_dir = item.is_dir()
        is_git_repo = False
        if is_dir and (item / '.git').is_dir():
            is_git_repo = True
        items.append({
            'name': item.name,
            'path': str(item.resolve()),
            'is_dir': is_dir,
            'is_git_repo': is_git_repo
        })

    # Sort items: directories first, then files
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

    if resolved_path != resolved_path.root:
        parent_path = str(resolved_path.parent.resolve())
        items.insert(0, {
            'name': '..',
            'path': parent_path,
            'is_dir': True,
            'is_git_repo': False
        })

    return items

@app.get("/branches_and_commits/")
async def get_branches_and_commits(repo_path: str = Query(...)):
    try:
        repo = get_repo(repo_path)
        branches_data = []
        # Filter out main branch, only get custom branches
        branches = [b for b in repo.branches if b.name != 'main']
        branches = sorted(branches, key=lambda b: b.commit.committed_datetime, reverse=True)

        for branch in branches:
            try:
                call_tree_file_content = repo.git.show(f'{branch.name}:call_tree.json')
                call_tree = json.loads(call_tree_file_content)
            except Exception as e:
                print(f"Error reading call_tree.json from branch {branch.name}: {str(e)}")
                continue

            branch_node = {
                'id': branch.name,
                'text': branch.name,
                'state': {'opened': True},
                'children': []
            }

            def build_tree(node):
                node_id = f"{node['ctx_file']}_{node['ctx_commit_hash']}"
                tree_node = {
                    'id': node_id,
                    'text': node['ctx_file'],
                    'ctx_file': node['ctx_file'],
                    'filename': node['filename'],
                    'md_file': node['filename'],
                    'md_commit_hash': node['md_commit_hash'],
                    'ctx_commit_hash': node['ctx_commit_hash'],
                    'trc_file': node.get('trc_file', ''),  # Add trc_file field
                    'trc_commit_hash': node.get('trc_commit_hash', ''),  # Add trc_commit_hash field
                    'branch': branch.name,
                    'children': []
                }
                for child in node.get('children', []):
                    child_node = build_tree(child)
                    tree_node['children'].append(child_node)
                return tree_node

            root_node = build_tree(call_tree)
            branch_node['children'].append(root_node)
            branches_data.append(branch_node)

        return branches_data
    except Exception as e:
        print(f"Error processing branches and commits: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@app.get("/get_file_content/")
async def get_file_content_endpoint(repo_path: str = Query(...), file_path: str = Query(...), commit_hash: str = Query(...)):
    try:
        repo = get_repo(repo_path)
        try:
            file_content = repo.git.show(f'{commit_hash}:{file_path}')
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"File not found in commit {commit_hash}: {str(e)}")
        return PlainTextResponse(file_content)
    except Exception as e:
        print(f"Error fetching file content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/get_enriched_call_tree/")
async def get_enriched_call_tree(repo_path: str = Query(...), branch: str = Query(...)):
    try:
        repo = get_repo(repo_path)
        call_tree_file_content = repo.git.show(f'{branch}:call_tree.json')
        call_tree = json.loads(call_tree_file_content)

        enriched_call_tree = enrich_call_tree(call_tree, repo)

        return JSONResponse(content=enriched_call_tree)
    except Exception as e:
        print(f"Error fetching enriched call tree: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})


@app.get("/get_file_content_disk/")
async def get_file_content_disk(path: str = Query(...)):
    try:
        if not os.path.isfile(path):
            return JSONResponse(status_code=404, content={"detail": "File not found."})
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="text/plain")
    except Exception as e:
        print(f"Error fetching file content from disk: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})


# Endpoint to save settings
@app.post("/save_settings/")
async def save_settings(request: Request):
    try:
        settings_data = await request.json()
        with open(SETTINGS_FILE_PATH, 'w') as f:
            toml.dump(settings_data, f)
        return JSONResponse(content={"detail": "Settings saved successfully"})
    except Exception as e:
        print(f"Error saving settings: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

# Endpoint to load settings
@app.get("/load_settings/")
async def load_settings():
    try:
        if not os.path.exists(SETTINGS_FILE_PATH):
            return JSONResponse(content={"settings": None})
        with open(SETTINGS_FILE_PATH, 'r') as f:
            settings_data = toml.load(f)
        return JSONResponse(content={"settings": settings_data})
    except Exception as e:
        print(f"Error loading settings: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

# Updated run_command endpoint to stream output with UTF-8 support
@app.post("/ws/run_command")
async def run_command(request: Request):
    data = await request.json()
    print("Data: ", data)
    command = data.get("command")
    path = data.get("path")

    if not command or not path:
        raise HTTPException(status_code=400, detail="Command and path are required")

    try:
        async def stream_command():
            # Set up UTF-8 environment for the subprocess
            env = os.environ.copy()
            env.update({
                'PYTHONIOENCODING': 'utf-8',
                'LC_ALL': 'en_US.UTF-8',
                'LANG': 'en_US.UTF-8'
            })
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=path,
                env=env
            )
            
            # Stream stdout with UTF-8-safe chunking to preserve Rich ANSI and encoding
            buffer = b''
            while True:
                chunk = await read_utf8_safe_chunk(process.stdout, 1024)
                if not chunk:
                    break
                
                # Add to buffer and yield complete chunk
                buffer += chunk
                try:
                    decoded_chunk = buffer.decode('utf-8', errors='strict')
                    yield decoded_chunk
                    buffer = b''  # Clear buffer after successful decode
                except UnicodeDecodeError:
                    # If we still can't decode, yield with error replacement
                    decoded_chunk = buffer.decode('utf-8', errors='replace')
                    yield decoded_chunk
                    buffer = b''

            # Yield any remaining buffer content
            if buffer:
                yield buffer.decode('utf-8', errors='replace')

            # Stream any stderr after stdout
            stderr_buffer = b''
            while True:
                chunk = await read_utf8_safe_chunk(process.stderr, 1024)
                if not chunk:
                    break
                
                stderr_buffer += chunk
                try:
                    decoded_chunk = stderr_buffer.decode('utf-8', errors='strict')
                    yield decoded_chunk
                    stderr_buffer = b''
                except UnicodeDecodeError:
                    decoded_chunk = stderr_buffer.decode('utf-8', errors='replace')
                    yield decoded_chunk
                    stderr_buffer = b''

            # Yield any remaining stderr buffer
            if stderr_buffer:
                yield stderr_buffer.decode('utf-8', errors='replace')

            # Wait for process to complete
            await process.wait()

        return StreamingResponse(stream_command(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute command: {str(e)}")

@app.post("/create_file/")
async def create_file_endpoint(path: str = Query(...), name: str = Query(...)):
    try:
        full_path = os.path.join(path, name)
        with open(full_path, 'w') as f:
            pass  # Creates an empty file
        return JSONResponse(status_code=200, content={"detail": "File created successfully"})
    except Exception as e:
        print(f"Error creating file: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@app.post("/create_folder/")
async def create_folder_endpoint(path: str = Query(...), name: str = Query(...)):
    try:
        full_path = os.path.join(path, name)
        os.makedirs(full_path, exist_ok=True)
        return JSONResponse(status_code=200, content={"detail": "Folder created successfully"})
    except Exception as e:
        print(f"Error creating folder: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@app.post("/save_file")
async def save_file(request: Request):
    try:
        # Get JSON payload
        data = await request.json()
        
        # Validate required fields
        if not all(key in data for key in ['path', 'content']):
            raise HTTPException(status_code=400, detail="Missing required fields")
            
        file_path = data['path']
        content = data['content']
        
        # Ensure path is within BASE_DIR
        full_path = (Path(BASE_DIR) / file_path).resolve()
        if not str(full_path).startswith(str(BASE_DIR)):
            raise HTTPException(status_code=403, detail="Access denied: Path outside base directory")
            
        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content to file
        full_path.write_text(content)
        
        return JSONResponse(
            content={"message": "File saved successfully"},
            status_code=200
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def read_utf8_safe_chunk(stream, chunk_size=1024):
    """Read a chunk that doesn't split UTF-8 characters"""
    chunk = await stream.read(chunk_size)
    if not chunk:
        return chunk
    
    # If chunk ends with incomplete UTF-8 sequence, read more bytes
    while True:
        try:
            chunk.decode('utf-8')
            break  # Valid UTF-8, safe to return
        except UnicodeDecodeError as e:
            if e.start < len(chunk) - 4:  # Error not at the end, return what we have
                break
            # Read one more byte and try again
            next_byte = await stream.read(1)
            if not next_byte:
                break  # End of stream
            chunk += next_byte
            if len(chunk) > chunk_size + 16:  # Prevent infinite loop
                break
    return chunk

@app.post("/ws/run_fractalic")
async def run_fractalic(request: Request):
    data = await request.json()
    file_path = data.get("file_path")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")

    # Build command
    server_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(server_dir)
    root_dir = os.path.dirname(parent_dir)
    fractalic_path = os.path.join(root_dir, "fractalic.py")

    # Using current Python (from venv)
    python_exe = sys.executable 
    command = f'"{python_exe}" "{fractalic_path}" "{file_path}"'

    async def stream_fractalic():
        # Set up UTF-8 environment for the subprocess
        env = os.environ.copy()
        env.update({
            'PYTHONIOENCODING': 'utf-8',
            'LC_ALL': 'en_US.UTF-8',
            'LANG': 'en_US.UTF-8'
        })
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root_dir,
            env=env
        )

        # Stream stdout with UTF-8-safe chunking to preserve Rich ANSI and encoding
        buffer = b''
        while True:
            chunk = await read_utf8_safe_chunk(process.stdout, 1024)
            if not chunk:
                break
            
            # Add to buffer and yield complete chunk
            buffer += chunk
            try:
                decoded_chunk = buffer.decode('utf-8', errors='strict')
                yield decoded_chunk
                buffer = b''  # Clear buffer after successful decode
            except UnicodeDecodeError:
                # If we still can't decode, yield with error replacement
                # This handles edge cases where the chunk boundary still splits characters
                decoded_chunk = buffer.decode('utf-8', errors='replace')
                yield decoded_chunk
                buffer = b''

        # Yield any remaining buffer content
        if buffer:
            yield buffer.decode('utf-8', errors='replace')

        # Stream any stderr after stdout
        stderr_buffer = b''
        while True:
            chunk = await read_utf8_safe_chunk(process.stderr, 1024)
            if not chunk:
                break
            
            stderr_buffer += chunk
            try:
                decoded_chunk = stderr_buffer.decode('utf-8', errors='strict')
                yield decoded_chunk
                stderr_buffer = b''
            except UnicodeDecodeError:
                decoded_chunk = stderr_buffer.decode('utf-8', errors='replace')
                yield decoded_chunk
                stderr_buffer = b''

        # Yield any remaining stderr buffer
        if stderr_buffer:
            yield stderr_buffer.decode('utf-8', errors='replace')

        await process.wait()

    return StreamingResponse(stream_fractalic(), media_type="text/plain")

# Cache for tools schema to avoid recreating ToolRegistry repeatedly
_tools_schema_cache = {}
_SCHEMA_CACHE_DURATION = 30  # Cache for 30 seconds

@app.get("/tools_schema/")
async def tools_schema(tools_dir: str = Query("tools", description="Path to the tools directory")):
    """
    Autodiscover tools from the specified tools_dir and return their schema in OpenAI/MCP-compatible JSON format.
    """
    try:
        import time
        current_time = time.time()
        
        # Check if we have a cached schema for this tools_dir
        cache_key = tools_dir
        if cache_key in _tools_schema_cache:
            cached_schema, timestamp = _tools_schema_cache[cache_key]
            if current_time - timestamp < _SCHEMA_CACHE_DURATION:
                return JSONResponse(content=cached_schema)
        
        # Generate fresh schema and cache it
        registry = ToolRegistry(tools_dir=tools_dir)
        schema = registry.generate_schema()
        _tools_schema_cache[cache_key] = (schema, current_time)
        return JSONResponse(content=schema)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@app.delete("/delete_item/")
async def delete_item(path: str = Query(...)):
    """
    Delete a file or directory from the filesystem.
    """
    try:
        # Resolve the path
        item_path = Path(path).resolve()
        
        # Ensure the path exists
        if not item_path.exists():
            raise HTTPException(status_code=404, detail="File or directory not found")
        
        # Check if it's a file or directory and delete accordingly
        if item_path.is_file():
            item_path.unlink()
            return JSONResponse(status_code=200, content={"detail": f"File '{item_path.name}' deleted successfully"})
        elif item_path.is_dir():
            import shutil
            shutil.rmtree(item_path)
            return JSONResponse(status_code=200, content={"detail": f"Directory '{item_path.name}' deleted successfully"})
        else:
            raise HTTPException(status_code=400, detail="Invalid file or directory")
            
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied: Cannot delete file or directory")
    except Exception as e:
        print(f"Error deleting item: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@app.post("/rename_item/")
async def rename_item(old_path: str = Query(...), new_name: str = Query(...)):
    """
    Rename a file or directory.
    """
    try:
        # Resolve the old path
        old_item_path = Path(old_path).resolve()
        
        # Ensure the old path exists
        if not old_item_path.exists():
            raise HTTPException(status_code=404, detail="File or directory not found")
        
        # Validate new name (basic validation)
        if not new_name or new_name.strip() == "":
            raise HTTPException(status_code=400, detail="New name cannot be empty")
        
        # Check for invalid characters in the new name
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in new_name for char in invalid_chars):
            raise HTTPException(status_code=400, detail="New name contains invalid characters")
        
        # Create the new path (same parent directory, new name)
        new_item_path = old_item_path.parent / new_name
        
        # Check if target already exists
        if new_item_path.exists():
            raise HTTPException(status_code=409, detail="A file or directory with that name already exists")
        
        # Rename the item
        old_item_path.rename(new_item_path)
        
        item_type = "directory" if new_item_path.is_dir() else "file"
        return JSONResponse(status_code=200, content={
            "detail": f"{item_type.capitalize()} renamed successfully",
            "old_name": old_item_path.name,
            "new_name": new_name,
            "new_path": str(new_item_path)
        })
        
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied: Cannot rename file or directory")
    except Exception as e:
        print(f"Error renaming item: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

# ============================================================================
# MCP Manager Control Routes
# ============================================================================

@app.post("/mcp/start")
async def start_mcp_manager_route():
    """Start the MCP manager process"""
    return await start_mcp_manager()

@app.post("/mcp/stop")
async def stop_mcp_manager_route():
    """Stop the MCP manager process"""
    return await stop_mcp_manager()

@app.get("/mcp/status")
async def get_mcp_manager_status_route():
    """Get the status of the MCP manager and its servers"""
    return await get_mcp_manager_status()

# ============================================================================
# Health Check and Info Routes
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    mcp_status = await get_mcp_manager_status()
    return {
        "status": "healthy",
        "ui_server": "running",
        "mcp_manager": mcp_status
    }

@app.get("/info")
async def get_info():
    """Get information about the application"""
    mcp_status = await get_mcp_manager_status()
    return {
        "application": "Fractalic UI Server",
        "version": "1.0.0",
        "features": {
            "git_operations": True,
            "file_management": True,
            "mcp_manager_control": True,
            "mcp_server_proxy": True
        },
        "mcp_manager": mcp_status
    }

# ============================================================================
# Docker Registry Deployment API
# ============================================================================

# Store active deployments (in production, use a database)
active_deployments: Dict[str, Dict[str, Any]] = {}

# Store for deployment progress streams
deployment_streams: Dict[str, List[Dict[str, Any]]] = {}

def validate_docker_registry_request(data: Dict[str, Any]) -> Dict[str, str]:
    """Validate Docker registry deployment request"""
    errors = []
    
    # Check required fields based on plugin expectations
    if not data.get("script_name", "").strip():
        errors.append("script_name is required")
    
    if not data.get("script_folder", "").strip():
        errors.append("script_folder is required") 
    
    # Note: image_name is hardcoded in backend, no validation needed
    
    return errors

@app.post("/api/deploy/docker-registry")
async def deploy_docker_registry(request: Request):
    """Deploy using Docker registry (non-streaming version)"""
    import uuid
    from datetime import datetime
    
    try:
        data = await request.json()
        
        # Validate input
        validation_errors = validate_docker_registry_request(data)
        if validation_errors:
            raise HTTPException(
                status_code=400, 
                detail=f"Validation failed: {', '.join(validation_errors)}"
            )
        
        deployment_id = str(uuid.uuid4())
        
        # Import the plugin manager
        from publisher.plugin_manager import PluginManager
        from publisher.models import PublishRequest
        
        # Initialize plugin manager and get Docker registry plugin
        plugin_manager = PluginManager()
        docker_plugin = plugin_manager.get_plugin("docker-registry")
        
        if not docker_plugin:
            raise HTTPException(status_code=500, detail="Docker registry plugin not available")
        
        # Create deployment config from request data
        from publisher.models import DeploymentConfig
        
        # Convert frontend request to DeploymentConfig
        config = DeploymentConfig(
            plugin_name="docker-registry",
            script_name=data.get("script_name", ""),
            script_folder=data.get("script_folder", ""),
            container_name=data.get("container_name", f"fractalic-{deployment_id[:8]}"),
            environment_vars=data.get("env_vars", {}),
            port_mapping={},
            custom_domain=None,
            plugin_specific={
                "image_name": "ghcr.io/fractalic-ai/fractalic:latest-production",  # Always use production image
                "config_files": data.get("config_files", []),
                "mount_paths": data.get("mount_paths", {})
            }
        )
        
        # Define progress callback for real-time updates
        def progress_callback(message: str, progress: int):
            print(f"[PROGRESS] {progress}% - {message}")
        
        # Run deployment (blocking) with correct interface
        response = docker_plugin.publish(
            source_path=data.get("script_folder", ""),
            config=config,
            progress_callback=progress_callback
        )
        
        # Store deployment info if successful
        if response.success and response.deployment_id:
            active_deployments[response.deployment_id] = {
                "deployment_id": response.deployment_id,
                "script_name": data.get("script_name", "unknown"),
                "status": "running",
                "created_at": time.time(),
                "metadata": response.metadata or {}
            }
        
        return {
            "success": response.success,
            "message": response.message,
            "deployment_id": response.deployment_id,
            "endpoint_url": response.url,  # Use 'url' field from PublishResult
            "metadata": response.metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")

@app.post("/api/deploy/docker-registry/stream")
async def deploy_docker_registry_with_progress(request: Request):
    """Deploy using Docker registry with real-time progress streaming via SSE"""
    import uuid
    import asyncio
    import json
    from datetime import datetime
    
    try:
        data = await request.json()
        
        # Validate input upfront - return HTTP error instead of SSE error for validation failures
        validation_errors = validate_docker_registry_request(data)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"Validation failed: {', '.join(validation_errors)}"
            )
        
        deployment_id = str(uuid.uuid4())
        
        # Initialize progress tracking
        deployment_streams[deployment_id] = []
        
        def progress_callback(message: str, progress: int):
            """Callback to track deployment progress"""
            progress_data = {
                "deployment_id": deployment_id,
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "stage": "deploying",  # Default stage for now
                "progress": progress
            }
            deployment_streams[deployment_id].append(progress_data)
        
        async def stream_deployment():
            """Stream deployment progress to client"""
            try:
                # Import the plugin manager
                from publisher.plugin_manager import PluginManager
                from publisher.models import PublishRequest
                
                # Initialize plugin manager and get Docker registry plugin
                plugin_manager = PluginManager()
                docker_plugin = plugin_manager.get_plugin("docker-registry")
                
                if not docker_plugin:
                    yield f"data: {json.dumps({'error': 'Docker registry plugin not available'})}\n\n"
                    return
                
                # Create deployment config from request data
                from publisher.models import DeploymentConfig
                
                # Convert frontend request to DeploymentConfig
                config = DeploymentConfig(
                    plugin_name="docker-registry",
                    script_name=data.get("script_name", ""),
                    script_folder=data.get("script_folder", ""),
                    container_name=data.get("container_name", f"fractalic-{deployment_id[:8]}"),
                    environment_vars=data.get("env_vars", {}),
                    port_mapping={},
                    custom_domain=None,
                    plugin_specific={
                        "image_name": "ghcr.io/fractalic-ai/fractalic:latest-production",  # Always use production image
                        "config_files": data.get("config_files", []),
                        "mount_paths": data.get("mount_paths", {})
                    }
                )
                
                # Start deployment in background
                loop = asyncio.get_event_loop()
                
                def run_deployment():
                    return docker_plugin.publish(
                        source_path=data.get("script_folder", ""),
                        config=config,
                        progress_callback=progress_callback
                    )
                
                # Run deployment in thread pool to avoid blocking
                deployment_future = loop.run_in_executor(None, run_deployment)
                
                # Stream progress updates
                last_sent_count = 0
                while not deployment_future.done():
                    # Send new progress updates
                    current_progress = deployment_streams.get(deployment_id, [])
                    for progress_data in current_progress[last_sent_count:]:
                        yield f"data: {json.dumps(progress_data)}\n\n"
                    last_sent_count = len(current_progress)
                    
                    await asyncio.sleep(0.5)  # Check for updates every 500ms
                
                # Get final result
                response = await deployment_future
                
                # Send any remaining progress updates
                current_progress = deployment_streams.get(deployment_id, [])
                for progress_data in current_progress[last_sent_count:]:
                    yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Send final result
                final_result = {
                    "deployment_id": deployment_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": "Deployment completed",
                    "stage": "completed",
                    "progress": 100,
                    "result": {
                        "success": response.success,
                        "message": response.message,
                        "deployment_id": response.deployment_id,
                        "endpoint_url": response.url,  # Use 'url' field from PublishResult
                        "metadata": response.metadata
                    }
                }
                
                yield f"data: {json.dumps(final_result)}\n\n"
                
                # Store deployment info if successful
                if response.success and response.deployment_id:
                    active_deployments[response.deployment_id] = {
                        "deployment_id": response.deployment_id,
                        "script_name": data.get("script_name", "unknown"),
                        "status": "running",
                        "created_at": time.time(),
                        "metadata": response.metadata or {}
                    }
                
            except Exception as e:
                error_data = {
                    "deployment_id": deployment_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Deployment failed: {str(e)}",
                    "stage": "error",
                    "progress": 100,
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            finally:
                # Cleanup progress tracking
                if deployment_id in deployment_streams:
                    del deployment_streams[deployment_id]
        
        return StreamingResponse(
            stream_deployment(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions to preserve status codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start deployment: {str(e)}")
