#!/usr/bin/env python3
"""
Northbound API Server - LLM-friendly interface to banking APIs.

This server proxies requests to the southbound mock server and enriches
the OpenAPI documentation with context for LLM orchestration.

Run:
    poetry run python examples/banking/northbound_server.py

Requires the southbound mock server to be running on port 9200:
    cd ../excom-context-mesh-banking-mock-server
    poetry run mock-server
"""

from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configuration
SOUTHBOUND_URL = "http://localhost:9200"
NORTHBOUND_PORT = 8053

app = FastAPI(
    title="Banking API (Northbound)",
    description="""
## Overview

LLM-friendly interface for banking customer service operations. This API provides endpoints
for customer management, account inquiries, transaction disputes, and credit card applications.

**Important**: Always fetch actual data from API endpoints. Do not assume values.

---

## Workflow 1: Transaction Dispute Resolution

Use when a customer disputes an unauthorized or incorrect transaction.

### Steps

1. `GET /customers/{id}` - Fetch customer profile (tenure, churn_risk, relationship value)
2. `GET /customers/{id}/accounts` - Get customer's accounts
3. `GET /accounts/{accountNumber}/transactions` - Review transaction history
4. Evaluate eligibility using decision rules (see playbook)
5. If eligible for immediate credit: `POST /credits` - Apply provisional credit
6. Create dispute record: `POST /disputes`
7. Always: `POST /notifications` - Notify customer of outcome

### Key Fields to Check

- `tenure_months`: Longer tenure = more trust
- `churn_risk`: High risk = prioritize retention
- `credit_score`: Affects dispute handling
- Account `status`: Must be active

---

## Workflow 2: Credit Card Application

Use when a customer wants to apply for a credit card.

### Steps

1. `GET /customers/{id}` - Check customer profile and eligibility
2. `GET /credit-cards/products` - List available card products
3. Match customer profile to appropriate product tier
4. If eligible: `POST /customers/{id}/credit-cards/apply` - Submit application
5. Always: `POST /notifications` - Send confirmation

### Product Matching

- **Basic Card**: New customers, 6+ months tenure
- **Premium Card**: 12+ months tenure, good standing
- **Elite Card**: 24+ months tenure, high relationship value

---

## API Categories

- **Customers**: Customer profiles and context
- **Accounts**: Account details and balances
- **Transactions**: Transaction history
- **Disputes**: Transaction dispute handling
- **Credits**: Provisional credits and refunds
- **Credit Cards**: Card products and applications
- **Cases**: Support case tracking
- **Notifications**: Customer communications
""",
    version="1.0.0",
)


# =============================================================================
# Request/Response Models with Rich Descriptions
# =============================================================================

class CustomerResponse(BaseModel):
    """
    Customer profile with banking context.

    Use this data to make decisions about dispute resolution and product eligibility:
    - High churn_risk + long tenure = prioritize retention
    - High relationship_value = premium service eligibility
    - Credit score affects card product recommendations
    """

    account_id: str = Field(
        ...,
        description="Unique customer/account identifier (format: ACCT-XXX)",
        examples=["ACCT-001", "ACCT-002"],
    )
    name: str = Field(
        ...,
        description="Customer's full name for personalization",
        examples=["Sarah Williams", "Michael Chen"],
    )
    email: str = Field(
        ...,
        description="Customer's email address for notifications",
        examples=["sarah.williams@example.com"],
    )
    account_type: str = Field(
        ...,
        description="Type of primary account: checking, savings, or both",
        examples=["checking", "savings"],
    )
    tenure_months: int = Field(
        ...,
        description="How long the customer has been with us in months. "
                    "Longer tenure indicates loyalty - check playbook for thresholds. "
                    "6+ months = Basic card eligible, 12+ = Premium, 24+ = Elite",
        examples=[48, 12, 6],
        ge=0,
    )
    total_relationship_value: float = Field(
        ...,
        description="Total value of customer's relationship including deposits, loans, investments. "
                    "Higher value customers qualify for premium products and expedited dispute handling.",
        examples=[125000.0, 45000.0, 15000.0],
        ge=0,
    )
    churn_risk: Literal["low", "medium", "high"] = Field(
        ...,
        description="Predicted likelihood of customer leaving. "
                    "HIGH = likely to churn, prioritize retention with faster resolution. "
                    "MEDIUM = monitor closely. "
                    "LOW = stable customer.",
        examples=["low", "medium", "high"],
    )
    credit_score: int = Field(
        ...,
        description="Customer's credit score (300-850). "
                    "Affects credit card eligibility: 700+ = Premium eligible, 750+ = Elite eligible",
        examples=[780, 720, 650],
        ge=300,
        le=850,
    )
    monthly_income: float = Field(
        ...,
        description="Customer's declared monthly income. "
                    "Used for credit card limit determination.",
        examples=[8500.0, 5000.0, 3500.0],
        ge=0,
    )


