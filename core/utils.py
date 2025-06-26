# Utilities
# - read_file
# - change_working_directory
# - print_ast_nodes
# - get_content_without_header
# - execute_shell_command

import os
import subprocess
import locale
from contextlib import contextmanager
import socket
import time

from core.ast_md.node import NodeType, Node
from core.ast_md.ast import AST

def parse_file(filename: str) -> AST:
    content = read_file(filename)
    return AST(content)

@contextmanager
def change_working_directory(new_path):
    """
    Temporarily change the working directory.
    
    :param new_path: Path to the new working directory
    """
    old_path = os.getcwd()
    os.chdir(new_path)
    try:
        yield
    finally:
        os.chdir(old_path)

def read_file(file_path: str) -> str:
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        raise IOError(f"Error reading file '{file_path}': {e}")



def print_ast_nodes(ast: AST) -> None:
    current_node = ast.get_first_node()
    if current_node is None:
        print("[Debug: print_ast_nodes] AST is empty.")
        return

    while current_node is not None:
        print(f"Key: {current_node.key}, ID: {current_node.id}, Content: {current_node.content.strip()}")
        current_node = current_node.next

    
def get_content_without_header(node: Node) -> str:
    content_lines = node.content.split('\n')
    if node.type == NodeType.HEADING and content_lines:
        content_lines = content_lines[1:]
    content_without_header = '\n'.join(content_lines)
    return content_without_header.strip()


import toml



def load_settings(settings_file='settings.toml'):
    """Load settings from TOML file with proper error handling."""
    print(f"Current working directory: {os.getcwd()}")
    print(f"Looking for settings file at: {settings_file}")
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            return toml.load(f)
    except FileNotFoundError:
        print(f"[WARNING] Settings file {settings_file} not found. Using defaults.")
        return {}
    except toml.TomlDecodeError as e:
        print(f"[ERROR] Error parsing {settings_file}: {e}")
        return {}

def is_port_available(host='localhost', port=8001):
    """Check if a port is available on the given host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # Port is available if connection fails
    except Exception:
        return False

def find_available_port(start_port=8001, max_attempts=100):
    """Find the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port=port):
            return port
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

def check_docker_container_on_port(port):
    """Check if there's a Docker container using the specified port."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', 'table {{.Names}}\t{{.Ports}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if f':{port}->' in line or f':{port}/' in line:
                    container_name = line.split('\t')[0]
                    return container_name
        return None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None

def find_available_ai_server_port(preferred_port=8001):
    """
    Find an available port for the AI server, checking for both system availability
    and Docker container conflicts.
    
    Returns:
        tuple: (port, conflict_info) where conflict_info is None if no conflict,
               or a dict with conflict details if a port was already in use.
    """
    conflict_info = None
    
    # Check if preferred port is available
    if is_port_available(port=preferred_port):
        # Double-check for Docker container conflicts
        container = check_docker_container_on_port(preferred_port)
        if not container:
            return preferred_port, None
        else:
            conflict_info = {
                'type': 'docker_container',
                'port': preferred_port,
                'container': container
            }
    else:
        conflict_info = {
            'type': 'port_in_use',
            'port': preferred_port
        }
    
    # Find next available port
    available_port = find_available_port(preferred_port + 1)
    return available_port, conflict_info

def generate_ai_server_info(port, container_name=None, script_path=None):
    """Generate AI server access information and sample commands."""
    base_url = f"http://localhost:{port}"
    
    # Use provided script path or default
    default_script_path = "/payload/script.md"
    if script_path:
        default_script_path = script_path
    
    info = {
        'url': base_url,
        'health_url': f"{base_url}/health",
        'docs_url': f"{base_url}/docs",
        'execute_url': f"{base_url}/execute",
        'sample_curl': f'curl -X POST {base_url}/execute -H "Content-Type: application/json" -d \'{{"filename": "{default_script_path}"}}\'',
        'port': port
    }
    
    if container_name:
        info.update({
            'container_name': container_name,
            'stop_command': f'docker stop {container_name}',
            'remove_command': f'docker rm {container_name}',
            'logs_command': f'docker logs {container_name}'
        })
    
    return info