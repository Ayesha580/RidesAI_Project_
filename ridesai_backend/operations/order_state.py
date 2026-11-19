"""
Strict Forward Order State Machine & Allowed Transitions.

Enforces that orders progress strictly forward and cannot move backward.
Terminal states (e.g., 'delivered', 'cancelled') reject any further transitions.
"""

from typing import Set, Dict
from operations.models import Order

# Forward-only transitions mapping
ALLOWED_ORDER_TRANSITIONS: Dict[str, Set[str]] = {
    Order.STATUS_NEW: {
        Order.STATUS_CONFIRMED,
        Order.STATUS_PREPARING,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PENDING: {
        Order.STATUS_CONFIRMED,
        Order.STATUS_PREPARING,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_CONFIRMED: {
        Order.STATUS_PREPARING,
        Order.STATUS_PREPARED,
        Order.STATUS_READY,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PREPARING: {
        Order.STATUS_PREPARED,
        Order.STATUS_READY,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PREPARED: {
        Order.STATUS_READY,
        Order.STATUS_ASSIGNED,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_READY: {
        Order.STATUS_ASSIGNED,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_ASSIGNED: {
        Order.STATUS_PICKED_UP,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PICKED_UP: {
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_ON_THE_WAY: {
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_OUT_FOR_DELIVERY: {
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    },
    # Terminal states: no further forward or backward movements permitted
    Order.STATUS_DELIVERED: set(),
    Order.STATUS_CANCELLED: set(),
}


def is_valid_order_transition(current_status: str, next_status: str) -> bool:
    """
    Validates if transitioning from current_status to next_status is permitted.
    Case-insensitive check.
    """
    curr = (current_status or "").strip().lower()
    nxt = (next_status or "").strip().lower()

    if curr == nxt:
        return True

    allowed = ALLOWED_ORDER_TRANSITIONS.get(curr, set())
    return nxt in allowed


def get_allowed_next_statuses(current_status: str) -> Set[str]:
    """Returns the set of valid next forward statuses for the given status."""
    curr = (current_status or "").strip().lower()
    return ALLOWED_ORDER_TRANSITIONS.get(curr, set())