class AccountResponse(BaseModel):
    """
    Bank account details.

    Use this to understand the customer's account status and balance
    before processing disputes or credits.
    """

    account_number: str = Field(
        ...,
        description="Unique account number",
        examples=["CHK-001-001", "SAV-001-001"],
    )
    customer_id: str = Field(
        ...,
        description="Customer ID who owns this account",
        examples=["ACCT-001"],
    )
    account_type: str = Field(
        ...,
        description="Type of account: checking or savings",
        examples=["checking", "savings"],
    )
    balance: float = Field(
        ...,
        description="Current account balance in dollars",
        examples=[5432.10, 15000.00],
    )
    available_balance: float = Field(
        ...,
        description="Available balance (may differ from balance due to pending transactions)",
        examples=[5200.00, 14800.00],
    )
    overdraft_limit: float = Field(
        default=0.0,
        description="Overdraft limit on the account",
        examples=[500.0, 0.0],
    )
    interest_rate: float = Field(
        default=0.0,
        description="Interest rate on the account (as percentage)",
        examples=[0.01, 4.25],
    )
    status: str = Field(
        ...,
        description="Account status: active, frozen, closed. "
                    "Only active accounts can receive credits or process disputes.",
        examples=["active", "frozen"],
    )


class TransactionResponse(BaseModel):
    """
    Individual transaction record.

    Review transactions to identify disputed charges.
    """

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier",
        examples=["TXN-001-001"],
    )
    account_number: str = Field(
        ...,
        description="Account number the transaction belongs to",
        examples=["ACCT-001-CHK"],
    )
    amount: float = Field(
        ...,
        description="Transaction amount (positive value, use transaction_type to determine direction)",
        examples=[45.99, 3.50, 500.00],
    )
    transaction_type: str = Field(
        ...,
        description="Transaction type: debit or credit",
        examples=["debit", "credit"],
    )
    description: str = Field(
        ...,
        description="Transaction description/merchant name",
        examples=["AMAZON.COM", "STARBUCKS #1234", "Direct Deposit - Payroll"],
    )
    balance_after: float = Field(
        ...,
        description="Account balance after this transaction",
        examples=[16566.88, 1234.50],
    )
    timestamp: str = Field(
        ...,
        description="Transaction timestamp (ISO 8601)",
        examples=["2024-12-01T10:30:00Z"],
    )
    status: str = Field(
        ...,
        description="Transaction status: completed, pending, disputed",
        examples=["completed", "pending"],
    )


