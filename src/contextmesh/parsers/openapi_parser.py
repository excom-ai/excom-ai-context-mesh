"""Parser for OpenAPI specifications with x-contextMesh extensions."""

from pathlib import Path
from typing import Any

import yaml

from contextmesh.core.models import ContextMeshExtension, OpenAPIEndpoint
from contextmesh.utils.exceptions import OpenAPIParseError


class OpenAPISpec:
    """Parsed OpenAPI specification with ContextMesh extensions."""

    def __init__(
        self,
        title: str,
        version: str,
        servers: list[dict[str, Any]],
        endpoints: list[OpenAPIEndpoint],
        raw_spec: dict[str, Any],
    ):
        self.title = title
        self.version = version
        self.servers = servers
        self.endpoints = endpoints
        self.raw_spec = raw_spec
        self._endpoint_map = {ep.operation_id: ep for ep in endpoints}

    def get_endpoint(self, operation_id: str) -> OpenAPIEndpoint | None:
        """Get an endpoint by operation ID."""
        return self._endpoint_map.get(operation_id)

    def get_endpoints_by_logic_module(self, logic_module: str) -> list[OpenAPIEndpoint]:
        """Get all endpoints associated with a logic module."""
        return [
            ep
            for ep in self.endpoints
            if ep.contextmesh and ep.contextmesh.logic_module == logic_module
        ]

    def get_base_url(self) -> str:
        """Get the base URL from servers."""
        if self.servers:
            return self.servers[0].get("url", "")
        return ""


