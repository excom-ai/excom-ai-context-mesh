#!/usr/bin/env python3
"""Interactive demo of ContextMesh orchestrator with detailed debug output."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from contextmesh import ContextMeshConfig, ContextMeshOrchestrator
from contextmesh.parsers.playbook_parser import PlaybookParser
from contextmesh.parsers.openapi_parser import OpenAPIParser
from contextmesh.templating.engine import TemplateEngine
from contextmesh.core.context import RuntimeContext

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
    """Run interactive demo with debug output."""
    example_dir = Path(__file__).parent

    print_section("CONTEXTMESH DEBUG DEMO", "=")

    # =========================================================================
    # STEP 1: Show Configuration
    # =========================================================================
    print_section("STEP 1: Configuration", "-")

    config = ContextMeshConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openapi_specs_dir=str(example_dir),
        playbooks_dir=str(example_dir / "playbooks"),
        model="claude-haiku-4-5-20251001",
    )

    print(f"API Key: {'*' * 20}...{config.anthropic_api_key[-4:] if config.anthropic_api_key else 'NOT SET'}")
    print(f"Model: {config.model}")
    print(f"Specs Directory: {config.openapi_specs_dir}")
    print(f"Playbooks Directory: {config.playbooks_dir}")

    # =========================================================================
    # STEP 2: Parse Playbook
    # =========================================================================
    print_section("STEP 2: Parsing Playbook", "-")

    playbook_parser = PlaybookParser()
    playbook_path = example_dir / "playbooks" / "telco_billing_resolution.md"
    playbook = playbook_parser.load_playbook(playbook_path)

    print(f"Module Name: {playbook.module_name}")
    print(f"Goal: {playbook.goal}")

    print_subsection("Preconditions")
    for p in playbook.preconditions:
        print(f"  • {p}")

    print_subsection("Steps")
    for i, step in enumerate(playbook.steps, 1):
        print(f"  {i}. {step}")

    print_subsection("Decision Rules")
    for rule in playbook.decision_rules:
        print(f"  • {rule}")

    print_subsection("Logic Variables to Compute")
    for var in playbook.variables:
        print(f"  • {var.name}")

    # =========================================================================
    # STEP 3: Parse OpenAPI Spec
    # =========================================================================
    print_section("STEP 3: Parsing OpenAPI Spec", "-")

    openapi_parser = OpenAPIParser()
    spec_path = example_dir / "openapi.yaml"
    spec = openapi_parser.load_spec(spec_path)

    print(f"API Title: {spec.title}")
    print(f"API Version: {spec.version}")
    print(f"Base URL: {spec.get_base_url()}")

    print_subsection("Endpoints with x-contextMesh")
    for ep in spec.endpoints:
        if ep.contextmesh:
            print(f"\n  📌 {ep.operation_id}")
            print(f"     Method: {ep.method} {ep.path}")
            print(f"     Logic Module: {ep.contextmesh.logic_module}")
            print(f"     Template Params:")
            for key, value in ep.contextmesh.template_params.items():
                if isinstance(value, dict):
                    print(f"       • {key}: (nested object)")
                else:
                    print(f"       • {key}: {value}")

    # =========================================================================
    # STEP 4: Create Orchestrator
    # =========================================================================
    print_section("STEP 4: Creating Orchestrator", "-")

    orchestrator = ContextMeshOrchestrator(config)

    print(f"Loaded Playbooks: {orchestrator.list_playbooks()}")
    print(f"Loaded Endpoints: {orchestrator.list_endpoints()}")

    # =========================================================================
    # STEP 5: Test Scenario
    # =========================================================================
    print_section("STEP 5: Test Scenario - High Risk Customer", "-")

    initial_context = {
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

    print_subsection("Initial Context (JSON)")
    print(json.dumps(initial_context, indent=2))

    # =========================================================================
    # STEP 6: Create RuntimeContext
    # =========================================================================
    print_section("STEP 6: RuntimeContext Demo", "-")

    context = RuntimeContext(initial_context)

    print("Reading values with dot notation:")
    print(f"  context.get('db.customer.name') = {context.get('db.customer.name')}")
    print(f"  context.get('db.customer.tenure_months') = {context.get('db.customer.tenure_months')}")
    print(f"  context.get('db.customer.churn_risk') = {context.get('db.customer.churn_risk')}")
    print(f"  context.get('db.invoice.disputed_amount') = {context.get('db.invoice.disputed_amount')}")
    print(f"  context.get('state.case_id') = {context.get('state.case_id')}")
    print(f"  context.get('input.dispute_reason') = {context.get('input.dispute_reason')}")

    # =========================================================================
    # STEP 7: Template Resolution Demo
    # =========================================================================
    print_section("STEP 7: Template Resolution Demo", "-")

    template_engine = TemplateEngine()

    templates = [
        "{{db.customer.customer_id}}",
        "{{db.invoice.number}}",
        "Customer {{db.customer.name}} has case {{state.case_id}}",
        "Dispute amount: ${{db.invoice.disputed_amount}}",
    ]

    for template in templates:
        resolved = template_engine.resolve(template, context)
        print(f"  Template: {template}")
        print(f"  Resolved: {resolved}")
        print()

    # =========================================================================
    # STEP 8: LLM Planning
    # =========================================================================
    print_section("STEP 8: LLM Workflow Planning", "-")

    print("Sending to Claude Haiku for planning...")
    print("  - Playbook content")
    print("  - Available endpoints")
    print("  - Current context")
    print()

    try:
        plan = orchestrator.plan_only(
            trigger="telco_billing_resolution",
            initial_context=initial_context,
        )

        print_subsection("Computed Logic Values")
        for key, value in plan.logic_values.items():
            print(f"  logic.{key} = {value}")

        print_subsection("Workflow Steps")
        for step in plan.steps:
            print(f"\n  Step {step.order}: {step.operation_id}")
            print(f"    Description: {step.description}")
            if step.depends_on:
                print(f"    Depends on: steps {step.depends_on}")

        print_subsection("LLM Reasoning")
        print(plan.reasoning)

        # =====================================================================
        # STEP 9: Template Resolution with Logic Values
        # =====================================================================
        print_section("STEP 9: Resolving Templates with Logic Values", "-")

        # Update context with computed logic values
        context.set_logic_values(plan.logic_values)

        print("Context updated with logic values:")
        for key in plan.logic_values:
            print(f"  context.get('logic.{key}') = {context.get(f'logic.{key}')}")

        # Now resolve the endpoint templates
        print_subsection("Resolving createBillingAdjustment Template Params")

        endpoint = spec.get_endpoint("createBillingAdjustment")
        if endpoint and endpoint.contextmesh:
            for key, template in endpoint.contextmesh.template_params.items():
                if isinstance(template, str) and "{{" in template:
                    try:
                        resolved = template_engine.resolve(template, context)
                        print(f"  {key}:")
                        print(f"    Template: {template}")
                        print(f"    Resolved: {resolved}")
                    except Exception as e:
                        print(f"  {key}: Error - {e}")
                else:
                    print(f"  {key}: {template} (static)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print_section("DEMO COMPLETE", "=")


if __name__ == "__main__":
    main()