class DisputeRequest(BaseModel):
    """
    Request to create a transaction dispute.

    Create disputes for unauthorized, duplicate, or fraudulent transactions.
    Check playbook for provisional credit eligibility rules.
    """

    account_number: str = Field(
        ...,
        description="Account number where the disputed transaction occurred",
        examples=["CHK-001-001"],
    )
    transaction_id: str = Field(
        ...,
        description="Transaction ID being disputed",
        examples=["TXN-001-001"],
    )
    dispute_type: Literal["unauthorized", "duplicate", "fraud", "service"] = Field(
        ...,
        description="Type of dispute: "
                    "'unauthorized' = customer didn't make the transaction, "
                    "'duplicate' = same charge appeared twice, "
                    "'fraud' = suspected fraudulent activity, "
                    "'service' = didn't receive goods/services",
        examples=["unauthorized", "fraud"],
    )
    amount: float = Field(
        ...,
        description="Amount being disputed in dollars",
        examples=[150.00, 45.99],
        gt=0,
    )
    description: str = Field(
        ...,
        description="Detailed description of the dispute. "
                    "Include: what happened, when noticed, any relevant context.",
        examples=[
            "Customer did not authorize this transaction. Card was in possession at all times.",
            "Duplicate charge for same purchase made on 12/1.",
        ],
        min_length=10,
    )


class DisputeResponse(BaseModel):
    """Response after creating a dispute."""

    dispute_id: str = Field(
        ...,
        description="Unique dispute identifier for tracking",
        examples=["DSP-001"],
    )
    account_number: str = Field(..., description="Account number")
    transaction_id: str = Field(..., description="Disputed transaction ID")
    dispute_type: str = Field(..., description="Type of dispute")
    amount: float = Field(..., description="Disputed amount")
    status: str = Field(
        ...,
        description="Dispute status: open, investigating, resolved, denied",
        examples=["open"],
    )
    provisional_credit: float = Field(
        ...,
        description="Amount of provisional credit applied (0 if none)",
        examples=[150.00, 0.0],
    )
    created_at: str = Field(
        ...,
        description="When dispute was created (ISO 8601)",
        examples=["2024-12-06T10:30:00Z"],
    )


class CreditRequest(BaseModel):
    """
    Request to apply a credit/refund to an account.

    Use for provisional credits during dispute investigation
    or goodwill credits for customer retention.
    """

    account_number: str = Field(
        ...,
        description="Account number to credit",
        examples=["CHK-001-001"],
    )
    amount: float = Field(
        ...,
        description="Credit amount in dollars. "
                    "Check playbook for auto-approval limits based on customer profile.",
        examples=[150.00, 50.00],
        gt=0,
    )
    reason: str = Field(
        ...,
        description="Reason for the credit. Include dispute ID if applicable.",
        examples=[
            "Provisional credit for dispute DSP-001",
            "Goodwill credit - service issue resolution",
        ],
        min_length=10,
    )
    credit_type: Literal["provisional", "refund", "goodwill", "correction"] = Field(
        ...,
        description="Type of credit: "
                    "'provisional' = pending dispute investigation, "
                    "'refund' = confirmed refund, "
                    "'goodwill' = customer retention, "
                    "'correction' = bank error correction",
        examples=["provisional", "goodwill"],
    )


class CreditResponse(BaseModel):
    """Response after applying a credit."""

    credit_id: str = Field(
        ...,
        description="Unique credit identifier",
        examples=["CRD-001"],
    )
    account_number: str = Field(..., description="Account credited")
    amount: float = Field(..., description="Credit amount applied")
    reason: str = Field(..., description="Reason for credit")
    credit_type: str = Field(..., description="Type of credit")
    status: str = Field(
        ...,
        description="Credit status: applied, pending, reversed",
        examples=["applied"],
    )
    created_at: str = Field(
        ...,
        description="When credit was applied (ISO 8601)",
        examples=["2024-12-06T10:30:00Z"],
    )


