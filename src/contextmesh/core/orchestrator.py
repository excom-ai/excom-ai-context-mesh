"""Main orchestration engine for ContextMesh."""

from pathlib import Path
from typing import Any

from contextmesh.chains.planner import WorkflowPlanner
from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import (
    APIResponse,
    ContextMeshConfig,
    OpenAPIEndpoint,
    Playbook,
    StateUpdate,
    WorkflowPlan,
    WorkflowResult,
)
from contextmesh.execution.api_executor import APIExecutor
from contextmesh.execution.state_manager import InMemoryStateBackend, StateManager
from contextmesh.parsers.openapi_parser import OpenAPIParser, OpenAPISpec
from contextmesh.parsers.playbook_parser import PlaybookParser
from contextmesh.templating.engine import TemplateEngine
from contextmesh.utils.exceptions import WorkflowExecutionError


class ContextMeshOrchestrator:
    """Main orchestration engine that ties all components together."""

    def __init__(self, config: ContextMeshConfig):
        """Initialize the orchestrator.

        Args:
            config: Configuration for the orchestrator
        """
        self.config = config

        # Initialize components
        self.planner = WorkflowPlanner(
            api_key=config.anthropic_api_key,
            model=config.model,
        )
        self.playbook_parser = PlaybookParser()
        self.openapi_parser = OpenAPIParser()
        self.template_engine = TemplateEngine()
        self.state_manager = StateManager(InMemoryStateBackend())

        # Load specs and playbooks
        self._specs: dict[str, OpenAPISpec] = {}
        self._playbooks: dict[str, Playbook] = {}
        self._base_url_override: str | None = None
        self._load_resources()

    def _load_resources(self) -> None:
        """Load OpenAPI specs and playbooks from configured directories."""
        # Load OpenAPI specs
        specs_path = Path(self.config.openapi_specs_dir)
        if specs_path.is_dir():
            for file_path in specs_path.glob("*.yaml"):
                try:
                    spec = self.openapi_parser.load_spec(file_path)
                    self._specs[spec.title] = spec
                except Exception:
                    pass  # Skip invalid specs

            for file_path in specs_path.glob("*.yml"):
                try:
                    spec = self.openapi_parser.load_spec(file_path)
                    self._specs[spec.title] = spec
                except Exception:
                    pass

        # Load playbooks
        playbooks_path = Path(self.config.playbooks_dir)
        if playbooks_path.is_dir():
            for file_path in playbooks_path.glob("*.md"):
                try:
                    playbook = self.playbook_parser.load_playbook(file_path)
                    self._playbooks[playbook.module_name] = playbook
                except Exception:
                    pass  # Skip invalid playbooks

    def execute_workflow(
        self,
        trigger: str,
        initial_context: dict[str, Any],
    ) -> WorkflowResult:
        """Execute a workflow.

        Args:
            trigger: Logic module name to execute (e.g., 'billing_dispute_resolution')
            initial_context: Initial context data with db, state, input namespaces

        Returns:
            WorkflowResult with execution details
        """
        errors: list[str] = []
        api_responses: list[APIResponse] = []
        state_updates: list[StateUpdate] = []

        # Initialize context
        context = RuntimeContext(initial_context)

        try:
            # Load playbook
            playbook = self._get_playbook(trigger)
            if not playbook:
                raise WorkflowExecutionError(f"Playbook not found: {trigger}")

            # Find relevant endpoints
            endpoints = self._get_endpoints_for_module(trigger)
            if not endpoints:
                raise WorkflowExecutionError(
                    f"No API endpoints found for logic module: {trigger}"
                )

            # Get base URL for API calls
            base_url = self._get_base_url()

            # Plan the workflow using LLM
            plan = self.planner.plan_workflow(playbook, endpoints, context)

            # Update context with computed logic values
            if plan.logic_values:
                context.set_logic_values(plan.logic_values)

            # Execute the plan
            api_executor = APIExecutor(base_url=base_url, timeout=self.config.timeout)

            try:
                for step in sorted(plan.steps, key=lambda s: s.order):
                    # Find the endpoint
                    endpoint = self._get_endpoint_by_id(step.operation_id)
                    if not endpoint:
                        errors.append(f"Endpoint not found: {step.operation_id}")
                        continue

                    # Execute the API call
                    response = api_executor.execute_with_templates(endpoint, context)
                    api_responses.append(response)

                    # Update context with response
                    context.update_from_response(response.body)

                    # Apply state updates if configured
                    if endpoint.contextmesh and endpoint.contextmesh.state_updates:
                        updates = self.state_manager.apply_updates(
                            endpoint.contextmesh.state_updates,
                            context,
                            response,
                        )
                        state_updates.extend(updates)

                    # Check for failure
                    if not response.success:
                        errors.append(
                            f"API call failed: {step.operation_id} - {response.error}"
                        )

            finally:
                api_executor.close()

            return WorkflowResult(
                success=len(errors) == 0,
                plan=plan,
                api_responses=api_responses,
                state_updates=state_updates,
                final_context=context.to_dict(),
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            return WorkflowResult(
                success=False,
                plan=None,
                api_responses=api_responses,
                state_updates=state_updates,
                final_context=context.to_dict(),
                errors=errors,
            )

    def plan_only(
        self,
        trigger: str,
        initial_context: dict[str, Any],
    ) -> WorkflowPlan:
        """Generate a workflow plan without executing it.

        Args:
            trigger: Logic module name
            initial_context: Initial context data

        Returns:
            WorkflowPlan (not executed)
        """
        context = RuntimeContext(initial_context)

        playbook = self._get_playbook(trigger)
        if not playbook:
            raise WorkflowExecutionError(f"Playbook not found: {trigger}")

        endpoints = self._get_endpoints_for_module(trigger)
        if not endpoints:
            raise WorkflowExecutionError(
                f"No API endpoints found for logic module: {trigger}"
            )

        return self.planner.plan_workflow(playbook, endpoints, context)

    def compute_logic_values(
        self,
        trigger: str,
        initial_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute logic.* values without executing workflow.

        Args:
            trigger: Logic module name
            initial_context: Initial context data

        Returns:
            Dictionary of computed logic values
        """
        context = RuntimeContext(initial_context)

        playbook = self._get_playbook(trigger)
        if not playbook:
            raise WorkflowExecutionError(f"Playbook not found: {trigger}")

        return self.planner.compute_logic_values(playbook, context)

    def _get_playbook(self, module_name: str) -> Playbook | None:
        """Get a playbook by module name."""
        return self._playbooks.get(module_name)

    def _get_endpoints_for_module(self, logic_module: str) -> list[OpenAPIEndpoint]:
        """Get all endpoints associated with a logic module."""
        endpoints: list[OpenAPIEndpoint] = []

        for spec in self._specs.values():
            endpoints.extend(spec.get_endpoints_by_logic_module(logic_module))

        return endpoints

    def _get_endpoint_by_id(self, operation_id: str) -> OpenAPIEndpoint | None:
        """Get an endpoint by operation ID across all specs."""
        for spec in self._specs.values():
            endpoint = spec.get_endpoint(operation_id)
            if endpoint:
                return endpoint
        return None

    def _get_base_url(self) -> str:
        """Get base URL from loaded specs or override."""
        if self._base_url_override:
            return self._base_url_override
        for spec in self._specs.values():
            base_url = spec.get_base_url()
            if base_url:
                return base_url
        return ""

    def set_base_url(self, base_url: str) -> None:
        """Override the base URL for API calls.

        Args:
            base_url: Base URL to use (e.g., 'http://localhost:8000')
        """
        self._base_url_override = base_url

    def add_playbook(self, playbook: Playbook) -> None:
        """Add a playbook to the orchestrator.

        Args:
            playbook: Playbook to add
        """
        self._playbooks[playbook.module_name] = playbook

    def add_spec(self, spec: OpenAPISpec) -> None:
        """Add an OpenAPI spec to the orchestrator.

        Args:
            spec: OpenAPISpec to add
        """
        self._specs[spec.title] = spec

    def list_playbooks(self) -> list[str]:
        """List available playbook module names."""
        return list(self._playbooks.keys())

    def list_endpoints(self) -> list[str]:
        """List all available endpoint operation IDs."""
        operation_ids: list[str] = []
        for spec in self._specs.values():
            for endpoint in spec.endpoints:
                operation_ids.append(endpoint.operation_id)
        return operation_ids
