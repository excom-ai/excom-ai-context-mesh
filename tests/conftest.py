"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest

from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import (
    ContextMeshExtension,
    OpenAPIEndpoint,
    Playbook,
    PlaybookVariable,
)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_context_data() -> dict:
    """Sample context data for testing."""
    return {
        "db": {
            "customer": {
                "id": "CUST-123",
                "customer_id": "CUST-123",
                "name": "John Smith",
                "tenure_months": 24,
                "arpu": 85.50,
                "churn_risk": "high",
            },
            "invoice": {
                "number": "INV-456",
                "amount": 150.00,
                "disputed_amount": 75.00,
            },
        },
        "state": {
            "case_id": "CASE-789",
            "workflow_type": "billing_dispute",
        },
        "input": {
            "dispute_reason": "Incorrect charge",
            "requested_action": "credit",
        },
        "logic": {},
    }


@pytest.fixture
def runtime_context(sample_context_data: dict) -> RuntimeContext:
    """Create a RuntimeContext with sample data."""
    return RuntimeContext(sample_context_data)


@pytest.fixture
def sample_playbook() -> Playbook:
    """Create a sample playbook for testing."""
    return Playbook(
        module_name="test_billing_resolution",
        goal="Resolve billing disputes based on customer profile",
        preconditions=["Customer exists", "Invoice is valid"],
        steps=[
            "Check customer tenure and churn risk",
            "Calculate recommended credit amount",
            "Create billing adjustment",
        ],
        decision_rules=[
            "If churn_risk is high and amount < 200: full credit",
            "If tenure > 12 months: eligible for higher credits",
        ],
        variables=[
            PlaybookVariable(
                name="logic.recommended_credit_amount",
                description="The credit amount to apply",
            ),
            PlaybookVariable(
                name="logic.escalation_required",
                description="Whether manual review is needed",
            ),
        ],
        raw_markdown="# Test Playbook\n\nGoal: Resolve billing disputes",
    )


@pytest.fixture
def sample_endpoint() -> OpenAPIEndpoint:
    """Create a sample OpenAPI endpoint for testing."""
    return OpenAPIEndpoint(
        operation_id="createBillingAdjustment",
        path="/billing/adjustments",
        method="POST",
        summary="Create a billing adjustment",
        description="Creates a credit or debit adjustment",
        request_schema={
            "type": "object",
            "properties": {
                "customerId": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["customerId", "amount"],
        },
        response_schema={
            "type": "object",
            "properties": {
                "adjustmentId": {"type": "string"},
                "amount": {"type": "number"},
            },
        },
        contextmesh=ContextMeshExtension(
            logic_module="test_billing_resolution",
            description="Creates billing adjustments for disputes",
            template_params={
                "customerId": "{{db.customer.customer_id}}",
                "amount": "{{logic.recommended_credit_amount}}",
                "reason": "Dispute for invoice {{db.invoice.number}}",
            },
            state_updates={
                "onSuccess": [
                    {
                        "write": {
                            "table": "adjustment_log",
                            "values": {
                                "case_id": "{{state.case_id}}",
                                "adjustment_id": "{{response.adjustmentId}}",
                            },
                        }
                    }
                ]
            },
        ),
    )


@pytest.fixture
def sample_playbook_markdown() -> str:
    """Sample playbook markdown content."""
    return """# Logic Module: test_resolution

## Goal

Resolve customer issues based on their profile.

## Preconditions

- Customer exists in system
- Request is valid

## Steps

1. Check customer data
2. Apply business rules
3. If logic.escalation_required: create ticket
4. Otherwise: apply resolution
5. Send notification

## Decision Rules

- If churn_risk is high and amount < threshold: full resolution
- If tenure > 12 months: priority treatment
- Else: standard process

## Variables

- logic.recommended_amount: Amount to apply
- logic.escalation_required: Whether to escalate
- logic.resolution_type: Type of resolution
"""


@pytest.fixture
def sample_openapi_yaml() -> str:
    """Sample OpenAPI spec YAML content."""
    return """
openapi: 3.0.3
info:
  title: Test API
  version: 1.0.0

servers:
  - url: https://api.test.com/v1

paths:
  /items:
    post:
      summary: Create an item
      operationId: createItem
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                value:
                  type: number
              required:
                - name
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string

      x-contextMesh:
        logicModule: test_module
        description: Test endpoint
        templateParams:
          name: "{{input.item_name}}"
          value: "{{logic.calculated_value}}"
        stateUpdates:
          onSuccess:
            - write:
                table: items_log
                values:
                  item_id: "{{response.id}}"

  /items/{itemId}:
    get:
      summary: Get an item
      operationId: getItem
      parameters:
        - name: itemId
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string
"""
