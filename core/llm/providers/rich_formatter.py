"""
Rich-based formatting utilities for terminal output

This module handles all Rich library functionality including:
- JSON syntax highlighting
- Console output formatting
- Color management
- Terminal display utilities
"""

import json
import re
from io import StringIO
from typing import Optional

from rich.console import Console
from rich.syntax import Syntax


class RichFormatter:
    """Handles Rich-based formatting for terminal output"""
    
    def __init__(self):
        # Initialize console with proper width handling
        self.console = Console(soft_wrap=True)
    
    def show(self, role: str, content: str, end: str = "\n"):
        """Display content with role-based coloring"""
        colours = {"user": "cyan", "assistant": "green",
                   "error": "red", "status": "dim"}
        
        if role in colours:
            self.console.print(f"[{colours[role]}]{role.upper()}:[/] {content}", 
                             end=end, soft_wrap=True)
        else:
            # Check if this is a tool call or response message
            if content.startswith("> TOOL CALL") or content.startswith("> TOOL RESPONSE"):
                formatted_content = self._format_tool_message(content)
                self.console.print(formatted_content, highlight=False, end=end,
                                 soft_wrap=True)
            else:
                self.console.print(content, highlight=False, end=end,
                                 soft_wrap=True)

    def status(self, message: str):
        """Display status message"""
        self.show("status", message)
    
    def error(self, message: str):
        """Display error message"""
        self.show("error", message)
    
    def _format_tool_message(self, content: str) -> str:
        """Format tool call/response messages with special colors"""
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            if line.startswith("> TOOL CALL") or line.startswith("> TOOL RESPONSE"):
                # Extract the main part and ID part
                if ", id: " in line:
                    main_part, id_part = line.split(", id: ", 1)
                    # Format: blue for "> TOOL CALL/RESPONSE", dark gray italic for "id: ..."
                    formatted_line = f"[bold blue]{main_part}[/bold blue], [dim italic]id: {id_part}[/dim italic]"
                else:
                    # Fallback if no ID found
                    formatted_line = f"[bold blue]{line}[/bold blue]"
                formatted_lines.append(formatted_line)
            else:
                # Keep other lines unchanged
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def format_json_clean(self, json_str: str) -> str:
        """Format JSON string with proper indentation, no colors (for context)"""
        try:
            # First try to parse to ensure it's valid JSON
            parsed = json.loads(json_str)
            
            # Handle nested escaped JSON strings (like in the "text" field)
            def unescape_nested_json(obj):
                if isinstance(obj, dict):
                    return {k: unescape_nested_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [unescape_nested_json(item) for item in obj]
                elif isinstance(obj, str):
                    # Try to parse as JSON if it looks like escaped JSON
                    if obj.strip().startswith(('{', '[')):
                        try:
                            # Attempt to parse the string as JSON
                            return json.loads(obj)
                        except json.JSONDecodeError:
                            return obj
                    return obj
                else:
                    return obj
            
            # Process nested JSON
            processed = unescape_nested_json(parsed)
            
            # Re-format with consistent indentation - clean, no syntax highlighting
            formatted_json = json.dumps(processed, indent=2, ensure_ascii=False)
            
            return formatted_json
            
        except (json.JSONDecodeError, Exception):
            # If JSON parsing fails, try to at least pretty-print it
            try:
                parsed = json.loads(json_str)
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            except:
                return json_str

    def format_json_colored(self, json_str: str) -> str:
        """Format JSON string with Rich syntax highlighting for terminal display
        
        Uses a wide fixed width to prevent truncation while maintaining syntax highlighting.
        Frontend terminal width detection should be handled at the UI layer, not here.
        """
        try:
            # Get clean formatted JSON first
            clean_json = self.format_json_clean(json_str)
            
            # Use a very wide fixed width to prevent truncation
            # This ensures syntax highlighting works while avoiding truncation
            # Frontend should handle responsive display if needed
            width = 300  # Wide enough for most JSON content
            
            # Create a console that renders with syntax highlighting
            string_output = StringIO()
            console = Console(
                file=string_output,
                width=width,
                force_terminal=True,
                no_color=False,
                legacy_windows=False
            )
            
            # Create syntax highlighting
            syntax = Syntax(
                clean_json,
                "json",
                theme="github-dark",
                background_color=None,
                line_numbers=False,
                word_wrap=False,  # Disable to prevent Rich's problematic wrapping
                padding=0
            )
            
            # Render with syntax highlighting
            console.print(syntax, end="")
            result = string_output.getvalue()
            
            # Clean up ANSI artifacts
            result = self._clean_ansi_artifacts(result)
            
            return result
            
        except Exception:
            # Fallback to clean formatting only if syntax highlighting completely fails
            return self.format_json_clean(json_str)

    def _clean_ansi_artifacts(self, text: str) -> str:
        """Clean up ANSI escape sequences and background artifacts"""
        # Convert combined foreground+background codes to foreground-only
        # Pattern: \x1b[38;2;r;g;b;48;2;r;g;b;m -> \x1b[38;2;r;g;b;m
        def extract_foreground_only(match):
            sequence = match.group(0)
            # Extract just the 38;2;r;g;b part (foreground)
            fg_match = re.search(r'38;2;\d+;\d+;\d+', sequence)
            if fg_match:
                return f'\x1b[{fg_match.group(0)}m'
            # If no foreground found, remove entirely
            return ''
        
        # Replace combined sequences with foreground-only
        result = re.sub(r'\x1b\[[^m]*38;2[^m]*48[^m]*m', extract_foreground_only, text)
        # Remove any remaining background-only sequences
        result = re.sub(r'\x1b\[48;2[^m]*m', '', result)
        result = re.sub(r'\x1b\[49m', '', result)
        
        # Remove excessive trailing whitespace that Rich adds for width filling
        # BUT be less aggressive to avoid truncating actual content
        lines = result.split('\n')
        cleaned_lines = []
        for line in lines:
            # Less aggressive cleanup: only remove trailing whitespace and reset codes
            # but preserve the actual content
            cleaned = re.sub(r'\s*\x1b\[0m\s*$', '', line)  # Remove reset codes and trailing spaces
            cleaned = cleaned.rstrip()  # Remove any remaining trailing whitespace
            cleaned_lines.append(cleaned)
        
        result = '\n'.join(cleaned_lines)
        
        # Remove any completely empty trailing lines (but preserve content)
        result = result.rstrip('\n')
        
        return result

    def format_json(self, json_str: str, title: str = "JSON") -> str:
        """Format JSON string with proper indentation and nested JSON handling (clean version)"""
        return self.format_json_clean(json_str)
