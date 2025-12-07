#!/usr/bin/env python3
"""Automated integration tests for hotel playbooks using the CLI.

Tests realistic scenarios and edge cases through the ContextMeshCLI,
verifying the agent behaves correctly from the user's perspective.

Prerequisites:
    1. Mock server running on port 9300
    2. Northbound server running on port 8054
    3. ANTHROPIC_API_KEY environment variable set

Usage:
    poetry run python examples/hotel/test_playbooks.py
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
OPENAPI_URL = "http://localhost:8054/openapi.json"
MOCK_SERVER_URL = "http://localhost:9300"
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


class TestableHotelCLI(ContextMeshCLI):
    """Extended CLI that captures tool calls for testing."""

    def __init__(self):
        super().__init__(
            openapi_url=OPENAPI_URL,
            playbooks_dir=PLAYBOOKS_DIR,
            system_prompt_file=SYSTEM_PROMPT_FILE,
            title="Hotel Test CLI",
            model="claude-haiku-4-5-20251001",
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
        httpx.get("http://localhost:8054/", timeout=2.0)
        return True
    except Exception:
        return False


# =============================================================================
# Test Cases - Each tests a playbook scenario
# =============================================================================

def test_new_booking_complete_flow(cli: TestableHotelCLI) -> TestResult:
    """New guest completes a full booking with available room."""
    result = TestResult(name="New Booking - Complete Flow")

    try:
        # Simulate realistic multi-turn conversation
        cli.send("Hi, I'd like to book a room")
        cli.send("January 10 to January 12, 2026")
        cli.send("I'm a new guest. John Smith, john@example.com, +1-555-1234")
        response = cli.send("A standard king room please")

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Playbook loading is optional for simple bookings
        if cli.was_tool_called("get_playbook"):
            result.checks_passed.append("Loaded playbook (optional)")

        # Verify guest was created
        if cli.was_tool_called("create_guest_guests_post"):
            result.checks_passed.append("Created guest profile")
        else:
            result.checks_failed.append("Did NOT create guest profile")

        # Verify availability was checked WITH dates
        avail_calls = cli.get_tool_calls("get_available_rooms_rooms_available_get")
        if avail_calls:
            if any("check_in" in tc.input for tc in avail_calls):
                result.checks_passed.append("Checked availability with dates")
            else:
                result.checks_failed.append("Checked availability WITHOUT dates")
        else:
            result.checks_failed.append("Did NOT check availability")

        # Verify reservation was created
        if cli.was_tool_called("create_reservation_reservations_post"):
            result.checks_passed.append("Created reservation via API")
        else:
            result.checks_failed.append("Did NOT create reservation via API")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_new_booking_unavailable_suggests_alternatives(cli: TestableHotelCLI) -> TestResult:
    """Guest requests unavailable room, agent suggests alternatives."""
    result = TestResult(name="New Booking - Unavailable Room Handling")

    try:
        # Request room type that's likely unavailable
        response = cli.send(
            "I'm Sarah Test, sarah@test.com, +1-555-9999. "
            "Book me a presidential suite for Feb 1-3, 2026"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must check availability
        if cli.was_tool_called("get_available_rooms_rooms_available_get"):
            result.checks_passed.append("Checked availability")
        else:
            result.checks_failed.append("Did NOT check availability")

        # Response should acknowledge availability situation
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["unavailable", "not available", "alternative", "instead", "available"]):
            result.checks_passed.append("Addressed availability in response")
        else:
            result.checks_failed.append("Did NOT address availability in response")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_existing_guest_recognized(cli: TestableHotelCLI) -> TestResult:
    """Existing guest is recognized and greeted by name."""
    result = TestResult(name="Existing Guest - Recognition")

    try:
        response = cli.send("Hi, I'm guest GUEST-001. I'd like to make a new booking.")

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must fetch existing guest profile
        if cli.was_tool_called("get_guest_guests__guest_id__get"):
            result.checks_passed.append("Fetched guest profile")
        else:
            result.checks_failed.append("Did NOT fetch guest profile")

        # Should NOT create a new guest
        if not cli.was_tool_called("create_guest_guests_post"):
            result.checks_passed.append("Did not create duplicate guest")
        else:
            result.checks_failed.append("Incorrectly tried to create new guest")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_complaint_files_and_compensates(cli: TestableHotelCLI) -> TestResult:
    """Guest complaint is filed with appropriate priority and compensation."""
    result = TestResult(name="Complaint - Filing and Compensation")

    try:
        response = cli.send(
            "I'm guest GUEST-001, reservation RES-001. "
            "The room hasn't been cleaned and there's garbage everywhere. This is unacceptable!"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must load complaint playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("complaint" in tc.input.get("playbook_name", "") for tc in playbook_calls):
            result.checks_passed.append("Loaded complaint playbook")
        else:
            result.checks_failed.append("Did NOT load complaint playbook")

        # Must file complaint via API
        if cli.was_tool_called("create_complaint_complaints_post"):
            result.checks_passed.append("Filed complaint via API")
            # Verify category
            complaint_calls = cli.get_tool_calls("create_complaint_complaints_post")
            if any(tc.input.get("category") == "cleanliness" for tc in complaint_calls):
                result.checks_passed.append("Correct category: cleanliness")
            else:
                result.checks_failed.append("Wrong complaint category")
        else:
            result.checks_failed.append("Did NOT file complaint via API")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_complaint_urgent_priority(cli: TestableHotelCLI) -> TestResult:
    """Urgent complaint (safety issue) gets high/urgent priority."""
    result = TestResult(name="Complaint - Urgent Priority")

    try:
        response = cli.send(
            "I'm GUEST-002, reservation RES-002. "
            "There's smoke coming from the bathroom outlet! This is an emergency!"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Check complaint was filed with appropriate priority
        complaint_calls = cli.get_tool_calls("create_complaint_complaints_post")
        if complaint_calls:
            priorities = [tc.input.get("priority") for tc in complaint_calls]
            if any(p in ["high", "urgent"] for p in priorities):
                result.checks_passed.append("Set high/urgent priority")
            else:
                result.checks_failed.append(f"Wrong priority: {priorities}")
        else:
            result.checks_failed.append("Did NOT file complaint")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_room_upgrade_checks_availability(cli: TestableHotelCLI) -> TestResult:
    """Room upgrade request checks availability before processing."""
    result = TestResult(name="Room Upgrade - Availability Check")

    try:
        response = cli.send(
            "I'm guest GUEST-001 with reservation RES-001. "
            "I'd like to upgrade to an executive suite."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should load upgrade playbook
        playbook_calls = cli.get_tool_calls("get_playbook")
        if any("upgrade" in tc.input.get("playbook_name", "") for tc in playbook_calls):
            result.checks_passed.append("Loaded upgrade playbook")
        else:
            result.checks_failed.append("Did NOT load upgrade playbook")

        # Should check availability
        if cli.was_tool_called("get_available_rooms_rooms_available_get"):
            result.checks_passed.append("Checked room availability")
        else:
            result.checks_failed.append("Did NOT check availability")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_reservation_modification(cli: TestableHotelCLI) -> TestResult:
    """Guest modifies reservation dates."""
    result = TestResult(name="Reservation Modification")

    try:
        response = cli.send(
            "I'm guest GUEST-002, reservation RES-002. "
            "I need to change my checkout to January 25, 2026."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Should fetch current reservation
        if cli.was_tool_called("get_reservation_reservations__reservation_id__get"):
            result.checks_passed.append("Fetched reservation details")
        else:
            result.checks_failed.append("Did NOT fetch reservation")

        # Should call modify API
        if cli.was_tool_called("modify_reservation_reservations__reservation_id__modify_put"):
            result.checks_passed.append("Called modify API")
        else:
            result.checks_failed.append("Did NOT call modify API")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_service_request_created(cli: TestableHotelCLI) -> TestResult:
    """Service request is properly created via API."""
    result = TestResult(name="Service Request")

    try:
        response = cli.send(
            "I'm guest GUEST-001, reservation RES-001. "
            "Can you send extra towels and pillows to my room?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must create service request via API
        if cli.was_tool_called("create_service_request_service_requests_post"):
            result.checks_passed.append("Created service request via API")
            # Check service type
            calls = cli.get_tool_calls("create_service_request_service_requests_post")
            if any(tc.input.get("service_type") == "housekeeping" for tc in calls):
                result.checks_passed.append("Correct service type: housekeeping")
        else:
            result.checks_failed.append("Did NOT create service request via API")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_loyalty_points_lookup(cli: TestableHotelCLI) -> TestResult:
    """Guest can check their loyalty points."""
    result = TestResult(name="Loyalty Points Lookup")

    try:
        response = cli.send("I'm guest GUEST-001. What's my loyalty status and how many points do I have?")

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Must fetch loyalty status via API
        if cli.was_tool_called("get_loyalty_status_guests__guest_id__loyalty_get"):
            result.checks_passed.append("Fetched loyalty status via API")
        else:
            result.checks_failed.append("Did NOT fetch loyalty status")

        # Response should mention points/tier
        resp_lower = response.lower()
        if "point" in resp_lower or "platinum" in resp_lower or "tier" in resp_lower:
            result.checks_passed.append("Response includes loyalty info")
        else:
            result.checks_failed.append("Response missing loyalty info")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_no_hallucination_must_call_api(cli: TestableHotelCLI) -> TestResult:
    """Agent must call APIs - cannot claim success without them."""
    result = TestResult(name="No Hallucination - API Required")

    try:
        response = cli.send(
            "Book a room immediately. I'm Alex Test, alex@test.com, +1-555-0000. "
            "Deluxe king, April 1-3, 2026. Just confirm it."
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # If claims success, must have called reservation API
        resp_lower = response.lower()
        claims_success = any(word in resp_lower for word in [
            "confirmed", "booked", "reserved", "reservation id", "res-"
        ])

        if claims_success:
            if cli.was_tool_called("create_reservation_reservations_post"):
                result.checks_passed.append("Claimed success AND called API - OK")
            else:
                result.checks_failed.append("HALLUCINATION: Claimed success without calling API")
        else:
            # Didn't claim success - check if it explained why
            result.checks_passed.append("Did not falsely claim success")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


def test_graceful_error_handling(cli: TestableHotelCLI) -> TestResult:
    """Agent handles errors gracefully (e.g., invalid guest ID)."""
    result = TestResult(name="Error Handling - Invalid Guest")

    try:
        response = cli.send(
            "I'm guest GUEST-INVALID-999. What's my reservation status?"
        )

        result.response = response
        result.tool_calls = cli.tool_calls.copy()

        # Attempted to fetch guest or their data (even if failed)
        if cli.was_tool_called("get_guest_guests__guest_id__get"):
            result.checks_passed.append("Attempted to fetch guest")
        elif cli.was_tool_called("get_guest_reservations_guests__guest_id__reservations_get"):
            result.checks_passed.append("Attempted to fetch guest reservations")
        else:
            result.checks_failed.append("Did NOT attempt to fetch guest")

        # Should not crash, should communicate the issue
        resp_lower = response.lower()
        if any(word in resp_lower for word in ["not found", "couldn't find", "unable", "error", "invalid", "don't have"]):
            result.checks_passed.append("Communicated error to user")
        else:
            result.checks_failed.append("Did NOT communicate error gracefully")

        result.passed = len(result.checks_failed) == 0

    except Exception as e:
        result.error = str(e)
        result.passed = False

    return result


# =============================================================================
# Test Runner
# =============================================================================

def run_tests():
    """Run all tests and print results."""
    print(f"\n{BOLD}{CYAN}Hotel Playbook Integration Tests{RESET}")
    print(f"{DIM}Testing through ContextMeshCLI at the highest level{RESET}")
    print("=" * 60)

    # Check prerequisites
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: ANTHROPIC_API_KEY not set{RESET}")
        sys.exit(1)

    if not check_servers():
        print(f"{RED}Error: Servers not running{RESET}")
        print("  - Mock server should be on port 9300")
        print("  - Northbound server should be on port 8054")
        sys.exit(1)

    print(f"{GREEN}Servers connected{RESET}\n")

    # All test cases
    tests = [
        test_new_booking_complete_flow,
        test_new_booking_unavailable_suggests_alternatives,
        test_existing_guest_recognized,
        test_complaint_files_and_compensates,
        test_complaint_urgent_priority,
        test_room_upgrade_checks_availability,
        test_reservation_modification,
        test_service_request_created,
        test_loyalty_points_lookup,
        test_no_hallucination_must_call_api,
        test_graceful_error_handling,
    ]

    results: list[TestResult] = []
    cli = TestableHotelCLI()

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
            tool_names = list(dict.fromkeys(tc.name for tc in result.tool_calls))  # unique, preserve order
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

    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
