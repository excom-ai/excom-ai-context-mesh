#!/usr/bin/env python3
"""
Northbound API Server - LLM-friendly interface to hotel/travel APIs.

This server proxies requests to the southbound mock server and enriches
the OpenAPI documentation with context for LLM orchestration.

Run:
    poetry run python examples/hotel/northbound_server.py

Requires the southbound mock server to be running on port 9300:
    cd ../excom-context-mesh-hotel-mock-server
    poetry run mock-server
"""

from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Configuration
SOUTHBOUND_URL = "http://localhost:9300"
NORTHBOUND_PORT = 8054

app = FastAPI(
    title="Hotel & Travel API (Northbound)",
    description="""
## Overview

LLM-friendly interface for hotel guest services operations. This API provides endpoints
for guest management, reservations, room upgrades, complaints, and loyalty programs.

**Important**: Always fetch actual data from API endpoints. Do not assume values.

---

## Workflow 1: Reservation Modification

Use when a guest wants to change dates, room type, or special requests.

### Steps

1. `GET /guests/{id}` - Fetch guest profile (loyalty tier, preferences)
2. `GET /reservations/{id}` - Get current reservation details
3. Evaluate modification fees using decision rules (see playbook)
4. Apply loyalty discounts if applicable
5. `PUT /reservations/{id}/modify` - Submit modification
6. Always: `POST /notifications` - Confirm changes with guest

### Key Fields to Check

- `loyalty_tier`: Higher tier = fee discounts and free modifications
- Days until check-in: Affects modification fees
- `status`: Only confirmed/checked_in reservations can be modified

---

## Workflow 2: Guest Complaint Resolution

Use when a guest reports an issue with their stay.

### Steps

1. `GET /guests/{id}` - Check guest profile and loyalty status
2. `GET /reservations/{id}` - Get reservation context
3. Assess complaint severity and category
4. Calculate compensation using matrix (see playbook)
5. `POST /complaints` - File complaint and offer compensation
6. If needed: `POST /service-requests` - Dispatch resolution service
7. Always: `POST /notifications` - Confirm resolution

---

## Workflow 3: Room Upgrade

Use when a guest requests an upgrade to a higher room category.

### Steps

1. `GET /guests/{id}` - Check loyalty tier for upgrade eligibility
2. `GET /reservations/{id}` - Get current room type and dates
3. `GET /rooms/available` - Check upgrade availability
4. `POST /reservations/{id}/upgrade` - Process upgrade (pricing calculated automatically)
5. Always: `POST /notifications` - Confirm upgrade

---

## API Categories

- **Guests**: Guest profiles and preferences
- **Reservations**: Booking management and modifications
- **Rooms**: Room availability and details
- **Complaints**: Issue resolution and compensation
- **Services**: Service requests (housekeeping, concierge, etc.)
- **Loyalty**: Points balance and redemption
- **Notifications**: Guest communications
""",
    version="1.0.0",
)


# =============================================================================
# Request/Response Models with Rich Descriptions
# =============================================================================

class CreateGuestRequest(BaseModel):
    """
    Request to create a new guest profile.

    Use this when booking for a new guest who doesn't have a profile yet.
    """

    name: str = Field(
        ...,
        description="Guest's full name",
        examples=["Peter Larnholt", "Jane Smith"],
    )
    email: str = Field(
        ...,
        description="Guest's email address for confirmations",
        examples=["peter@example.com"],
    )
    phone: str = Field(
        ...,
        description="Guest's phone number",
        examples=["+1-555-0123", "+971-559534046"],
    )
    preferences: dict[str, str] = Field(
        default_factory=dict,
        description="Optional preferences (room_type, floor, dietary, etc.)",
        examples=[{"floor": "high", "dietary": "vegetarian"}],
    )