class CreditCardProductResponse(BaseModel):
    """
    Credit card product details.

    Use to match customers with appropriate card products based on their profile.
    """

    product_id: str = Field(
        ...,
        description="Unique product identifier",
        examples=["basic-rewards", "premium-travel", "elite-platinum"],
    )
    name: str = Field(
        ...,
        description="Product display name",
        examples=["Basic Rewards Card", "Premium Travel Card", "Elite Platinum Card"],
    )
    annual_fee: float = Field(
        ...,
        description="Annual fee in dollars. $0 for basic cards.",
        examples=[0, 95, 495],
        ge=0,
    )
    apr_range: str = Field(
        ...,
        description="APR range for the card",
        examples=["15.99% - 24.99%", "14.99% - 22.99%"],
    )
    rewards_rate: str = Field(
        ...,
        description="Rewards earning rate description",
        examples=["1% on all purchases", "2x on travel and dining"],
    )
    min_credit_score: int = Field(
        ...,
        description="Minimum credit score required. Check customer's credit_score against this.",
        examples=[650, 700, 750],
        ge=300,
        le=850,
    )
    credit_limit_range: str = Field(
        default="",
        description="Credit limit range for the card",
        examples=["$500 - $5,000", "$25,000 - $100,000"],
    )
    tier: int = Field(
        default=1,
        description="Card tier (1=basic, 2=premium, 3=elite)",
        examples=[1, 2, 3],
    )
    min_tenure_months: int = Field(
        default=0,
        description="Minimum banking tenure required in months. "
                    "Check customer's tenure_months against this.",
        examples=[6, 12, 24],
        ge=0,
    )
    benefits: list[str] = Field(
        default_factory=list,
        description="List of card benefits",
        examples=[["No annual fee", "1% cashback"], ["Airport lounge access", "Travel insurance"]],
    )


class CreditCardApplicationRequest(BaseModel):
    """
    Request to apply for a credit card.

    Prerequisites:
    - Customer profile fetched to verify eligibility
    - Product selected based on customer's credit score and tenure
    """

    product_id: str = Field(
        ...,
        description="Product ID to apply for. Must match customer eligibility.",
        examples=["basic-rewards", "premium-travel"],
    )
    requested_limit: float | None = Field(
        default=None,
        description="Optional requested credit limit. Bank may approve different amount.",
        examples=[5000, 10000],
    )


class CreditCardApplicationResponse(BaseModel):
    """Response after submitting credit card application."""

    application_id: str = Field(
        ...,
        description="Unique application identifier for tracking",
        examples=["APP-001"],
    )
    customer_id: str = Field(..., description="Customer who applied")
    product_id: str = Field(..., description="Product applied for")
    product_name: str = Field(..., description="Product display name")
    status: str = Field(
        ...,
        description="Application status: approved, pending_review, declined",
        examples=["approved", "pending_review"],
    )
    approved_limit: float | None = Field(
        None,
        description="Approved credit limit (if approved)",
        examples=[5000, 10000],
    )
    decision_reason: str = Field(
        ...,
        description="Explanation of the decision",
        examples=["Approved based on excellent credit history", "Pending additional verification"],
    )
    created_at: str = Field(
        ...,
        description="When application was submitted (ISO 8601)",
        examples=["2024-12-06T10:30:00Z"],
    )


class CaseRequest(BaseModel):
    """
    Request to create a customer service case.

    Create cases to track complex customer interactions that span multiple
    transactions or require follow-up.
    """

    customer_id: str = Field(
        ...,
        description="Customer ID for the case",
        examples=["ACCT-001"],
    )
    case_type: Literal["dispute", "inquiry", "complaint", "request"] = Field(
        ...,
        description="Type of case for routing",
        examples=["dispute", "inquiry"],
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        ...,
        description="Priority level. Use 'high' for high churn risk customers, "
                    "'urgent' for fraud or large amounts.",
        examples=["high", "medium"],
    )
    subject: str = Field(
        ...,
        description="Brief subject line for the case",
        examples=["Transaction dispute - unauthorized charge"],
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Detailed description of the case",
        min_length=20,
    )


