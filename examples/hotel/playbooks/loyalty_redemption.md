# Loyalty Points Redemption

## Goal

Process loyalty point redemptions, applying appropriate conversion rates and validating eligibility.

## When to Use

Guest wants to redeem accumulated loyalty points for room nights, upgrades, or service credits.

## Steps

1. **Verify Guest & Balance**
   - Fetch guest profile
   - Check current points balance
   - Confirm sufficient points for redemption

2. **Determine Redemption Type**
   - Night stay credit
   - Room upgrade credit
   - Spa credit
   - Dining credit

3. **Calculate Value**
   - Apply conversion rate based on redemption type
   - Verify minimum points requirement met

4. **Process Redemption**
   - Deduct points from balance
   - Apply credit to guest account
   - Send confirmation notification

## Redemption Values

| Type | Value per 100 Points |
|------|---------------------|
| night_stay | $1.00 |
| room_upgrade | $0.80 |
| spa_credit | $1.20 |
| dining_credit | $1.50 |

### Minimum Redemption

- Minimum: 1,000 points per redemption
- No maximum limit

## Decision Criteria

### Immediate Approval

- Sufficient points balance
- Valid redemption type
- Guest account in good standing

### Not Allowed

- Balance below minimum
- Account with outstanding balance
- Expired points (if applicable)

## Customer Communication

- Confirm points to be redeemed
- Show dollar value being applied
- Display remaining balance after redemption
- Suggest optimal redemption types based on guest preferences