class GuestResponse(BaseModel):
    """
    Guest profile with loyalty and preference context.

    Use this data to make decisions about complaint resolution and upgrade eligibility:
    - Higher loyalty_tier = more benefits and compensation
    - Preferences inform room matching and service customization
    - lifetime_value indicates guest importance
    """

    guest_id: str = Field(
        ...,
        description="Unique guest identifier (format: GUEST-XXX)",
        examples=["GUEST-001", "GUEST-002"],
    )
    name: str = Field(
        ...,
        description="Guest's full name for personalization",
        examples=["James Anderson", "Maria Garcia"],
    )
    email: str = Field(
        ...,
        description="Guest's email address for notifications",
        examples=["james.anderson@example.com"],
    )
    phone: str = Field(
        ...,
        description="Guest's phone number for urgent communications",
        examples=["+1-555-0101"],
    )
    loyalty_tier: Literal["member", "silver", "gold", "platinum"] = Field(
        ...,
        description="Loyalty program tier. Higher tiers receive better benefits.",
        examples=["platinum", "gold", "silver", "member"],
    )
    loyalty_points: int = Field(
        ...,
        description="Current points balance available for redemption.",
        examples=[125000, 45000, 15000],
        ge=0,
    )
    total_stays: int = Field(
        ...,
        description="Total number of stays with us.",
        examples=[47, 12, 5],
        ge=0,
    )
    lifetime_value: float = Field(
        ...,
        description="Total revenue from this guest.",
        examples=[28500.0, 8200.0, 2800.0],
        ge=0,
    )
    preferences: dict[str, str] = Field(
        ...,
        description="Guest preferences for room and services. Keys: "
                    "room_type (preferred type), floor (high/low/any), "
                    "pillow_type, newspaper, dietary restrictions.",
        examples=[{"room_type": "suite", "floor": "high", "dietary": "vegetarian"}],
    )


class ReservationResponse(BaseModel):
    """
    Reservation details with booking context.

    Use this to understand the current booking before modifications or complaints.
    """

    reservation_id: str = Field(
        ...,
        description="Unique reservation identifier",
        examples=["RES-001", "RES-002"],
    )
    guest_id: str = Field(
        ...,
        description="Guest ID for this reservation",
        examples=["GUEST-001"],
    )
    room_number: str = Field(
        ...,
        description="Assigned room number",
        examples=["1201", "805"],
    )
    room_type: str = Field(
        ...,
        description="Room type: standard_double, standard_king, deluxe_queen, "
                    "deluxe_king, junior_suite, executive_suite, presidential_suite",
        examples=["executive_suite", "deluxe_king"],
    )
    check_in: str = Field(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2024-12-15"],
    )
    check_out: str = Field(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2024-12-20"],
    )
    nights: int = Field(
        ...,
        description="Number of nights",
        examples=[5, 2, 1],
        ge=1,
    )
    rate_per_night: float = Field(
        ...,
        description="Nightly rate in dollars",
        examples=[450.0, 280.0],
        ge=0,
    )
    total_amount: float = Field(
        ...,
        description="Total reservation amount",
        examples=[2250.0, 560.0],
        ge=0,
    )
    status: str = Field(
        ...,
        description="Reservation status: confirmed, checked_in, checked_out, cancelled. "
                    "Only confirmed/checked_in can be modified.",
        examples=["confirmed", "checked_in"],
    )
    special_requests: list[str] = Field(
        ...,
        description="Special requests for this stay",
        examples=[["Late check-out", "Airport transfer"]],
    )
    created_at: str = Field(
        ...,
        description="When reservation was created (ISO 8601)",
        examples=["2024-11-01T10:30:00Z"],
    )


class RoomResponse(BaseModel):
    """Room details."""

    room_number: str = Field(..., description="Room number")
    room_type: str = Field(..., description="Room type category")
    floor: int = Field(..., description="Floor number")
    beds: str = Field(..., description="Bed configuration")
    max_occupancy: int = Field(..., description="Maximum guests")
    base_rate: float = Field(..., description="Base nightly rate")
    amenities: list[str] = Field(..., description="Room amenities")
    status: str = Field(..., description="Status: available, reserved, occupied, maintenance")


class RoomAvailabilityResponse(BaseModel):
    """Room availability for date range."""

    room_number: str = Field(..., description="Room number")
    room_type: str = Field(..., description="Room type")
    base_rate: float = Field(..., description="Base rate per night")
    amenities: list[str] = Field(..., description="Room amenities")
    available: bool = Field(..., description="Whether room is available for dates")


