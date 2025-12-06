#!/usr/bin/env python3
"""Interactive CLI for testing ContextMesh billing dispute scenarios.

Run the mock server first (from excom-context-mesh-mock-server repo):
    cd ../excom-context-mesh-mock-server
    poetry run mock-server

Then run this CLI:
    poetry run python examples/telco_billing/cli.py
"""

import json
import os
import random
import sys
from pathlib import Path

import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

from contextmesh import ContextMeshConfig, ContextMeshOrchestrator
from contextmesh.parsers.playbook_parser import PlaybookParser

BACKEND_URL = "http://localhost:9100"
NORTHBOUND_URL = "http://localhost:8052"

# Load environment variables
load_dotenv()

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def build_dynamic_system_prompt(playbooks_dir: Path) -> str:
    """Build system prompt dynamically from playbooks and OpenAPI spec."""

    # Load playbooks
    parser = PlaybookParser()
    playbooks = []
    for playbook_file in playbooks_dir.glob("*.md"):
        try:
            playbook = parser.load_playbook(playbook_file)
            playbooks.append(playbook)
        except Exception:
            pass

    # Fetch OpenAPI description from northbound server
    api_description = ""
    try:
        response = httpx.get(f"{NORTHBOUND_URL}/openapi.json", timeout=2.0)
        if response.status_code == 200:
            spec = response.json()
            api_description = spec.get("info", {}).get("description", "")
    except Exception:
        pass

    # Fetch available plans from backend
    plans_info = ""
    try:
        response = httpx.get(f"{BACKEND_URL}/plans", timeout=2.0)
        if response.status_code == 200:
            plans = response.json()
            plans_info = "\n## Available Plans\n\n"
            plans_info += "| Plan | Monthly Rate | Data | Minutes | Tier |\n"
            plans_info += "|------|-------------|------|---------|------|\n"
            for plan in plans:
                data = f"{plan['data_gb']}GB" if plan['data_gb'] > 0 else "Unlimited"
                mins = str(plan['minutes']) if plan['minutes'] > 0 else "Unlimited"
                plans_info += f"| {plan['name']} | ${plan['monthly_rate']} | {data} | {mins} | {plan['tier']} |\n"
            plans_info += "\n**Note:** Customers can only upgrade to a higher tier (not downgrade).\n"
    except Exception:
        pass

    # Build workflows section from playbooks
    workflows_section = ""
    for pb in playbooks:
        workflows_section += f"""
### {pb.module_name.replace('_', ' ').title()}
**Goal:** {pb.goal}
"""

    # Build the dynamic prompt
    prompt = f"""You are a helpful telecom customer service assistant.
You help customers with various requests including billing disputes and plan changes.

## Available Workflows
{workflows_section}
{plans_info}
## API Context
{api_description[:1500] if api_description else "API documentation not available."}

## Your Capabilities

Based on the available workflows, you can help customers with:
"""

    # Add capabilities based on playbooks
    for pb in playbooks:
        if "billing" in pb.module_name.lower() or "dispute" in pb.module_name.lower():
            prompt += """
- **Billing Disputes**: Help customers file disputes for incorrect charges, service issues, or billing errors
"""
        if "upgrade" in pb.module_name.lower() or "plan" in pb.module_name.lower():
            prompt += """
- **Plan Upgrades**: Help customers upgrade their service plans with loyalty discounts
"""

    prompt += """
## Tools Available

**Customer Data Tools:**
- `get_customer_profile` - Fetch name, tenure, churn risk, outstanding balance, ARPU
- `get_customer_plan` - Fetch current plan name, monthly rate, payment history
- `get_customer_invoices` - Fetch invoice history with amounts and statuses

**Business Rules Tools:**
- `list_playbooks` - List all available business playbooks with their goals
- `get_playbook` - Load a specific playbook to get detailed business rules, decision criteria, and thresholds

## CRITICAL: Customer ID is Always Given

The customer ID is always provided at the start of the conversation. Your job is to:
1. **Immediately use your tools** to fetch the customer's profile, plan, and invoices
2. **Greet the customer by name** using the fetched data
3. **Ask what they need help with** - only ask for information specific to their request
4. **Once you know their request, use `list_playbooks` and `get_playbook`** to load the relevant business rules

NEVER ask for the customer ID - it's already given.
NEVER ask for name, tenure, current plan, or account status - USE THE TOOLS to look it up.
ALWAYS load the relevant playbook before making decisions about eligibility, discounts, or escalations.

## How to Help Customers

**For Billing Disputes:**
- Use customer tools to fetch profile, plan, and invoices
- Use `get_playbook("billing_dispute_resolution")` to get business rules
- Apply the playbook's decision rules to determine eligibility and credit amount

**For Plan Upgrades:**
- Use customer tools to fetch profile and current plan
- Use `get_playbook("plan_upgrade")` to get discount rules and eligibility criteria
- Apply the playbook's tenure-based discounts and balance thresholds

## Creating Cases

When you have enough information, respond with a JSON block (use ```json code fence):

**For Billing Disputes:**
```json
{
  "action": "create_dispute",
  "customer": {
    "customer_id": "CUST-001"
  },
  "invoice": {
    "number": "INV-XXXX",
    "amount": 100.00,
    "disputed_amount": 50.00
  },
  "dispute_reason": "Description of the issue"
}
```

**For Plan Upgrades:**
```json
{
  "action": "create_upgrade",
  "customer": {
    "customer_id": "CUST-001"
  },
  "target_plan": "premium",
  "upgrade_reason": "Customer wants more data"
}
```

Note: If customer provides their ID, you only need to include customer_id in the customer object.
The system will automatically fetch their name, tenure, churn_risk, and other profile data.

For churn_risk (only if no customer ID): estimate based on customer's tone:
- "high" if frustrated or threatens to leave
- "low" if patient and understanding
- "medium" otherwise

Keep responses concise and helpful.
"""
    return prompt


