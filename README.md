# ContextMesh

**AI-powered business process automation using natural language playbooks.**

ContextMesh connects your business rules to your systems through conversational AI. Define what you want in plain English, and let AI handle the execution.

## What is ContextMesh?

ContextMesh is a framework for building AI assistants that follow your business rules. Instead of hardcoding logic, you write **playbooks** - simple documents that describe how to handle different scenarios. The AI reads these playbooks and takes action by calling your APIs.

### The Problem

Traditional automation requires developers to translate business rules into code:

1. Business writes rules in documents
2. Developers interpret and implement
3. Changes require code updates and deployments
4. Business logic gets buried in code

### The Solution

With ContextMesh, business rules stay in plain language:

1. Business writes playbooks in markdown
2. AI reads playbooks and follows instructions
3. Changes are instant - just update the document
4. Business logic remains readable and auditable

## Capabilities

### Define Business Rules in Plain English

Write playbooks that describe how to handle customer requests:

```markdown
## Billing Dispute Resolution

### Decision Rules

- High churn risk customers get priority treatment
- Long-tenure customers (>12 months) are eligible for higher credits
- Disputes over $200 require escalation to a manager

### Steps

1. Check customer tenure and payment history
2. Validate the dispute amount against the invoice
3. Apply credit based on eligibility rules
4. Send confirmation to customer
```

The AI interprets these rules and makes decisions accordingly.

### Connect to Any System via APIs

ContextMesh generates tools from your OpenAPI specifications automatically. Add a new API endpoint, and it's immediately available to the AI.

Supported operations:

- Customer lookups
- Invoice retrieval
- Billing adjustments
- Case creation
- Notifications
- Any REST API you expose

### Maintain Confidentiality

Define what information should never be shared with customers:

- Internal risk scores
- Revenue metrics (ARPU)
- Decision thresholds
- System identifiers

The AI uses this data for decisions but presents customer-friendly explanations.

### Handle Complex Workflows

Multi-step processes that traditionally require complex state machines become simple playbooks:

| Scenario           | Traditional Approach                  | ContextMesh Approach   |
| ------------------ | ------------------------------------- | ---------------------- |
| Billing dispute    | State machine + business rules engine | Markdown playbook      |
| Plan upgrade       | Hardcoded eligibility logic           | Natural language rules |
| Customer retention | Decision trees in code                | Documented guidelines  |

## Use Cases

### Customer Service Automation

- **Billing disputes**: Automated credit decisions based on customer profile
- **Plan changes**: Eligibility checks with loyalty discounts
- **Account inquiries**: Self-service with escalation paths

### Operations Support

- **Incident triage**: Route issues based on severity rules
- **Approval workflows**: Automated decisions within defined limits
- **Compliance checks**: Policy enforcement at point of action

### Sales Enablement

- **Pricing decisions**: Discount eligibility based on customer value
- **Renewal handling**: Retention offers for at-risk accounts
- **Upsell recommendations**: Contextual suggestions based on usage

## How It Works

```text
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │     │                  │
│    Playbooks     │────▶│   AI Assistant   │────▶│   Your Systems   │
│  (Business Rules)│     │  (Decision Maker)│     │     (APIs)       │
│                  │     │                  │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

1. **Playbooks** define what the AI should do in each scenario
2. **AI Assistant** reads playbooks and makes decisions
3. **Your Systems** execute actions via API calls

## Benefits

### For Business Teams

- Write rules in language you understand
- Update policies without waiting for development
- Audit decisions by reading playbooks
- Test scenarios with real customer data

### For Development Teams

- No more translating business docs to code
- API-first integration with any system
- Observability through tool call logging
- Reduced maintenance burden

### For Operations

- Consistent decision-making across channels
- Instant policy updates
- Reduced manual processing
- Clear escalation paths
