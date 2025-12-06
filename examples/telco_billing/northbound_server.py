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

LLM-friendly interface for telco billing operations. This API provides context-rich
endpoints for customer management, billing adjustments, notifications, and escalations.

## Decision Context

When handling billing disputes, consider:

1. **Customer Value**: High ARPU and long tenure customers are more valuable
2. **Churn Risk**: High-risk customers should be treated with priority
3. **Dispute History**: Repeat disputes may indicate fraud or chronic issues
4. **Amount Thresholds**: Large disputes (>$200) typically require escalation

## Recommended Workflow

1. Fetch customer context via `GET /crm/customers/{id}`
2. Evaluate eligibility based on tenure, churn_risk, and dispute history
3. For eligible cases: Create adjustment via `POST /billing/adjustments`
4. Send notification via `POST /notifications/send`
5. For ineligible cases: Create escalation via `POST /tickets/create`
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
                    "Longer tenure (>12 months) indicates loyalty and may qualify for higher credits.",
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
                    "High balances (>$500) may indicate payment issues.",
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
                    "4+ disputes should trigger automatic escalation for review.",
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
        description="Adjustment amount in dollars. Positive for credits, negative for debits. "
                    "Auto-approval limits: High churn risk <$200, Long tenure <$100, Others <$50",
        examples=[75.0, 50.0, 25.0],
        gt=0,
    )
    reason: str = Field(
        ...,
        description="Detailed reason for the adjustment. Required for compliance and audit. "
                    "Include: dispute type, customer situation, and justification.",
        examples=[
            "Customer dispute: service outage on 2024-01-15. High churn risk, full credit approved.",
            "Partial credit for billing error. 50% goodwill adjustment.",
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
    - Dispute amount > $200
    - Customer has 4+ disputes in 30 days
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
                    "'urgent' for fraud or large amounts (>$500)",
        examples=["high", "medium"],
    )
    subject: str = Field(
        ...,
        description="Brief subject line for the ticket",
        examples=["Billing dispute requires supervisor approval - $350"],
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Detailed description including: customer context, dispute details, "
                    "reason for escalation, and recommended action",
        examples=[
            "Customer CUST-001 (Alice Johnson) disputes $350 on INV-2024-001. "
            "High churn risk, 36 month tenure. Amount exceeds auto-approval limit. "
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

## Decision Guidelines

Based on the response, determine eligibility:

| Condition | Credit Limit | Action |
|-----------|--------------|--------|
| churn_risk = "high" AND amount < $200 | Full credit | Auto-approve |
| tenure_months > 12 AND amount < $100 | Full credit | Auto-approve |
| tenure_months > 6 AND amount < $50 | 50% credit | Partial approve |
| disputes_last_30_days >= 4 | $0 | Escalate |
| amount > $200 | $0 | Escalate |

## Adjustments

- If disputes_last_30_days > 0: Reduce credit by 25%
- If outstanding_balance > $500: Consider escalation

## Next Steps

After fetching customer:
1. Evaluate eligibility using the guidelines above
2. If eligible: `POST /billing/adjustments`
3. Always: `POST /notifications/send`
4. If not eligible: `POST /tickets/create`
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
2. Verify eligibility based on tenure, churn_risk, and dispute history
3. Calculate appropriate credit amount (apply 25% reduction for repeat disputes)

## Auto-Approval Limits

| Customer Profile | Max Auto-Approval |
|-----------------|-------------------|
| High churn risk | $200 |
| Tenure > 12 months | $100 |
| Tenure 6-12 months | $50 (partial) |
| Others | Escalate |

## After Creating Adjustment

Always send a notification to confirm:
```
POST /notifications/send
{
  "customerId": "CUST-001",
  "templateId": "credit_issued",
  "templateData": {"amount": 75.0, "invoiceNumber": "INV-001"}
}
```
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

- Dispute amount > $200
- Customer has 4+ disputes in last 30 days
- Outstanding balance > $500
- Fraud indicators present
- Policy exception required

## Priority Guidelines

| Situation | Priority |
|-----------|----------|
| Fraud suspected | urgent |
| Amount > $500 | urgent |
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
    print()

    uvicorn.run(app, host="0.0.0.0", port=NORTHBOUND_PORT)
