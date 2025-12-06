# Logic Module: test_billing_resolution

## Goal

Resolve customer billing disputes based on tenure, ARPU, and churn risk.

## Preconditions

- Customer exists in the system
- Invoice exists and is valid
- Dispute has been logged

## Steps

1. Check customer tenure and churn risk
2. Validate dispute amount against invoice
3. Apply decision rules:
   - If churn_risk is high and amount < 200: full credit
   - If tenure > 12 months and amount < 100: full credit
   - Otherwise: escalate
4. Create billing adjustment if approved
5. Send notification to customer

## Decision Rules

- High churn risk customers get priority
- Long-tenure customers (>12 months) eligible for higher credits
- Disputes over $200 require escalation

## Variables

- logic.recommended_credit_amount: Credit amount to apply
- logic.escalation_required: Boolean for manual review
- logic.resolution_type: One of "full_credit", "partial_credit", "escalate"
