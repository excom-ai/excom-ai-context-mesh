# Reservation Modification

## Goal

Help guests modify their reservations (dates, room type, special requests) while applying appropriate fees and loyalty benefits.

## When to Use

Guest wants to change check-in/check-out dates, upgrade room type, or update special requests for an existing reservation.

## Steps

1. **Verify Guest Identity**
   - Fetch guest profile
   - Confirm reservation details

2. **Review Current Reservation**
   - Get reservation details
   - Note current dates, room type, and status
   - Confirm reservation can be modified (not cancelled or checked out)

3. **Assess Modification Type**
   - **Date Change**: New check-in or check-out dates
   - **Room Change**: Different room type requested
   - **Special Requests**: Additional amenities or services

4. **Process Modification**
   - Submit modification request
   - System applies fees and loyalty discounts automatically
   - Confirm changes with guest

5. **Send Confirmation**
   - Notify guest of successful modification
   - Include any fees charged
   - Provide updated reservation details

## Modification Fee Structure

| Days Before Check-in | Base Fee  |
| -------------------- | --------- |
| 7+ days              | $0 (free) |
| 3-6 days             | $25       |
| 1-2 days             | $50       |
| Same day             | $75       |

### Loyalty Discounts on Fees

| Tier     | Discount                  |
| -------- | ------------------------- |
| Member   | 0%                        |
| Silver   | 25%                       |
| Gold     | 50%                       |
| Platinum | 100% (free modifications) |

## Decision Criteria

### Immediate Approval

- Request is well before check-in
- Guest is in good standing
- Room availability confirmed (for room changes)

### Manager Review Required

- Same-day modification request
- Multiple modifications to same reservation
- Request to waive fees for non-loyalty members
- Date change to sold-out period

### Not Allowed

- Modifications to past reservations
- Modifications to cancelled reservations
- Changes that violate minimum stay requirements

## Customer Communication

- Clearly explain any fees before processing
- Highlight loyalty benefits being applied
- Provide updated confirmation details
- Offer alternative dates if requested dates unavailable
- For declines, explain reason and offer alternatives
