# filepath: /Users/marina/llexem-jan-25-deploy/llexem_deploy_2025/fractalic/fractalic.py
import warnings
# TODO: #5 remove warning supression when pydantic v2 is stable
warnings.filterwarnings(
    "ignore",
    message="Valid config keys have changed in V2:",  # match only the first line
    category=UserWarning,
    module="pydantic._internal._config",
)

import os
import sys
import io
import builtins
import argparse
import traceback
import toml
from pathlib import Path

from core.git import commit_changes, ensure_git_repo
from core.ast_md.parser import print_parsed_structure
from core.utils import parse_file, load_settings
from core.config import Config
from core.ast_md.ast import AST
from core.utils import read_file
from core.operations.runner import run
from core.operations.call_tree import CallTreeNode
from core.errors import BlockNotFoundError, UnknownOperationError
from core.render.render_ast import render_ast_to_markdown

from rich.console import Console
from rich.panel import Panel

# Set the encoding for standard output, input, and error streams to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

original_open = open


def run_fractalic(input_file, task_file=None, param_input_user_request=None, capture_output=False, 
                 model=None, api_key=None, operation=None, show_operations=False):
    """
    Run a Fractalic script programmatically - the core execution function.
    
    Args:
        input_file: Path to the Fractalic script to execute
        task_file: Optional path to task file for parameter injection
        param_input_user_request: Optional parameter path for injection
        capture_output: Whether to capture output (not used in current implementation)
        model: LLM model to use (overrides settings.defaultProvider)
        api_key: LLM API key (overrides settings)
        operation: Default operation to perform
        show_operations: Make operations visible to LLM
    
    Returns:
        dict: Execution result with success status, output, and return information
    """
    original_cwd = os.getcwd()
    
    try:
        # Load settings
        settings = load_settings()
        
        # Update show-operations setting if explicitly requested
        if show_operations:
            if 'settings' not in settings:
                settings['settings'] = {}
            settings['settings']['enableOperationsVisibility'] = True
        
        # Setup provider configuration
        raw_model = model or settings.get("defaultProvider")
        if not raw_model:
            return {
                'success': False,
                'error': 'No model specified and no defaultProvider in settings.toml',
                'output': '',
                'explicit_return': False,
                'return_content': None,
                'branch_name': None
            }

        all_models = settings.get("settings", {})
        model_key = None

        # 1) direct match on the table key
        if raw_model in all_models:
            model_key = raw_model
        else:
            # 2) match against each record's "model" field (and common variants)
            for key, conf in all_models.items():
                name = conf.get("model", key)
                if raw_model == name \
                   or raw_model == name.replace(".", "-") \
                   or raw_model == name.replace(".", "_"):
                    model_key = key
                    break
            # 3) fallback: sanitize CLI string to table keys
            if model_key is None:
                for alt in (raw_model.replace(".", "-"), raw_model.replace(".", "_")):
                    if alt in all_models:
                        model_key = alt
                        break

        if model_key is None:
            return {
                'success': False,
                'error': f'model "{raw_model}" not found under [settings]. Available models: {", ".join(all_models.keys())}',
                'output': '',
                'explicit_return': False,
                'return_content': None,
                'branch_name': None
            }

        # use the section name (anthropic/openrouter/openai) as provider
        provider = model_key
        provider_settings = all_models[model_key]
        # ensure downstream sees the actual model name (with dots if present)
        provider_settings = {
            **provider_settings,
            "model": provider_settings.get("model", model_key),
        }

        # Get API key (prefer parameter, then provider settings)
        final_api_key = api_key or provider_settings.get("apiKey")
        if not final_api_key:
            return {
                'success': False,
                'error': f'No API key found for provider {provider}',
                'output': '',
                'explicit_return': False,
                'return_content': None,
                'branch_name': None
            }
        
        # Configure globals
        Config.TOML_SETTINGS = settings
        Config.LLM_PROVIDER = provider
        Config.API_KEY = final_api_key
        Config.DEFAULT_OPERATION = operation or settings.get('defaultOperation', 'append')
        
        # Set environment variable for API key
        os.environ[f"{provider.upper()}_API_KEY"] = final_api_key
        
        # Change working directory to the input file's directory for proper git tracking
        input_file_dir = os.path.dirname(os.path.abspath(input_file))
        
        # Change to the input file's directory so git operations happen in the right place
        os.chdir(input_file_dir)
        print(f"Changed working directory to: {input_file_dir}")
        
        # Validate input file exists
        input_file_basename = os.path.basename(input_file)
        if not os.path.exists(input_file_basename):
            return {
                'success': False,
                'error': f"Input file not found: {input_file}",
                'output': '',
                'explicit_return': False,
                'return_content': None,
                'branch_name': None
            }
        
        # Handle parameter injection if provided
        param_node = None
        if task_file and param_input_user_request:
            if not os.path.exists(task_file):
                return {
                    'success': False,
                    'error': f"Task file not found: {task_file}",
                    'output': '',
                    'explicit_return': False,
                    'return_content': None,
                    'branch_name': None
                }
            temp_ast = parse_file(task_file)
            param_node = temp_ast.get_part_by_path(param_input_user_request, True)
        
        # Run the Fractalic script (use basename since we're in the correct directory)
        result_nodes, call_tree_root, ctx_file, ctx_hash, trc_file, trc_hash, branch_name, explicit_return = run(
            input_file_basename,
            param_node,
            p_call_tree_node=None
        )
        
        # Extract return content if there was an explicit return
        return_content = None
        try:
            if explicit_return and result_nodes:
                # Extract content directly from nodes
                if hasattr(result_nodes, 'parser') and result_nodes.parser.nodes:
                    content_parts = []
                    try:
                        current = result_nodes.first()
                        while current:
                            if hasattr(current, 'content') and current.content:
                                # Format content similar to render_ast_to_markdown
                                formatted_content = '\n'.join(current.content.splitlines()) + '\n'
                                content_parts.append(formatted_content)
                            current = current.next
                        
                        if content_parts:
                            return_content = ''.join(content_parts)
                    except Exception as e:
                        print(f"DEBUG: Error in content extraction: {e}")
        except Exception as e:
            print(f"DEBUG: Exception in return content extraction: {e}")
        
        # Save call tree
        call_tree_path = os.path.join('.', 'call_tree.json')
        
        with open(call_tree_path, 'w', encoding='utf-8') as json_file:
            call_tree_root.ctx_file = ctx_file
            call_tree_root.ctx_hash = ctx_hash
            call_tree_root.trc_file = trc_file  
            call_tree_root.trc_hash = trc_hash  
            json_file.write(call_tree_root.to_json())
        
        # Commit the call_tree.json file
        md_commit_hash = commit_changes(
            '.',  # Current directory (which is the input file's directory)
            "Saving call_tree.json",
            [call_tree_path],
            None,
            None
        )
        
        # Build output
        output = f"Execution completed. Branch: {branch_name}, Context: {ctx_hash}"
        
        return {
            'success': True,
            'output': output,
            'explicit_return': explicit_return,
            'return_content': return_content,
            'branch_name': branch_name,
            'ctx_file': ctx_file,
            'ctx_hash': ctx_hash
        }
        
    except (BlockNotFoundError, UnknownOperationError, FileNotFoundError, ValueError) as e:
        return {
            'success': False,
            'error': str(e),
            'output': '',
            'explicit_return': False,
            'return_content': None,
            'branch_name': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}",
            'output': '',
            'explicit_return': False,
            'return_content': None,
            'branch_name': None
        }
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (10) + key[-4:]