class CaseResponse(BaseModel):
    """Response after creating a case."""

    case_id: str = Field(
        ...,
        description="Unique case identifier",
        examples=["CASE-001"],
    )
    customer_id: str = Field(..., description="Customer ID")
    case_type: str = Field(..., description="Case type")
    priority: str = Field(..., description="Priority level")
    subject: str = Field(..., description="Case subject")
    status: str = Field(
        ...,
        description="Case status: open, in_progress, resolved, closed",
        examples=["open"],
    )
    created_at: str = Field(
        ...,
        description="When case was created (ISO 8601)",
        examples=["2024-12-06T10:30:00Z"],
    )


class NotificationRequest(BaseModel):
    """
    Request to send a notification to a customer.

    Always notify customers after:
    - Creating a dispute
    - Applying a credit
    - Approving/declining a credit card application
    """

    customer_id: str = Field(
        ...,
        description="Customer ID to notify",
        examples=["ACCT-001"],
    )
    channel: Literal["email", "sms", "push"] = Field(
        default="email",
        description="Notification channel. Email is default and most reliable.",
        examples=["email", "sms"],
    )
    template_id: str = Field(
        ...,
        description="Notification template to use. Available templates: "
                    "'dispute_created' - confirms dispute filed, "
                    "'credit_applied' - confirms credit applied, "
                    "'application_status' - card application update, "
                    "'case_update' - case status update",
        examples=["dispute_created", "credit_applied", "application_status"],
    )
    template_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic data to populate the template",
        examples=[{"amount": 150.00, "dispute_id": "DSP-001"}],
    )


class NotificationResponse(BaseModel):
    """Response after sending a notification."""

    notification_id: str = Field(
        ...,
        description="Unique notification identifier",
        examples=["NOT-001"],
    )
    customer_id: str = Field(..., description="Customer notified")
    channel: str = Field(..., description="Channel used")
    template_id: str = Field(..., description="Template used")
    status: str = Field(
        ...,
        description="Delivery status: sent, pending, failed",
        examples=["sent"],
    )
    sent_at: str = Field(
        ...,
        description="When notification was sent (ISO 8601)",
        examples=["2024-12-06T10:30:00Z"],
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
        service="Banking API (Northbound)",
        southbound_status=southbound_status,
        version="1.0.0",
    )


# =============================================================================
# Customer Endpoints
# =============================================================================

@app.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    tags=["Customers"],
    summary="Get customer profile and relationship context",
    description="""
Retrieve complete customer profile including relationship value for decision-making.

## Key Response Fields

- `churn_risk`: Customer's likelihood to leave ("low", "medium", "high")
- `tenure_months`: How long they've been a customer (affects product eligibility)
- `total_relationship_value`: Total deposits, loans, investments (premium service eligibility)
- `credit_score`: Affects credit card product recommendations

## Decision Factors

Use these fields to evaluate eligibility:

- **tenure_months**: 6+ = Basic card, 12+ = Premium, 24+ = Elite
- **credit_score**: 650+ = Basic, 700+ = Premium, 750+ = Elite
- **churn_risk**: High risk = prioritize fast resolution
- **total_relationship_value**: Higher value = premium handling

## Workflow

1. Fetch this endpoint to get customer context
2. Use tenure and credit_score to match products
3. Use churn_risk to determine handling priority
""",
)
def get_customer(customer_id: str):
    """Get customer details with relationship context."""
    return proxy_get(f"/customers/{customer_id}")


@app.get(
    "/customers/{customer_id}/accounts",
    response_model=list[AccountResponse],
    tags=["Accounts"],
    summary="Get all accounts for a customer",
    description="""
List all bank accounts belonging to a customer.

## Response Fields

- `account_number`: Unique identifier for the account
- `account_type`: checking or savings
- `balance`: Current balance
- `available_balance`: Available funds (may differ due to pending transactions)
- `status`: Account status (only 'active' accounts can receive credits)

## Usage

1. Fetch customer's accounts to find the relevant account
2. Use account_number when creating disputes or credits
3. Check status before applying credits
""",
)
def get_customer_accounts(customer_id: str):
    """Get all accounts for a customer."""
    return proxy_get(f"/customers/{customer_id}/accounts")


# =============================================================================
# Account Endpoints
# =============================================================================

