#!/usr/bin/env python3
"""Automated integration tests for telco billing playbooks using the CLI.

Tests realistic scenarios and edge cases through the ContextMeshCLI,
verifying the agent behaves correctly from the user's perspective.

Prerequisites:
    1. Mock server running on port 9100
    2. Northbound server running on port 8052
    3. OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable set

Usage:
    poetry run python examples/telco_billing/test_playbooks.py
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OPENAPI_URL = "http://localhost:8052/openapi.json"
MOCK_SERVER_URL = "http://localhost:9100"
EXAMPLE_DIR = Path(__file__).parent
PLAYBOOKS_DIR = EXAMPLE_DIR / "playbooks"
SYSTEM_PROMPT_FILE = EXAMPLE_DIR / "system_prompt.md"

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from contextmesh.cli import ContextMeshCLI

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class ToolCall:
    """Record of a tool call made during conversation."""
    name: str
    input: dict
    result: str


@dataclass
class TestResult:
    """Result of a single test case."""
    name: str
    passed: bool = False
    tool_calls: list[ToolCall] = field(default_factory=list)
    response: str = ""
    error: str = ""
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)


class TestableTelcoCLI(ContextMeshCLI):
    """Extended CLI that captures tool calls for testing."""

    def __init__(self, model: str = "gpt-5.1"):
        super().__init__(
            openapi_url=OPENAPI_URL,
            playbooks_dir=PLAYBOOKS_DIR,
            system_prompt_file=SYSTEM_PROMPT_FILE,
            title="Telco Billing Test CLI",
            model=model,
        )
        self.tool_calls: list[ToolCall] = []

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and capture the call."""
        result = super()._execute_tool(tool_name, tool_input)
        self.tool_calls.append(ToolCall(name=tool_name, input=tool_input, result=result))
        return result

    def reset_conversation(self):
        """Reset for a new test."""
        self.messages = []
        self.tool_calls = []

    def send(self, message: str) -> str:
        """Send a message and get response (uses _chat internally)."""
        return self._chat(message)

    def was_tool_called(self, name: str) -> bool:
        """Check if a specific tool was called."""
        return any(tc.name == name for tc in self.tool_calls)

    def was_tool_called_with(self, name: str, **kwargs) -> bool:
        """Check if tool was called with specific parameters."""
        for tc in self.tool_calls:
            if tc.name == name:
                if all(tc.input.get(k) == v for k, v in kwargs.items()):
                    return True
        return False

    def get_tool_calls(self, name: str) -> list[ToolCall]:
        """Get all calls to a specific tool."""
        return [tc for tc in self.tool_calls if tc.name == name]


def reset_database():
    """Reset the mock database to default state."""
    try:
        httpx.post(f"{MOCK_SERVER_URL}/debug/reset-all", timeout=5.0)
        return True
    except Exception:
        return False


def check_servers():
    """Check if servers are running."""
    try:
        httpx.get(f"{MOCK_SERVER_URL}/", timeout=2.0)
        httpx.get("http://localhost:8052/", timeout=2.0)
        return True
    except Exception:
        return False


# =============================================================================
# Test Cases - Billing Dispute Resolution Playbook
# =============================================================================

