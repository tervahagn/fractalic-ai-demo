#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thin wrapper for Model-Context-Protocol discovery/execution.
You can swap this for an official SDK later.
"""
from __future__ import annotations
import requests
import time
from typing import Dict, Any, List

# Simple caching to reduce repeated HTTP calls to MCP servers
_list_tools_cache: Dict[str, tuple] = {}  # server -> (response, timestamp)
_CACHE_DURATION = 30  # Cache for 30 seconds

def clear_cache(server: str = None):
    """Clear cache for a specific server or all servers."""
    global _list_tools_cache
    if server:
        _list_tools_cache.pop(server, None)
    else:
        _list_tools_cache.clear()

def list_tools(server: str) -> List[Dict[str, Any]]:
    """List tools from MCP server with caching to reduce load."""
    current_time = time.time()
    
    # Check if we have a recent cached response
    if server in _list_tools_cache:
        cached_response, timestamp = _list_tools_cache[server]
        if current_time - timestamp < _CACHE_DURATION:
            return cached_response
    
    # Fetch fresh data and cache it
    try:
        response = requests.get(f"{server.rstrip('/')}/list_tools", timeout=5).json()
        _list_tools_cache[server] = (response, current_time)
        return response
    except Exception as e:
        # If there's an error and we have cached data, return it (even if stale)
        if server in _list_tools_cache:
            cached_response, _ = _list_tools_cache[server]
            return cached_response
        raise e

def call_tool(server: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return requests.post(f"{server.rstrip('/')}/call_tool",
                         json={"name": name, "arguments": args},
                         timeout=30).json()