@app.get(
    "/accounts/{account_number}",
    response_model=AccountResponse,
    tags=["Accounts"],
    summary="Get account details",
    description="""
Get detailed information about a specific bank account.

Use this to verify account status and balance before processing transactions.
""",
)
def get_account(account_number: str):
    """Get account details by account number."""
    return proxy_get(f"/accounts/{account_number}")


@app.get(
    "/accounts/{account_number}/transactions",
    response_model=list[TransactionResponse],
    tags=["Transactions"],
    operation_id="get_account_transactions",
    summary="Get recent transactions for an account",
    description="""
Retrieve recent transactions for a bank account.

## Response Fields

- `transaction_id`: Unique ID (use when creating disputes)
- `amount`: Transaction amount (negative = debit, positive = credit)
- `status`: posted, pending, or disputed
- `category`: Transaction category

## Usage

1. Review transactions to identify disputed charges
2. Use transaction_id and amount when creating disputes
3. Note the date and merchant for dispute documentation
""",
)
def get_account_transactions(account_number: str):
    """Get recent transactions for an account."""
    return proxy_get(f"/accounts/{account_number}/transactions")


# =============================================================================
# Dispute Endpoints
# =============================================================================

@app.post(
    "/disputes",
    response_model=DisputeResponse,
    tags=["Disputes"],
    summary="Create a transaction dispute",
    description="""
Create a dispute for an unauthorized or incorrect transaction.

## Prerequisites

Before calling this endpoint:
1. Fetch customer via `GET /customers/{id}` to assess eligibility
2. Get account via `GET /customers/{id}/accounts`
3. Review transactions via `GET /accounts/{number}/transactions`
4. Load the transaction_dispute playbook for decision rules

## Dispute Types

| Type | Description | Provisional Credit |
|------|-------------|-------------------|
| unauthorized | Customer didn't make transaction | Usually yes |
| duplicate | Same charge appeared twice | Yes if confirmed |
| fraud | Suspected fraudulent activity | Yes for <$500 |
| service | Didn't receive goods/services | Case by case |

## Decision Rules (see playbook for details)

- **Immediate Credit**: tenure > 6 months, no fraud claims in 12 months, amount ≤ $500
- **Provisional (10 days)**: amount > $500 or previous disputes
- **Escalation**: amount > $2,500, third dispute in 90 days

## After Creating Dispute

Send notification using `POST /notifications` with:
- `template_id`: "dispute_created"
- `template_data`: Include dispute_id and amount
""",
)
def create_dispute(request: DisputeRequest):
    """Create a transaction dispute."""
    # Map northbound field names to mock server field names
    payload = {
        "account_id": request.account_number,
        "transaction_id": request.transaction_id,
        "dispute_type": request.dispute_type,
        "amount": request.amount,
        "reason": request.description,
    }
    response = proxy_post("/disputes", payload)
    # Map response back to northbound field names
    if isinstance(response, dict):
        response["account_number"] = response.pop("account_id", request.account_number)
        response["description"] = response.pop("reason", request.description)
    return response


@app.get(
    "/disputes/{dispute_id}",
    response_model=DisputeResponse,
    tags=["Disputes"],
    summary="Get dispute details",
    description="""
Get the current status and details of a dispute.

Use this to check if provisional credit was applied and track resolution progress.
""",
)
def get_dispute(dispute_id: str):
    """Get dispute details."""
    return proxy_get(f"/disputes/{dispute_id}")


# =============================================================================
# Credit Endpoints
# =============================================================================

