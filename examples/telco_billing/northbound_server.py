#!/usr/bin/env python3
"""
Northbound API Server - LLM-friendly interface to telco billing APIs.

This server proxies requests to the southbound mock server and enriches
the OpenAPI documentation with context for LLM orchestration.

Run:
    poetry run python examples/telco_billing/northbound_server.py

Requires the southbound mock server to be running on port 9100:
    cd ../excom-context-mesh-mock-server
    poetry run mock-server
"""

from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configuration
SOUTHBOUND_URL = "http://localhost:9100"
NORTHBOUND_PORT = 8052

app = FastAPI(
    title="Telco Billing API (Northbound)",
    description="""
## Overview

LLM-friendly interface for telco billing operations. This API provides endpoints
for customer management, billing adjustments, notifications, escalations, and plan upgrades.

**Important**: Always fetch actual data from API endpoints. Do not assume values.

---

## Workflow 1: Billing Dispute Resolution

Use when a customer disputes a charge on their bill.

### Steps

1. `GET /crm/customers/{id}` - Fetch customer profile (tenure, churn_risk, dispute history)
2. Evaluate eligibility using decision rules in endpoint documentation
3. If eligible: `POST /billing/adjustments` - Issue credit
4. Always: `POST /notifications/send` - Notify customer
5. If not eligible: `POST /tickets/create` - Escalate for review

### Key Fields to Check

- `churn_risk`: Determines retention priority
- `tenure_months`: Affects credit eligibility
- `disputes_last_30_days`: May trigger escalation
- `outstanding_balance`: May affect eligibility

---

## Workflow 2: Plan Upgrade

Use when a customer requests to upgrade their service plan.

### Steps

1. `GET /crm/customers/{id}` - Check customer profile and outstanding_balance
2. `GET /customers/{id}/plan` - Get current plan and payment history
3. `GET /plans` - Fetch available plans (compare tiers for valid upgrades)
4. If eligible: `POST /customers/{id}/plan/upgrade` - Process upgrade
5. Always: `POST /notifications/send` - Send confirmation

### Key Fields to Check

- `outstanding_balance`: May block upgrade
- `late_payments_last_90_days`: May require escalation
- `tier`: New plan tier must be higher than current

---

## API Categories

- **CRM**: Customer profiles and context
- **Billing**: Adjustments (credits/debits)
- **Invoices**: Customer invoice history and line items
- **Plans**: Service plans and upgrades
- **Notifications**: Customer communications
- **Tickets**: Escalations for manual review
""",
    version="1.0.0",
)


# =============================================================================
# Request/Response Models with Rich Descriptions
# =============================================================================

class CustomerResponse(BaseModel):
    """
    Customer profile with billing context.

    Use this data to make decisions about dispute resolution:
    - High churn_risk + high tenure = prioritize retention
    - Multiple recent disputes = consider escalation
    - High ARPU = higher credit thresholds acceptable
    """

    customer_id: str = Field(
        ...,
        description="Unique customer identifier (format: CUST-XXX)",
        examples=["CUST-001", "CUST-002"],
    )
    name: str = Field(
        ...,
        description="Customer's full name for personalization",
        examples=["Alice Johnson", "Bob Smith"],
    )
    email: str = Field(
        ...,
        description="Customer's email address for notifications",
        examples=["alice.johnson@example.com"],
    )
    tenure_months: int = Field(
        ...,
        description="How long the customer has been with us in months. "
                    "Longer tenure indicates loyalty - check playbook for specific thresholds.",
        examples=[36, 6, 12],
        ge=0,
    )
    arpu: float = Field(
        ...,
        description="Average Revenue Per User - monthly value of this customer in dollars. "
                    "Higher ARPU customers are more valuable and may warrant higher credit limits.",
        examples=[120.0, 45.0, 75.0],
        ge=0,
    )
    churn_risk: Literal["low", "medium", "high"] = Field(
        ...,
        description="Predicted likelihood of customer leaving. "
                    "HIGH = likely to churn, prioritize retention. "
                    "MEDIUM = monitor closely. "
                    "LOW = stable customer.",
        examples=["high", "medium", "low"],
    )
    outstanding_balance: float = Field(
        ...,
        description="Current unpaid balance on the account in dollars. "
                    "High balances may indicate payment issues - check playbook for thresholds.",
        examples=[50.0, 200.0, 0.0],
        ge=0,
    )
    total_credits_last_30_days: float = Field(
        default=0.0,
        description="Total credits already issued to this customer in the last 30 days. "
                    "High values may indicate abuse or systemic issues.",
        examples=[0.0, 75.0, 150.0],
        ge=0,
    )
    disputes_last_30_days: int = Field(
        default=0,
        description="Number of disputes filed in the last 30 days. "
                    "High dispute count may trigger escalation - check playbook for thresholds.",
        examples=[0, 1, 3],
        ge=0,
    )