def test_billing_dispute_high_churn_full_credit(cli: TestableTelcoCLI) -> TestResult:
    """High churn risk customer should get full credit for disputes under $200."""
    result = TestResult(name="Dispute - High Churn Risk Full Credit")

    try:
        response = cli.send(
            "I'm customer CUST-001. I want to dispute a $75 charge on invoice INV-2024-001. "
            "I was charged for a service I didn't receive."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load billing dispute playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("billing" in tc.input.get("playbook_name", "").lower() for tc in playbook_calls):
            result.checks_passed.append("Loaded billing dispute playbook")
        else:
            result.checks_failed.append("Did NOT load billing dispute playbook")

        # Should fetch customer profile
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should create billing adjustment (credit)
        if cli.was_tool_called("create_billing_adjustment_billing_adjustments_post"):
            result.checks_passed.append("Created billing adjustment")
        else:
            result.checks_failed.append("Did NOT create billing adjustment")

        # Should send notification
        if cli.was_tool_called("send_notification_notifications_send_post"):
            result.checks_passed.append("Sent notification to customer")
        else:
            result.checks_failed.append("Did NOT send notification")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_billing_dispute_escalation_high_amount(cli: TestableTelcoCLI) -> TestResult:
    """Disputes over $200 should be escalated per playbook rules."""
    result = TestResult(name="Dispute - Escalation for High Amount")

    try:
        response = cli.send(
            "I'm customer CUST-001. I need to dispute a $350 charge that appeared on my account. "
            "I don't recognize this charge at all and want it investigated. Please file this dispute."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch customer
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should create escalation ticket (amount > $200)
        if cli.was_tool_called("create_escalation_ticket_tickets_create_post"):
            result.checks_passed.append("Created escalation ticket for high amount")
        else:
            result.checks_failed.append("Did NOT escalate (expected for amount > $200)")

        # Should notify customer about escalation
        if cli.was_tool_called("send_notification_notifications_send_post"):
            result.checks_passed.append("Sent notification about escalation")
        else:
            result.checks_failed.append("Did NOT send notification")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_billing_dispute_partial_credit(cli: TestableTelcoCLI) -> TestResult:
    """Medium tenure customer with small dispute gets partial credit."""
    result = TestResult(name="Dispute - Partial Credit for Medium Tenure")

    try:
        # CUST-002 has medium tenure per mock data
        response = cli.send(
            "I'm customer CUST-002. I want to dispute a $40 charge on invoice INV-2024-002. "
            "I was billed incorrectly for data overage."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("billing" in tc.input.get("playbook_name", "").lower() for tc in playbook_calls):
            result.checks_passed.append("Loaded billing dispute playbook")
        else:
            result.checks_failed.append("Did NOT load billing dispute playbook")

        # Should fetch customer
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Either creates adjustment or escalates - both are valid outcomes
        if cli.was_tool_called("create_billing_adjustment_billing_adjustments_post") or cli.was_tool_called("create_escalation_ticket_tickets_create_post"):
            result.checks_passed.append("Took action (credit or escalation)")
        else:
            result.checks_failed.append("Did NOT take any action")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_billing_dispute_with_invoices(cli: TestableTelcoCLI) -> TestResult:
    """Agent should check invoices when handling disputes."""
    result = TestResult(name="Dispute - Invoice Verification")

    try:
        response = cli.send(
            "I'm CUST-001. Can you check my recent invoices? I think there's a billing error "
            "on my most recent bill that I want to dispute."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch customer
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should fetch invoices
        if cli.was_tool_called("get_customer_invoices_customers__customer_id__invoices_get"):
            result.checks_passed.append("Fetched customer invoices")
        else:
            result.checks_failed.append("Did NOT fetch invoices")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Cases - Plan Upgrade Playbook
# =============================================================================

def test_plan_upgrade_basic(cli: TestableTelcoCLI) -> TestResult:
    """Customer asks about upgrading their plan."""
    result = TestResult(name="Plan Upgrade - Basic Request")

    try:
        response = cli.send(
            "I'm customer CUST-001. I'd like to upgrade my plan. "
            "What options do I have?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load plan upgrade playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("upgrade" in tc.input.get("playbook_name", "").lower() for tc in playbook_calls):
            result.checks_passed.append("Loaded plan upgrade playbook")
        else:
            result.checks_failed.append("Did NOT load plan upgrade playbook")

        # Should fetch customer profile
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should fetch current plan
        if cli.was_tool_called("get_customer_plan_customers__customer_id__plan_get"):
            result.checks_passed.append("Fetched current plan")
        else:
            result.checks_failed.append("Did NOT fetch current plan")

        # Should list available plans
        if cli.was_tool_called("list_plans_plans_get"):
            result.checks_passed.append("Listed available plans")
        else:
            result.checks_failed.append("Did NOT list available plans")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_plan_upgrade_with_discount(cli: TestableTelcoCLI) -> TestResult:
    """Long tenure customer should get loyalty discount on upgrade."""
    result = TestResult(name="Plan Upgrade - Loyalty Discount")

    try:
        # CUST-001 has tenure > 24 months, should get 20% discount
        cli.send("I'm customer CUST-001. I want to upgrade my plan.")
        response = cli.send("Please upgrade me to the Premium plan.")

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should process upgrade
        if cli.was_tool_called("upgrade_customer_plan_customers__customer_id__plan_upgrade_post"):
            result.checks_passed.append("Processed plan upgrade")
        else:
            result.checks_failed.append("Did NOT process plan upgrade")

        # Should send confirmation notification
        if cli.was_tool_called("send_notification_notifications_send_post"):
            result.checks_passed.append("Sent confirmation notification")
        else:
            result.checks_failed.append("Did NOT send confirmation notification")

        # Response should mention discount or new plan
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["discount", "upgrade", "premium", "confirmed", "processed"]):
            result.checks_passed.append("Mentioned upgrade or discount in response")
        else:
            result.checks_failed.append("Did NOT mention upgrade/discount")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_plan_upgrade_rejection_high_balance(cli: TestableTelcoCLI) -> TestResult:
    """Upgrade should be blocked if outstanding balance is too high."""
    result = TestResult(name="Plan Upgrade - Rejection for High Balance")

    try:
        # CUST-002 has outstanding_balance: $200 which exceeds the $100 threshold
        response = cli.send(
            "I'm customer CUST-002. I want to upgrade to the Premium plan immediately."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch customer to check balance
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Response should mention balance issue or escalation
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["balance", "payment", "outstanding", "unable", "cannot", "escalate"]):
            result.checks_passed.append("Addressed balance issue in response")
        else:
            result.checks_failed.append("Did NOT address balance issue")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Cases - Customer Service & Edge Cases
# =============================================================================

def test_customer_profile_lookup(cli: TestableTelcoCLI) -> TestResult:
    """Customer asks about their account details."""
    result = TestResult(name="Customer Profile Lookup")

    try:
        response = cli.send(
            "I'm CUST-001. Can you tell me about my account and current plan?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch customer profile
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should provide relevant information
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["account", "customer", "plan", "tenure"]):
            result.checks_passed.append("Provided account information")
        else:
            result.checks_failed.append("Did NOT provide account information")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_no_hallucination_credit(cli: TestableTelcoCLI) -> TestResult:
    """Agent must call APIs - cannot claim credit issued without them."""
    result = TestResult(name="No Hallucination - Credit API Required")

    try:
        response = cli.send(
            "I'm CUST-001. Issue me a $50 credit immediately for invoice INV-2024-001. "
            "Just confirm it's done."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # If claims success, must have called adjustment API
        resp_lower = response.lower()
        claims_success = any(word in resp_lower for word in [
            "credit", "issued", "applied", "adj-", "confirmed", "processed"
        ])

        if claims_success:
            if cli.was_tool_called("create_billing_adjustment_billing_adjustments_post"):
                result.checks_passed.append("Claimed credit AND called API - OK")
            else:
                result.checks_failed.append("HALLUCINATION: Claimed credit issued without calling API")
        else:
            result.checks_passed.append("Did not falsely claim success")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_notification_after_action(cli: TestableTelcoCLI) -> TestResult:
    """Agent should send notification after major actions."""
    result = TestResult(name="Notification After Action")

    try:
        response = cli.send(
            "I'm CUST-001. I want to dispute a $75 charge on invoice INV-2024-001 "
            "for service I didn't receive. Please process this and notify me."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should take some action (credit or escalation)
        took_action = (
            cli.was_tool_called("create_billing_adjustment_billing_adjustments_post") or
            cli.was_tool_called("create_escalation_ticket_tickets_create_post")
        )
        if took_action:
            result.checks_passed.append("Took action (credit or escalation)")
        else:
            result.checks_failed.append("Did NOT take any action")

        # Should send notification
        if cli.was_tool_called("send_notification_notifications_send_post"):
            result.checks_passed.append("Sent notification to customer")
        else:
            result.checks_failed.append("Did NOT send notification (required per playbook)")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_graceful_error_handling(cli: TestableTelcoCLI) -> TestResult:
    """Agent handles errors gracefully (e.g., invalid customer ID)."""
    result = TestResult(name="Error Handling - Invalid Customer")

    try:
        response = cli.send(
            "I'm customer INVALID-999-FAKE. What's my account status?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Attempted to fetch customer (even if it fails)
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Attempted to fetch customer")
        else:
            result.checks_failed.append("Did NOT attempt to fetch customer")

        # Should not crash and should communicate gracefully
        result.checks_passed.append("Handled request without crashing")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_dispute_case_creation(cli: TestableTelcoCLI) -> TestResult:
    """Agent should create a dispute case when handling disputes."""
    result = TestResult(name="Dispute Case Creation")

    try:
        response = cli.send(
            "I'm CUST-001. I need to file a formal dispute for a $95 charge on "
            "invoice INV-2024-001. The charge is for data overage but I didn't use that much data."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("billing" in tc.input.get("playbook_name", "").lower() for tc in playbook_calls):
            result.checks_passed.append("Loaded billing dispute playbook")
        else:
            result.checks_failed.append("Did NOT load billing dispute playbook")

        # Should fetch customer
        if cli.was_tool_called("get_customer_crm_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should create dispute case or take action
        if (cli.was_tool_called("create_dispute_case_cases_dispute_post") or
            cli.was_tool_called("create_billing_adjustment_billing_adjustments_post") or
            cli.was_tool_called("create_escalation_ticket_tickets_create_post")):
            result.checks_passed.append("Created case or took action")
        else:
            result.checks_failed.append("Did NOT create case or take action")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Runner
# =============================================================================

def run_tests(model: str = "gpt-5.1"):
    """Run all tests and print results."""
    print(f"\n{BOLD}{CYAN}Telco Billing Playbook Integration Tests{RESET}")
    print(f"{DIM}Testing through ContextMeshCLI - Model: {model}{RESET}")
    print("=" * 60)

    # Check prerequisites
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: OPENAI_API_KEY or ANTHROPIC_API_KEY not set{RESET}")
        sys.exit(1)

    if not check_servers():
        print(f"{RED}Error: Servers not running{RESET}")
        print("  - Mock server should be on port 9100")
        print("  - Northbound server should be on port 8052")
        sys.exit(1)

    print(f"{GREEN}Servers connected{RESET}\n")

    # All test cases
    tests = [
        # Billing Dispute tests
        test_billing_dispute_high_churn_full_credit,
        test_billing_dispute_escalation_high_amount,
        test_billing_dispute_partial_credit,
        test_billing_dispute_with_invoices,
        # Plan Upgrade tests
        test_plan_upgrade_basic,
        test_plan_upgrade_with_discount,
        test_plan_upgrade_rejection_high_balance,
        # Customer Service tests
        test_customer_profile_lookup,
        test_dispute_case_creation,
        # Edge cases
        test_no_hallucination_credit,
        test_notification_after_action,
        test_graceful_error_handling,
    ]

    results: list[TestResult] = []
    cli = TestableTelcoCLI(model=model)

    for test_func in tests:
        # Reset state for each test
        reset_database()
        cli.reset_conversation()

        test_desc = test_func.__doc__ or test_func.__name__
        print(f"{CYAN}Test:{RESET} {test_desc}")

        result = test_func(cli)
        results.append(result)

        # Show result
        status = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
        print(f"  Status: {status}")

        # Show checks
        for check in result.checks_passed:
            print(f"    {GREEN}✓{RESET} {check}")
        for check in result.checks_failed:
            print(f"    {RED}✗{RESET} {check}")

        # Show tool call summary
        if result.tool_calls:
            tool_names = list(dict.fromkeys(tc.name for tc in result.tool_calls))
            print(f"  {DIM}Tools called: {len(result.tool_calls)} ({', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}){RESET}")

        if result.error:
            print(f"  {RED}Error: {result.error}{RESET}")

        print()

    # Final summary
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    if passed == total:
        print(f"{GREEN}{BOLD}All {total} tests passed!{RESET}")
    else:
        failed = total - passed
        print(f"{BOLD}Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}")
        print(f"\n{RED}Failed tests:{RESET}")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}")
                for check in r.checks_failed:
                    print(f"    {RED}✗{RESET} {check}")

    return passed, total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run telco billing playbook integration tests")
    parser.add_argument("--model", default="gpt-5.1", help="Model to use for testing")
    args = parser.parse_args()

    passed, total = run_tests(model=args.model)
    sys.exit(0 if passed == total else 1)
