"""Chat tools for the telco billing CLI.

Tools are dynamically generated from the northbound OpenAPI specification,
plus static playbook tools for loading business rules.
"""

import json
import re
from pathlib import Path

import httpx

from playbook_tools import execute_playbook_tool, get_playbook_tools

NORTHBOUND_URL = "http://localhost:8052"

# Cache for OpenAPI spec
_openapi_cache: dict | None = None


def fetch_openapi_spec() -> dict | None:
    """Fetch the OpenAPI spec from the northbound server."""
    global _openapi_cache
    if _openapi_cache is not None:
        return _openapi_cache

    try:
        response = httpx.get(f"{NORTHBOUND_URL}/openapi.json", timeout=5.0)
        if response.status_code == 200:
            _openapi_cache = response.json()
            return _openapi_cache
    except Exception:
        pass
    return None


def _convert_path_params_to_schema(path: str, operation: dict) -> dict:
    """Convert path parameters to JSON schema properties."""
    properties = {}
    required = []

    # Extract path parameters like {customer_id}
    path_params = re.findall(r"\{(\w+)\}", path)

    # Get parameter details from operation
    params = operation.get("parameters", [])
    for param in params:
        if param.get("in") == "path":
            name = param["name"]
            schema = param.get("schema", {"type": "string"})
            properties[name] = {
                "type": schema.get("type", "string"),
                "description": param.get("description", f"The {name} parameter"),
            }
            if param.get("required", True):
                required.append(name)

    # Add any path params not in parameters (fallback)
    for param in path_params:
        if param not in properties:
            properties[param] = {
                "type": "string",
                "description": f"The {param.replace('_', ' ')}",
            }
            required.append(param)

    return {"type": "object", "properties": properties, "required": required}


def _create_tool_name(path: str, method: str) -> str:
    """Create a tool name from path and method."""
    # Remove leading slash and convert to snake_case
    name = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    # Handle common prefixes
    name = name.replace("crm_", "")
    # Add method prefix for non-GET
    if method != "get":
        name = f"{method}_{name}"
    return name


def generate_api_tools_from_openapi() -> list[dict]:
    """Generate chat tools from the northbound OpenAPI specification."""
    spec = fetch_openapi_spec()
    if not spec:
        return []

    tools = []
    paths = spec.get("paths", {})

    # Tags to exclude (debug endpoints)
    excluded_tags = {"Debug", "Health"}

    for path, path_item in paths.items():
        for method in ["get", "post"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            tags = operation.get("tags", [])

            # Skip debug/health endpoints
            if any(tag in excluded_tags for tag in tags):
                continue

            # Get operation details
            summary = operation.get("summary", "")
            description = operation.get("description", summary)

            # Create tool name
            operation_id = operation.get("operationId")
            if operation_id:
                tool_name = operation_id
            else:
                tool_name = _create_tool_name(path, method)

            # Build input schema
            if method == "get":
                input_schema = _convert_path_params_to_schema(path, operation)
            else:
                # For POST, use request body schema
                request_body = operation.get("requestBody", {})
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                schema_ref = json_content.get("schema", {})

                # Resolve $ref if present
                if "$ref" in schema_ref:
                    ref_path = schema_ref["$ref"].split("/")[-1]
                    schema = spec.get("components", {}).get("schemas", {}).get(ref_path, {})
                else:
                    schema = schema_ref

                input_schema = {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                }

                # Add path parameters for POST endpoints with path params
                path_params = re.findall(r"\{(\w+)\}", path)
                for param in path_params:
                    if param not in input_schema["properties"]:
                        input_schema["properties"][param] = {
                            "type": "string",
                            "description": f"The {param.replace('_', ' ')}",
                        }
                        if param not in input_schema["required"]:
                            input_schema["required"].append(param)

            # Truncate description for tool (Claude has limits)
            tool_description = description.strip()
            if len(tool_description) > 1000:
                tool_description = tool_description[:997] + "..."

            tool = {
                "name": tool_name,
                "description": tool_description,
                "input_schema": input_schema,
                # Store metadata for execution
                "_path": path,
                "_method": method,
            }
            tools.append(tool)

    return tools


def get_chat_tools() -> list[dict]:
    """Return all tools available during chat.

    Tools are dynamically generated from the northbound OpenAPI spec,
    plus static playbook tools.
    """
    api_tools = generate_api_tools_from_openapi()
    playbook_tools = get_playbook_tools()

    # Return tools without internal metadata
    all_tools = []
    for tool in api_tools + playbook_tools:
        clean_tool = {k: v for k, v in tool.items() if not k.startswith("_")}
        all_tools.append(clean_tool)

    return all_tools


def _find_api_tool(tool_name: str) -> dict | None:
    """Find an API tool by name and return its metadata."""
    api_tools = generate_api_tools_from_openapi()
    for tool in api_tools:
        if tool["name"] == tool_name:
            return tool
    return None


def _execute_api_call(path: str, method: str, params: dict) -> str:
    """Execute an API call against the northbound server."""
    # Substitute path parameters
    url_path = path
    for key, value in params.items():
        url_path = url_path.replace(f"{{{key}}}", str(value))

    url = f"{NORTHBOUND_URL}{url_path}"

    try:
        if method == "get":
            response = httpx.get(url, timeout=5.0)
        else:
            # For POST, remove path params from body
            path_params = re.findall(r"\{(\w+)\}", path)
            body = {k: v for k, v in params.items() if k not in path_params}
            response = httpx.post(url, json=body, timeout=5.0)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 404:
            return f"Not found: {url_path}"
        else:
            return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"API call failed: {e}"


def execute_tool(tool_name: str, tool_input: dict, playbooks_dir: Path) -> str:
    """Execute a chat tool and return the result.

    Handles:
    - Playbook tools (static, load from local files)
    - API tools (dynamic, generated from OpenAPI spec)
    """
    # Handle playbook tools
    playbook_result = execute_playbook_tool(tool_name, tool_input, playbooks_dir)
    if playbook_result is not None:
        return playbook_result

    # Handle API tools
    api_tool = _find_api_tool(tool_name)
    if api_tool:
        path = api_tool.get("_path", "")
        method = api_tool.get("_method", "get")
        return _execute_api_call(path, method, tool_input)

    return f"Unknown tool: {tool_name}"