def enable_rich_terminal_features():
    """Comprehensive test function to check Rich terminal capabilities for xterm."""
    # Force environment variables for maximum xterm compatibility
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLORTERM'] = 'truecolor'
    os.environ['FORCE_COLOR'] = '1'
    if 'NO_COLOR' in os.environ:
        del os.environ['NO_COLOR']


def main():
    """Main function - thin wrapper that handles argument parsing and calls run_fractalic"""
    # Test Rich terminal capabilities first
    enable_rich_terminal_features()
    
    settings = load_settings()  # Load settings.toml once
    
    default_provider = settings.get('defaultProvider', 'openai')
    default_operation = settings.get('defaultOperation', 'append')

    parser = argparse.ArgumentParser(description="Process and run operations on a markdown file.")
    parser.add_argument('input_file', type=str, help='Path to the input markdown file.')
    parser.add_argument('--task_file', type=str, help='Path to the task markdown file.')
    parser.add_argument('--api_key', type=str, help='LLM API key', default=None)
    parser.add_argument(
        "--model",
        help="LLM model to use (overrides settings.defaultProvider)"
    )
    parser.add_argument('--operation', type=str, help='Default operation to perform',
                       default=default_operation)
    parser.add_argument('--param_input_user_request', type=str,
                       help='Part path for ParamInput-UserRequest', default=None)
    parser.add_argument('-v', '--show-operations', action='store_true',
                       help='Make operations visible to LLM (overrides TOML setting)')

    args = parser.parse_args()

    try:
        # Call the core execution function
        result = run_fractalic(
            input_file=args.input_file,
            task_file=args.task_file,
            param_input_user_request=args.param_input_user_request,
            model=args.model,
            api_key=args.api_key,
            operation=args.operation,
            show_operations=args.show_operations
        )
        
        if not result['success']:
            print(f"[ERROR fractalic.py] {result['error']}")
            sys.exit(1)
        
        # Use same force settings as test function for consistency
        console = Console(
            force_terminal=True, 
            force_interactive=True,
            color_system="truecolor",
            legacy_windows=False
        )

        # Extract provider info for display (we need to re-calculate this for console output)
        raw_model = args.model or settings.get("defaultProvider")
        all_models = settings.get("settings", {})
        model_key = None
        
        if raw_model in all_models:
            model_key = raw_model
        else:
            for key, conf in all_models.items():
                name = conf.get("model", key)
                if raw_model == name \
                   or raw_model == name.replace(".", "-") \
                   or raw_model == name.replace(".", "_"):
                    model_key = key
                    break
            if model_key is None:
                for alt in (raw_model.replace(".", "-"), raw_model.replace(".", "_")):
                    if alt in all_models:
                        model_key = alt
                        break
        
        if model_key:
            provider_settings = all_models[model_key]
            final_api_key = args.api_key or provider_settings.get("apiKey")
            
            # show masked key and its source with icons
            masked = _mask_key(final_api_key)
            source = "CLI argument" if args.api_key else "settings.toml"
            console.print(f"[bright_green]✓[/bright_green] Using provider [bold]{model_key}[/bold], model [bold]{provider_settings.get('model')}[/bold]")
            console.print(f"[bright_green]✓[/bright_green] API key [bold]{masked}[/bold] (from {source})")

        # Send message to UI for branch information
        print(f"[EventMessage: Root-Context-Saved] ID: {result['branch_name']}, {result['ctx_hash']}")
        
        # Log information about how the workflow completed
        if result['explicit_return']:
            print(f"[EventMessage: Execution-Mode] Explicit @return operation")
            
            # Print the content of the returned AST
            print("\n[EventMessage: Return-Content-Start]")
            if result['return_content']:
                print(result['return_content'])
            print("[EventMessage: Return-Content-End]\n")
        else:
            print(f"[EventMessage: Execution-Mode] Natural workflow completion")

    except (BlockNotFoundError, UnknownOperationError, FileNotFoundError, ValueError) as e:
        print(f"[ERROR fractalic.py] {str(e)}")
        sys.exit(1)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)
        filename, line_no, func_name, text = tb[-1]  # Get the last frame (where error originated)
        print(f"[ERROR][Unexpected] {exc_type.__name__} in module {filename}, line {line_no}: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