class BillingAdjustmentRequest(BaseModel):
    """
    Request to create a billing adjustment (credit or debit).

    Use this to issue credits for valid disputes. Ensure:
    - Customer is eligible based on tenure/churn_risk
    - Amount is within auto-approval limits
    - A clear reason is provided for audit trail
    """

    customerId: str = Field(
        ...,
        description="Customer ID to apply the adjustment to",
        examples=["CUST-001"],
    )
    invoiceNumber: str = Field(
        ...,
        description="Invoice number being adjusted",
        examples=["INV-2024-001", "INV-2024-002"],
    )
    amount: float = Field(
        ...,
        description="Adjustment amount in dollars. Positive for credits. "
                    "Check playbook for auto-approval limits based on customer profile.",
        examples=[75.0, 50.0, 25.0],
        gt=0,
    )
    reason: str = Field(
        ...,
        description="Detailed reason for the adjustment. Required for compliance and audit. "
                    "Include: dispute type, customer situation, and justification.",
        examples=[
            "Customer dispute: service outage on 2024-01-15. High churn risk, full credit approved.",
            "Partial credit for billing error. Goodwill adjustment per playbook rules.",
        ],
        min_length=10,
    )
    adjustmentType: Literal["credit", "debit"] = Field(
        default="credit",
        description="Type of adjustment: 'credit' reduces balance, 'debit' increases balance",
        examples=["credit", "debit"],
    )


class BillingAdjustmentResponse(BaseModel):
    """Response after creating a billing adjustment."""

    adjustmentId: str = Field(
        ...,
        description="Unique identifier for this adjustment (format: ADJ-XXXXXXXX)",
        examples=["ADJ-A1B2C3D4"],
    )
    customerId: str = Field(..., description="Customer ID")
    invoiceNumber: str = Field(..., description="Invoice number adjusted")
    amount: float = Field(..., description="Adjustment amount applied")
    reason: str = Field(..., description="Reason provided")
    adjustmentType: str = Field(..., description="Type: credit or debit")
    status: str = Field(
        ...,
        description="Status of the adjustment: 'applied', 'pending', or 'rejected'",
        examples=["applied"],
    )
    createdAt: str = Field(
        ...,
        description="ISO 8601 timestamp when adjustment was created",
        examples=["2024-01-15T10:30:00Z"],
    )


class NotificationRequest(BaseModel):
    """
    Request to send a notification to a customer.

    Always notify customers after:
    - Issuing a credit (use template: credit_issued)
    - Creating an escalation (use template: escalation_created)
    - Resolving a dispute (use template: dispute_resolved)
    """

    customerId: str = Field(
        ...,
        description="Customer ID to notify",
        examples=["CUST-001"],
    )
    channel: Literal["email", "sms", "push"] = Field(
        default="email",
        description="Notification channel. Email is default and most reliable.",
        examples=["email", "sms"],
    )
    templateId: str = Field(
        ...,
        description="Notification template to use. Available templates: "
                    "'credit_issued' - confirms credit applied, "
                    "'escalation_created' - informs of manual review, "
                    "'dispute_resolved' - final resolution notice",
        examples=["credit_issued", "escalation_created", "dispute_resolved"],
    )
    templateData: dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic data to populate the template. "
                    "Common fields: amount, invoiceNumber, caseId, resolutionType",
        examples=[{"amount": 75.0, "invoiceNumber": "INV-2024-001"}],
    )


