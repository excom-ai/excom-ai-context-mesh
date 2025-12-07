# Service Request Handling

## Goal

Process guest service requests efficiently, prioritizing based on request type and guest loyalty status.

## When to Use

Guest requests hotel services: room service, housekeeping, maintenance, concierge, spa booking, or transportation.

## Steps

1. **Verify Guest & Reservation**
   - Fetch guest profile
   - Confirm active reservation
   - Note loyalty tier for priority

2. **Categorize Request**
   - Identify service type
   - Determine urgency level
   - Note preferred timing if specified

3. **Dispatch Service**
   - Create service request
   - Assign to appropriate department
   - Set expected completion time

4. **Confirm & Follow Up**
   - Notify guest of expected time
   - Track completion status
   - Follow up if delayed

## Service Response Times

| Service Type | Standard Response | Priority Response     |
| ------------ | ----------------- | --------------------- |
| room_service | 30 minutes        | 20 minutes            |
| housekeeping | 45 minutes        | 30 minutes            |
| maintenance  | 60 minutes        | 30 minutes            |
| concierge    | 15 minutes        | 10 minutes            |
| spa          | Scheduled booking | Same-day if available |
| transport    | 20 minutes        | 15 minutes            |

### Priority Service Eligibility

| Tier     | Priority Service   |
| -------- | ------------------ |
| Member   | Standard only      |
| Silver   | Standard only      |
| Gold     | Priority available |
| Platinum | Always priority    |

## Decision Criteria

### Immediate Dispatch

- Standard service request
- Guest in good standing
- Resources available

### Expedited Handling

- Gold/Platinum guest
- Urgent request flagged
- Safety or maintenance emergency

### Scheduling Required

- Spa appointments
- Airport transfers with specific times
- Special event arrangements

## Customer Communication

- Confirm request received
- Provide estimated completion time
- Update if delays occur
- Follow up after completion
