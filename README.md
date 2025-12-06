# ContextMesh

LLM-driven orchestration engine using OpenAPI extensions and Markdown playbooks.

## Overview

ContextMesh is an orchestration engine that uses an extended OpenAPI specification to connect:

- Live context from databases and systems
- Human-readable business logic (Markdown playbooks)
- Executable API operations

The key idea: we do not build a separate orchestration config language. Instead, we extend OpenAPI so that the same spec that describes your APIs also describes how ContextMesh should use them.

## Installation

```bash
pip install contextmesh
```

Or for development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from contextmesh import ContextMeshOrchestrator, ContextMeshConfig

# Configure the orchestrator
config = ContextMeshConfig(
    anthropic_api_key="sk-ant-...",
    openapi_specs_dir="./specs",
    playbooks_dir="./playbooks",
)

# Create orchestrator
orchestrator = ContextMeshOrchestrator(config)

# Execute a workflow
result = orchestrator.execute_workflow(
    trigger="billing_dispute_resolution",
    initial_context={
        "db": {
            "customer": {"id": "CUST-123", "churn_risk": "high"},
            "invoice": {"number": "INV-456", "amount": 150.00},
        },
        "input": {"dispute_reason": "Incorrect charge"},
    }
)

if result.success:
    print(f"Workflow completed! Logic values: {result.plan.logic_values}")
else:
    print(f"Workflow failed: {result.errors}")
```

## Key Concepts

### OpenAPI Extensions (`x-contextMesh`)

Add orchestration metadata to your OpenAPI specs:

```yaml
paths:
  /billing/adjustments:
    post:
      operationId: createBillingAdjustment
      x-contextMesh:
        logicModule: billing_resolution
        templateParams:
          customerId: "{{db.customer.id}}"
          amount: "{{logic.recommended_credit_amount}}"
        stateUpdates:
          onSuccess:
            - write:
                table: adjustment_log
                values:
                  adjustment_id: "{{response.adjustmentId}}"
```

### Markdown Playbooks

Define business logic in human-readable Markdown:

```markdown
# Logic Module: billing_resolution

## Goal
Resolve billing disputes based on customer profile.

## Steps
1. Check customer tenure and churn risk
2. If churn_risk is high and amount < 200: approve full credit
3. Otherwise: escalate to manual review

## Variables
- logic.recommended_credit_amount
- logic.escalation_required
```

### Runtime Context

Access data through namespaced paths:

- `db.*` - Database/system data
- `state.*` - Workflow state
- `input.*` - User/trigger input
- `logic.*` - LLM-computed values
- `response.*` - API response data

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=contextmesh --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run integration tests (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... pytest tests/integration/
```

## Project Structure

```
contextmesh/
├── src/contextmesh/
│   ├── core/           # Context, models, orchestrator
│   ├── parsers/        # OpenAPI and playbook parsing
│   ├── templating/     # Template resolution engine
│   ├── chains/         # LangChain integration
│   ├── tools/          # OpenAPI to LangChain tools
│   ├── execution/      # API executor, state management
│   └── utils/          # Exceptions, utilities
├── examples/           # Example workflows
└── tests/              # Unit and integration tests
```

## License

MIT