class NotificationResponse(BaseModel):
    """Response after sending a notification."""

    notificationId: str = Field(
        ...,
        description="Unique identifier for this notification (format: NOT-XXXXXXXX)",
        examples=["NOT-A1B2C3D4"],
    )
    customerId: str = Field(..., description="Customer ID notified")
    channel: str = Field(..., description="Channel used")
    templateId: str = Field(..., description="Template used")
    status: str = Field(
        ...,
        description="Delivery status: 'sent', 'pending', or 'failed'",
        examples=["sent"],
    )
    sentAt: str = Field(
        ...,
        description="ISO 8601 timestamp when notification was sent",
        examples=["2024-01-15T10:30:00Z"],
    )


class EscalationTicketRequest(BaseModel):
    """
    Request to create an escalation ticket for manual review.

    Create escalations when:
    - Dispute amount exceeds auto-approval threshold (see playbook)
    - Customer has high dispute count (see playbook)
    - Case requires supervisor approval
    - Fraud suspected
    """

    customerId: str = Field(
        ...,
        description="Customer ID for the escalation",
        examples=["CUST-001"],
    )
    category: Literal["billing_dispute", "fraud", "service_issue", "other"] = Field(
        ...,
        description="Category of the escalation for routing",
        examples=["billing_dispute", "fraud"],
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        ...,
        description="Priority level. Use 'high' for high churn risk customers, "
                    "'urgent' for fraud or exceptional cases.",
        examples=["high", "medium"],
    )
    subject: str = Field(
        ...,
        description="Brief subject line for the ticket",
        examples=["Billing dispute requires supervisor approval"],
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Detailed description including: customer context, dispute details, "
                    "reason for escalation, and recommended action",
        examples=[
            "Customer CUST-001 (Alice Johnson) disputes charge on INV-2024-001. "
            "High churn risk, long tenure. Amount exceeds auto-approval limit. "
            "Recommend full credit to retain customer."
        ],
        min_length=20,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context: invoiceNumber, disputedAmount, churnRisk, tenure",
        examples=[{
            "invoiceNumber": "INV-2024-001",
            "disputedAmount": 350.0,
            "churnRisk": "high",
            "tenureMonths": 36,
        }],
    )