@app.post(
    "/credits",
    response_model=CreditResponse,
    tags=["Credits"],
    summary="Apply a credit or refund to an account",
    description="""
Apply a credit (provisional, refund, goodwill, or correction) to a customer's account.

## Prerequisites

1. Fetch customer profile to determine eligibility
2. Load playbook for credit limits and approval rules
3. Have a valid reason documented

## Credit Types

| Type | When to Use |
|------|-------------|
| provisional | During dispute investigation |
| refund | Confirmed merchant refund |
| goodwill | Customer retention |
| correction | Bank error correction |

## Auto-Approval Limits (see playbook)

- Standard customers: Up to $100
- High-value customers (>$50K relationship): Up to $500
- Escalation required for larger amounts

## After Applying Credit

Send notification using `POST /notifications` with:
- `template_id`: "credit_applied"
- `template_data`: Include amount and reason
""",
)
def create_credit(request: CreditRequest):
    """Apply a credit to an account."""
    # Map northbound field names to mock server field names
    payload = {
        "account_id": request.account_number,
        "amount": request.amount,
        "reason": request.reason,
    }
    response = proxy_post("/credits", payload)
    # Map response back to northbound field names
    if isinstance(response, dict):
        response["account_number"] = response.pop("account_id", request.account_number)
        response["credit_id"] = response.pop("refund_id", response.get("credit_id", ""))
        response["credit_type"] = request.credit_type
    return response


# =============================================================================
# Credit Card Endpoints
# =============================================================================

@app.get(
    "/credit-cards/products",
    response_model=list[CreditCardProductResponse],
    tags=["Credit Cards"],
    summary="List available credit card products",
    description="""
Fetch all available credit card products to recommend to customers.

## Response Fields

- `product_id`: Unique identifier for the product
- `min_credit_score`: Minimum score required
- `min_tenure_months`: Minimum banking tenure required
- `annual_fee`: Annual fee ($0 for basic)
- `benefits`: List of card benefits

## Product Matching (see playbook)

| Product | Tenure | Credit Score | Annual Fee |
|---------|--------|--------------|------------|
| Basic Rewards | 6+ months | 650+ | $0 |
| Premium Travel | 12+ months | 700+ | $95 |
| Elite Platinum | 24+ months | 750+ | $495 |

## Usage

1. Fetch customer profile to get tenure and credit score
2. Filter products where customer meets min_tenure and min_credit_score
3. Present eligible products to customer
4. Process application via `POST /customers/{id}/credit-cards/apply`
""",
)
def list_credit_card_products():
    """List available credit card products."""
    return proxy_get("/credit-cards/products")


@app.get(
    "/credit-cards/products/{product_id}",
    response_model=CreditCardProductResponse,
    tags=["Credit Cards"],
    summary="Get credit card product details",
    description="""
Get detailed information about a specific credit card product.

Use this to explain product benefits to customers before application.
""",
)
def get_credit_card_product(product_id: str):
    """Get credit card product details."""
    return proxy_get(f"/credit-cards/products/{product_id}")


@app.post(
    "/customers/{customer_id}/credit-cards/apply",
    response_model=CreditCardApplicationResponse,
    tags=["Credit Cards"],
    operation_id="apply_for_credit_card",
    summary="Apply for a credit card",
    description="""
Submit a credit card application for a customer.

## Prerequisites

1. Fetch customer profile via `GET /customers/{id}`
2. Verify customer meets product requirements:
   - `tenure_months` >= product's `min_tenure_months`
   - `credit_score` >= product's `min_credit_score`
3. Fetch product details via `GET /credit-cards/products/{id}`

## Decision Outcomes

| Status | Meaning |
|--------|---------|
| approved | Instant approval, card will be mailed |
| pending_review | Needs manual review (borderline eligibility) |
| declined | Does not meet requirements |

## After Application

Send notification using `POST /notifications` with:
- `template_id`: "application_status"
- `template_data`: Include status, product_name, approved_limit (if applicable)
""",
)
def apply_for_credit_card(customer_id: str, request: CreditCardApplicationRequest):
    """Submit a credit card application."""
    return proxy_post(f"/customers/{customer_id}/credit-cards/apply", request.model_dump())


# =============================================================================
# Case Endpoints
# =============================================================================

