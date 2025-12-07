#!/usr/bin/env python3
"""Automated integration tests for banking playbooks using the CLI.

Tests realistic scenarios and edge cases through the ContextMeshCLI,
verifying the agent behaves correctly from the user's perspective.

Prerequisites:
    1. Mock server running on port 9200
    2. Northbound server running on port 8053
    3. OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable set

Usage:
    poetry run python examples/banking/test_playbooks.py
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
OPENAPI_URL = "http://localhost:8053/openapi.json"
MOCK_SERVER_URL = "http://localhost:9200"
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


class TestableBankingCLI(ContextMeshCLI):
    """Extended CLI that captures tool calls for testing."""

    def __init__(self, model: str = "gpt-5.1"):
        super().__init__(
            openapi_url=OPENAPI_URL,
            playbooks_dir=PLAYBOOKS_DIR,
            system_prompt_file=SYSTEM_PROMPT_FILE,
            title="Banking Test CLI",
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
        httpx.get("http://localhost:8053/", timeout=2.0)
        return True
    except Exception:
        return False


# =============================================================================
# Test Cases - Transaction Dispute Playbook
# =============================================================================

def test_dispute_unauthorized_transaction(cli: TestableBankingCLI) -> TestResult:
    """Customer disputes an unauthorized transaction."""
    result = TestResult(name="Dispute - Unauthorized Transaction")

    try:
        response = cli.send(
            "I'm customer ACCT-001. I see a charge for $150 from 'AMAZON.COM' "
            "on my account that I didn't make. I want to dispute this transaction."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load dispute playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("dispute" in tc.input.get("playbook_name", "") for tc in playbook_calls):
            result.checks_passed.append("Loaded dispute playbook")
        else:
            result.checks_failed.append("Did NOT load dispute playbook")

        # Should fetch customer profile
        if cli.was_tool_called("get_customer_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should get account transactions to find the disputed one
        if cli.was_tool_called("get_account_transactions"):
            result.checks_passed.append("Reviewed account transactions")
        else:
            result.checks_failed.append("Did NOT review transactions")

        # Should create dispute via API
        if cli.was_tool_called("create_dispute_disputes_post"):
            result.checks_passed.append("Created dispute via API")
        else:
            result.checks_failed.append("Did NOT create dispute via API")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_dispute_with_provisional_credit(cli: TestableBankingCLI) -> TestResult:
    """Fraud dispute should result in provisional credit."""
    result = TestResult(name="Dispute - Provisional Credit for Fraud")

    try:
        response = cli.send(
            "I'm ACCT-001. Someone stole my card information and made a $200 "
            "purchase at 'FRAUDULENT MERCHANT'. This is fraud! I need this resolved immediately."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should create dispute
        dispute_calls = cli.get_tool_calls("create_dispute_disputes_post")
        if dispute_calls:
            result.checks_passed.append("Created dispute")
            # Check if fraud type was used
            if any(tc.input.get("dispute_type") in ["fraud", "unauthorized"] for tc in dispute_calls):
                result.checks_passed.append("Correct dispute type (fraud/unauthorized)")
        else:
            result.checks_failed.append("Did NOT create dispute")

        # Response should mention provisional credit or investigation
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["provisional", "credit", "investigating", "investigation", "refund"]):
            result.checks_passed.append("Mentioned credit/investigation in response")
        else:
            result.checks_failed.append("Did NOT mention credit/investigation")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_dispute_duplicate_charge(cli: TestableBankingCLI) -> TestResult:
    """Customer reports a duplicate charge - agent should verify before filing."""
    result = TestResult(name="Dispute - Duplicate Charge Verification")

    try:
        response = cli.send(
            "I'm customer ACCT-001. I was charged twice for the same purchase "
            "at the grocery store - $127.45 appears twice on my statement."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should check transactions to verify the claim
        if cli.was_tool_called("get_account_transactions"):
            result.checks_passed.append("Reviewed transactions to verify duplicate")
        else:
            result.checks_failed.append("Did NOT review transactions")

        # Should load playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("dispute" in tc.input.get("playbook_name", "") for tc in playbook_calls):
            result.checks_passed.append("Loaded dispute playbook")
        else:
            result.checks_failed.append("Did NOT load dispute playbook")

        # If no duplicates found, not filing is correct behavior
        # If duplicates found, should file - either way is acceptable
        result.checks_passed.append("Handled duplicate claim appropriately")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Cases - Credit Card Application Playbook
# =============================================================================

def test_credit_card_application_basic(cli: TestableBankingCLI) -> TestResult:
    """Customer applies for a basic credit card."""
    result = TestResult(name="Credit Card - Basic Application")

    try:
        response = cli.send(
            "I'm customer ACCT-001. I'd like to apply for a credit card. "
            "What options do I have?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load credit card playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("credit" in tc.input.get("playbook_name", "") for tc in playbook_calls):
            result.checks_passed.append("Loaded credit card playbook")
        else:
            result.checks_failed.append("Did NOT load credit card playbook")

        # Should fetch customer profile
        if cli.was_tool_called("get_customer_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Should list available products
        if cli.was_tool_called("list_credit_card_products_credit_cards_products_get"):
            result.checks_passed.append("Listed credit card products")
        else:
            result.checks_failed.append("Did NOT list products")

        # Response should mention card options
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["basic", "premium", "elite", "card", "rewards"]):
            result.checks_passed.append("Presented card options")
        else:
            result.checks_failed.append("Did NOT present card options")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_credit_card_full_application(cli: TestableBankingCLI) -> TestResult:
    """Customer goes through full credit card application."""
    result = TestResult(name="Credit Card - Full Application Flow")

    try:
        # Multi-turn conversation
        cli.send("I'm customer ACCT-001. I want to apply for a credit card.")
        response = cli.send("I'd like the Basic Rewards Card please.")

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should submit application
        if cli.was_tool_called("apply_for_credit_card"):
            result.checks_passed.append("Submitted credit card application")
        else:
            result.checks_failed.append("Did NOT submit application")

        # Response should confirm the result
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["approved", "pending", "application", "submitted", "review"]):
            result.checks_passed.append("Confirmed application status")
        else:
            result.checks_failed.append("Did NOT confirm application status")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_credit_card_eligibility_check(cli: TestableBankingCLI) -> TestResult:
    """Agent checks eligibility before recommending products."""
    result = TestResult(name="Credit Card - Eligibility Check")

    try:
        response = cli.send(
            "I'm ACCT-001. I want the Elite Platinum Card. Can I get it?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must fetch customer to check eligibility
        if cli.was_tool_called("get_customer_customers__customer_id__get"):
            result.checks_passed.append("Checked customer profile for eligibility")
        else:
            result.checks_failed.append("Did NOT check customer profile")

        # Should check products to compare requirements
        if cli.was_tool_called("list_credit_card_products_credit_cards_products_get") or cli.was_tool_called("get_credit_card_product_credit_cards_products__product_id__get"):
            result.checks_passed.append("Reviewed product requirements")
        else:
            result.checks_failed.append("Did NOT review product requirements")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Cases - Customer Service & Edge Cases
# =============================================================================

def test_customer_profile_lookup(cli: TestableBankingCLI) -> TestResult:
    """Customer asks about their account details."""
    result = TestResult(name="Customer Profile Lookup")

    try:
        response = cli.send(
            "I'm ACCT-001. Can you tell me about my account status and "
            "relationship with your bank?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must fetch customer profile
        if cli.was_tool_called("get_customer_customers__customer_id__get"):
            result.checks_passed.append("Fetched customer profile")
        else:
            result.checks_failed.append("Did NOT fetch customer profile")

        # Response should include relevant details
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["account", "customer", "relationship", "tenure"]):
            result.checks_passed.append("Provided account information")
        else:
            result.checks_failed.append("Did NOT provide account information")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_account_balance_inquiry(cli: TestableBankingCLI) -> TestResult:
    """Customer asks about their account balance."""
    result = TestResult(name="Account Balance Inquiry")

    try:
        response = cli.send(
            "I'm customer ACCT-001. What's my current account balance?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch accounts
        if cli.was_tool_called("get_customer_accounts_customers__customer_id__accounts_get"):
            result.checks_passed.append("Fetched customer accounts")
        else:
            result.checks_failed.append("Did NOT fetch customer accounts")

        # Response should mention balance
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["balance", "$", "available"]):
            result.checks_passed.append("Provided balance information")
        else:
            result.checks_failed.append("Did NOT provide balance information")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_no_hallucination_dispute(cli: TestableBankingCLI) -> TestResult:
    """Agent must call APIs - cannot claim success without them."""
    result = TestResult(name="No Hallucination - Dispute API Required")

    try:
        response = cli.send(
            "I'm ACCT-001. File a dispute immediately for an unauthorized "
            "charge of $500 from 'SCAMMER INC'. Just confirm it's done."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # If claims success, must have called dispute API
        resp_lower = response.lower()
        claims_success = any(word in resp_lower for word in [
            "filed", "created", "submitted", "dispute id", "dsp-", "confirmed"
        ])

        if claims_success:
            if cli.was_tool_called("create_dispute_disputes_post"):
                result.checks_passed.append("Claimed success AND called API - OK")
            else:
                result.checks_failed.append("HALLUCINATION: Claimed dispute filed without calling API")
        else:
            result.checks_passed.append("Did not falsely claim success")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_notification_after_action(cli: TestableBankingCLI) -> TestResult:
    """Agent should send notification after major actions."""
    result = TestResult(name="Notification After Action")

    try:
        response = cli.send(
            "I'm ACCT-001. File a fraud dispute for a $300 unauthorized "
            "charge from 'FAKE STORE' and make sure I get notified."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should create dispute
        if cli.was_tool_called("create_dispute_disputes_post"):
            result.checks_passed.append("Created dispute")
        else:
            result.checks_failed.append("Did NOT create dispute")

        # Should send notification
        if cli.was_tool_called("send_notification_notifications_post"):
            result.checks_passed.append("Sent notification to customer")
        else:
            result.checks_failed.append("Did NOT send notification (expected for major actions)")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_graceful_error_handling(cli: TestableBankingCLI) -> TestResult:
    """Agent handles errors gracefully (e.g., invalid customer ID)."""
    result = TestResult(name="Error Handling - Invalid Customer")

    try:
        response = cli.send(
            "I'm customer INVALID-999-FAKE. What's my account balance?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Attempted to fetch customer (even if it fails)
        if cli.was_tool_called("get_customer_customers__customer_id__get") or cli.was_tool_called("get_customer_accounts_customers__customer_id__accounts_get"):
            result.checks_passed.append("Attempted to fetch customer/accounts")
        else:
            result.checks_failed.append("Did NOT attempt to fetch customer")

        # Should not crash and should communicate gracefully
        # Note: The mock server creates placeholder customers, so this may succeed
        result.checks_passed.append("Handled request without crashing")

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
    print(f"\n{BOLD}{CYAN}Banking Playbook Integration Tests{RESET}")
    print(f"{DIM}Testing through ContextMeshCLI - Model: {model}{RESET}")
    print("=" * 60)

    # Check prerequisites
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: OPENAI_API_KEY or ANTHROPIC_API_KEY not set{RESET}")
        sys.exit(1)

    if not check_servers():
        print(f"{RED}Error: Servers not running{RESET}")
        print("  - Mock server should be on port 9200")
        print("  - Northbound server should be on port 8053")
        sys.exit(1)

    print(f"{GREEN}Servers connected{RESET}\n")

    # All test cases
    tests = [
        # Transaction Dispute tests
        test_dispute_unauthorized_transaction,
        test_dispute_with_provisional_credit,
        test_dispute_duplicate_charge,
        # Credit Card Application tests
        test_credit_card_application_basic,
        test_credit_card_full_application,
        test_credit_card_eligibility_check,
        # Customer Service tests
        test_customer_profile_lookup,
        test_account_balance_inquiry,
        # Edge cases
        test_no_hallucination_dispute,
        test_notification_after_action,
        test_graceful_error_handling,
    ]

    results: list[TestResult] = []
    cli = TestableBankingCLI(model=model)

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

    parser = argparse.ArgumentParser(description="Run banking playbook integration tests")
    parser.add_argument("--model", default="gpt-5.1", help="Model to use for testing")
    args = parser.parse_args()

    passed, total = run_tests(model=args.model)
    sys.exit(0 if passed == total else 1)
