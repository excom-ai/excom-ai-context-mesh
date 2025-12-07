"""Generate Anthropic-compatible tools from OpenAPI specifications."""

import json
import re

import httpx


def fetch_openapi_spec(openapi_url: str) -> dict | None:
    """Fetch the OpenAPI spec from a server.

    Args:
        openapi_url: URL to fetch OpenAPI spec from (e.g., http://localhost:8052/openapi.json)

    Returns:
        Parsed OpenAPI spec dict, or None if fetch failed
    """
    try:
        response = httpx.get(openapi_url, timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def _convert_params_to_schema(path: str, operation: dict) -> dict:
    """Convert path and query parameters to JSON schema properties."""
    properties = {}
    required = []

    # Extract path parameters like {customer_id}
    path_params = re.findall(r"\{(\w+)\}", path)

    # Get parameter details from operation
    params = operation.get("parameters", [])
    for param in params:
        param_in = param.get("in")
        # Handle both path and query parameters
        if param_in in ("path", "query"):
            name = param["name"]
            schema = param.get("schema", {"type": "string"})
            properties[name] = {
                "type": schema.get("type", "string"),
                "description": param.get("description", f"The {name} parameter"),
            }
            # Path params are always required; query params use their required flag
            if param_in == "path" or param.get("required", False):
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
    # Add method prefix for non-GET
    if method != "get":
        name = f"{method}_{name}"
    return name


def generate_tools_from_openapi(
    spec: dict,
    excluded_tags: set[str] | None = None,
) -> list[dict]:
    """Generate Anthropic-compatible tool definitions from OpenAPI spec.

    Args:
        spec: Parsed OpenAPI specification
        excluded_tags: Set of tags to exclude (e.g., {"Debug", "Health"})

    Returns:
        List of tool definitions with _path and _method metadata
    """
    if excluded_tags is None:
        excluded_tags = {"Debug", "Health"}

    tools = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            tags = operation.get("tags", [])

            # Skip excluded endpoints
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
                input_schema = _convert_params_to_schema(path, operation)
            else:
                # For POST/PUT/PATCH, use request body schema
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


def execute_api_tool(
    tool: dict,
    params: dict,
    base_url: str,
) -> str:
    """Execute an API tool and return the result.

    Args:
        tool: Tool definition with _path and _method
        params: Parameters from the tool call
        base_url: Base URL of the API server

    Returns:
        JSON string result or error message
    """
    path = tool.get("_path", "")
    method = tool.get("_method", "get")

    # Extract path parameters from the path template
    path_params = re.findall(r"\{(\w+)\}", path)

    # Substitute path parameters in the URL
    url_path = path
    for key, value in params.items():
        if key in path_params:
            url_path = url_path.replace(f"{{{key}}}", str(value))

    url = f"{base_url}{url_path}"

    try:
        if method == "get":
            # For GET, pass non-path params as query parameters
            query_params = {k: v for k, v in params.items() if k not in path_params}
            response = httpx.get(url, params=query_params, timeout=5.0)
        elif method == "delete":
            # For DELETE, no body needed
            response = httpx.delete(url, timeout=5.0)
        else:
            # For POST/PUT/PATCH, remove path params from body
            body = {k: v for k, v in params.items() if k not in path_params}
            if method == "put":
                response = httpx.put(url, json=body, timeout=5.0)
            elif method == "patch":
                response = httpx.patch(url, json=body, timeout=5.0)
            else:
                response = httpx.post(url, json=body, timeout=5.0)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 404:
            return f"Not found: {url_path}"
        else:
            return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"API call failed: {e}"


class OpenAPIToolkit:
    """Toolkit for managing tools generated from an OpenAPI spec."""

    def __init__(self, openapi_url: str, excluded_tags: set[str] | None = None):
        """Initialize the toolkit.

        Args:
            openapi_url: URL to fetch OpenAPI spec from
            excluded_tags: Tags to exclude from tool generation
        """
        self.openapi_url = openapi_url
        self.base_url = openapi_url.rsplit("/", 1)[0]  # Remove /openapi.json
        self.excluded_tags = excluded_tags or {"Debug", "Health"}
        self._tools: list[dict] | None = None
        self._tools_by_name: dict[str, dict] = {}

    def get_tools(self) -> list[dict]:
        """Get all available tools (fetches spec if needed).

        Returns:
            List of tool definitions without internal metadata
        """
        if self._tools is None:
            spec = fetch_openapi_spec(self.openapi_url)
            if spec:
                self._tools = generate_tools_from_openapi(spec, self.excluded_tags)
                self._tools_by_name = {t["name"]: t for t in self._tools}
            else:
                self._tools = []

        # Return tools without internal metadata
        return [
            {k: v for k, v in tool.items() if not k.startswith("_")}
            for tool in self._tools
        ]

    def execute(self, tool_name: str, params: dict) -> str:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool

        Returns:
            Result string or error message
        """
        # Ensure tools are loaded
        self.get_tools()

        tool = self._tools_by_name.get(tool_name)
        if not tool:
            return f"Unknown API tool: {tool_name}"

        return execute_api_tool(tool, params, self.base_url)
