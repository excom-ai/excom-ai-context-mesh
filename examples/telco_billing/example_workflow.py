#!/usr/bin/env python3
"""Example workflow execution using ContextMesh.

This example demonstrates how to use ContextMesh to resolve a billing dispute
using the telco_billing_resolution playbook.
"""

import os
from pathlib import Path

from contextmesh import ContextMeshConfig, ContextMeshOrchestrator


def main():
    """Run the example billing dispute workflow."""
    # Get the directory containing this example
    example_dir = Path(__file__).parent

    # Configure ContextMesh
    config = ContextMeshConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openapi_specs_dir=str(example_dir),
        playbooks_dir=str(example_dir / "playbooks"),
        model="claude-haiku-4-5-20251001",
    )

    # Create orchestrator
    orchestrator = ContextMeshOrchestrator(config)

    # Define the initial context for a billing dispute scenario
    initial_context = {
        "db": {
            "customer": {
                "customer_id": "CUST-12345",
                "name": "John Smith",
                "email": "john.smith@example.com",
                "tenure_months": 24,
                "arpu": 85.50,
                "churn_risk": "high",
                "outstanding_balance": 150.00,
            },
            "invoice": {
                "number": "INV-98765",
                "amount": 150.00,
                "disputed_amount": 75.00,
                "issue_date": "2024-01-15",
                "due_date": "2024-02-15",
            },
        },
        "state": {
            "case_id": "CASE-567",
            "workflow_type": "billing_dispute",
        },
        "input": {
            "dispute_reason": "Incorrect data charges",
            "requested_action": "credit",
        },
    }

    print("=" * 60)
    print("ContextMesh - Billing Dispute Resolution Example")
    print("=" * 60)
    print()

    # List available resources
    print("Available Playbooks:", orchestrator.list_playbooks())
    print("Available Endpoints:", orchestrator.list_endpoints())
    print()

    # Option 1: Just compute logic values (no API calls)
    print("-" * 40)
    print("Step 1: Computing Logic Values")
    print("-" * 40)

    try:
        logic_values = orchestrator.compute_logic_values(
            trigger="telco_billing_resolution",
            initial_context=initial_context,
        )
        print("Computed logic values:")
        for key, value in logic_values.items():
            print(f"  logic.{key} = {value}")
    except Exception as e:
        print(f"Error computing logic values: {e}")

    print()

    # Option 2: Plan without executing
    print("-" * 40)
    print("Step 2: Planning Workflow")
    print("-" * 40)

    try:
        plan = orchestrator.plan_only(
            trigger="telco_billing_resolution",
            initial_context=initial_context,
        )

        print(f"Workflow Plan ({len(plan.steps)} steps):")
        for step in plan.steps:
            print(f"  {step.order}. {step.operation_id}: {step.description}")

        print()
        print("Logic Values in Plan:")
        for key, value in plan.logic_values.items():
            print(f"  logic.{key} = {value}")

        print()
        print("Reasoning:")
        print(f"  {plan.reasoning}")

    except Exception as e:
        print(f"Error planning workflow: {e}")

    print()

    # Option 3: Full execution (commented out as it requires real APIs)
    # print("-" * 40)
    # print("Step 3: Executing Workflow")
    # print("-" * 40)
    #
    # result = orchestrator.execute_workflow(
    #     trigger="telco_billing_resolution",
    #     initial_context=initial_context,
    # )
    #
    # print(f"Workflow completed: {'Success' if result.success else 'Failed'}")
    # print(f"API calls made: {len(result.api_responses)}")
    # print(f"State updates: {len(result.state_updates)}")
    #
    # if result.errors:
    #     print("Errors:")
    #     for error in result.errors:
    #         print(f"  - {error}")

    print()
    print("=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