class EscalationTicketResponse(BaseModel):
    """Response after creating an escalation ticket."""

    ticketId: str = Field(
        ...,
        description="Unique identifier for this ticket (format: TKT-XXXXXXXX)",
        examples=["TKT-A1B2C3D4"],
    )
    customerId: str = Field(..., description="Customer ID")
    category: str = Field(..., description="Ticket category")
    priority: str = Field(..., description="Priority level")
    subject: str = Field(..., description="Ticket subject")
    status: str = Field(
        ...,
        description="Ticket status: 'open', 'in_progress', 'resolved', 'closed'",
        examples=["open"],
    )
    createdAt: str = Field(
        ...,
        description="ISO 8601 timestamp when ticket was created",
        examples=["2024-01-15T10:30:00Z"],
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status: 'healthy' or 'unhealthy'")
    service: str = Field(..., description="Service name")
    southbound_status: str = Field(
        ...,
        description="Status of southbound connection: 'healthy', 'unhealthy', or 'unreachable'"
    )
    version: str = Field(..., description="API version")


# =============================================================================
# Plan Models with Rich Descriptions
# =============================================================================

class PlanResponse(BaseModel):
    """
    Service plan details.

    Plans are tiered from basic (1) to unlimited (4). Higher tiers include
    more data, minutes, and premium features. Use tier comparison to validate
    upgrade requests - customers can only upgrade to higher tiers.
    """

    plan_id: str = Field(
        ...,
        description="Unique plan identifier: basic, standard, premium, unlimited",
        examples=["basic", "standard", "premium", "unlimited"],
    )
    name: str = Field(
        ...,
        description="Display name of the plan",
        examples=["Basic", "Standard", "Premium", "Unlimited"],
    )
    monthly_rate: float = Field(
        ...,
        description="Base monthly rate in dollars before any discounts",
        examples=[29.99, 49.99, 79.99, 99.99],
        gt=0,
    )
    data_gb: int = Field(
        ...,
        description="Monthly data allowance in GB. -1 indicates unlimited data.",
        examples=[5, 15, 50, -1],
    )
    minutes: int = Field(
        ...,
        description="Monthly voice minutes. -1 indicates unlimited minutes.",
        examples=[500, 1000, 2000, -1],
    )
    tier: int = Field(
        ...,
        description="Plan tier level (1-4). Higher tier = better plan. "
                    "Upgrades must be to a HIGHER tier. "
                    "1=Basic, 2=Standard, 3=Premium, 4=Unlimited",
        examples=[1, 2, 3, 4],
        ge=1,
        le=4,
    )


class CustomerPlanResponse(BaseModel):
    """
    Customer's current plan assignment with payment history.

    Use this to:
    - Check if customer is eligible for upgrade
    - Validate that requested plan is higher tier than current
    - Check payment history before approving upgrade
    """

    customer_id: str = Field(
        ...,
        description="Customer ID",
        examples=["CUST-001"],
    )
    plan_id: str = Field(
        ...,
        description="Current plan ID",
        examples=["basic", "standard"],
    )
    plan_name: str = Field(
        ...,
        description="Current plan display name",
        examples=["Basic", "Standard"],
    )
    monthly_rate: float = Field(
        ...,
        description="Current monthly rate being charged",
        examples=[29.99, 49.99],
    )
    start_date: str = Field(
        ...,
        description="When customer started this plan (ISO 8601)",
        examples=["2024-01-01T00:00:00Z"],
    )
    late_payments_last_90_days: int = Field(
        default=0,
        description="Number of late payments in last 90 days. "
                    "High values may require manager approval - see playbook for thresholds.",
        examples=[0, 1, 2],
        ge=0,
    )


class PlanUpgradeRequest(BaseModel):
    """
    Request to upgrade a customer's plan.

    Prerequisites:
    - New plan must be higher tier than current plan
    - Customer outstanding balance must be within limits (see playbook)
    - Late payments must be within limits (see playbook for thresholds)
    """

    new_plan_id: str = Field(
        ...,
        description="Target plan ID. Must be higher tier than current. "
                    "Options: standard, premium, unlimited",
        examples=["premium", "unlimited"],
    )
    effective_date: str | None = Field(
        default=None,
        description="When upgrade takes effect (ISO 8601). "
                    "If null/omitted, upgrade is immediate.",
        examples=["2024-02-01T00:00:00Z", None],
    )


class InvoiceItemResponse(BaseModel):
    """Line item on an invoice."""

    description: str = Field(..., description="Description of the charge")
    amount: float = Field(..., description="Amount for this line item")


class InvoiceResponse(BaseModel):
    """
    Customer invoice with line item details.

    Use this to understand customer billing history when handling disputes.
    Look for patterns like recurring overages or disputed charges.
    """

    invoice_id: str = Field(
        ...,
        description="Unique invoice identifier",
        examples=["INV-CUST-001-006"],
    )
    customer_id: str = Field(..., description="Customer this invoice belongs to")
    invoice_number: str = Field(
        ...,
        description="Human-readable invoice number for customer reference",
        examples=["INV-2024-12345"],
    )
    amount: float = Field(
        ...,
        description="Total invoice amount in dollars",
        examples=[29.99, 45.98, 79.99],
    )
    due_date: str = Field(
        ...,
        description="Payment due date (YYYY-MM-DD format)",
        examples=["2024-12-20"],
    )
    status: str = Field(
        ...,
        description="Invoice status: paid, unpaid, overdue, or disputed. "
                    "Disputed invoices may already have pending adjustments.",
        examples=["paid", "unpaid", "disputed"],
    )
    issued_date: str = Field(
        ...,
        description="Date invoice was issued (YYYY-MM-DD format)",
        examples=["2024-12-06"],
    )
    items: list[InvoiceItemResponse] = Field(
        ...,
        description="Line items showing breakdown of charges. "
                    "Check for overage charges or unexpected add-ons.",
    )


class PlanUpgradeResponse(BaseModel):
    """
    Result of a plan upgrade request.

    The response includes computed discounts based on tenure.
    See playbook for specific tenure thresholds and discount percentages.
    """

    upgrade_id: str = Field(
        ...,
        description="Unique upgrade transaction ID (format: UPG-XXXXXXXX)",
        examples=["UPG-A1B2C3D4"],
    )
    customer_id: str = Field(..., description="Customer ID")
    old_plan_id: str = Field(
        ...,
        description="Previous plan ID",
        examples=["basic"],
    )
    new_plan_id: str = Field(
        ...,
        description="New plan ID",
        examples=["premium"],
    )
    old_monthly_rate: float = Field(
        ...,
        description="Previous monthly rate",
        examples=[29.99],
    )
    new_monthly_rate: float = Field(
        ...,
        description="New plan base rate (before discount)",
        examples=[79.99],
    )
    discount_percent: float = Field(
        ...,
        description="Loyalty discount applied based on tenure - see playbook for tiers",
        examples=[0.0, 10.0, 20.0],
    )
    final_monthly_rate: float = Field(
        ...,
        description="Final rate after loyalty discount applied",
        examples=[63.99, 71.99, 79.99],
    )
    effective_date: str = Field(
        ...,
        description="When the upgrade takes effect (ISO 8601)",
        examples=["2024-01-15T10:30:00Z"],
    )
    status: str = Field(
        ...,
        description="Upgrade status: 'completed', 'pending', or 'rejected'",
        examples=["completed"],
    )
    created_at: str = Field(
        ...,
        description="When upgrade was processed (ISO 8601)",
        examples=["2024-01-15T10:30:00Z"],
    )


# =============================================================================
# Helper Functions
# =============================================================================

def proxy_get(path: str) -> dict:
    """Proxy GET request to southbound."""
    try:
        response = httpx.get(f"{SOUTHBOUND_URL}{path}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Southbound unavailable: {e}")


def proxy_post(path: str, data: dict) -> dict:
    """Proxy POST request to southbound."""
    try:
        response = httpx.post(f"{SOUTHBOUND_URL}{path}", json=data, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Southbound unavailable: {e}")


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse, tags=["Health"])
def health_check():
    """
    Check health of northbound and southbound services.

    Use this to verify connectivity before making API calls.
    """
    southbound_status = "unknown"
    try:
        response = httpx.get(f"{SOUTHBOUND_URL}/", timeout=2.0)
        southbound_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        southbound_status = "unreachable"

    return HealthResponse(
        status="healthy",
        service="Telco Billing API (Northbound)",
        southbound_status=southbound_status,
        version="1.0.0",
    )


@app.get(
    "/crm/customers/{customer_id}",
    response_model=CustomerResponse,
    tags=["CRM"],
    summary="Get customer profile and dispute context",
    description="""
Retrieve complete customer profile including billing context for decision-making.

## Key Response Fields

- `churn_risk`: Customer's likelihood to leave ("low", "medium", "high")
- `tenure_months`: How long they've been a customer
- `arpu`: Average revenue per user (customer value)
- `outstanding_balance`: Current unpaid balance
- `disputes_last_30_days`: Recent dispute count (high = possible fraud pattern)
- `total_credits_last_30_days`: Recent credits issued

## Decision Factors

Use these fields to evaluate eligibility:

- **churn_risk**: Higher risk = prioritize retention
- **tenure_months**: Longer tenure = more trust, higher limits
- **disputes_last_30_days**: Many recent disputes = escalate for review
- **outstanding_balance**: High balance = may affect eligibility

## Workflow

1. Fetch this endpoint to get customer context
2. Evaluate eligibility based on playbook rules
3. If eligible: `POST /billing/adjustments`
4. Always: `POST /notifications/send`
5. If not eligible: `POST /tickets/create`
""",
)
def get_customer(customer_id: str):
    """Get customer details with dispute history and billing context."""
    return proxy_get(f"/crm/customers/{customer_id}")


@app.post(
    "/billing/adjustments",
    response_model=BillingAdjustmentResponse,
    tags=["Billing"],
    summary="Create billing adjustment (credit/debit)",
    description="""
Create a billing adjustment to credit or debit a customer's account.

## Prerequisites

Before calling this endpoint:
1. Fetch customer via `GET /crm/customers/{id}`
2. Evaluate eligibility using playbook rules
3. Calculate appropriate credit amount based on rules

## Request Fields

- `customerId`: Customer to adjust
- `invoiceNumber`: Invoice being adjusted
- `amount`: Credit/debit amount (use value from eligibility calculation)
- `reason`: Detailed explanation for audit trail
- `adjustmentType`: "credit" or "debit"

## Response

Returns confirmation with:
- `adjustmentId`: Reference number
- `status`: "applied", "pending", or "rejected"

## After Creating Adjustment

Send notification using `POST /notifications/send` with:
- `templateId`: "credit_issued"
- `templateData`: Include amount and invoice from this response
""",
)
def create_billing_adjustment(request: BillingAdjustmentRequest):
    """Create a billing adjustment (credit/debit) for a customer."""
    return proxy_post("/billing/adjustments", request.model_dump())


@app.post(
    "/notifications/send",
    response_model=NotificationResponse,
    tags=["Notifications"],
    summary="Send notification to customer",
    description="""
Send a notification to inform the customer about their dispute resolution.

## Available Templates

| Template ID | When to Use |
|-------------|-------------|
| `credit_issued` | After applying a credit adjustment |
| `escalation_created` | After creating an escalation ticket |
| `dispute_resolved` | Final resolution notification |

## Template Data

Include relevant context in `templateData`:
- `amount`: Credit amount (for credit_issued)
- `invoiceNumber`: The invoice being disputed
- `caseId`: Reference number for tracking
- `resolutionType`: "full_credit", "partial_credit", or "escalated"
""",
)
def send_notification(request: NotificationRequest):
    """Send a notification to a customer."""
    return proxy_post("/notifications/send", request.model_dump())


@app.post(
    "/tickets/create",
    response_model=EscalationTicketResponse,
    tags=["Tickets"],
    summary="Create escalation ticket for manual review",
    description="""
Create an escalation ticket when a dispute cannot be auto-resolved.

## When to Escalate

- Dispute amount exceeds auto-approval threshold (see playbook)
- Customer has excessive disputes in last 30 days (see playbook)
- Outstanding balance exceeds threshold (see playbook)
- Fraud indicators present
- Policy exception required

## Priority Guidelines

| Situation | Priority |
|-----------|----------|
| Fraud suspected | urgent |
| Large amount (see playbook) | urgent |
| High churn risk customer | high |
| Standard escalation | medium |
| Information request | low |

## After Creating Ticket

Notify the customer that their case is under review:
```
POST /notifications/send
{
  "customerId": "CUST-001",
  "templateId": "escalation_created",
  "templateData": {"ticketId": "TKT-XXX", "subject": "..."}
}
```
""",
)
def create_escalation_ticket(request: EscalationTicketRequest):
    """Create an escalation ticket for manual review."""
    return proxy_post("/tickets/create", request.model_dump())


# =============================================================================
# Plan Endpoints
# =============================================================================

@app.get(
    "/plans",
    response_model=list[PlanResponse],
    tags=["Plans"],
    summary="List all available service plans",
    description="""
Fetch all available service plans. Use the returned data to determine valid upgrade paths.

## Response Fields

- `plan_id`: Unique identifier for the plan
- `name`: Display name
- `monthly_rate`: Base price (before discounts)
- `data_gb`: Data allowance (-1 = unlimited)
- `minutes`: Voice minutes (-1 = unlimited)
- `tier`: Numeric tier level for comparison

## Upgrade Rules

- Upgrades must be to a HIGHER tier (compare `tier` values)
- Cannot downgrade or move to same tier
- Loyalty discounts are applied automatically based on customer tenure

## Usage

1. Fetch this list to see available options
2. Get customer's current plan via `GET /customers/{id}/plan`
3. Filter to plans where `tier` > customer's current tier
4. Process via `POST /customers/{id}/plan/upgrade`
""",
)
def list_plans():
    """List all available service plans."""
    return proxy_get("/plans")


@app.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    tags=["Plans"],
    summary="Get plan details",
    description="""
Get details for a specific plan.

Use this to validate that a target plan exists and check its tier
before processing an upgrade request.
""",
)
def get_plan(plan_id: str):
    """Get details for a specific plan."""
    return proxy_get(f"/plans/{plan_id}")


