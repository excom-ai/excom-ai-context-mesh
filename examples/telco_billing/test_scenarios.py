#!/usr/bin/env python3
"""Run test scenarios to demonstrate ContextMesh billing dispute resolution."""

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from contextmesh import ContextMeshConfig, ContextMeshOrchestrator

load_dotenv()

BACKEND_URL = "http://localhost:9100"

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def create_orchestrator():
    """Create and configure the orchestrator."""
    example_dir = Path(__file__).parent
    config = ContextMeshConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openapi_specs_dir=str(example_dir),
        playbooks_dir=str(example_dir / "playbooks"),
        model="claude-haiku-4-5-20251001",
    )
    orchestrator = ContextMeshOrchestrator(config)
    orchestrator.set_base_url(BACKEND_URL)
    return orchestrator


def get_history():
    """Get current dispute history."""
    response = httpx.get(f"{BACKEND_URL}/debug/history")
    return response.json().get("history", {})


def reset_history():
    """Reset all history."""
    httpx.post(f"{BACKEND_URL}/debug/reset")


def print_header(title: str):
    """Print scenario header."""
    print(f"\n{'='*70}")
    print(f"{CYAN}{BOLD} {title}{RESET}")
    print(f"{'='*70}")


def print_result(result, context):
    """Print workflow result summary."""
    if result.plan:
        logic = result.plan.logic_values
        resolution = logic.get("resolution_type", "unknown")
        amount = logic.get("recommended_credit_amount", 0)
        reason = logic.get("resolution_reason", "")

        if resolution == "full_credit":
            print(f"  {GREEN}✓ FULL CREDIT: ${amount}{RESET}")
        elif resolution == "partial_credit":
            print(f"  {YELLOW}◐ PARTIAL CREDIT: ${amount}{RESET}")
        elif resolution == "escalate":
            print(f"  {MAGENTA}↑ ESCALATED{RESET}")
        else:
            print(f"  Resolution: {resolution}")

        print(f"  {DIM}{reason[:100]}...{RESET}" if len(reason) > 100 else f"  {DIM}{reason}{RESET}")

    # Show actions
    for resp in result.api_responses:
        if resp.body:
            if "adjustmentId" in resp.body:
                print(f"  → Adjustment: {resp.body['adjustmentId']} (${resp.body.get('amount', 0)})")
            elif "ticketId" in resp.body:
                print(f"  → Ticket: {resp.body['ticketId']} (priority: {resp.body.get('priority', 'N/A')})")


def enrich_context_with_history(context: dict) -> dict:
    """Add dispute history to context before running workflow."""
    customer_id = context["db"]["customer"]["customer_id"]
    history = get_history().get(customer_id, {"total_credits": 0, "dispute_count": 0})

    # Add history to context
    context["db"]["customer"]["total_credits_last_30_days"] = history.get("total_credits", 0)
    context["db"]["customer"]["disputes_last_30_days"] = history.get("dispute_count", 0)

    return context


def run_scenario(orchestrator, name: str, context: dict):
    """Run a single scenario."""
    customer = context["db"]["customer"]
    invoice = context["db"]["invoice"]

    print(f"\n{BOLD}Scenario: {name}{RESET}")
    print(f"  Customer: {customer['name']} | Tenure: {customer['tenure_months']}mo | Risk: {customer['churn_risk']}")
    print(f"  Dispute: ${invoice['disputed_amount']} on {invoice['number']}")

    # Get history and enrich context
    history = get_history().get(customer["customer_id"], {})
    if history.get("dispute_count", 0) > 0:
        print(f"  {DIM}History: {history['dispute_count']} disputes, ${history['total_credits']} total{RESET}")

    # Enrich context with history before running
    enriched_context = enrich_context_with_history(context.copy())

    # Run workflow with enriched context
    result = orchestrator.execute_workflow(
        trigger="telco_billing_resolution",
        initial_context=enriched_context,
    )

    print_result(result, context)
    return result


