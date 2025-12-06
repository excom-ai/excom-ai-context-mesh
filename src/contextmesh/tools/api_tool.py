"""Convert OpenAPI endpoints to LangChain tools."""

from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from contextmesh.core.models import OpenAPIEndpoint


def create_pydantic_model_from_schema(
    name: str, schema: dict[str, Any]
) -> type[BaseModel]:
    """Create a Pydantic model from an OpenAPI schema.

    Args:
        name: Name for the model class
        schema: OpenAPI schema dictionary

    Returns:
        Dynamically created Pydantic model class
    """
    if not schema or schema.get("type") != "object":
        # Return a simple model with arbitrary kwargs
        return create_model(name, **{"kwargs": (dict, Field(default_factory=dict))})

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, Any] = {}

    for prop_name, prop_schema in properties.items():
        prop_type = _openapi_type_to_python(prop_schema.get("type", "string"))
        description = prop_schema.get("description", "")

        if prop_name in required:
            fields[prop_name] = (prop_type, Field(description=description))
        else:
            fields[prop_name] = (
                prop_type | None,
                Field(default=None, description=description),
            )

    if not fields:
        fields["kwargs"] = (dict, Field(default_factory=dict))

    return create_model(name, **fields)


def _openapi_type_to_python(openapi_type: str) -> type:
    """Convert OpenAPI type to Python type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(openapi_type, str)


def create_api_tool(
    endpoint: OpenAPIEndpoint,
    executor_func: Callable[[str, str, dict[str, Any]], dict[str, Any]],
) -> StructuredTool:
    """Create a LangChain StructuredTool from an OpenAPI endpoint.

    Args:
        endpoint: OpenAPIEndpoint to convert
        executor_func: Function that executes API calls
            Signature: (operation_id, method, params) -> response

    Returns:
        LangChain StructuredTool
    """
    # Create args schema from request schema
    model_name = f"{endpoint.operation_id}Args"
    args_schema = create_pydantic_model_from_schema(model_name, endpoint.request_schema)

    # Build description
    description = endpoint.summary or endpoint.description
    if endpoint.contextmesh:
        description += f"\n\nContextMesh: {endpoint.contextmesh.description}"

    def tool_func(**kwargs: Any) -> dict[str, Any]:
        """Execute the API call."""
        return executor_func(endpoint.operation_id, endpoint.method, kwargs)

    return StructuredTool.from_function(
        func=tool_func,
        name=endpoint.operation_id,
        description=description or f"Call {endpoint.method} {endpoint.path}",
        args_schema=args_schema,
    )


def create_api_tools(
    endpoints: list[OpenAPIEndpoint],
    executor_func: Callable[[str, str, dict[str, Any]], dict[str, Any]],
) -> list[StructuredTool]:
    """Create LangChain tools from multiple endpoints.

    Args:
        endpoints: List of OpenAPIEndpoint objects
        executor_func: Function that executes API calls

    Returns:
        List of LangChain StructuredTools
    """
    return [create_api_tool(ep, executor_func) for ep in endpoints]


class APIToolkit:
    """Toolkit for managing API tools in a workflow."""

    def __init__(
        self,
        endpoints: list[OpenAPIEndpoint],
        executor_func: Callable[[str, str, dict[str, Any]], dict[str, Any]],
    ):
        """Initialize the toolkit.

        Args:
            endpoints: Available API endpoints
            executor_func: Function to execute API calls
        """
        self.endpoints = {ep.operation_id: ep for ep in endpoints}
        self.executor_func = executor_func
        self._tools: dict[str, StructuredTool] = {}

    def get_tool(self, operation_id: str) -> StructuredTool | None:
        """Get or create a tool for an operation.

        Args:
            operation_id: The operation ID

        Returns:
            StructuredTool or None if operation not found
        """
        if operation_id not in self._tools:
            endpoint = self.endpoints.get(operation_id)
            if endpoint:
                self._tools[operation_id] = create_api_tool(endpoint, self.executor_func)

        return self._tools.get(operation_id)

    def get_tools(self, operation_ids: list[str] | None = None) -> list[StructuredTool]:
        """Get tools for specified operations or all operations.

        Args:
            operation_ids: List of operation IDs, or None for all

        Returns:
            List of StructuredTools
        """
        if operation_ids is None:
            operation_ids = list(self.endpoints.keys())

        tools = []
        for op_id in operation_ids:
            tool = self.get_tool(op_id)
            if tool:
                tools.append(tool)

        return tools

    def get_tools_for_plan(self, plan) -> list[StructuredTool]:
        """Get tools needed for a workflow plan.

        Args:
            plan: WorkflowPlan object

        Returns:
            List of StructuredTools for plan steps
        """
        operation_ids = [step.operation_id for step in plan.steps]
        return self.get_tools(operation_ids)
