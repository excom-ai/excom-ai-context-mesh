"""HTTP API executor for making actual API calls."""

from typing import Any

import httpx

from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import APIResponse, OpenAPIEndpoint
from contextmesh.templating.engine import TemplateEngine
from contextmesh.utils.exceptions import APIExecutionError


class APIExecutor:
    """Executes HTTP API calls based on OpenAPI endpoints."""

    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ):
        """Initialize the API executor.

        Args:
            base_url: Base URL for API calls
            timeout: Request timeout in seconds
            headers: Default headers to include in requests
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_headers = headers or {}
        self.template_engine = TemplateEngine()
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers=self.default_headers,
            )
        return self._client

    def execute(
        self,
        endpoint: OpenAPIEndpoint,
        params: dict[str, Any],
        context: RuntimeContext | None = None,
    ) -> APIResponse:
        """Execute an API call.

        Args:
            endpoint: The OpenAPI endpoint to call
            params: Request parameters (already resolved)
            context: Optional context for additional template resolution

        Returns:
            APIResponse with results
        """
        # Build full URL
        url = self._build_url(endpoint.path, params)

        # Separate body params from query/path params
        body_params, query_params = self._separate_params(endpoint, params)

        try:
            response = self._make_request(
                method=endpoint.method,
                url=url,
                body=body_params if body_params else None,
                query=query_params if query_params else None,
            )

            return APIResponse(
                status_code=response.status_code,
                body=response.json() if response.content else {},
                headers=dict(response.headers),
                success=200 <= response.status_code < 300,
            )

        except httpx.HTTPError as e:
            return APIResponse(
                status_code=0,
                body={},
                headers={},
                success=False,
                error=str(e),
            )
        except Exception as e:
            return APIResponse(
                status_code=0,
                body={},
                headers={},
                success=False,
                error=f"Unexpected error: {e}",
            )

    def execute_with_templates(
        self,
        endpoint: OpenAPIEndpoint,
        context: RuntimeContext,
    ) -> APIResponse:
        """Execute an API call with template resolution from context.

        Uses the endpoint's x-contextMesh.templateParams to resolve parameters.

        Args:
            endpoint: The OpenAPI endpoint to call
            context: RuntimeContext for template resolution

        Returns:
            APIResponse with results
        """
        if not endpoint.contextmesh:
            raise APIExecutionError(
                f"Endpoint {endpoint.operation_id} has no contextMesh configuration"
            )

        # Resolve template parameters
        params = self.template_engine.resolve_params(
            endpoint.contextmesh.template_params,
            context,
            strict=False,
        )

        return self.execute(endpoint, params, context)

    def execute_by_operation_id(
        self,
        operation_id: str,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an API call by operation ID (for use as tool function).

        This method signature matches what LangChain tools expect.

        Args:
            operation_id: Operation identifier
            method: HTTP method
            params: Request parameters

        Returns:
            Response body as dict
        """
        url = self._build_url_from_params(params)

        try:
            response = self._make_request(
                method=method,
                url=url,
                body=params,
            )

            result = response.json() if response.content else {}
            result["_status_code"] = response.status_code
            result["_success"] = 200 <= response.status_code < 300
            return result

        except Exception as e:
            return {
                "_success": False,
                "_error": str(e),
                "_status_code": 0,
            }

    def _build_url(self, path: str, params: dict[str, Any]) -> str:
        """Build full URL with path parameter substitution."""
        # Substitute path parameters like {id}
        for key, value in params.items():
            path = path.replace(f"{{{key}}}", str(value))

        return f"{self.base_url}{path}"

    def _build_url_from_params(self, params: dict[str, Any]) -> str:
        """Build URL from params, handling _path special param."""
        path = params.pop("_path", "/")
        return self._build_url(path, params)

    def _separate_params(
        self,
        endpoint: OpenAPIEndpoint,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separate parameters into body and query parameters.

        Args:
            endpoint: The endpoint definition
            params: All parameters

        Returns:
            Tuple of (body_params, query_params)
        """
        body_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}

        schema = endpoint.request_schema
        properties = schema.get("properties", {})

        for key, value in params.items():
            if key.startswith("_"):
                continue  # Skip internal params

            prop_info = properties.get(key, {})
            param_in = prop_info.get("in", "body")

            if param_in == "query":
                query_params[key] = value
            elif param_in == "path":
                continue  # Already handled in URL building
            else:
                body_params[key] = value

        return body_params, query_params

    def _make_request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make the actual HTTP request."""
        method = method.upper()

        if method == "GET":
            return self.client.get(url, params=query)
        elif method == "POST":
            return self.client.post(url, json=body, params=query)
        elif method == "PUT":
            return self.client.put(url, json=body, params=query)
        elif method == "PATCH":
            return self.client.patch(url, json=body, params=query)
        elif method == "DELETE":
            return self.client.delete(url, params=query)
        else:
            raise APIExecutionError(f"Unsupported HTTP method: {method}")

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "APIExecutor":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class MockAPIExecutor(APIExecutor):
    """Mock API executor for testing."""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None):
        """Initialize mock executor.

        Args:
            responses: Dict mapping operation_id to mock responses
        """
        super().__init__()
        self.responses = responses or {}
        self.call_history: list[dict[str, Any]] = []

    def execute(
        self,
        endpoint: OpenAPIEndpoint,
        params: dict[str, Any],
        context: RuntimeContext | None = None,
    ) -> APIResponse:
        """Return mock response."""
        self.call_history.append({
            "operation_id": endpoint.operation_id,
            "method": endpoint.method,
            "path": endpoint.path,
            "params": params,
        })

        mock_response = self.responses.get(
            endpoint.operation_id,
            {"status": "ok", "message": "Mock response"},
        )

        return APIResponse(
            status_code=200,
            body=mock_response,
            headers={},
            success=True,
        )