@app.post(
    "/cases",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Create a customer service case",
    description="""
Create a case to track complex customer interactions.

## When to Create Cases

- Disputes that require escalation
- Complex inquiries spanning multiple interactions
- Complaints requiring follow-up
- Special requests needing approval

## Priority Guidelines

| Situation | Priority |
|-----------|----------|
| Fraud suspected | urgent |
| Large amount (>$2,500) | urgent |
| High churn risk | high |
| Standard issue | medium |
| Information request | low |
""",
)
def create_case(request: CaseRequest):
    """Create a customer service case."""
    return proxy_post("/cases", request.model_dump())


# =============================================================================
# Notification Endpoints
# =============================================================================

@app.post(
    "/notifications",
    response_model=NotificationResponse,
    tags=["Notifications"],
    summary="Send notification to customer",
    description="""
Send a notification to inform the customer about their request status.

## Available Templates

| Template ID | When to Use |
|-------------|-------------|
| `dispute_created` | After filing a dispute |
| `credit_applied` | After applying a credit |
| `application_status` | After credit card decision |
| `case_update` | Case status changes |

## Template Data

Include relevant context in `template_data`:
- `amount`: Credit or disputed amount
- `dispute_id`: Dispute reference number
- `case_id`: Case reference number
- `status`: Current status
- `product_name`: For card applications
""",
)
def send_notification(request: NotificationRequest):
    """Send a notification to a customer."""
    return proxy_post("/notifications", request.model_dump())


# =============================================================================
# Debug Endpoints
# =============================================================================

@app.get("/debug/customers", tags=["Debug"], summary="List all customers")
def list_customers():
    """List all customers for debugging."""
    return proxy_get("/debug/customers")


@app.get("/debug/accounts", tags=["Debug"], summary="List all accounts")
def list_accounts():
    """List all accounts for debugging."""
    return proxy_get("/debug/accounts")


@app.get("/debug/disputes", tags=["Debug"], summary="List all disputes")
def list_disputes():
    """List all disputes for debugging."""
    return proxy_get("/debug/disputes")


@app.get("/debug/cases", tags=["Debug"], summary="List all cases")
def list_cases():
    """List all cases for debugging."""
    return proxy_get("/debug/cases")


@app.post("/debug/reset", tags=["Debug"], summary="Reset transaction data")
def reset_data():
    """Reset transaction data (keeps customers)."""
    return proxy_post("/debug/reset", {})


@app.post("/debug/reset-all", tags=["Debug"], summary="Reset everything")
def reset_all():
    """Reset everything to defaults."""
    return proxy_post("/debug/reset-all", {})


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" Banking API (Northbound - LLM Context Enriched)")
    print("=" * 60)
    print(f"\n  Northbound: http://localhost:{NORTHBOUND_PORT}")
    print(f"  Southbound: {SOUTHBOUND_URL}")
    print(f"\n  OpenAPI docs: http://localhost:{NORTHBOUND_PORT}/docs")
    print(f"  OpenAPI JSON: http://localhost:{NORTHBOUND_PORT}/openapi.json")
    print("\nCustomers & Accounts:")
    print("  GET  /customers/{id}                - Get customer profile")
    print("  GET  /customers/{id}/accounts       - List customer accounts")
    print("  GET  /accounts/{number}             - Get account details")
    print("  GET  /accounts/{number}/transactions - Get transactions")
    print("\nDisputes & Credits:")
    print("  POST /disputes                      - Create dispute")
    print("  GET  /disputes/{id}                 - Get dispute status")
    print("  POST /credits                       - Apply credit")
    print("\nCredit Cards:")
    print("  GET  /credit-cards/products         - List products")
    print("  GET  /credit-cards/products/{id}    - Get product details")
    print("  POST /customers/{id}/credit-cards/apply - Apply for card")
    print("\nCases & Notifications:")
    print("  POST /cases                         - Create case")
    print("  POST /notifications                 - Send notification")
    print()

    uvicorn.run(app, host="0.0.0.0", port=NORTHBOUND_PORT)