@app.get(
    "/customers/{customer_id}/plan",
    response_model=CustomerPlanResponse,
    tags=["Plans"],
    summary="Get customer's current plan",
    description="""
Get the customer's current plan assignment and payment history.

## Decision Context

Use this before processing upgrade to check:

| Field | Check | Action |
|-------|-------|--------|
| plan_id | Compare tier with target | Must upgrade to higher tier |
| late_payments_last_90_days | Above threshold | Escalate (see playbook) |
| late_payments_last_90_days | Within threshold | Proceed with upgrade |

## Workflow

1. Fetch current plan to get tier and payment history
2. Fetch customer profile for outstanding_balance check
3. Check outstanding_balance against playbook threshold
4. Check late_payments against playbook threshold
5. If eligible: Process upgrade via `POST /customers/{id}/plan/upgrade`
""",
)
def get_customer_plan(customer_id: str):
    """Get customer's current plan assignment."""
    return proxy_get(f"/customers/{customer_id}/plan")


@app.get(
    "/customers/{customer_id}/invoices",
    response_model=list[InvoiceResponse],
    tags=["Invoices"],
    summary="Get customer invoices",
    description="""
Get all invoices for a customer, including line item details.

## When to Use

- Review billing history when handling disputes
- Identify specific invoices with disputed charges
- Check for patterns of overages or add-on charges

## Response Fields

- `invoice_id`: Unique identifier for the invoice
- `invoice_number`: Human-readable invoice number (use this when referencing invoices)
- `amount`: Total invoice amount
- `status`: paid, unpaid, overdue, or disputed
- `items`: Line items showing charge breakdown

## Workflow Integration

1. Fetch invoices to understand billing history
2. Identify the disputed invoice by number
3. Check status and line items for dispute details
4. Use invoice_number when creating adjustments
""",
)
def get_customer_invoices(customer_id: str):
    """Get customer's invoice history."""
    return proxy_get(f"/customers/{customer_id}/invoices")


