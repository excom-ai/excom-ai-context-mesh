"""LangChain-based workflow planner."""

import json
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser

from contextmesh.chains.prompts import (
    LOGIC_COMPUTER_PROMPT,
    PLANNER_PROMPT,
    format_endpoints_summary,
)
from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import (
    OpenAPIEndpoint,
    Playbook,
    WorkflowPlan,
    WorkflowStep,
)


class WorkflowPlanner:
    """LangChain-based workflow planner using Claude."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        """Initialize the planner.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.llm = ChatAnthropic(
            model=model,
            api_key=api_key,
            max_tokens=4096,
        )
        self.json_parser = JsonOutputParser()

    def plan_workflow(
        self,
        playbook: Playbook,
        endpoints: list[OpenAPIEndpoint],
        context: RuntimeContext,
    ) -> WorkflowPlan:
        """Generate a workflow plan using the LLM.

        Args:
            playbook: The business logic playbook
            endpoints: Available API endpoints
            context: Current runtime context

        Returns:
            WorkflowPlan with steps and computed logic values
        """
        # Build the prompt
        prompt_values = {
            "playbook_name": playbook.module_name,
            "playbook_content": playbook.raw_markdown,
            "endpoints_summary": format_endpoints_summary(endpoints),
            "context_json": json.dumps(context.to_dict(), indent=2),
        }

        # Create chain with structured output
        chain = PLANNER_PROMPT | self.llm.with_structured_output(WorkflowPlanSchema)

        # Execute the chain
        result = chain.invoke(prompt_values)

        # Convert to WorkflowPlan
        return self._schema_to_plan(result)

    def compute_logic_values(
        self,
        playbook: Playbook,
        context: RuntimeContext,
    ) -> dict[str, Any]:
        """Compute logic.* variables using the LLM.

        Args:
            playbook: The business logic playbook
            context: Current runtime context

        Returns:
            Dictionary of computed logic values (without 'logic.' prefix)
        """
        if not playbook.variables:
            return {}

        variables_list = "\n".join(
            f"- {v.name}: {v.description}" for v in playbook.variables
        )

        prompt_values = {
            "playbook_content": playbook.raw_markdown,
            "variables_list": variables_list,
            "context_json": json.dumps(context.to_dict(), indent=2),
        }

        # Create chain
        chain = LOGIC_COMPUTER_PROMPT | self.llm | self.json_parser

        # Execute
        result = chain.invoke(prompt_values)

        return result if isinstance(result, dict) else {}

    def _schema_to_plan(self, schema_result: Any) -> WorkflowPlan:
        """Convert LLM schema output to WorkflowPlan model."""
        if isinstance(schema_result, dict):
            steps = []
            for i, step_data in enumerate(schema_result.get("steps", []), 1):
                steps.append(
                    WorkflowStep(
                        order=step_data.get("order", i),
                        operation_id=step_data.get("operation_id", ""),
                        description=step_data.get("description", ""),
                        depends_on=step_data.get("depends_on", []),
                    )
                )

            return WorkflowPlan(
                steps=steps,
                logic_values=schema_result.get("logic_values", {}),
                reasoning=schema_result.get("reasoning", ""),
            )

        # If it's already a WorkflowPlan-like object with attributes
        steps = []
        for i, step_data in enumerate(getattr(schema_result, "steps", []), 1):
            if isinstance(step_data, dict):
                steps.append(
                    WorkflowStep(
                        order=step_data.get("order", i),
                        operation_id=step_data.get("operation_id", ""),
                        description=step_data.get("description", ""),
                        depends_on=step_data.get("depends_on", []),
                    )
                )
            else:
                steps.append(
                    WorkflowStep(
                        order=getattr(step_data, "order", i),
                        operation_id=getattr(step_data, "operation_id", ""),
                        description=getattr(step_data, "description", ""),
                        depends_on=getattr(step_data, "depends_on", []),
                    )
                )

        return WorkflowPlan(
            steps=steps,
            logic_values=getattr(schema_result, "logic_values", {}),
            reasoning=getattr(schema_result, "reasoning", ""),
        )


# Pydantic schema for structured output
from pydantic import BaseModel, Field


class WorkflowStepSchema(BaseModel):
    """Schema for a workflow step."""

    order: int = Field(description="Execution order (1-based)")
    operation_id: str = Field(description="Operation ID of the endpoint to call")
    description: str = Field(description="Description of what this step does")
    depends_on: list[int] = Field(
        default_factory=list, description="Step orders this depends on"
    )


class WorkflowPlanSchema(BaseModel):
    """Schema for structured LLM output."""

    steps: list[WorkflowStepSchema] = Field(
        description="Ordered list of workflow steps"
    )
    logic_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Computed logic values without 'logic.' prefix",
    )
    reasoning: str = Field(
        description="Explanation of why this plan is appropriate"
    )
