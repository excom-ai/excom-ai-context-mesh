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
   - Confirm amount, date, and merchant with the customer

3. **Assess Dispute Type**
   - **Unauthorized**: Customer didn't make the transaction
   - **Duplicate**: Same charge appeared twice
   - **Fraud**: Suspected fraudulent activity
   - **Service**: Didn't receive goods/services

4. **Determine Provisional Credit Eligibility**
   - Fraud/unauthorized claims under $500: Immediate provisional credit
   - Larger amounts: Provisional credit within 10 business days
   - Duplicate charges: Immediate credit if confirmed

5. **File the Dispute** (REQUIRED)
   - Create the dispute record in the system
   - Include: account number, transaction ID (use customer's description if exact ID not found), dispute type, amount, and description
   - If the transaction isn't visible in recent history, still file the dispute with the information provided
   - You MUST file the dispute before telling the customer it's done

6. **Apply Provisional Credit** (if eligible)
   - Apply the credit to the customer's account
   - Document the reason (e.g., "Provisional credit for dispute")

7. **Notify Customer** (REQUIRED)
   - Send confirmation notification to the customer
   - Include dispute reference number and next steps

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
- Confirm notification will be sent via email