class CreateReservationRequest(BaseModel):
    """
    Request to create a new reservation.

    IMPORTANT: You MUST check room availability first using
    GET /rooms/available?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD
    before calling this endpoint. Only book room types that show available: true.
    """

    guest_id: str = Field(
        ...,
        description="Guest ID for the reservation. Create guest first if new.",
        examples=["GUEST-001"],
    )
    room_type: Literal[
        "standard_double", "standard_king", "deluxe_queen", "deluxe_king",
        "junior_suite", "executive_suite", "presidential_suite"
    ] = Field(
        ...,
        description="Room type to book. MUST verify availability first via GET /rooms/available.",
        examples=["deluxe_king", "executive_suite"],
    )
    check_in: str = Field(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2024-12-15"],
    )
    check_out: str = Field(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2024-12-20"],
    )
    special_requests: list[str] = Field(
        default_factory=list,
        description="Special requests for the stay",
        examples=[["Late check-out", "High floor"]],
    )


class ModifyReservationRequest(BaseModel):
    """
    Request to modify a reservation.

    At least one of the modification fields must be provided.
    Check playbook for fee structure based on days until check-in.
    """

    new_check_in: str | None = Field(
        default=None,
        description="New check-in date (YYYY-MM-DD). Fee applies if <7 days to original check-in.",
        examples=["2024-12-16"],
    )
    new_check_out: str | None = Field(
        default=None,
        description="New check-out date (YYYY-MM-DD)",
        examples=["2024-12-21"],
    )
    new_room_type: str | None = Field(
        default=None,
        description="New room type (fee may apply).",
        examples=["deluxe_king", "executive_suite"],
    )
    special_requests: list[str] | None = Field(
        default=None,
        description="Updated special requests list",
        examples=[["Late check-out", "Quiet room"]],
    )


class ModificationResponse(BaseModel):
    """Response after modifying a reservation."""

    modification_id: str = Field(..., description="Unique modification ID")
    reservation_id: str = Field(..., description="Reservation that was modified")
    change_type: str = Field(..., description="Type of change: dates, room_type, special_requests")
    old_value: str = Field(..., description="Previous value")
    new_value: str = Field(..., description="New value")
    fee: float = Field(
        ...,
        description="Modification fee charged (if any).",
        ge=0,
    )
    status: str = Field(..., description="Modification status")
    created_at: str = Field(..., description="When modification was made")


class CancelReservationResponse(BaseModel):
    """Response after cancelling a reservation."""

    reservation_id: str = Field(..., description="Cancelled reservation ID")
    cancellation_fee: float = Field(
        ...,
        description="Cancellation fee charged based on cancellation policy.",
    )
    refund_amount: float = Field(..., description="Amount to be refunded")
    status: str = Field(..., description="New status (cancelled)")
    cancelled_at: str = Field(..., description="Cancellation timestamp")


class ComplaintRequest(BaseModel):
    """
    Request to file a guest complaint.

    Compensation is automatically calculated based on category, priority,
    and guest loyalty tier. See playbook for details.
    """

    guest_id: str = Field(
        ...,
        description="Guest filing the complaint",
        examples=["GUEST-001"],
    )
    reservation_id: str | None = Field(
        default=None,
        description="Related reservation (if applicable)",
        examples=["RES-001"],
    )
    category: Literal["room_quality", "service", "noise", "cleanliness", "billing", "amenities"] = Field(
        ...,
        description="Complaint category: "
                    "'room_quality' = issues with room condition. "
                    "'service' = staff service issues. "
                    "'noise' = noise disturbances. "
                    "'cleanliness' = hygiene issues. "
                    "'billing' = billing disputes. "
                    "'amenities' = facility issues.",
        examples=["room_quality", "noise"],
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Priority level: 'low' for minor issues, 'medium' for standard, "
                    "'high' for significant impact, 'urgent' for safety or major failures",
        examples=["high", "medium"],
    )
    description: str = Field(
        ...,
        description="Detailed description of the issue",
        min_length=10,
    )


class ComplaintResponse(BaseModel):
    """Response after filing a complaint."""

    complaint_id: str = Field(..., description="Unique complaint ID for tracking")
    guest_id: str = Field(..., description="Guest who filed complaint")
    reservation_id: str | None = Field(None, description="Related reservation")
    category: str = Field(..., description="Complaint category")
    priority: str = Field(..., description="Priority level")
    description: str = Field(..., description="Issue description")
    status: str = Field(..., description="Complaint status: open, investigating, resolved")
    compensation_offered: float = Field(
        ...,
        description="Compensation amount offered to the guest (credit or discount)",
    )
    created_at: str = Field(..., description="When complaint was filed")


