"""
Auto-Assignment Engine for Delivery Dispatch.
Selects and assigns the best available delivery rider using least-busy load balancing.
Strict multi-tenant isolation enforced.
"""

import logging
from typing import Optional
from django.contrib.auth import get_user_model
from django.db.models import Q

logger = logging.getLogger("operations.dispatch")


def assign_best_rider(order) -> Optional[object]:
    """
    Finds all active riders belonging to order.company and assigns the rider
    with the least number of currently active deliveries.
    
    Active deliveries include orders in:
    - 'prepared' / 'ready'
    - 'out_for_delivery' / 'picked_up' / 'on_the_way'
    - 'assigned'
    
    :param order: operations.models.Order instance
    :return: Assigned User instance or None if no rider is available.
    """
    from operations.models import Order, OrderEvent

    company = getattr(order, "company", None)
    if not company:
        logger.warning(f"[Dispatch] Order #{order.order_number} has no associated company.")
        return None

    User = get_user_model()

    # 1. Look up all active delivery riders for this specific tenant
    rider_filter = (
        Q(role="rider")
        | Q(staff_role__name__iexact="rider")
        | Q(staff_role__name__iexact="delivery boy")
        | Q(staff_role__name__iexact="delivery")
    )
    riders = list(
        User.objects.filter(company=company, is_active=True)
        .filter(rider_filter)
        .order_by("id")
    )

    if not riders:
        logger.info(
            f"[Dispatch] No active riders available for company '{company.name}' (Order #{order.order_number}). "
            "Leaving unassigned for manual dispatch."
        )
        return None

    # 2. Determine active workload for each candidate rider
    active_statuses = [
        Order.STATUS_PREPARED,
        Order.STATUS_READY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ASSIGNED,
    ]

    best_rider = None
    min_active_count = float("inf")

    for rider in riders:
        active_count = Order.objects.filter(
            company=company,
            assigned_rider=rider,
            status__in=active_statuses,
        ).count()

        if active_count < min_active_count:
            min_active_count = active_count
            best_rider = rider

    if not best_rider:
        best_rider = riders[0]

    # 3. Assign order to the chosen rider
    order.assigned_rider = best_rider
    order.save(update_fields=["assigned_rider", "updated_at"])

    # 4. Audit log event
    try:
        OrderEvent.objects.create(
            company=company,
            order=order,
            event_type="rider_auto_assigned",
            from_status=order.status,
            to_status=order.status,
            note=f"Auto-assigned to rider {best_rider.username} (active deliveries: {min_active_count})",
            metadata={
                "rider_id": best_rider.id,
                "rider_username": best_rider.username,
                "active_orders_count": min_active_count,
            },
        )
    except Exception as exc:
        logger.error(f"[Dispatch] Failed to log OrderEvent for Order #{order.order_number}: {exc}")

    logger.info(
        f"[Dispatch] Order #{order.order_number} auto-assigned to rider '{best_rider.username}' "
        f"(active workload: {min_active_count})."
    )
    return best_rider
