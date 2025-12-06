#!/usr/bin/env python3
"""Demo of ContextMesh with live FastAPI mock backend.

Run the mock server first (from excom-context-mesh-mock-server repo):
    cd ../excom-context-mesh-mock-server
    poetry run mock-server

Then run this demo:
    poetry run python examples/telco_billing/demo_with_backend.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from contextmesh import ContextMeshConfig, ContextMeshOrchestrator

# Load environment variables
load_dotenv()


def print_section(title: str, char: str = "="):
    """Print a section header."""
    print(f"\n{char * 70}")
    print(f" {title}")
    print(f"{char * 70}")


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def main():
    """Run demo with live backend."""
    example_dir = Path(__file__).parent

    print_section("CONTEXTMESH + FASTAPI BACKEND DEMO", "=")

    # =========================================================================
    # Configuration - Point to local mock server
    # =========================================================================
    print_section("Configuration", "-")

    # Update OpenAPI spec to use local server
    config = ContextMeshConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openapi_specs_dir=str(example_dir),
        playbooks_dir=str(example_dir / "playbooks"),
        model="claude-haiku-4-5-20251001",
    )

    print(f"Model: {config.model}")
    print(f"Backend: http://localhost:9100 (FastAPI Mock Server)")

    # =========================================================================
    # Create Orchestrator
    # =========================================================================
    print_section("Creating Orchestrator", "-")

    orchestrator = ContextMeshOrchestrator(config)

    # Override the base URL to point to local server
    orchestrator.set_base_url("http://localhost:9100")

    print(f"Playbooks: {orchestrator.list_playbooks()}")
    print(f"Endpoints: {orchestrator.list_endpoints()}")
    print(f"Base URL: http://localhost:9100")

    # =========================================================================
    # Test Scenario 1: High Risk Customer (Full Credit)
    # =========================================================================
    print_section("SCENARIO 1: High Risk Customer - Full Credit Expected", "=")

    context_1 = {
        "db": {
            "customer": {
                "customer_id": "CUST-001",
                "name": "Alice Johnson",
                "tenure_months": 36,
                "arpu": 120.00,
                "churn_risk": "high",
                "outstanding_balance": 50.00,
            },
            "invoice": {
                "number": "INV-2024-001",
                "amount": 150.00,
                "disputed_amount": 75.00,
            },
        },
        "state": {"case_id": "CASE-001"},
        "input": {"dispute_reason": "Charged for service not received"},
    }

    print_subsection("Input Context")
    print(f"  Customer: {context_1['db']['customer']['name']}")
    print(f"  Churn Risk: {context_1['db']['customer']['churn_risk']}")
    print(f"  Tenure: {context_1['db']['customer']['tenure_months']} months")
    print(f"  Disputed Amount: ${context_1['db']['invoice']['disputed_amount']}")

    try:
        print_subsection("Step 1: LLM Planning")
        plan = orchestrator.plan_only(
            trigger="telco_billing_resolution",
            initial_context=context_1,
        )

        print(f"\nComputed Logic Values:")
        for key, value in plan.logic_values.items():
            print(f"  logic.{key} = {value}")

        print(f"\nPlanned Steps:")
        for step in plan.steps:
            print(f"  {step.order}. {step.operation_id}: {step.description}")

        print_subsection("Step 2: Execute Workflow")
        result = orchestrator.execute_workflow(
            trigger="telco_billing_resolution",
            initial_context=context_1,
        )

        print(f"\nWorkflow Success: {result.success}")
        print(f"API Calls Made: {len(result.api_responses)}")

        for i, response in enumerate(result.api_responses, 1):
            print(f"\n  API Call {i}:")
            print(f"    Status: {response.status_code}")
            print(f"    Success: {response.success}")
            if response.body:
                print(f"    Response: {json.dumps(response.body, indent=6)}")
            if response.error:
                print(f"    Error: {response.error}")

        if result.errors:
            print(f"\nErrors: {result.errors}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # Test Scenario 2: Large Dispute (Escalation Required)
    # =========================================================================
    print_section("SCENARIO 2: Large Dispute - Escalation Expected", "=")

    context_2 = {
        "db": {
            "customer": {
                "customer_id": "CUST-002",
                "name": "Bob Smith",
                "tenure_months": 6,
                "arpu": 45.00,
                "churn_risk": "low",
                "outstanding_balance": 200.00,
            },
            "invoice": {
                "number": "INV-2024-002",
                "amount": 500.00,
                "disputed_amount": 350.00,  # Over $200 threshold
            },
        },
        "state": {"case_id": "CASE-002"},
        "input": {"dispute_reason": "Unauthorized premium service charges"},
    }

    print_subsection("Input Context")
    print(f"  Customer: {context_2['db']['customer']['name']}")
    print(f"  Churn Risk: {context_2['db']['customer']['churn_risk']}")
    print(f"  Tenure: {context_2['db']['customer']['tenure_months']} months")
    print(f"  Disputed Amount: ${context_2['db']['invoice']['disputed_amount']} (> $200)")

    try:
        print_subsection("Step 1: LLM Planning")
        plan = orchestrator.plan_only(
            trigger="telco_billing_resolution",
            initial_context=context_2,
        )

        print(f"\nComputed Logic Values:")
        for key, value in plan.logic_values.items():
            print(f"  logic.{key} = {value}")

        print(f"\nPlanned Steps:")
        for step in plan.steps:
            print(f"  {step.order}. {step.operation_id}: {step.description}")

        print_subsection("Step 2: Execute Workflow")
        result = orchestrator.execute_workflow(
            trigger="telco_billing_resolution",
            initial_context=context_2,
        )

        print(f"\nWorkflow Success: {result.success}")
        print(f"API Calls Made: {len(result.api_responses)}")

        for i, response in enumerate(result.api_responses, 1):
            print(f"\n  API Call {i}:")
            print(f"    Status: {response.status_code}")
            print(f"    Success: {response.success}")
            if response.body:
                print(f"    Response: {json.dumps(response.body, indent=6)}")
            if response.error:
                print(f"    Error: {response.error}")

        if result.errors:
            print(f"\nErrors: {result.errors}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print_section("DEMO COMPLETE", "=")
    print("\nCheck the mock server terminal for API call logs!")


if __name__ == "__main__":
    main()
