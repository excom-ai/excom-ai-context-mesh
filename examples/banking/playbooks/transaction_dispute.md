# Transaction Dispute Resolution

## Goal

Help customers dispute unauthorized or incorrect transactions and determine appropriate resolution.

## When to Use

Customer reports an unauthorized charge, duplicate transaction, or fraudulent activity on their account.

## Steps

1. **Verify Customer Identity**
   - Fetch customer profile using account ID
   - Confirm basic account details

2. **Review Transaction Details**
   - Get account transactions to locate the disputed transaction
   - Confirm amount, date, and merchant

3. **Assess Dispute Type**
   - **Unauthorized**: Customer didn't make the transaction
   - **Duplicate**: Same charge appeared twice
   - **Fraud**: Suspected fraudulent activity
   - **Service**: Didn't receive goods/services

4. **Determine Provisional Credit Eligibility**
   - Fraud/unauthorized claims under $500: Immediate provisional credit
   - Larger amounts: Provisional credit within 10 business days
   - Duplicate charges: Immediate credit if confirmed

5. **Create Dispute Record**
   - Log the dispute with full details
   - Apply provisional credit if eligible
   - Notify customer of investigation timeline

## Decision Criteria

### Immediate Credit Approved

- Account tenure > 6 months AND
- No previous fraud claims in last 12 months AND
- Dispute amount ≤ $500

### Provisional Credit (10 days)

- Dispute amount > $500 OR
- Previous disputes exist but were resolved in customer's favor

### Escalation Required

- Dispute amount > $2,500
- Third dispute in 90 days
- Suspected organized fraud

## Customer Communication

- Confirm the transaction details with customer
- Explain the investigation timeline (typically 10-45 days)
- Provide case reference number
- Offer to send confirmation via email