@app.post(
    "/customers/{customer_id}/plan/upgrade",
    response_model=PlanUpgradeResponse,
    tags=["Plans"],
    summary="Upgrade customer's plan",
    description="""
Process a plan upgrade for a customer.

## Prerequisites

Before calling this endpoint:

1. Fetch customer profile: `GET /crm/customers/{id}`
   - Check `outstanding_balance` field
2. Fetch current plan: `GET /customers/{id}/plan`
   - Check `late_payments_last_90_days` field
3. Fetch target plan: `GET /plans/{plan_id}`
   - Verify target `tier` > current `tier`

## Eligibility Rules

- High `outstanding_balance`: May block upgrade (require payment first)
- High `late_payments_last_90_days`: May require escalation
- Target tier must be HIGHER than current tier

## Response Fields

The response includes:
- `discount_percent`: Loyalty discount applied (based on customer tenure)
- `final_monthly_rate`: Actual rate after discount
- `status`: Whether upgrade succeeded

## After Upgrade

Send confirmation notification using `POST /notifications/send` with:
- `templateId`: "plan_upgraded"
- `templateData`: Include old/new plan names and final rate from response
""",
)
def upgrade_customer_plan(customer_id: str, request: PlanUpgradeRequest):
    """Process a plan upgrade for a customer."""
    return proxy_post(f"/customers/{customer_id}/plan/upgrade", request.model_dump())