class ServiceRequestModel(BaseModel):
    """
    Request for hotel services.

    Create service requests for housekeeping, maintenance, room service, etc.
    """

    guest_id: str = Field(
        ...,
        description="Guest requesting service",
        examples=["GUEST-001"],
    )
    reservation_id: str = Field(
        ...,
        description="Reservation for service delivery",
        examples=["RES-001"],
    )
    service_type: Literal["room_service", "housekeeping", "maintenance", "concierge", "spa", "transport"] = Field(
        ...,
        description="Type of service: "
                    "'room_service' = food/beverage. "
                    "'housekeeping' = cleaning and turndown. "
                    "'maintenance' = repairs and fixes. "
                    "'concierge' = reservations/info. "
                    "'spa' = spa booking. "
                    "'transport' = car service.",
        examples=["room_service", "housekeeping"],
    )
    description: str = Field(
        ...,
        description="Service request details",
        examples=["Extra towels and toiletries"],
    )
    preferred_time: str | None = Field(
        default=None,
        description="Preferred service time (ISO 8601)",
        examples=["2024-12-15T10:00:00Z"],
    )


class ServiceResponse(BaseModel):
    """Response after creating a service request."""

    request_id: str = Field(..., description="Unique service request ID")
    guest_id: str = Field(..., description="Guest who requested")
    reservation_id: str = Field(..., description="Reservation")
    service_type: str = Field(..., description="Type of service")
    description: str = Field(..., description="Request details")
    status: str = Field(..., description="Status: pending, in_progress, completed")
    estimated_completion: str | None = Field(
        None,
        description="Estimated completion time",
    )
    created_at: str = Field(..., description="When request was created")


class UpgradeRequest(BaseModel):
    """Request for a room upgrade."""

    target_room_type: str = Field(
        ...,
        description="Desired room type. Must be a higher category than current room.",
        examples=["executive_suite", "deluxe_king"],
    )


class UpgradeResponse(BaseModel):
    """Response after processing an upgrade request."""

    upgrade_id: str = Field(..., description="Unique upgrade ID")
    reservation_id: str = Field(..., description="Reservation being upgraded")
    original_room_type: str = Field(..., description="Original room type")
    new_room_type: str = Field(..., description="New room type")
    price_difference: float = Field(
        ...,
        description="Price difference to pay (may be waived based on eligibility)",
    )
    status: str = Field(..., description="Status: approved, denied, pending")
    reason: str | None = Field(None, description="Explanation of decision")


class LoyaltyStatusResponse(BaseModel):
    """Guest loyalty program status."""

    guest_id: str = Field(..., description="Guest ID")
    current_tier: str = Field(..., description="Current loyalty tier")
    points_balance: int = Field(..., description="Available points")
    total_stays: int = Field(..., description="Lifetime stays")
    lifetime_value: float = Field(..., description="Lifetime revenue")
    benefits: dict[str, Any] = Field(..., description="Current tier benefits")
    next_tier: str | None = Field(None, description="Next tier to achieve")
    points_to_next_tier: int | None = Field(None, description="Points needed for next tier")


class LoyaltyRedemptionRequest(BaseModel):
    """
    Request to redeem loyalty points.

    Points can be redeemed for nights, upgrades, or credits.
    """

    points_to_redeem: int = Field(
        ...,
        description="Number of points to redeem. Minimum: 1,000",
        examples=[10000, 5000],
        ge=1000,
    )
    redemption_type: Literal["night_stay", "room_upgrade", "spa_credit", "dining_credit"] = Field(
        ...,
        description="What to redeem points for: "
                    "'night_stay' = credit toward room charges. "
                    "'room_upgrade' = credit toward upgrades. "
                    "'spa_credit' = credit for spa services. "
                    "'dining_credit' = credit for dining.",
        examples=["night_stay", "dining_credit"],
    )


class LoyaltyRedemptionResponse(BaseModel):
    """Response after redeeming points."""

    redemption_id: str = Field(..., description="Unique redemption ID")
    guest_id: str = Field(..., description="Guest who redeemed")
    points_redeemed: int = Field(..., description="Points used")
    redemption_type: str = Field(..., description="Type of redemption")
    value: float = Field(..., description="Dollar value of redemption")
    status: str = Field(..., description="Redemption status")
    remaining_points: int = Field(..., description="Points balance after redemption")