class OpenAPIParser:
    """Parser for OpenAPI specs with x-contextMesh extensions."""

    EXTENSION_KEY = "x-contextMesh"

    def load_spec(self, file_path: str | Path) -> OpenAPISpec:
        """Load and parse an OpenAPI spec from a file.

        Args:
            file_path: Path to the OpenAPI YAML/JSON file

        Returns:
            Parsed OpenAPISpec object

        Raises:
            OpenAPIParseError: If file cannot be read or parsed
        """
        path = Path(file_path)

        if not path.exists():
            raise OpenAPIParseError(f"OpenAPI spec file not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")

            if path.suffix.lower() in [".yaml", ".yml"]:
                spec_dict = yaml.safe_load(content)
            else:
                import json

                spec_dict = json.loads(content)

        except yaml.YAMLError as e:
            raise OpenAPIParseError(f"Failed to parse YAML: {e}")
        except Exception as e:
            raise OpenAPIParseError(f"Failed to read OpenAPI spec: {e}")

        return self.parse_spec(spec_dict)

    def parse_spec(self, spec_dict: dict[str, Any]) -> OpenAPISpec:
        """Parse an OpenAPI spec dictionary.

        Args:
            spec_dict: Raw OpenAPI spec as a dictionary

        Returns:
            Parsed OpenAPISpec object
        """
        # Extract info
        info = spec_dict.get("info", {})
        title = info.get("title", "Unknown API")
        version = info.get("version", "1.0.0")

        # Extract servers
        servers = spec_dict.get("servers", [])

        # Parse paths/endpoints
        endpoints = self._parse_paths(spec_dict)

        return OpenAPISpec(
            title=title,
            version=version,
            servers=servers,
            endpoints=endpoints,
            raw_spec=spec_dict,
        )

    def _parse_paths(self, spec_dict: dict[str, Any]) -> list[OpenAPIEndpoint]:
        """Parse all paths/operations from the spec."""
        endpoints: list[OpenAPIEndpoint] = []
        paths = spec_dict.get("paths", {})
        components = spec_dict.get("components", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    endpoint = self._parse_operation(
                        path=path,
                        method=method.upper(),
                        operation=operation,
                        components=components,
                    )
                    if endpoint:
                        endpoints.append(endpoint)

        return endpoints

    def _parse_operation(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        components: dict[str, Any],
    ) -> OpenAPIEndpoint | None:
        """Parse a single operation into an OpenAPIEndpoint."""
        operation_id = operation.get("operationId")

        if not operation_id:
            # Generate operation ID from path and method
            operation_id = f"{method.lower()}_{path.replace('/', '_').strip('_')}"

        # Extract schemas
        request_schema = self._extract_request_schema(operation, components)
        response_schema = self._extract_response_schema(operation, components)

        # Extract x-contextMesh extension
        contextmesh = None
        if self.EXTENSION_KEY in operation:
            contextmesh = self._parse_contextmesh_extension(operation[self.EXTENSION_KEY])

        return OpenAPIEndpoint(
            operation_id=operation_id,
            path=path,
            method=method,
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            request_schema=request_schema,
            response_schema=response_schema,
            contextmesh=contextmesh,
        )

    def _parse_contextmesh_extension(
        self, extension_data: dict[str, Any]
    ) -> ContextMeshExtension:
        """Parse x-contextMesh extension data."""
        return ContextMeshExtension(
            logic_module=extension_data.get("logicModule", ""),
            description=extension_data.get("description", ""),
            template_params=extension_data.get("templateParams", {}),
            state_updates=extension_data.get("stateUpdates", {}),
        )

    def _extract_request_schema(
        self, operation: dict[str, Any], components: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract request body schema, resolving $ref if needed."""
        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})

        # Try JSON first, then others
        for content_type in ["application/json", "application/x-www-form-urlencoded"]:
            if content_type in content:
                schema = content[content_type].get("schema", {})
                return self._resolve_schema(schema, components)

        # Also include path/query parameters
        parameters = operation.get("parameters", [])
        if parameters:
            return self._params_to_schema(parameters, components)

        return {}

    def _extract_response_schema(
        self, operation: dict[str, Any], components: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract response schema for success responses."""
        responses = operation.get("responses", {})

        # Look for 200, 201, or default success response
        for status in ["200", "201", "default"]:
            if status in responses:
                response = responses[status]
                content = response.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    return self._resolve_schema(schema, components)

        return {}

    def _resolve_schema(
        self, schema: dict[str, Any], components: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve $ref in schema to actual schema definition."""
        if "$ref" in schema:
            ref_path = schema["$ref"]
            # Handle #/components/schemas/... references
            if ref_path.startswith("#/components/schemas/"):
                schema_name = ref_path.split("/")[-1]
                schemas = components.get("schemas", {})
                if schema_name in schemas:
                    return schemas[schema_name]

        return schema

    def _params_to_schema(
        self, parameters: list[dict[str, Any]], components: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert OpenAPI parameters to a schema-like structure."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in parameters:
            name = param.get("name", "")
            if name:
                schema = param.get("schema", {"type": "string"})
                schema = self._resolve_schema(schema, components)

                properties[name] = {
                    "type": schema.get("type", "string"),
                    "description": param.get("description", ""),
                    "in": param.get("in", "query"),
                }

                if param.get("required", False):
                    required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }


def load_spec(file_path: str | Path) -> OpenAPISpec:
    """Convenience function to load an OpenAPI spec.

    Args:
        file_path: Path to the OpenAPI spec file

    Returns:
        Parsed OpenAPISpec object
    """
    parser = OpenAPIParser()
    return parser.load_spec(file_path)


def load_specs_from_directory(directory: str | Path) -> list[OpenAPISpec]:
    """Load all OpenAPI specs from a directory.

    Args:
        directory: Path to directory containing spec files

    Returns:
        List of parsed OpenAPISpec objects
    """
    parser = OpenAPIParser()
    specs: list[OpenAPISpec] = []
    dir_path = Path(directory)

    if not dir_path.is_dir():
        raise OpenAPIParseError(f"Not a directory: {directory}")

    for file_path in dir_path.glob("*.yaml"):
        try:
            specs.append(parser.load_spec(file_path))
        except OpenAPIParseError:
            pass  # Skip invalid specs

    for file_path in dir_path.glob("*.yml"):
        try:
            specs.append(parser.load_spec(file_path))
        except OpenAPIParseError:
            pass

    return specs
