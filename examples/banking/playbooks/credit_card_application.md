# Credit Card Application

## Goal

Help customers apply for credit cards and guide them to the right product based on their profile.

## When to Use

Customer wants to apply for a credit card or upgrade their existing card.

## Steps

1. **Review Customer Profile**
   - Fetch customer information
   - Note tenure, relationship value, and account standing

2. **Assess Eligibility**
   - Check if customer has existing accounts in good standing
   - Review monthly income and credit factors

3. **List Available Products**
   - Fetch all credit card products
   - Compare requirements against customer profile

4. **Recommend Products**
   - Match customer profile to appropriate tier:
     - **Basic Card**: Entry-level, no annual fee
     - **Premium Card**: Travel rewards, moderate fee
     - **Elite Card**: Premium benefits, higher requirements
   - Explain benefits and fees of recommended products

5. **Submit Application** (REQUIRED)
   - Submit the application in the system
   - You MUST submit the application before telling the customer it's done
   - Provide the decision to the customer (approved, pending, or declined)

6. **Notify Customer** (REQUIRED)
   - Send confirmation notification to the customer
   - Include application status and next steps

## Product Matching Guidelines

### Basic Rewards Card

- Best for: New customers, building credit
- Requirements: 6+ months banking relationship
- Annual fee: $0

### Premium Travel Card

- Best for: Frequent travelers, good credit history
- Requirements: 12+ months tenure, good standing
- Annual fee: $95
- Benefits: 2x points on travel/dining, no foreign fees

### Elite Platinum Card

- Best for: High-value customers, excellent credit
- Requirements: 24+ months tenure, significant relationship
- Annual fee: $495
- Benefits: 3x points, airport lounge access, concierge

## Decision Criteria

### Immediate Approval

- Account in good standing
- Meets minimum requirements for selected product
- No recent credit issues

### Pending Review

- Borderline eligibility
- Recent account changes
- First credit product with bank

### Decline (with alternative offer)

- Doesn't meet minimum requirements
- Offer lower-tier product instead
- Provide guidance on improving eligibility

## Customer Communication

- Explain product benefits clearly
- Be transparent about annual fees
- Offer alternatives if declined
- Never reveal specific credit score thresholds
