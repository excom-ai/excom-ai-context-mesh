#!/usr/bin/env python3
"""FastAPI mock backend for Telco Billing API."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Telco Billing API (Mock)", version="1.0.0")

# In-memory storage
adjustments_db: dict[str, dict] = {}
notifications_db: dict[str, dict] = {}
tickets_db: dict[str, dict] = {}
disputes_history: dict[str, list] = {}  # customer_id -> list of past disputes

customers_db: dict[str, dict] = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "Alice Johnson",
        "email": "alice.johnson@example.com",
        "tenure_months": 36,
        "arpu": 120.00,
        "churn_risk": "high",
        "outstanding_balance": 50.00,
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Bob Smith",
        "email": "bob.smith@example.com",
        "tenure_months": 6,
        "arpu": 45.00,
        "churn_risk": "low",
        "outstanding_balance": 200.00,
    },
}


# Request/Response Models
class BillingAdjustmentRequest(BaseModel):
    customerId: str
    invoiceNumber: str
    amount: float
    reason: str
    adjustmentType: str = "credit"


class BillingAdjustmentResponse(BaseModel):
    adjustmentId: str
    customerId: str
    invoiceNumber: str
    amount: float
    reason: str
    adjustmentType: str
    status: str
    createdAt: str


class NotificationRequest(BaseModel):
    customerId: str
    channel: str = "email"
    templateId: str
    templateData: dict[str, Any] = {}


class NotificationResponse(BaseModel):
    notificationId: str
    customerId: str
    channel: str
    templateId: str
    status: str
    sentAt: str


class EscalationTicketRequest(BaseModel):
    customerId: str
    category: str
    priority: str
    subject: str
    description: str
    metadata: dict[str, Any] = {}


class EscalationTicketResponse(BaseModel):
    ticketId: str
    customerId: str
    category: str
    priority: str
    subject: str
    status: str
    createdAt: str


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    email: str
    tenure_months: int
    arpu: float
    churn_risk: str
    outstanding_balance: float
    total_credits_last_30_days: float = 0.0
    disputes_last_30_days: int = 0


# Endpoints
@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "Telco Billing API (Mock)"}


@app.get("/crm/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str):
    """Get customer details with dispute history."""
    print(f"\n📥 GET /crm/customers/{customer_id}")

    # Auto-create customer if not found (for demo purposes)
    if customer_id not in customers_db:
        print(f"   ⚠️  Customer not found, creating placeholder...")
        customers_db[customer_id] = {
            "customer_id": customer_id,
            "name": f"Customer {customer_id}",
            "email": f"{customer_id.lower()}@example.com",
            "tenure_months": 12,
            "arpu": 50.00,
            "churn_risk": "medium",
            "outstanding_balance": 0.00,
        }

    customer = customers_db[customer_id].copy()

    # Calculate credits and disputes in last 30 days
    history = disputes_history.get(customer_id, [])
    total_credits = sum(d.get("amount", 0) for d in history)
    dispute_count = len(history)

    customer["total_credits_last_30_days"] = total_credits
    customer["disputes_last_30_days"] = dispute_count

    print(f"   ✅ Found customer: {customer['name']}")
    print(f"   📊 Credits last 30 days: ${total_credits} ({dispute_count} disputes)")
    return customer


@app.post("/billing/adjustments", response_model=BillingAdjustmentResponse)
def create_billing_adjustment(request: BillingAdjustmentRequest):
    """Create a billing adjustment (credit/debit)."""
    print(f"\n📥 POST /billing/adjustments")
    print(f"   Customer: {request.customerId}")
    print(f"   Invoice: {request.invoiceNumber}")
    print(f"   Amount: ${request.amount}")
    print(f"   Type: {request.adjustmentType}")
    print(f"   Reason: {request.reason[:50]}...")

    adjustment_id = f"ADJ-{uuid.uuid4().hex[:8].upper()}"

    adjustment = {
        "adjustmentId": adjustment_id,
        "customerId": request.customerId,
        "invoiceNumber": request.invoiceNumber,
        "amount": request.amount,
        "reason": request.reason,
        "adjustmentType": request.adjustmentType,
        "status": "applied",
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    adjustments_db[adjustment_id] = adjustment

    # Track in dispute history
    if request.customerId not in disputes_history:
        disputes_history[request.customerId] = []
    disputes_history[request.customerId].append({
        "adjustment_id": adjustment_id,
        "amount": request.amount,
        "invoice": request.invoiceNumber,
        "created_at": adjustment["createdAt"],
    })

    # Show accumulated total
    total = sum(d["amount"] for d in disputes_history[request.customerId])
    print(f"   ✅ Created adjustment: {adjustment_id}")
    print(f"   📊 Customer total credits: ${total} ({len(disputes_history[request.customerId])} disputes)")

    return adjustment


@app.post("/notifications/send", response_model=NotificationResponse)
def send_notification(request: NotificationRequest):
    """Send a notification to a customer."""
    print(f"\n📥 POST /notifications/send")
    print(f"   Customer: {request.customerId}")
    print(f"   Channel: {request.channel}")
    print(f"   Template: {request.templateId}")
    print(f"   Data: {request.templateData}")

    notification_id = f"NOT-{uuid.uuid4().hex[:8].upper()}"

    notification = {
        "notificationId": notification_id,
        "customerId": request.customerId,
        "channel": request.channel,
        "templateId": request.templateId,
        "status": "sent",
        "sentAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    notifications_db[notification_id] = notification
    print(f"   ✅ Sent notification: {notification_id}")

    return notification


@app.post("/tickets/create", response_model=EscalationTicketResponse)
def create_escalation_ticket(request: EscalationTicketRequest):
    """Create an escalation ticket."""
    print(f"\n📥 POST /tickets/create")
    print(f"   Customer: {request.customerId}")
    print(f"   Category: {request.category}")
    print(f"   Priority: {request.priority}")
    print(f"   Subject: {request.subject}")

    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

    ticket = {
        "ticketId": ticket_id,
        "customerId": request.customerId,
        "category": request.category,
        "priority": request.priority,
        "subject": request.subject,
        "status": "open",
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    tickets_db[ticket_id] = ticket
    print(f"   ✅ Created ticket: {ticket_id}")

    return ticket


# Debug endpoints
@app.get("/debug/adjustments")
def list_adjustments():
    """List all adjustments (debug)."""
    return {"adjustments": list(adjustments_db.values())}


@app.get("/debug/notifications")
def list_notifications():
    """List all notifications (debug)."""
    return {"notifications": list(notifications_db.values())}


@app.get("/debug/tickets")
def list_tickets():
    """List all tickets (debug)."""
    return {"tickets": list(tickets_db.values())}


@app.get("/debug/history")
def list_dispute_history():
    """List dispute history by customer (debug)."""
    summary = {}
    for customer_id, disputes in disputes_history.items():
        total = sum(d["amount"] for d in disputes)
        summary[customer_id] = {
            "total_credits": total,
            "dispute_count": len(disputes),
            "disputes": disputes,
        }
    return {"history": summary}


@app.post("/debug/reset")
def reset_all():
    """Reset all data (debug)."""
    adjustments_db.clear()
    notifications_db.clear()
    tickets_db.clear()
    disputes_history.clear()
    return {"status": "reset", "message": "All data cleared"}


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" Telco Billing API - Mock Server")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /crm/customers/{customerId}")
    print("  POST /billing/adjustments")
    print("  POST /notifications/send")
    print("  POST /tickets/create")
    print("\nDebug:")
    print("  GET  /debug/adjustments")
    print("  GET  /debug/notifications")
    print("  GET  /debug/tickets")
    print()

    uvicorn.run(app, host="0.0.0.0", port=9100)