class NotificationRequest(BaseModel):
    """
    Request to send a notification to a guest.

    Always notify guests after:
    - Modifying a reservation
    - Filing a complaint
    - Processing an upgrade
    - Completing a service request
    """

    guest_id: str = Field(
        ...,
        description="Guest ID to notify",
        examples=["GUEST-001"],
    )
    channel: Literal["email", "sms", "push"] = Field(
        default="email",
        description="Notification channel. Email for confirmations, SMS for urgent.",
        examples=["email", "sms"],
    )
    template_id: str = Field(
        ...,
        description="Notification template: "
                    "'reservation_modified' - confirms changes. "
                    "'reservation_cancelled' - confirms cancellation. "
                    "'complaint_received' - acknowledges complaint. "
                    "'upgrade_confirmed' - confirms room upgrade. "
                    "'service_completed' - service request done. "
                    "'loyalty_update' - points/tier changes.",
        examples=["reservation_modified", "complaint_received"],
    )
    template_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic data for template",
        examples=[{"room_type": "Executive Suite", "check_in": "Dec 15"}],
    )


class NotificationResponse(BaseModel):
    """Response after sending a notification."""

    notification_id: str = Field(..., description="Unique notification ID")
    guest_id: str = Field(..., description="Guest notified")
    channel: str = Field(..., description="Channel used")
    template_id: str = Field(..., description="Template used")
    status: str = Field(..., description="Delivery status: sent, pending, failed")
    sent_at: str = Field(..., description="When sent")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    southbound_status: str = Field(..., description="Southbound connection status")
    version: str = Field(..., description="API version")


# =============================================================================
# Helper Functions
# =============================================================================

def proxy_get(path: str) -> dict:
    """Proxy GET request to southbound."""
    try:
        response = httpx.get(f"{SOUTHBOUND_URL}{path}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Southbound unavailable: {e}")


