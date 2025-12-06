# Logic Module: telco_billing_resolution

## Goal

Resolve customer billing disputes within defined credit limits based on customer tenure, ARPU, and churn risk.

## Preconditions

- Customer exists in the system
- Invoice exists and is valid
- Dispute has been logged

## Steps

1. Check customer tenure, ARPU, and churn risk from the context
2. Validate the dispute amount against the invoice
3. Check for previous disputes using db.customer.disputes_last_30_days
4. Apply decision rules to determine BASE credit:
   - If churn risk is HIGH and dispute amount < $200: full credit
   - If tenure > 12 months and dispute amount < $100: full credit
   - If tenure > 6 months and dispute amount < $50: partial credit (50%)
   - Otherwise: escalate to manual review
5. MANDATORY: Apply repeat dispute reduction (see Credit Adjustments below)
6. Create billing adjustment if credit is approved
7. Send notification to customer

## Decision Rules

- High churn risk customers get priority treatment
- Long-tenure customers (>12 months) are eligible for higher credits
- Disputes over $200 always require escalation
- Partial credits are 50% of disputed amount

## Credit Adjustments (MUST BE APPLIED)

IMPORTANT: After calculating the base credit amount, you MUST apply these adjustments:

1. **Repeat Dispute Reduction**: If db.customer.disputes_last_30_days > 0, reduce the credit by 25%
   - Example: Base credit $75 with 1 previous dispute → Final credit = $75 × 0.75 = $56.25
   - This applies to ALL credits (full or partial)

2. **Escalation Override**: If db.customer.disputes_last_30_days >= 4, escalate instead of giving credit
   - Too many disputes indicates a pattern requiring manual review

## Escalation Triggers

- Dispute amount > $200
- Invoice older than 90 days
- Outstanding balance > $500
- 4 or more disputes in last 30 days