# Will be set dynamically at startup
CHAT_SYSTEM_PROMPT = ""


def print_header(workflows: list[str] | None = None):
    """Print welcome header."""
    workflow_list = ""
    if workflows:
        workflow_list = f"\n{BOLD}Available Workflows:{RESET}\n"
        for wf in workflows:
            workflow_list += f"  {GREEN}•{RESET} {wf}\n"

    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════╗
║              ContextMesh - Customer Service CLI                  ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
{workflow_list}
{BOLD}Chat Mode:{RESET} Describe what you need help with.
           The AI will guide you through the process.

{BOLD}Commands:{RESET}
  {GREEN}/new{RESET}      - Start a new conversation
  {GREEN}/preset{RESET}   - Use a preset scenario
  {GREEN}/context{RESET}  - Show current case context
  {GREEN}/run{RESET}      - Execute current workflow
  {GREEN}/plan{RESET}     - Show plan without executing
  {GREEN}/history{RESET}  - Show all history
  {GREEN}/reset{RESET}    - Clear all history
  {GREEN}/help{RESET}     - Show this help
  {GREEN}/quit{RESET}     - Exit

{DIM}Just type your message to chat with the AI assistant.{RESET}
""")


def print_prompt():
    """Print input prompt."""
    print(f"{CYAN}You:{RESET} ", end="", flush=True)


def print_ai_response(text: str):
    """Print AI response with formatting."""
    print(f"{MAGENTA}Assistant:{RESET} {text}\n")


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


def fetch_customer_history(customer_id: str) -> dict:
    """Fetch customer dispute history from backend."""
    try:
        response = httpx.get(f"{BACKEND_URL}/debug/history")
        if response.status_code == 200:
            history = response.json().get("history", {})
            return history.get(customer_id, {"total_credits": 0, "dispute_count": 0})
    except Exception:
        pass
    return {"total_credits": 0, "dispute_count": 0}


def enrich_context_with_history(context: dict) -> dict:
    """Add dispute history to context before running workflow."""
    customer_id = context["db"]["customer"]["customer_id"]
    history = fetch_customer_history(customer_id)

    # Add history to context
    context["db"]["customer"]["total_credits_last_30_days"] = history.get("total_credits", 0)
    context["db"]["customer"]["disputes_last_30_days"] = history.get("dispute_count", 0)

    return context


def create_anthropic_client():
    """Create Anthropic client for chat."""
    return Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def extract_json_from_response(text: str) -> dict | None:
    """Extract JSON from AI response if present."""
    import re

    # Look for ```json ... ``` blocks
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Also try to find raw JSON object
    json_match = re.search(r'\{\s*"action"\s*:\s*"create_dispute".*?\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def fetch_customer_profile(customer_id: str) -> dict | None:
    """Fetch customer profile from the backend."""
    try:
        response = httpx.get(f"{BACKEND_URL}/crm/customers/{customer_id}", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def fetch_customer_plan(customer_id: str) -> dict | None:
    """Fetch customer's current plan from the backend."""
    try:
        response = httpx.get(f"{BACKEND_URL}/customers/{customer_id}/plan", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def build_context_from_chat(data: dict) -> dict:
    """Build a context dictionary from chat-extracted data."""
    customer = data.get("customer", {})
    invoice = data.get("invoice", {})

    # Check if customer_id was provided - if so, fetch from backend
    customer_id = customer.get("customer_id")
    if customer_id and customer_id.startswith("CUST-"):
        print(f"{DIM}Looking up customer {customer_id}...{RESET}")
        profile = fetch_customer_profile(customer_id)
        plan_info = fetch_customer_plan(customer_id)
        if profile:
            plan_name = plan_info.get("plan_name", "Unknown") if plan_info else "Unknown"
            print(f"{GREEN}✓ Found: {profile.get('name', 'Unknown')} (Plan: {plan_name}){RESET}")
            # Use fetched profile data
            customer_data = {
                "customer_id": customer_id,
                "name": profile.get("name", customer.get("name", "Unknown Customer")),
                "tenure_months": profile.get("tenure_months", customer.get("tenure_months", 12)),
                "arpu": profile.get("arpu", customer.get("arpu", 75.00)),
                "churn_risk": profile.get("churn_risk", customer.get("churn_risk", "medium")),
                "outstanding_balance": profile.get("outstanding_balance", customer.get("outstanding_balance", 0.00)),
                "current_plan_id": plan_info.get("plan_id") if plan_info else profile.get("current_plan_id", "basic"),
                "current_plan_name": plan_info.get("plan_name") if plan_info else "Unknown",
                "current_monthly_rate": plan_info.get("monthly_rate") if plan_info else 0.0,
            }
        else:
            print(f"{YELLOW}Customer not found, using provided data{RESET}")
            customer_data = {
                "customer_id": customer_id,
                "name": customer.get("name", "Unknown Customer"),
                "tenure_months": customer.get("tenure_months", 12),
                "arpu": customer.get("arpu", 75.00),
                "churn_risk": customer.get("churn_risk", "medium"),
                "outstanding_balance": customer.get("outstanding_balance", 0.00),
            }
    else:
        # Generate new customer ID
        customer_id = f"CUST-{random.randint(1000, 9999)}"
        customer_data = {
            "customer_id": customer_id,
            "name": customer.get("name", "Unknown Customer"),
            "tenure_months": customer.get("tenure_months", 12),
            "arpu": customer.get("arpu", 75.00),
            "churn_risk": customer.get("churn_risk", "medium"),
            "outstanding_balance": customer.get("outstanding_balance", 0.00),
        }

    case_id = f"CASE-{random.randint(1000, 9999)}"
    invoice_number = invoice.get("number", f"INV-{random.randint(10000, 99999)}")

    return {
        "db": {
            "customer": customer_data,
            "invoice": {
                "number": invoice_number,
                "amount": invoice.get("amount", invoice.get("disputed_amount", 0) * 2),
                "disputed_amount": invoice.get("disputed_amount", 0),
            },
        },
        "state": {"case_id": case_id},
        "input": {"dispute_reason": data.get("dispute_reason", data.get("upgrade_reason", "Customer request"))},
    }


def get_chat_tools() -> list[dict]:
    """Return tools available during chat for looking up customer info and playbooks."""
    return [
        {
            "name": "get_customer_profile",
            "description": "Fetch a customer's profile including name, tenure, churn risk, outstanding balance, and ARPU. Use this when a customer provides their ID.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., CUST-001)"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "get_customer_plan",
            "description": "Fetch a customer's current plan details including plan name, monthly rate, and payment history.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., CUST-001)"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "get_customer_invoices",
            "description": "Fetch a customer's invoice history including amounts, statuses, and line items.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., CUST-001)"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "list_playbooks",
            "description": "List all available business playbooks with their goals. Use this to find the right playbook for the customer's request.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_playbook",
            "description": "Load a specific business playbook to get detailed rules, steps, decision criteria, and thresholds. Use this after identifying which playbook matches the customer's request.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "playbook_name": {
                        "type": "string",
                        "description": "The playbook name (e.g., 'billing_dispute_resolution', 'plan_upgrade')"
                    }
                },
                "required": ["playbook_name"]
            }
        }
    ]