# =============================================================================
# Debug Endpoints
# =============================================================================

@app.get("/debug/adjustments", tags=["Debug"], summary="List all billing adjustments")
def list_adjustments():
    """List all adjustments for debugging."""
    return proxy_get("/debug/adjustments")


@app.get("/debug/notifications", tags=["Debug"], summary="List all notifications")
def list_notifications():
    """List all notifications for debugging."""
    return proxy_get("/debug/notifications")


@app.get("/debug/tickets", tags=["Debug"], summary="List all escalation tickets")
def list_tickets():
    """List all tickets for debugging."""
    return proxy_get("/debug/tickets")


@app.get("/debug/history", tags=["Debug"], summary="List dispute history by customer")
def list_dispute_history():
    """List dispute history by customer for debugging."""
    return proxy_get("/debug/history")


@app.get("/debug/customers", tags=["Debug"], summary="List all customers")
def list_customers():
    """List all customers for debugging."""
    return proxy_get("/debug/customers")


@app.get("/debug/data", tags=["Debug"], summary="Get all raw data")
def get_raw_data():
    """Get all raw data for debugging."""
    return proxy_get("/debug/data")


@app.post("/debug/reset", tags=["Debug"], summary="Reset transaction data")
def reset_all():
    """Reset all transaction data (keeps customers)."""
    return proxy_post("/debug/reset", {})