def main():
    print(f"\n{CYAN}{BOLD}{'='*70}")
    print(" CONTEXTMESH - BILLING DISPUTE RESOLUTION TEST SCENARIOS")
    print(f"{'='*70}{RESET}\n")

    orchestrator = create_orchestrator()

    # =========================================================================
    # SCENARIO 1: High Risk Customer - Full Credit
    # =========================================================================
    print_header("SCENARIO 1: High Churn Risk Customer")

    scenario1 = {
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
                "number": "INV-001",
                "amount": 150.00,
                "disputed_amount": 75.00,
            },
        },
        "state": {"case_id": "CASE-001"},
        "input": {"dispute_reason": "Charged for service not received"},
    }

    run_scenario(orchestrator, "High risk, 36mo tenure, $75 dispute", scenario1)
    time.sleep(1)

    # =========================================================================
    # SCENARIO 2: Large Dispute - Escalation
    # =========================================================================
    print_header("SCENARIO 2: Large Dispute (>$200)")

    scenario2 = {
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
                "number": "INV-002",
                "amount": 500.00,
                "disputed_amount": 350.00,
            },
        },
        "state": {"case_id": "CASE-002"},
        "input": {"dispute_reason": "Unauthorized premium charges"},
    }

    run_scenario(orchestrator, "Low risk, 6mo tenure, $350 dispute (>$200)", scenario2)
    time.sleep(1)

    # =========================================================================
    # SCENARIO 3: Medium Tenure - Partial Credit
    # =========================================================================
    print_header("SCENARIO 3: Medium Tenure Customer")

    scenario3 = {
        "db": {
            "customer": {
                "customer_id": "CUST-003",
                "name": "Carol Davis",
                "tenure_months": 8,
                "arpu": 65.00,
                "churn_risk": "medium",
                "outstanding_balance": 0.00,
            },
            "invoice": {
                "number": "INV-003",
                "amount": 80.00,
                "disputed_amount": 40.00,
            },
        },
        "state": {"case_id": "CASE-003"},
        "input": {"dispute_reason": "Duplicate charge on account"},
    }

    run_scenario(orchestrator, "Medium risk, 8mo tenure, $40 dispute", scenario3)
    time.sleep(1)

    # =========================================================================
    # SCENARIO 4: Long Tenure Customer
    # =========================================================================
    print_header("SCENARIO 4: Long Tenure Customer (>12 months)")

    scenario4 = {
        "db": {
            "customer": {
                "customer_id": "CUST-004",
                "name": "David Wilson",
                "tenure_months": 24,
                "arpu": 95.00,
                "churn_risk": "low",
                "outstanding_balance": 0.00,
            },
            "invoice": {
                "number": "INV-004",
                "amount": 150.00,
                "disputed_amount": 85.00,
            },
        },
        "state": {"case_id": "CASE-004"},
        "input": {"dispute_reason": "Incorrect data charges"},
    }

    run_scenario(orchestrator, "Low risk, 24mo tenure, $85 dispute (<$100)", scenario4)
    time.sleep(1)

    # =========================================================================
    # SCENARIO 5: Repeat Customer - Testing History
    # =========================================================================
    print_header("SCENARIO 5: Repeat Disputes (Same Customer)")

    print(f"\n{DIM}Running Alice's dispute 3 more times to test history impact...{RESET}")

    for i in range(3):
        scenario1["db"]["invoice"]["number"] = f"INV-001-R{i+1}"
        scenario1["state"]["case_id"] = f"CASE-001-R{i+1}"
        run_scenario(orchestrator, f"Alice - Repeat #{i+2}", scenario1)
        time.sleep(1)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_header("FINAL DISPUTE HISTORY")

    history = get_history()
    for cust_id, data in history.items():
        print(f"\n  {GREEN}{cust_id}{RESET}: {data['dispute_count']} disputes, ${data['total_credits']} total credits")
        for d in data.get("disputes", []):
            print(f"    - {d['adjustment_id']}: ${d['amount']}")

    print(f"\n{'='*70}")
    print(f"{GREEN}{BOLD}All scenarios completed!{RESET}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
