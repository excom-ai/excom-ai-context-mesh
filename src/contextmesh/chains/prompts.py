"""Prompt templates for LangChain chains."""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for workflow planning
PLANNER_SYSTEM_PROMPT = """You are a workflow planning agent for ContextMesh, an orchestration engine.

Your role is to:
1. Analyze the business logic playbook and available API endpoints
2. Compute any logic.* variables defined in the playbook based on the current context
3. Plan which API endpoints to call and in what order
4. Explain your reasoning

You have access to the following context:
- db.* - Database/system data
- state.* - Current workflow state
- input.* - User/trigger input
- logic.* - Variables you compute based on playbook rules

When computing logic.* values, follow the rules in the playbook exactly.
When planning API calls, only use the available endpoints provided.

Respond with a structured plan including:
- logic_values: Any computed logic.* values (as a dictionary without 'logic.' prefix in keys)
- steps: List of workflow steps with operation_id, order, and description
- reasoning: Your explanation of why this plan is appropriate
"""

PLANNER_HUMAN_PROMPT = """## Playbook: {playbook_name}

{playbook_content}

## Available API Endpoints

{endpoints_summary}

## Current Context

```json
{context_json}
```

Based on the playbook rules and current context:
1. Compute any logic.* variables needed
2. Plan which API endpoints to call and in what order

Provide your plan as a structured response."""

# Create the planner prompt template
PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", PLANNER_SYSTEM_PROMPT),
        ("human", PLANNER_HUMAN_PROMPT),
    ]
)

# System prompt for execution agent
EXECUTOR_SYSTEM_PROMPT = """You are a workflow execution agent for ContextMesh.

You have been given a plan to execute. Your job is to:
1. Call the appropriate API tools in the planned order
2. Handle responses and update context as needed
3. Apply any state updates defined in the endpoint configurations

Use the provided tools to make API calls. Follow the plan exactly unless you encounter errors.

If an API call fails, document the error and decide whether to:
- Retry the call
- Skip to the next step
- Abort the workflow

Always report what actions you took and their results."""

EXECUTOR_HUMAN_PROMPT = """## Workflow Plan

{plan_summary}

## Context

```json
{context_json}
```

## Resolved Parameters

{resolved_params}

Execute the workflow plan using the available API tools."""

EXECUTOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", EXECUTOR_SYSTEM_PROMPT),
        ("human", EXECUTOR_HUMAN_PROMPT),
    ]
)

# Simple prompt for computing logic values only
LOGIC_COMPUTER_SYSTEM_PROMPT = """You are a rule evaluator for ContextMesh.

Your task is to compute logic.* variables based on playbook rules and context data.

Follow the decision rules exactly as specified in the playbook.
Use the context data to evaluate conditions.
Return only the computed values as a JSON object.

Example output:
{{"recommended_credit_amount": 150.00, "escalation_required": false}}

Do not include the 'logic.' prefix in your output keys."""

LOGIC_COMPUTER_HUMAN_PROMPT = """## Playbook Rules

{playbook_content}

## Variables to Compute

{variables_list}

## Current Context

```json
{context_json}
```

Compute the logic variables based on the rules and context above.
Return a JSON object with the computed values."""

LOGIC_COMPUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", LOGIC_COMPUTER_SYSTEM_PROMPT),
        ("human", LOGIC_COMPUTER_HUMAN_PROMPT),
    ]
)


def format_endpoints_summary(endpoints: list) -> str:
    """Format endpoints list for inclusion in prompts.

    Args:
        endpoints: List of OpenAPIEndpoint objects

    Returns:
        Formatted string describing available endpoints
    """
    lines = []
    for ep in endpoints:
        lines.append(f"### {ep.operation_id}")
        lines.append(f"- **{ep.method}** `{ep.path}`")
        if ep.summary:
            lines.append(f"- {ep.summary}")
        if ep.contextmesh:
            lines.append(f"- Logic Module: {ep.contextmesh.logic_module}")
            if ep.contextmesh.template_params:
                lines.append("- Template Parameters:")
                for key, value in ep.contextmesh.template_params.items():
                    lines.append(f"  - {key}: `{value}`")
        lines.append("")

    return "\n".join(lines)


def format_plan_summary(plan) -> str:
    """Format workflow plan for inclusion in prompts.

    Args:
        plan: WorkflowPlan object

    Returns:
        Formatted string describing the plan
    """
    lines = ["### Steps"]
    for step in plan.steps:
        lines.append(f"{step.order}. **{step.operation_id}**: {step.description}")

    if plan.logic_values:
        lines.append("\n### Computed Logic Values")
        for key, value in plan.logic_values.items():
            lines.append(f"- logic.{key} = {value}")

    lines.append(f"\n### Reasoning\n{plan.reasoning}")

    return "\n".join(lines)
