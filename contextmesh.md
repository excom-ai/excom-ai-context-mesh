# ContextMesh  
LLM-Driven Orchestration Layer Using OpenAPI Extensions

## Overview  
ContextMesh is an orchestration engine that uses an extended OpenAPI specification to connect:

- live context from databases and systems  
- human-readable business logic (Markdown playbooks)  
- executable API operations

The key idea: we do not build a separate orchestration config language. Instead, we extend OpenAPI so that the same spec that describes your APIs also describes how ContextMesh should use them.

---

# 1. Core Concept

ContextMesh uses OpenAPI as the backbone and adds custom extensions to describe:

1. How to map runtime context (database, state, user input) into API parameters.  
2. Which business logic playbook the LLM should read to decide what to do.  
3. How API calls participate in end-to-end workflows across systems.

This is implemented using OpenAPI extension fields (for example `x-contextMesh`).

---

# 2. OpenAPI Extension Design

## 2.1 Extension Goals

The OpenAPI extensions should:

- Keep the base OpenAPI spec valid and standard-compliant.  
- Add metadata for ContextMesh to:
  - perform dynamic parameter templating  
  - locate the right business logic module  
  - understand the role of each endpoint in a workflow  
- Avoid embedding complex business rules into the API spec itself.

APIs remain clean and reusable; orchestration intelligence lives in ContextMesh.

---

## 2.2 Example OpenAPI Extensions

```yaml
paths:
  /billing/adjustments:
    post:
      summary: Create a billing adjustment
      operationId: createBillingAdjustment
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BillingAdjustmentRequest'
      responses:
        '200':
          description: Adjustment created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BillingAdjustmentResponse'

      x-contextMesh:
        logicModule: telco_billing_resolution
        description: >
          Used by ContextMesh as part of billing dispute resolution workflows.
        templateParams:
          customerId: "{{db.customer.customer_id}}"
          invoiceNumber: "{{db.invoice.number}}"
          amount: "{{logic.recommended_credit_amount}}"
          reason: "Dispute for invoice {{db.invoice.number}} (case {{state.case_id}})"
        stateUpdates:
          onSuccess:
            - write:
                table: billing_adjustment_log
                values:
                  case_id: "{{state.case_id}}"
                  adjustment_id: "{{response.adjustmentId}}"
                  amount: "{{response.amount}}"
                  status: "APPLIED"
```

### Notes

- **logicModule**  
  Points to the Markdown playbook.

- **templateParams**  
  Defines how to build request parameters from runtime context.

- **stateUpdates**  
  Optional instructions for writing back into system state.

---

## 2.3 Separation Of Concerns

- **OpenAPI base fields**  
  - Path, schema, operations  
  - Standard and tool-compatible  

- **`x-contextMesh` metadata**  
  - Templating  
  - Logic module selection  
  - Workflow hints  

- **Markdown playbooks**  
  - Policies  
  - Decision trees  
  - Workflow intent  

This keeps the architecture clean and scalable.

---

# 3. Feature Architecture

## 3.1 LLM Orchestration Engine

The engine:

- Reads relevant OpenAPI specs (including `x-contextMesh`).  
- Loads the business logic Markdown module.  
- Plans the workflow:
  - which endpoints to call  
  - in what order  
- Maps context → parameters using templating.  
- Executes API calls through an OpenAPI tool client.

---

## 3.2 Dynamic Parameter Templating

Parameters are defined as templates inside `x-contextMesh.templateParams`.

Supported template sources:

- `db.*` — database fields  
- `state.*` — orchestration context  
- `input.*` — user/event payload  
- `logic.*` — values computed by the LLM using playbook rules

Example:

```yaml
x-contextMesh:
  templateParams:
    customerId: "{{db.customer.id}}"
    planCode: "{{db.subscription.plan_code}}"
    discountPercentage: "{{logic.discount_percentage}}"
    note: "Campaign {{state.campaign_id}} applied to customer {{db.customer.id}}"
```

---

## 3.3 Centralized Business Logic (Markdown Playbooks)

Each `logicModule` points to a Markdown file describing:

- Goals  
- Preconditions  
- Steps  
- Decision rules  
- Edge cases  
- Variables the LLM may compute

Example:

```markdown
# Logic Module: telco_billing_resolution

Goal: Resolve customer billing disputes within defined credit limits.

Steps:
1. Check tenure, ARPU, churn risk.
2. Validate dispute and invoice.
3. If risk high and amount < threshold_X:
   - logic.recommended_credit_amount = invoice_amount
4. If amount < threshold_Y:
   - partial credit based on tenure
5. Else:
   - escalate to ticketing

Variables:
- logic.recommended_credit_amount
- logic.escalation_required
```

---

## 3.4 Context Management & Retrieval (RAG)

Because OpenAPI + playbooks may exceed context window:

- Docs and specs are modular.  
- A retrieval layer returns only what’s needed.  

Runtime steps:

1. Identify domain and task.  
2. Retrieve relevant OpenAPI fragment(s).  
3. Retrieve relevant logic module(s).  
4. Load them into LLM context.  

Scales to hundreds of workflows and thousands of API definitions.

---

# 4. End-to-End Workflow

1. **Trigger**  
   Workflow starts (e.g., dispute, campaign, approval).

2. **Context Loading**  
   System retrieves all required state:
   - Customer, invoice, product, ARPU  
   - Campaign data  
   - Churn risk, usage  

3. **Logic and API Retrieval**  
   - Load playbook via `logicModule`  
   - Load matching OpenAPI endpoints  

4. **Planning**  
   - LLM reads logic + OpenAPI  
   - Plans actions and sequences  

5. **Templating & Execution**  
   - Replace all template parameters  
   - Send requests using OpenAPI client  
   - Handle responses, follow-up actions  

6. **State Update**  
   - Write logs / updates as defined by `stateUpdates`  

---

# 5. Example Telco Scenarios

## 5.1 Billing Dispute Resolution

Endpoints involved:

- `/billing/adjustments`  
- `/crm/customers/{id}`  
- `/notifications/send`

ContextMesh:

- Loads customer + billing data  
- Reads playbook  
- Calls CRM, billing, notifications  
- Resolves issue in one unified flow

**Value:**  
Cross-system action, not just analysis.

---

## 5.2 Commercial–Finance Alignment

Endpoints involved:

- `/offers/create`  
- `/finance/forecast`  
- `/catalog/publish`

Flow:

- Load catalog + financial context  
- Follow playbook rules for margin checks  
- Update offers + catalog when approved  

**Value:**  
Commercial + finance aligned automatically.

---

# 6. Benefits

- OpenAPI remains the single source of truth  
- Extensions add orchestration metadata cleanly  
- Business logic stays in Markdown, readable to humans  
- Horizontal workflows across CRM, billing, finance, ERP  
- LLM executes—not just advises—by calling real APIs  
- Scales across unlimited workflows with RAG  

---