def execute_chat_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a chat tool and return the result."""
    customer_id = tool_input.get("customer_id", "")

    if tool_name == "get_customer_profile":
        result = fetch_customer_profile(customer_id)
        if result:
            return json.dumps(result, indent=2)
        return f"Customer {customer_id} not found"

    elif tool_name == "get_customer_plan":
        result = fetch_customer_plan(customer_id)
        if result:
            return json.dumps(result, indent=2)
        return f"Plan info for {customer_id} not found"

    elif tool_name == "get_customer_invoices":
        try:
            response = httpx.get(f"{BACKEND_URL}/customers/{customer_id}/invoices", timeout=5.0)
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
        except Exception:
            pass
        return f"Invoices for {customer_id} not found"

    elif tool_name == "list_playbooks":
        # Load all playbooks and return their names and goals
        example_dir = Path(__file__).parent
        playbooks_dir = example_dir / "playbooks"
        parser = PlaybookParser()
        playbooks_list = []
        for playbook_file in playbooks_dir.glob("*.md"):
            try:
                pb = parser.load_playbook(playbook_file)
                playbooks_list.append({
                    "name": pb.module_name,
                    "goal": pb.goal
                })
            except Exception:
                pass
        return json.dumps({"playbooks": playbooks_list}, indent=2)

    elif tool_name == "get_playbook":
        playbook_name = tool_input.get("playbook_name", "")
        example_dir = Path(__file__).parent
        playbooks_dir = example_dir / "playbooks"
        parser = PlaybookParser()

        # Try to find the playbook
        for playbook_file in playbooks_dir.glob("*.md"):
            try:
                pb = parser.load_playbook(playbook_file)
                if pb.module_name == playbook_name or playbook_file.stem == playbook_name:
                    # Return the raw markdown content for full business rules
                    return pb.raw_markdown
            except Exception:
                pass
        return f"Playbook '{playbook_name}' not found. Use list_playbooks to see available options."

    return f"Unknown tool: {tool_name}"


def chat_with_ai(
    client: Anthropic, messages: list, user_input: str, current_context: dict | None = None
) -> str:
    """Send message to AI and get response."""
    messages.append({"role": "user", "content": user_input})

    # Build system prompt with context if available
    system_prompt = CHAT_SYSTEM_PROMPT

    if current_context:
        customer = current_context["db"]["customer"]
        invoice = current_context["db"]["invoice"]
        context_info = f"""