@app.get("/debug/upgrades", tags=["Debug"], summary="List all plan upgrades")
def list_upgrades():
    """List all plan upgrades for debugging."""
    return proxy_get("/debug/upgrades")


@app.get("/debug/customer-plans", tags=["Debug"], summary="List all customer plan assignments")
def list_customer_plans():
    """List all customer plan assignments for debugging."""
    return proxy_get("/debug/customer-plans")


@app.post("/debug/reset-all", tags=["Debug"], summary="Reset everything to defaults")
def reset_everything():
    """Reset everything to defaults."""
    return proxy_post("/debug/reset-all", {})


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" Telco Billing API (Northbound - LLM Context Enriched)")
    print("=" * 60)
    print(f"\n  Northbound: http://localhost:{NORTHBOUND_PORT}")
    print(f"  Southbound: {SOUTHBOUND_URL}")
    print(f"\n  OpenAPI docs: http://localhost:{NORTHBOUND_PORT}/docs")
    print(f"  OpenAPI JSON: http://localhost:{NORTHBOUND_PORT}/openapi.json")
    print("\nEndpoints:")
    print("  GET  /crm/customers/{customerId} - Get customer with context")
    print("  POST /billing/adjustments        - Create credit/debit")
    print("  POST /notifications/send         - Send notification")
    print("  POST /tickets/create             - Create escalation")
    print("\nPlans:")
    print("  GET  /plans                      - List all plans")
    print("  GET  /plans/{planId}             - Get plan details")
    print("  GET  /customers/{id}/plan        - Get customer's plan")
    print("  POST /customers/{id}/plan/upgrade - Upgrade plan")
    print("\nInvoices:")
    print("  GET  /customers/{id}/invoices    - Get customer invoices")
    print()

    uvicorn.run(app, host="0.0.0.0", port=NORTHBOUND_PORT)
