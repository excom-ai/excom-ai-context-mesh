# Room Upgrade Request

## Goal

Process guest room upgrade requests, applying appropriate pricing and loyalty benefits.

## When to Use

Guest requests an upgrade to a higher room category during their stay or before check-in.

## Steps

1. **Verify Guest & Reservation**
   - Fetch guest profile
   - Get current reservation details
   - Note loyalty tier and preferences

2. **Check Room Availability**
   - Query available rooms for the guest's dates
   - Identify upgrade options
   - Verify target room type is available

3. **Process Upgrade**
   - Submit upgrade request
   - System calculates price difference with loyalty discounts
   - System checks for complimentary upgrade eligibility

4. **Confirm with Guest**
   - Present the upgrade details
   - Explain any charges or complimentary status
   - Send confirmation notification

## Room Tier Hierarchy

| Tier | Room Type          | Base Rate |
| ---- | ------------------ | --------- |
| 1    | Standard Double    | $180      |
| 2    | Standard King      | $200      |
| 3    | Deluxe Queen       | $250      |
| 4    | Deluxe King        | $280      |
| 5    | Junior Suite       | $350      |
| 6    | Executive Suite    | $450      |
| 7    | Presidential Suite | $800      |

### Upgrade Pricing

Price difference = (Target rate - Current rate) × Remaining nights

### Loyalty Benefits

| Tier     | Discount | Free Upgrade Tiers |
| -------- | -------- | ------------------ |
| Member   | 0%       | 0                  |
| Silver   | 10%      | 1                  |
| Gold     | 20%      | 2                  |
| Platinum | 30%      | 3                  |

## Decision Criteria

### Immediate Approval

- Target room is available
- Guest can pay any difference (or is eligible for complimentary)
- Upgrade follows normal tier progression

### Complimentary Upgrade Eligibility

- Higher loyalty tiers qualify for free upgrades (subject to availability)
- Special occasions noted in guest profile
- Service recovery situations
- Check-in day with available inventory

### Decline (with alternatives)

- Target room not available for dates
- Skip-tier upgrade requested (e.g., Standard to Presidential)
- Always offer next available tier as alternative

## Customer Communication

- Highlight the value and amenities of the upgrade
- Explain loyalty savings being applied
- Describe what makes the new room special
- Offer to arrange a room viewing if possible
- Never mention internal availability or inventory issues
- For declines, always present alternatives positively