CURRENT DISPUTE LOADED:
- Customer: {customer['name']} (ID: {customer['customer_id']})
- Tenure: {customer['tenure_months']} months
- Churn Risk: {customer['churn_risk']}
- Invoice: {invoice['number']}
- Invoice Amount: ${invoice['amount']}
- Disputed Amount: ${invoice['disputed_amount']}
- Reason: {current_context['input']['dispute_reason']}

This dispute is already set up. If the user asks about it or says hello, acknowledge their case.
They can type /run to process it or /plan to see the resolution plan.
If they want to file a NEW dispute, help them with that instead.
"""
        system_prompt = CHAT_SYSTEM_PROMPT + context_info

    # Get available tools for chat
    tools = get_chat_tools()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=tools,
    )

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        # Find all tool use blocks
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        # Execute tools and collect results
        tool_results = []
        for tool_use in tool_uses:
            print(f"{DIM}  → Calling {tool_use.name}({tool_use.input})...{RESET}")
            result = execute_chat_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })

        # Add assistant response (with tool use) and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Get next response
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

    # Extract text from final response
    text_blocks = [block.text for block in response.content if hasattr(block, "text")]
    assistant_message = "\n".join(text_blocks)

    messages.append({"role": "assistant", "content": assistant_message})

    return assistant_message


def get_preset_scenarios():
    """Return preset scenarios."""
    return {
        "high-risk": {
            "name": "High Risk Customer - Full Credit",
            "context": {
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
            },
        },
        "escalation": {
            "name": "Large Dispute - Escalation Required",
            "context": {
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
                        "disputed_amount": 350.00,
                    },
                },
                "state": {"case_id": "CASE-002"},
                "input": {"dispute_reason": "Unauthorized premium charges"},
            },
        },
        "partial": {
            "name": "Medium Tenure - Partial Credit",
            "context": {
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
                        "number": "INV-2024-003",
                        "amount": 80.00,
                        "disputed_amount": 40.00,
                    },
                },
                "state": {"case_id": "CASE-003"},
                "input": {"dispute_reason": "Duplicate charge on account"},
            },
        },
    }


def show_context(context: dict):
    """Display the current context."""
    if not context:
        print(f"\n{YELLOW}No dispute loaded yet. Chat with the AI or use /preset.{RESET}\n")
        return

    customer = context["db"]["customer"]
    invoice = context["db"]["invoice"]

    # Fetch latest history
    history = fetch_customer_history(customer["customer_id"])
    total_credits = history.get("total_credits", 0)
    dispute_count = history.get("dispute_count", 0)

    history_line = ""
    if dispute_count > 0:
        history_line = f"""
  {BOLD}Dispute History (last 30 days):{RESET}
    Previous disputes: {dispute_count}
    Total credits given: ${total_credits}
    {YELLOW}Note: Credit may be reduced by 25% due to recent disputes{RESET}
