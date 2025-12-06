"""Pydantic models for ContextMesh."""

from typing import Any

from pydantic import BaseModel, Field


class ContextMeshConfig(BaseModel):
    """Configuration for ContextMesh orchestrator."""

    anthropic_api_key: str = Field(..., description="Anthropic API key")
    openapi_specs_dir: str = Field(..., description="Directory containing OpenAPI specs")
    playbooks_dir: str = Field(..., description="Directory containing playbooks")
    model: str = Field(default="claude-sonnet-4-20250514", description="Claude model to use")
    max_retries: int = Field(default=3, description="Max retries for API calls")
    timeout: int = Field(default=30, description="Timeout for API calls in seconds")


class PlaybookVariable(BaseModel):
    """Represents a logic variable defined in a playbook."""

    name: str = Field(..., description="Variable name (e.g., 'logic.recommended_credit_amount')")
    description: str = Field(default="", description="Description of the variable")
    type_hint: str | None = Field(default=None, description="Optional type hint")


class Playbook(BaseModel):
    """Structured representation of a Markdown playbook."""

    module_name: str = Field(..., description="Logic module name")
    goal: str = Field(default="", description="Goal/objective of the playbook")
    preconditions: list[str] = Field(default_factory=list, description="Required preconditions")
    steps: list[str] = Field(default_factory=list, description="Execution steps")
    decision_rules: list[str] = Field(default_factory=list, description="Decision rules")
    variables: list[PlaybookVariable] = Field(
        default_factory=list, description="Logic variables to compute"
    )
    raw_markdown: str = Field(default="", description="Original markdown content")


class ContextMeshExtension(BaseModel):
    """Represents x-contextMesh metadata from OpenAPI spec."""

    logic_module: str = Field(..., description="Reference to playbook module")
    description: str = Field(default="", description="Description of the endpoint's role")
    template_params: dict[str, str] = Field(
        default_factory=dict, description="Parameter templates (e.g., '{{db.customer.id}}')"
    )
    state_updates: dict[str, Any] = Field(
        default_factory=dict, description="State update instructions"
    )


class OpenAPIEndpoint(BaseModel):
    """Enriched OpenAPI endpoint with ContextMesh metadata."""

    operation_id: str = Field(..., description="Unique operation identifier")
    path: str = Field(..., description="API path")
    method: str = Field(..., description="HTTP method")
    summary: str = Field(default="", description="Endpoint summary")
    description: str = Field(default="", description="Endpoint description")
    request_schema: dict[str, Any] = Field(
        default_factory=dict, description="Request body schema"
    )
    response_schema: dict[str, Any] = Field(
        default_factory=dict, description="Response schema"
    )
    contextmesh: ContextMeshExtension | None = Field(
        default=None, description="ContextMesh extension metadata"
    )


class WorkflowStep(BaseModel):
    """Individual step in a workflow plan."""

    order: int = Field(..., description="Execution order (1-based)")
    operation_id: str = Field(..., description="Operation to execute")
    description: str = Field(default="", description="What this step does")
    depends_on: list[int] = Field(
        default_factory=list, description="Step numbers this depends on"
    )


class WorkflowPlan(BaseModel):
    """LLM-generated workflow plan."""

    steps: list[WorkflowStep] = Field(default_factory=list, description="Ordered workflow steps")
    logic_values: dict[str, Any] = Field(
        default_factory=dict, description="Computed logic.* values"
    )
    reasoning: str = Field(default="", description="LLM's reasoning for this plan")


class APIResponse(BaseModel):
    """Wrapped API response."""

    status_code: int = Field(..., description="HTTP status code")
    body: dict[str, Any] = Field(default_factory=dict, description="Response body")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    success: bool = Field(default=True, description="Whether the call succeeded")
    error: str | None = Field(default=None, description="Error message if failed")


class StateUpdate(BaseModel):
    """Represents a state update operation."""

    operation: str = Field(..., description="Operation type: write, update, delete")
    table: str = Field(..., description="Target table/collection")
    values: dict[str, Any] = Field(default_factory=dict, description="Values to write")
    condition: dict[str, Any] | None = Field(default=None, description="Update condition")


class WorkflowResult(BaseModel):
    """Result of workflow execution."""

    success: bool = Field(..., description="Whether workflow completed successfully")
    plan: WorkflowPlan | None = Field(default=None, description="The executed plan")
    api_responses: list[APIResponse] = Field(default_factory=list, description="API call results")
    state_updates: list[StateUpdate] = Field(
        default_factory=list, description="State updates applied"
    )
    final_context: dict[str, Any] = Field(default_factory=dict, description="Final context state")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")