def proxy_post(path: str, data: dict) -> dict:
    """Proxy POST request to southbound."""
    try:
        response = httpx.post(f"{SOUTHBOUND_URL}{path}", json=data, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Southbound unavailable: {e}")


def proxy_put(path: str, data: dict) -> dict:
    """Proxy PUT request to southbound."""
    try:
        response = httpx.put(f"{SOUTHBOUND_URL}{path}", json=data, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Southbound unavailable: {e}")


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Check health of northbound and southbound services."""
    southbound_status = "unknown"
    try:
        response = httpx.get(f"{SOUTHBOUND_URL}/", timeout=2.0)
        southbound_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        southbound_status = "unreachable"

    return HealthResponse(
        status="healthy",
        service="Hotel & Travel API (Northbound)",
        southbound_status=southbound_status,
        version="1.0.0",
    )


# =============================================================================
# Guest Endpoints
# =============================================================================

@app.get(
    "/guests/{guest_id}",
    response_model=GuestResponse,
    tags=["Guests"],
    summary="Get guest profile with loyalty status and preferences",
    description="""
Retrieve complete guest profile including loyalty tier and preferences.

## Key Response Fields

- `loyalty_tier`: Guest's loyalty program level
- `loyalty_points`: Available for redemption
- `preferences`: Room and service preferences
- `lifetime_value`: Total revenue from guest

## Workflow

1. Fetch guest profile first
2. Note loyalty tier for service level
3. Check preferences for personalization
""",
)
def get_guest(guest_id: str):
    """Get guest details with loyalty context."""
    return proxy_get(f"/guests/{guest_id}")


@app.post(
    "/guests",
    response_model=GuestResponse,
    tags=["Guests"],
    summary="Create a new guest profile",
    description="""
Create a new guest profile for first-time guests.

## When to Use

Call this BEFORE creating a reservation for a new guest who doesn't have a profile yet.

## Flow

1. Collect guest information (name, email, phone)
2. Call `POST /guests` to create the profile
3. Use the returned `guest_id` to create the reservation

## Note

If a guest with the same email already exists, returns the existing profile instead of creating a duplicate.
""",
)
def create_guest(request: CreateGuestRequest):
    """Create a new guest profile."""
    return proxy_post("/guests", request.model_dump())


# =============================================================================
# Reservation Endpoints
# =============================================================================

@app.get(
    "/guests/{guest_id}/reservations",
    response_model=list[ReservationResponse],
    tags=["Reservations"],
    summary="Get all reservations for a guest",
    description="""
List all reservations for a guest (past and upcoming).

Use to find the relevant reservation before modifications or complaints.
""",
)
def get_guest_reservations(guest_id: str):
    """Get all reservations for a guest."""
    return proxy_get(f"/guests/{guest_id}/reservations")


@app.post(
    "/reservations",
    response_model=ReservationResponse,
    tags=["Reservations"],
    summary="Create a new reservation",
    description="""
Create a new reservation for a guest.

## Prerequisites (MUST complete in order)

1. **Create/fetch guest** - `GET /guests/{id}` or `POST /guests` for new guests
2. **Check availability** - `GET /rooms/available?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD`
   - Use the guest's requested dates in the query parameters
   - Only proceed if the response shows `available: true` for desired room type
3. **Load playbook** - `get_playbook(new_booking)` for pricing rules

## IMPORTANT

Do NOT call this endpoint unless you have verified availability for the requested dates and room type.

## After Booking

Send notification using `POST /notifications` with template "reservation_confirmed".
""",
)
def create_reservation(request: CreateReservationRequest):
    """Create a new reservation."""
    return proxy_post("/reservations", request.model_dump())


@app.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    tags=["Reservations"],
    summary="Get reservation details",
    description="""
Get detailed information about a specific reservation.

## Response Fields

- `status`: confirmed, checked_in, checked_out, cancelled
- `room_type`: Current room category
- `rate_per_night`: Current nightly rate
- `special_requests`: Current requests

## Usage

1. Fetch before modifications to understand current state
2. Check status - only confirmed/checked_in can be modified
3. Note dates for cancellation fee calculation
""",
)
def get_reservation(reservation_id: str):
    """Get reservation details."""
    return proxy_get(f"/reservations/{reservation_id}")


@app.put(
    "/reservations/{reservation_id}/modify",
    response_model=ModificationResponse,
    tags=["Reservations"],
    summary="Modify a reservation - CALL THIS to change dates/room",
    description="""
**Call this endpoint to modify a reservation.** Changes dates, room type, or special requests.

Fees are calculated automatically based on timing and guest loyalty status.

## When to Call

- Guest wants to change check-in or check-out dates
- Guest wants to change room type
- Guest wants to update special requests

## Parameters

Provide at least one of: `new_check_in`, `new_check_out`, `new_room_type`, or `special_requests`.

## Response

Returns modification details including any fees charged.
""",
)
def modify_reservation(reservation_id: str, request: ModifyReservationRequest):
    """Modify a reservation."""
    return proxy_put(f"/reservations/{reservation_id}/modify", request.model_dump(exclude_none=True))


@app.post(
    "/reservations/{reservation_id}/cancel",
    response_model=CancelReservationResponse,
    tags=["Reservations"],
    summary="Cancel a reservation",
    description="""
Cancel a reservation. Cancellation fee and refund are calculated automatically based on timing.

## After Cancellation

Send notification using `POST /notifications` with template "reservation_cancelled".
""",
)
def cancel_reservation(reservation_id: str):
    """Cancel a reservation."""
    return proxy_post(f"/reservations/{reservation_id}/cancel", {})


@app.post(
    "/reservations/{reservation_id}/upgrade",
    response_model=UpgradeResponse,
    tags=["Reservations"],
    summary="Process room upgrade - CALL THIS when guest wants upgrade",
    description="""
**Call this endpoint to process a room upgrade request.**

Pricing and complimentary eligibility are calculated automatically based on guest loyalty status.

## When to Call

- Guest asks to upgrade to a higher room category
- Guest wants a better room

## Before Calling

1. Check availability via `GET /rooms/available` to verify target room type is available
2. Load `room_upgrade` playbook for pricing and eligibility rules

## Parameters

- `target_room_type`: The room type the guest wants to upgrade to

## Response

Returns upgrade details including price difference and approval status.
""",
)
def request_upgrade(reservation_id: str, request: UpgradeRequest):
    """Request a room upgrade."""
    return proxy_post(f"/reservations/{reservation_id}/upgrade", request.model_dump())


# =============================================================================
# Room Endpoints
# =============================================================================

@app.get(
    "/rooms",
    response_model=list[RoomResponse],
    tags=["Rooms"],
    summary="List all rooms",
    description="Get a list of all rooms in the hotel with their details and current status.",
)
def list_rooms():
    """List all rooms."""
    return proxy_get("/rooms")


@app.get(
    "/rooms/available",
    response_model=list[RoomAvailabilityResponse],
    tags=["Rooms"],
    summary="Check room availability for dates",
    description="""
Check which rooms are available for specific dates. You MUST provide check_in and check_out dates.

## REQUIRED Parameters

- `check_in`: Guest's check-in date (YYYY-MM-DD format, e.g., "2026-01-01")
- `check_out`: Guest's check-out date (YYYY-MM-DD format, e.g., "2026-01-03")

## Optional Parameters

- `room_type`: Filter by specific room type

## Response

Returns a list of rooms. Check the `available` field:
- `available: true` = room can be booked for these dates
- `available: false` = room is not available

## Usage

1. Call BEFORE attempting to create a reservation
2. Only book room types where `available: true`
3. If preferred type unavailable, suggest available alternatives
""",
)
def get_available_rooms(
    check_in: str = Query(..., description="Check-in date in YYYY-MM-DD format (e.g., 2026-01-01)"),
    check_out: str = Query(..., description="Check-out date in YYYY-MM-DD format (e.g., 2026-01-03)"),
    room_type: str | None = Query(None, description="Optional: filter by room type"),
):
    """Get available rooms for date range."""
    params = f"?check_in={check_in}&check_out={check_out}"
    if room_type:
        params += f"&room_type={room_type}"
    return proxy_get(f"/rooms/available{params}")


@app.get(
    "/rooms/{room_number}",
    response_model=RoomResponse,
    tags=["Rooms"],
    summary="Get room details",
    description="Get detailed information about a specific room.",
)
def get_room(room_number: str):
    """Get room details."""
    return proxy_get(f"/rooms/{room_number}")


# =============================================================================
# Complaint Endpoints
# =============================================================================

@app.post(
    "/complaints",
    response_model=ComplaintResponse,
    tags=["Complaints"],
    summary="File a guest complaint",
    description="""
File a complaint on behalf of a guest. Compensation is calculated automatically based on complaint category, priority, and guest loyalty status.

## Prerequisites

1. Fetch guest via `GET /guests/{id}` for context
2. Get reservation via `GET /reservations/{id}` if complaint is reservation-related
3. Load complaint playbook for escalation decision rules

## After Filing

1. If immediate action needed: `POST /service-requests` to dispatch housekeeping/maintenance
2. Always: `POST /notifications` with template "complaint_received"
""",
)
def create_complaint(request: ComplaintRequest):
    """Create a guest complaint."""
    return proxy_post("/complaints", request.model_dump())


@app.get(
    "/complaints/{complaint_id}",
    response_model=ComplaintResponse,
    tags=["Complaints"],
    summary="Get complaint details",
    description="Get the current status and details of a complaint.",
)
def get_complaint(complaint_id: str):
    """Get complaint details."""
    return proxy_get(f"/complaints/{complaint_id}")


# =============================================================================
# Service Endpoints
# =============================================================================

@app.post(
    "/service-requests",
    response_model=ServiceResponse,
    tags=["Services"],
    summary="Create a service request",
    description="""
Create a service request for housekeeping, room service, maintenance, etc.

## Service Types

- `room_service` - Food and beverage delivery
- `housekeeping` - Cleaning and turndown service
- `maintenance` - Repairs and fixes
- `concierge` - Reservations and information
- `spa` - Spa booking (requires scheduling)
- `transport` - Car service and transfers

## Priority Handling

Higher-tier loyalty guests receive expedited service.
Urgent requests (safety, maintenance) are prioritized.

## After Request

Service completion triggers automatic notification.
Follow up if estimated_completion exceeded.
""",
)
def create_service_request(request: ServiceRequestModel):
    """Create a service request."""
    return proxy_post("/service-requests", request.model_dump())


# =============================================================================
# Loyalty Endpoints
# =============================================================================

@app.get(
    "/guests/{guest_id}/loyalty",
    response_model=LoyaltyStatusResponse,
    tags=["Loyalty"],
    summary="Get guest loyalty status",
    description="""
Get detailed loyalty program status including current tier, points balance, and progress to next tier.
""",
)
def get_loyalty_status(guest_id: str):
    """Get guest loyalty status."""
    return proxy_get(f"/guests/{guest_id}/loyalty")


@app.post(
    "/guests/{guest_id}/loyalty/redeem",
    response_model=LoyaltyRedemptionResponse,
    tags=["Loyalty"],
    summary="Redeem loyalty points",
    description="""
Redeem loyalty points for various benefits. Redemption values are calculated automatically based on redemption type.

## Usage

1. Check points balance via `GET /guests/{id}/loyalty`
2. Process redemption
3. Notify guest of remaining balance
""",
)
def redeem_loyalty_points(guest_id: str, request: LoyaltyRedemptionRequest):
    """Redeem loyalty points."""
    return proxy_post(f"/guests/{guest_id}/loyalty/redeem", request.model_dump())


# =============================================================================
# Notification Endpoints
# =============================================================================

@app.post(
    "/notifications",
    response_model=NotificationResponse,
    tags=["Notifications"],
    summary="Send notification to guest",
    description="""
Send a notification to inform the guest about their request status.

## Available Templates

| Template ID | When to Use |
|-------------|-------------|
| `reservation_modified` | After any reservation change |
| `reservation_cancelled` | After cancellation |
| `complaint_received` | After filing complaint |
| `upgrade_confirmed` | After room upgrade |
| `service_completed` | After service request done |
| `loyalty_update` | Points/tier changes |

## Template Data

Include relevant context:
- `room_type`: For upgrades
- `check_in`, `check_out`: For date changes
- `amount`: For charges/refunds
- `compensation`: For complaints
""",
)
def send_notification(request: NotificationRequest):
    """Send a notification to a guest."""
    return proxy_post("/notifications", request.model_dump())


# =============================================================================
# Debug Endpoints
# =============================================================================

@app.get("/debug/guests", tags=["Debug"], summary="List all guests")
def list_guests():
    """List all guests for debugging."""
    return proxy_get("/debug/guests")


@app.get("/debug/reservations", tags=["Debug"], summary="List all reservations")
def list_reservations():
    """List all reservations for debugging."""
    return proxy_get("/debug/reservations")


@app.get("/debug/complaints", tags=["Debug"], summary="List all complaints")
def list_complaints():
    """List all complaints for debugging."""
    return proxy_get("/debug/complaints")


@app.post("/debug/reset", tags=["Debug"], summary="Reset transaction data")
def reset_data():
    """Reset transaction data (keeps guests and rooms)."""
    return proxy_post("/debug/reset", {})


@app.post("/debug/reset-all", tags=["Debug"], summary="Reset everything")
def reset_all():
    """Reset everything to defaults."""
    return proxy_post("/debug/reset-all", {})


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" Hotel & Travel API (Northbound - LLM Context Enriched)")
    print("=" * 60)
    print(f"\n  Northbound: http://localhost:{NORTHBOUND_PORT}")
    print(f"  Southbound: {SOUTHBOUND_URL}")
    print(f"\n  OpenAPI docs: http://localhost:{NORTHBOUND_PORT}/docs")
    print(f"  OpenAPI JSON: http://localhost:{NORTHBOUND_PORT}/openapi.json")
    print("\nGuests & Reservations:")
    print("  GET  /guests/{id}                    - Get guest profile")
    print("  GET  /guests/{id}/reservations       - List reservations")
    print("  GET  /reservations/{id}              - Get reservation details")
    print("  PUT  /reservations/{id}/modify       - Modify reservation")
    print("  POST /reservations/{id}/cancel       - Cancel reservation")
    print("  POST /reservations/{id}/upgrade      - Request upgrade")
    print("\nRooms:")
    print("  GET  /rooms                          - List all rooms")
    print("  GET  /rooms/available                - Check availability")
    print("  GET  /rooms/{number}                 - Get room details")
    print("\nComplaints & Services:")
    print("  POST /complaints                     - File complaint")
    print("  GET  /complaints/{id}                - Get complaint status")
    print("  POST /service-requests               - Create service request")
    print("\nLoyalty:")
    print("  GET  /guests/{id}/loyalty            - Get loyalty status")
    print("  POST /guests/{id}/loyalty/redeem     - Redeem points")
    print("\nNotifications:")
    print("  POST /notifications                  - Send notification")
    print()

    uvicorn.run(app, host="0.0.0.0", port=NORTHBOUND_PORT)
