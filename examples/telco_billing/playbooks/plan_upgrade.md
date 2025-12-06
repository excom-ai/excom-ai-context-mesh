# Logic Module: plan_upgrade

## Goal

Handle customer plan upgrade requests, applying appropriate discounts based on loyalty and offering promotional pricing.

## Preconditions

- Customer exists in the system
- Customer has an active plan
- Requested plan is a higher tier than current plan

## Steps

1. Retrieve customer profile and current plan details
2. Check customer tenure and payment history
3. Calculate loyalty discount based on tenure:
   - Tenure > 24 months: 20% discount on first 3 months
   - Tenure > 12 months: 10% discount on first 3 months
   - Tenure < 12 months: No discount
4. Check if customer has any outstanding balance
   - If balance > $100: require payment before upgrade
   - If balance <= $100: proceed with upgrade
5. Apply promotional pricing if available
6. Process the plan upgrade
7. Send confirmation notification with new plan details

## Decision Rules

- High-value customers (ARPU > $100) get priority processing
- Customers with payment issues in last 90 days require manager approval
- Upgrade effective date is immediate unless customer requests future date
- Promotional discounts stack with loyalty discounts (max 30% total)

## Variables

The following logic.* variables should be computed:

- logic.loyalty_discount_percent: Discount percentage based on tenure (0, 10, or 20)
- logic.promotional_discount_percent: Any active promotional discount
- logic.total_discount_percent: Combined discount (capped at 30)
- logic.upgrade_approved: Boolean indicating if upgrade can proceed
- logic.requires_payment: Boolean if outstanding balance blocks upgrade
- logic.new_monthly_rate: Final monthly rate after discounts
- logic.upgrade_reason: Explanation of discount applied or rejection reason

## Rejection Triggers

- Outstanding balance > $100
- Account suspended or in collections
- More than 2 late payments in last 90 days
- Current plan is already highest tier

## Notifications

- On success: Send upgrade confirmation with new rate and discount details
- On rejection: Send explanation with steps to resolve (e.g., pay balance)