"""

    print(f"""
{BOLD}Current Dispute:{RESET}
  {BOLD}Customer:{RESET}
    ID: {customer['customer_id']}
    Name: {customer['name']}
    Tenure: {customer['tenure_months']} months
    Churn Risk: {customer['churn_risk']}

  {BOLD}Invoice:{RESET}
    Number: {invoice['number']}
    Amount: ${invoice['amount']}
    Disputed: ${invoice['disputed_amount']}

  {BOLD}Dispute:{RESET}
    Case ID: {context['state']['case_id']}
    Reason: {context['input']['dispute_reason']}
{history_line}""")


def show_plan(orchestrator, context: dict):
    """Show the workflow plan without executing."""
    if not context:
        print(f"\n{YELLOW}No dispute loaded. Chat with the AI first.{RESET}\n")
        return

    print(f"\n{YELLOW}Planning workflow...{RESET}\n")

    # Enrich with history before planning
    enriched_context = enrich_context_with_history(context.copy())

    try:
        plan = orchestrator.plan_only(
            trigger="telco_billing_resolution",
            initial_context=enriched_context,
        )

        print(f"{BOLD}Computed Logic Values:{RESET}")
        for key, value in plan.logic_values.items():
            print(f"  logic.{key} = {value}")

        print(f"\n{BOLD}Planned Steps:{RESET}")
        for step in plan.steps:
            print(f"  {step.order}. {GREEN}{step.operation_id}{RESET}")
            print(f"     {DIM}{step.description}{RESET}")

        print(f"\n{BOLD}Reasoning:{RESET}")
        print(f"  {DIM}{plan.reasoning}{RESET}\n")

    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}\n")


def execute_workflow(orchestrator, context: dict):
    """Execute the workflow against the mock backend."""
    if not context:
        print(f"\n{YELLOW}No dispute loaded. Chat with the AI first.{RESET}\n")
        return

    print(f"\n{YELLOW}Processing your dispute...{RESET}\n")

    # Enrich with history before executing
    enriched_context = enrich_context_with_history(context.copy())

    # Show if history affects this dispute
    history = fetch_customer_history(context["db"]["customer"]["customer_id"])
    if history.get("dispute_count", 0) > 0:
        print(f"{DIM}Note: Customer has {history['dispute_count']} previous dispute(s) "
              f"(${history['total_credits']} in credits){RESET}\n")

    try:
        result = orchestrator.execute_workflow(
            trigger="telco_billing_resolution",
            initial_context=enriched_context,
        )

        # Show logic values
        if result.plan:
            print(f"{BOLD}Resolution Decision:{RESET}")
            logic = result.plan.logic_values
            resolution_type = logic.get("resolution_type", "unknown")
            credit_amount = logic.get("recommended_credit_amount", 0)

            if resolution_type == "full_credit":
                print(f"  {GREEN}Full credit approved: ${credit_amount}{RESET}")
            elif resolution_type == "partial_credit":
                print(f"  {YELLOW}Partial credit approved: ${credit_amount}{RESET}")
            elif resolution_type == "escalate":
                print(f"  {YELLOW}Case escalated for manual review{RESET}")
            else:
                print(f"  Resolution: {resolution_type}")

            if logic.get("resolution_reason"):
                print(f"  Reason: {DIM}{logic['resolution_reason']}{RESET}")
            print()

        # Show API calls
        print(f"{BOLD}Actions Taken:{RESET}")
        for i, response in enumerate(result.api_responses, 1):
            if response.body:
                body = response.body
                if "adjustmentId" in body:
                    print(f"  {GREEN}✓{RESET} Billing adjustment created: {body['adjustmentId']}")
                    print(f"    Credit amount: ${body.get('amount', 'N/A')}")
                elif "notificationId" in body:
                    print(f"  {GREEN}✓{RESET} Notification sent via {body.get('channel', 'email')}")
                elif "ticketId" in body:
                    print(f"  {GREEN}✓{RESET} Escalation ticket created: {body['ticketId']}")
                    print(f"    Priority: {body.get('priority', 'N/A')}")
                elif "customer_id" in body:
                    print(f"  {GREEN}✓{RESET} Customer record verified")

        # Show result
        if result.success:
            print(f"\n{GREEN}{BOLD}Your dispute has been processed successfully!{RESET}\n")
        else:
            print(f"\n{RED}{BOLD}There was an issue processing your dispute:{RESET}")
            for error in result.errors:
                print(f"  {RED}• {error}{RESET}")
            print()

    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}\n")


def show_presets():
    """Show available preset scenarios."""
    presets = get_preset_scenarios()
    print(f"\n{BOLD}Available Presets:{RESET}")
    for key, preset in presets.items():
        ctx = preset["context"]
        customer = ctx["db"]["customer"]
        invoice = ctx["db"]["invoice"]
        print(f"\n  {GREEN}{key}{RESET} - {preset['name']}")
        print(f"    Customer: {customer['name']} (churn: {customer['churn_risk']})")
        print(f"    Dispute: ${invoice['disputed_amount']}")
    print()


def show_history():
    """Show all dispute history."""
    try:
        response = httpx.get(f"{BACKEND_URL}/debug/history")
        if response.status_code == 200:
            history = response.json().get("history", {})
            if not history:
                print(f"\n{DIM}No dispute history yet.{RESET}\n")
                return

            print(f"\n{BOLD}Dispute History:{RESET}")
            for customer_id, data in history.items():
                print(f"\n  {GREEN}{customer_id}{RESET}")
                print(f"    Total credits: ${data['total_credits']}")
                print(f"    Disputes: {data['dispute_count']}")
                for d in data.get("disputes", []):
                    print(f"      - {d['adjustment_id']}: ${d['amount']} ({d['invoice']})")
            print()
    except Exception as e:
        print(f"{RED}Error fetching history: {e}{RESET}\n")


def reset_history():
    """Clear all dispute history."""
    try:
        response = httpx.post(f"{BACKEND_URL}/debug/reset")
        if response.status_code == 200:
            print(f"\n{GREEN}✓ All dispute history cleared{RESET}\n")
        else:
            print(f"{RED}Failed to reset history{RESET}\n")
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}\n")


def main():
    """Run the interactive CLI."""
    global CHAT_SYSTEM_PROMPT

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: ANTHROPIC_API_KEY not set{RESET}")
        print("Run: export ANTHROPIC_API_KEY=your-key-here\n")
        sys.exit(1)

    # Build dynamic system prompt from playbooks and OpenAPI
    example_dir = Path(__file__).parent
    playbooks_dir = example_dir / "playbooks"

    # Load playbook names for display
    parser = PlaybookParser()
    workflow_names = []
    for playbook_file in playbooks_dir.glob("*.md"):
        try:
            playbook = parser.load_playbook(playbook_file)
            workflow_names.append(playbook.module_name.replace('_', ' ').title())
        except Exception:
            pass

    # Print header with discovered workflows
    print_header(workflow_names)

    # Build dynamic system prompt
    print(f"{DIM}Loading workflows from playbooks...{RESET}")
    CHAT_SYSTEM_PROMPT = build_dynamic_system_prompt(playbooks_dir)
    print(f"{GREEN}✓ Loaded {len(workflow_names)} workflow(s){RESET}")

    # Create orchestrator and AI client
    try:
        orchestrator = create_orchestrator()
        ai_client = create_anthropic_client()
        print(f"{GREEN}✓ Connected to backend at {BACKEND_URL}{RESET}")
        print(f"{GREEN}✓ AI assistant ready{RESET}\n")
    except Exception as e:
        print(f"{RED}Error initializing: {e}{RESET}\n")
        sys.exit(1)

    current_context = None
    chat_messages = []
    presets = get_preset_scenarios()

    # Initial greeting based on available workflows
    greeting = "Hello! I'm here to help you with "
    if len(workflow_names) > 1:
        greeting += ", ".join(workflow_names[:-1]).lower() + f" and {workflow_names[-1].lower()}"
    elif workflow_names:
        greeting += workflow_names[0].lower()
    else:
        greeting += "your requests"
    greeting += ". How can I help you today?"

    print_ai_response(greeting)

    while True:
        print_prompt()
        try:
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input[1:].lower().split()[0]

            if cmd in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            elif cmd == "help":
                print_header(workflow_names)

            elif cmd == "new":
                chat_messages = []
                current_context = None
                print(f"\n{GREEN}✓ Started new conversation{RESET}\n")
                print_ai_response(
                    "Let's start fresh! How can I help you today?"
                )

            elif cmd == "preset":
                show_presets()
                print("Enter preset name: ", end="", flush=True)
                preset_name = input().strip().lower()
                if preset_name in presets:
                    current_context = presets[preset_name]["context"]
                    print(f"\n{GREEN}✓ Loaded: {presets[preset_name]['name']}{RESET}")
                    show_context(current_context)
                else:
                    print(f"{RED}Unknown preset: {preset_name}{RESET}\n")

            elif cmd == "context":
                show_context(current_context)

            elif cmd == "plan":
                show_plan(orchestrator, current_context)

            elif cmd == "run":
                execute_workflow(orchestrator, current_context)

            elif cmd == "history":
                show_history()

            elif cmd == "reset":
                reset_history()

            elif cmd in presets:
                current_context = presets[cmd]["context"]
                print(f"\n{GREEN}✓ Loaded: {presets[cmd]['name']}{RESET}")
                show_context(current_context)

            else:
                print(f"{YELLOW}Unknown command: /{cmd}. Type /help for options.{RESET}\n")

        else:
            # Chat with AI
            try:
                response = chat_with_ai(ai_client, chat_messages, user_input, current_context)

                # Check if AI extracted dispute info
                extracted = extract_json_from_response(response)

                if extracted and extracted.get("action") == "create_dispute":
                    # Build context from extracted data
                    current_context = build_context_from_chat(extracted)

                    # Clean response (remove JSON block for display)
                    import re
                    clean_response = re.sub(
                        r"```json\s*\{.*?\}\s*```", "", response, flags=re.DOTALL
                    ).strip()

                    if clean_response:
                        print_ai_response(clean_response)

                    print(f"\n{GREEN}{BOLD}✓ Dispute case created!{RESET}")
                    show_context(current_context)
                    print(
                        f"{DIM}Type /run to process this dispute, "
                        f"or /plan to see what will happen.{RESET}\n"
                    )

                else:
                    print_ai_response(response)

            except Exception as e:
                print(f"{RED}Error communicating with AI: {e}{RESET}\n")


if __name__ == "__main__":
    main()
