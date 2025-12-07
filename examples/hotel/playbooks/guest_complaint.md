# Guest Complaint Resolution

## Goal

Effectively resolve guest complaints and determine appropriate compensation based on complaint severity and guest value.

## When to Use

Guest reports an issue with their stay: room quality, noise, cleanliness, service failure, billing error, or amenity problems.

## Steps

1. **Verify Guest Identity**
   - Fetch guest profile
   - Note loyalty tier and lifetime value

2. **Document the Complaint**
   - Get full details of the issue
   - Categorize complaint type
   - Assess severity/priority

3. **Check Service History**
   - Review current reservation
   - Note any previous complaints
   - Check for pattern issues

4. **Determine Resolution**
   - System calculates compensation automatically
   - Consider additional remedies beyond monetary compensation
   - Offer appropriate resolution options

5. **Execute Resolution**
   - Create complaint record
   - Dispatch service request if immediate action needed
   - Send confirmation to guest

## Compensation Matrix

### Base Compensation by Category

| Category     | Base Amount |
| ------------ | ----------- |
| room_quality | $50         |
| service      | $30         |
| noise        | $40         |
| cleanliness  | $45         |
| billing      | $25         |
| amenities    | $35         |

### Priority Multipliers

| Priority | Multiplier |
| -------- | ---------- |
| low      | 0.5x       |
| medium   | 1.0x       |
| high     | 1.5x       |
| urgent   | 2.0x       |

### Loyalty Tier Multipliers

| Tier     | Multiplier |
| -------- | ---------- |
| Member   | 1.0x       |
| Silver   | 1.25x      |
| Gold     | 1.5x       |
| Platinum | 2.0x       |

**Formula**: Compensation = Base × Priority Multiplier × Loyalty Multiplier

## Decision Criteria

### Immediate Resolution

- Minor issues with clear resolution
- Guest in good standing
- First complaint of this type

### Manager Escalation Required

- Safety concerns of any kind
- Repeated same issue (3+ times during stay)
- Platinum guest with any complaint
- Guest mentions social media or review sites
- Guest requests to speak with manager

### Service Dispatch Needed

- Cleanliness issues: Housekeeping
- Room defects: Maintenance
- Noise complaints after 10pm: Security
- Food quality: F&B manager

## Additional Resolution Options

Beyond monetary compensation, consider offering:
- Room move to quieter location
- Complimentary upgrade for current or future stay
- Bonus loyalty points
- Dining or spa credit
- Late checkout or early check-in

## Customer Communication

- Apologize sincerely without over-explaining
- Acknowledge the specific issue
- Explain what you're doing to resolve it
- Never blame other departments or staff
- Follow up to ensure satisfaction
