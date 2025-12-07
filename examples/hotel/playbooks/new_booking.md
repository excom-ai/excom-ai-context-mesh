# New Reservation Booking

## Goal

Create new reservations for guests, applying appropriate pricing based on room type and loyalty status.

## When to Use

Guest wants to make a new reservation for a future stay.

## Steps

1. **Identify or Create Guest**
   - Ask for guest email to check if they exist in the system
   - For returning guests, retrieve their profile and loyalty status
   - For new guests, collect name, email, and phone to create a profile
   - A guest profile must exist before creating a reservation

2. **Determine Requirements**
   - Check-in and check-out dates (required)
   - Room type preference
   - Number of guests
   - Special requests (late check-out, high floor, etc.)

3. **Check Availability**
   - Verify room availability for the requested dates
   - If preferred room type is unavailable, present available alternatives
   - Do not proceed with booking unless availability is confirmed

4. **Calculate Pricing**
   - Apply base rate for selected room type
   - Apply loyalty discount based on guest's tier
   - Calculate total: (base_rate × nights) × (1 - loyalty_discount)

5. **Create Reservation**
   - Only proceed after confirming availability
   - Record the reservation and assigned room
   - Send confirmation to guest

## Room Pricing

| Room Type | Base Rate/Night |
|-----------|-----------------|
| standard_double | $180 |
| standard_king | $200 |
| deluxe_queen | $250 |
| deluxe_king | $280 |
| junior_suite | $350 |
| executive_suite | $450 |
| presidential_suite | $800 |

### Loyalty Discounts

| Tier | Discount |
|------|----------|
| Member | 0% |
| Silver | 10% |
| Gold | 20% |
| Platinum | 30% |

## Decision Criteria

### Immediate Confirmation

- Room type available for requested dates
- Valid guest information
- No minimum stay violations

### Waitlist or Alternative

- Preferred room type unavailable
- Dates partially available
- Suggest comparable alternatives

### Cannot Book

- Hotel fully booked for dates
- Invalid date range (check-out before check-in)
- Minimum stay not met (if applicable)

## Customer Communication

- Confirm dates and room type selection
- Present total pricing with any discounts applied
- Mention loyalty benefits being applied
- Offer to add special requests
- Send confirmation with reservation details
