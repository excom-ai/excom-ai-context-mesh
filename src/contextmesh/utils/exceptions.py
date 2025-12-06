"""Custom exceptions for ContextMesh."""


class ContextMeshError(Exception):
    """Base exception for ContextMesh errors."""

    pass


class PlaybookParseError(ContextMeshError):
    """Error parsing a playbook file."""

    pass


class OpenAPIParseError(ContextMeshError):
    """Error parsing an OpenAPI specification."""

    pass


class TemplateResolutionError(ContextMeshError):
    """Error resolving a template expression."""

    pass


class ContextPathError(ContextMeshError):
    """Error accessing a context path."""

    pass


class WorkflowExecutionError(ContextMeshError):
    """Error executing a workflow."""

    pass


class APIExecutionError(ContextMeshError):
    """Error executing an API call."""

    pass
