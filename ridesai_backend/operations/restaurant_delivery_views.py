"""
Restaurant Deliveries, Live Rider Dispatch & COD Reconciliation APIs.

Strictly scoped to request.user.company and order_type="delivery".
"""

from decimal import Decimal
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response

from accounts.models import User
from .models import DeliveryAssignment, Order, OrderEvent
from .views import BusinessAPIView


ACTIVE_RIDER_ORDER_STATUSES = (
    Order.STATUS_NEW,
    Order.STATUS_PENDING,
    Order.STATUS_CONFIRMED,
    Order.STATUS_PREPARING,
    Order.STATUS_PREPARED,
    Order.STATUS_READY,
    Order.STATUS_ASSIGNED,
    Order.STATUS_PICKED_UP,
    Order.STATUS_ON_THE_WAY,
    Order.STATUS_OUT_FOR_DELIVERY,
)

PENDING_DISPATCH_STATUSES = (
    Order.STATUS_NEW,
    Order.STATUS_PENDING,
    Order.STATUS_CONFIRMED,
    Order.STATUS_PREPARING,
    Order.STATUS_PREPARED,
    Order.STATUS_READY,
    Order.STATUS_ASSIGNED,
)

IN_TRANSIT_STATUSES = (
    Order.STATUS_PICKED_UP,
    Order.STATUS_ON_THE_WAY,
    Order.STATUS_OUT_FOR_DELIVERY,
)


def _get_company_riders(company):
    """Return all active delivery riders for the tenant."""
    rider_role_q = (
        Q(role="rider")
        | Q(staff_role__name__iexact="rider")
        | Q(staff_role__name__iexact="delivery boy")
        | Q(staff_role__name__iexact="delivery")
        | Q(staff_role__name__iexact="driver")
    )
    candidates = (
        User.objects.filter(company=company, is_active=True)
        .select_related("staff_role")
        .order_by("id")
    )
    by_id = {}
    for user in candidates.filter(rider_role_q):
        by_id[user.id] = user
    for user in candidates.filter(role=User.ROLE_STAFF, staff_role__is_active=True):
        if user.id not in by_id and user.has_business_permission("deliveries.view_assigned"):
            by_id[user.id] = user
    return [by_id[uid] for uid in sorted(by_id.keys())]


def _rider_display_name(rider):
    if not rider:
        return ""
    full = f"{getattr(rider, 'first_name', '')} {getattr(rider, 'last_name', '')}".strip()
    return full or getattr(rider, "username", "") or getattr(rider, "email", "")


def select_best_available_rider(company, exclude_order_id=None):
    """
    Smart Fairness Rider Selection:
    1. Only active delivery riders belonging to `company`.
    2. Fewest currently active delivery orders (excluding `exclude_order_id`).
    3. Fewest completed (delivered) orders today (fairness tie-breaker).
    4. Lowest rider.id as deterministic final tie-breaker.
    """
    riders = _get_company_riders(company)
    if not riders:
        return None

    today = timezone.localdate()
    scored = []
    for rider in riders:
        active_qs = Order.objects.filter(
            company=company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            assigned_rider=rider,
            status__in=ACTIVE_RIDER_ORDER_STATUSES,
        )
        if exclude_order_id is not None:
            active_qs = active_qs.exclude(pk=exclude_order_id)
        active_count = active_qs.count()

        completed_today_count = (
            Order.objects.filter(
                company=company,
                order_type=Order.ORDER_TYPE_DELIVERY,
                assigned_rider=rider,
                status=Order.STATUS_DELIVERED,
            )
            .filter(Q(delivered_at__date=today) | Q(delivered_at__isnull=True, updated_at__date=today))
            .count()
        )
        scored.append((active_count, completed_today_count, rider.id, rider))

    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    return scored[0][3]


def auto_assign_delivery_order_if_enabled(order, actor=None):
    """
    Automatically assigns the best available rider to a newly created delivery order
    when the company's `auto_dispatch_enabled` setting is True.
    """
    if not order or order.order_type != Order.ORDER_TYPE_DELIVERY:
        return None
    if order.assigned_rider_id is not None:
        return order.assigned_rider

    company = getattr(order, "company", None)
    if not company or not getattr(company, "auto_dispatch_enabled", True):
        return None

    rider = select_best_available_rider(company, exclude_order_id=order.id)
    if not rider:
        return None

    order.assigned_rider = rider
    order.save(update_fields=["assigned_rider", "updated_at"])

    DeliveryAssignment.objects.update_or_create(
        order=order,
        defaults={
            "company": company,
            "rider": rider,
            "assigned_by": actor,
            "status": order.status,
        },
    )

    OrderEvent.objects.create(
        company=company,
        order=order,
        actor=actor,
        event_type="rider_smart_auto_assigned",
        from_status=order.status,
        to_status=order.status,
        note=f"Smart Auto-Dispatch assigned to {_rider_display_name(rider)}",
        metadata={"rider_id": rider.id, "auto_dispatch": True},
    )
    return rider


def _serialize_delivery_order(order):
    rider = order.assigned_rider
    if not rider:
        assignment = getattr(order, "delivery", None)
        rider = getattr(assignment, "rider", None) if assignment else None

    items_data = []
    for item in order.items.all():
        items_data.append({
            "id": item.id,
            "item_name": item.item_name,
            "quantity": float(item.quantity),
            "unit_price": str(item.unit_price),
            "line_total": str(item.line_total),
            "selected_modifiers": item.selected_modifiers or [],
            "item_notes": item.item_notes or "",
        })

    delivery_minutes = None
    if order.delivered_at:
        start_ts = order.dispatched_at or order.created_at
        if start_ts and order.delivered_at >= start_ts:
            delivery_minutes = round((order.delivered_at - start_ts).total_seconds() / 60.0, 1)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "order_type": order.order_type,
        "status": order.status,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "delivery_address": order.delivery_address,
        "subtotal": str(order.subtotal),
        "delivery_fee": str(order.delivery_fee),
        "total": str(order.total),
        "total_amount": float(order.total or 0),
        "notes": order.notes,
        "source": order.source,
        "assigned_rider_id": rider.id if rider else None,
        "assigned_rider_name": _rider_display_name(rider),
        "assigned_rider_phone": getattr(rider, "phone", "") or "" if rider else "",
        "cod_collected": bool(order.cod_collected),
        "cod_settled": bool(order.cod_settled),
        "cod_settled_at": order.cod_settled_at.isoformat() if order.cod_settled_at else None,
        "dispatched_at": order.dispatched_at.isoformat() if order.dispatched_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "delivery_minutes": delivery_minutes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": items_data,
    }


class RestaurantDeliveryBoardAPIView(BusinessAPIView):
    """
    GET /api/operations/restaurant/deliveries/?status=all|unassigned|active|delivered|cancelled&date=today|all
    Returns KPIs, active riders with workload & unsettled COD cash, and filtered delivery orders.
    """

    required_business_permission = None

    def get(self, request):
        company = self.company
        status_filter = str(request.query_params.get("status", "all")).strip().lower()
        date_filter = str(request.query_params.get("date", "all")).strip().lower()
        today = timezone.localdate()

        base_qs = (
            Order.objects.filter(company=company, order_type=Order.ORDER_TYPE_DELIVERY)
            .select_related("assigned_rider", "delivery__rider")
            .prefetch_related("items")
            .order_by("-created_at")
        )

        # --- KPI Summary ---
        pending_dispatch = base_qs.filter(status__in=PENDING_DISPATCH_STATUSES).count()
        out_for_delivery = base_qs.filter(status__in=IN_TRANSIT_STATUSES).count()

        delivered_today_qs = base_qs.filter(status=Order.STATUS_DELIVERED).filter(
            Q(delivered_at__date=today) | Q(delivered_at__isnull=True, updated_at__date=today)
        )
        delivered_today = delivered_today_qs.count()

        # Average delivery duration (minutes)
        durations = []
        for row in delivered_today_qs.values("dispatched_at", "delivered_at", "created_at"):
            delivered_at = row["delivered_at"]
            if delivered_at:
                start_ts = row["dispatched_at"] or row["created_at"]
                if start_ts and delivered_at >= start_ts:
                    durations.append((delivered_at - start_ts).total_seconds() / 60.0)
        if not durations:
            recent_delivered = base_qs.filter(
                status=Order.STATUS_DELIVERED, delivered_at__isnull=False
            ).values("dispatched_at", "delivered_at", "created_at")[:50]
            for row in recent_delivered:
                delivered_at = row["delivered_at"]
                start_ts = row["dispatched_at"] or row["created_at"]
                if start_ts and delivered_at >= start_ts:
                    durations.append((delivered_at - start_ts).total_seconds() / 60.0)
        avg_delivery_minutes = round(sum(durations) / len(durations), 1) if durations else 0.0

        unsettled_cod_qs = base_qs.filter(
            status=Order.STATUS_DELIVERED,
            cod_collected=True,
            cod_settled=False,
        )
        unsettled_cod_agg = unsettled_cod_qs.aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        # --- Riders & COD Ledger ---
        riders = _get_company_riders(company)
        rider_map = {r.id: r for r in riders}

        # Include any rider who has unsettled COD orders even if their role changed
        for o in unsettled_cod_qs.select_related("assigned_rider"):
            if o.assigned_rider_id and o.assigned_rider_id not in rider_map:
                rider_map[o.assigned_rider_id] = o.assigned_rider

        riders_payload = []
        for rid, rider in rider_map.items():
            rider_orders = base_qs.filter(assigned_rider_id=rid)
            active_count = rider_orders.filter(status__in=ACTIVE_RIDER_ORDER_STATUSES).count()
            completed_today = rider_orders.filter(status=Order.STATUS_DELIVERED).filter(
                Q(delivered_at__date=today) | Q(delivered_at__isnull=True, updated_at__date=today)
            ).count()
            rider_unsettled = unsettled_cod_qs.filter(assigned_rider_id=rid)
            rider_unsettled_ids = list(rider_unsettled.values_list("id", flat=True))
            rider_unsettled_total = rider_unsettled.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
            riders_payload.append({
                "id": rider.id,
                "name": _rider_display_name(rider),
                "username": rider.username,
                "phone": getattr(rider, "phone", "") or "",
                "active_deliveries": active_count,
                "completed_today": completed_today,
                "unsettled_cod_count": len(rider_unsettled_ids),
                "unsettled_cod_total": float(rider_unsettled_total),
                "unsettled_order_ids": rider_unsettled_ids,
            })

        # Also surface any delivered unsettled COD orders with no rider assigned
        unassigned_cod = unsettled_cod_qs.filter(assigned_rider__isnull=True)
        unassigned_cod_ids = list(unassigned_cod.values_list("id", flat=True))
        unassigned_cod_total = unassigned_cod.aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        # --- Filtered Orders List ---
        orders_qs = base_qs
        if date_filter == "today":
            orders_qs = orders_qs.filter(
                Q(created_at__date=today) | Q(delivered_at__date=today)
            )

        if status_filter == "unassigned":
            orders_qs = orders_qs.filter(assigned_rider__isnull=True).exclude(
                status__in=(Order.STATUS_DELIVERED, Order.STATUS_CANCELLED)
            )
        elif status_filter in ("active", "out_for_delivery"):
            orders_qs = orders_qs.filter(status__in=IN_TRANSIT_STATUSES)
        elif status_filter == "pending":
            orders_qs = orders_qs.filter(status__in=PENDING_DISPATCH_STATUSES)
        elif status_filter == "delivered":
            orders_qs = orders_qs.filter(status=Order.STATUS_DELIVERED)
        elif status_filter == "cancelled":
            orders_qs = orders_qs.filter(status=Order.STATUS_CANCELLED)

        orders_data = [_serialize_delivery_order(o) for o in orders_qs[:200]]

        return Response({
            "auto_dispatch_enabled": bool(getattr(company, "auto_dispatch_enabled", True)),
            "kpis": {
                "pending_dispatch": pending_dispatch,
                "out_for_delivery": out_for_delivery,
                "delivered_today": delivered_today,
                "avg_delivery_minutes": avg_delivery_minutes,
                "unsettled_cod_total": float(unsettled_cod_agg),
                "unsettled_cod_count": unsettled_cod_qs.count(),
            },
            "riders": riders_payload,
            "unassigned_cod": {
                "count": len(unassigned_cod_ids),
                "total": float(unassigned_cod_total),
                "order_ids": unassigned_cod_ids,
            },
            "orders": orders_data,
        })


class RestaurantDeliveryAssignAPIView(BusinessAPIView):
    """
    POST /api/operations/restaurant/deliveries/<order_id>/assign/
    Body: { "rider_id": <id> } OR { "auto": true }, optional "mark_out_for_delivery": true
    """

    required_business_permission = None

    def post(self, request, order_id):
        company = self.company
        order = get_object_or_404(
            Order.objects.select_related("assigned_rider").prefetch_related("items"),
            pk=order_id,
            company=company,
        )
        if order.order_type != Order.ORDER_TYPE_DELIVERY:
            return Response({"detail": "Only delivery orders can be assigned to a rider."}, status=400)
        if order.status in (Order.STATUS_DELIVERED, Order.STATUS_CANCELLED):
            return Response({"detail": f"Cannot assign a rider to a {order.status} order."}, status=409)

        raw_auto = request.data.get("auto")
        auto = raw_auto is True or (isinstance(raw_auto, str) and raw_auto.strip().lower() == "true")
        rider_id = request.data.get("rider_id")
        raw_mark_out = request.data.get("mark_out_for_delivery")
        mark_out = raw_mark_out is True or (isinstance(raw_mark_out, str) and raw_mark_out.strip().lower() == "true")

        if rider_id is not None and str(rider_id).strip() != "" and not auto:
            rider = get_object_or_404(User, pk=rider_id, company=company, is_active=True)
        elif auto:
            rider = select_best_available_rider(company, exclude_order_id=order.id)
            if not rider:
                return Response(
                    {"detail": "No active riders available. Please add a rider in Staff / Employees."},
                    status=400,
                )
        else:
            return Response({"detail": "Provide rider_id or set auto=true."}, status=400)

        previous_status = order.status
        now_ts = timezone.now()
        update_fields = ["assigned_rider", "updated_at"]
        order.assigned_rider = rider

        if mark_out:
            order.status = Order.STATUS_OUT_FOR_DELIVERY
            update_fields.append("status")
            if not order.dispatched_at:
                order.dispatched_at = now_ts
                update_fields.append("dispatched_at")
        elif order.status in (
            Order.STATUS_NEW,
            Order.STATUS_PENDING,
            Order.STATUS_CONFIRMED,
            Order.STATUS_PREPARING,
            Order.STATUS_PREPARED,
            Order.STATUS_READY,
        ):
            order.status = Order.STATUS_ASSIGNED
            update_fields.append("status")

        order.save(update_fields=update_fields)

        DeliveryAssignment.objects.update_or_create(
            order=order,
            defaults={
                "company": company,
                "rider": rider,
                "assigned_by": request.user,
                "status": order.status,
            },
        )
        # Ensure fresh relation data (including updated DeliveryAssignment) before serializing
        order = (
            Order.objects.select_related("assigned_rider", "delivery__rider")
            .prefetch_related("items")
            .get(pk=order.pk)
        )

        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=request.user,
            event_type="rider_auto_assigned" if auto else "rider_assigned",
            from_status=previous_status,
            to_status=order.status,
            note=f"Assigned to {_rider_display_name(rider)}",
            metadata={"rider_id": rider.id, "auto": auto},
        )

        if order.status != previous_status:
            try:
                from operations.notifications import send_order_status_notification
                send_order_status_notification(
                    order=order,
                    previous_status=previous_status,
                    new_status=order.status,
                )
            except Exception:
                pass

        rider_name = _rider_display_name(rider)
        return Response({
            "success": True,
            "assigned_rider_id": rider.id,
            "assigned_rider_name": rider_name,
            "order": _serialize_delivery_order(order),
            "rider": {
                "id": rider.id,
                "name": rider_name,
                "phone": getattr(rider, "phone", "") or "",
            },
        })


class RestaurantDeliveryStatusAPIView(BusinessAPIView):
    """
    POST /api/operations/restaurant/deliveries/<order_id>/status/
    1-click delivery lifecycle transition: out_for_delivery | delivered | cancelled.
    """

    required_business_permission = None

    ALLOWED_TARGETS = {
        Order.STATUS_ASSIGNED,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    }

    def post(self, request, order_id):
        company = self.company
        order = get_object_or_404(
            Order.objects.select_related("assigned_rider").prefetch_related("items"),
            pk=order_id,
            company=company,
        )
        if order.order_type != Order.ORDER_TYPE_DELIVERY:
            return Response({"detail": "Only delivery orders can be updated via dispatch."}, status=400)

        next_status = str(request.data.get("status") or "").strip().lower()
        note = str(request.data.get("note") or "").strip()
        if next_status not in self.ALLOWED_TARGETS:
            return Response(
                {"detail": f"Invalid delivery status '{next_status}'. Allowed: out_for_delivery, delivered, cancelled."},
                status=400,
            )

        previous_status = order.status
        now_ts = timezone.now()
        order.status = next_status
        update_fields = ["status", "updated_at"]

        if next_status in (Order.STATUS_OUT_FOR_DELIVERY, Order.STATUS_ON_THE_WAY):
            if not order.dispatched_at:
                order.dispatched_at = now_ts
                update_fields.append("dispatched_at")
        elif next_status == Order.STATUS_DELIVERED:
            if not order.delivered_at:
                order.delivered_at = now_ts
                update_fields.append("delivered_at")
            if not order.cod_collected:
                order.cod_collected = True
                update_fields.append("cod_collected")

        order.save(update_fields=update_fields)
        DeliveryAssignment.objects.filter(order=order).update(status=next_status)

        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=request.user,
            event_type="delivery_status_changed",
            from_status=previous_status,
            to_status=next_status,
            note=note,
        )

        if next_status == Order.STATUS_CANCELLED:
            try:
                from operations.restaurant_inventory_views import restore_recipe_ingredients_for_order
                restore_recipe_ingredients_for_order(order)
            except Exception:
                pass

        try:
            from operations.notifications import send_order_status_notification
            send_order_status_notification(
                order=order,
                previous_status=previous_status,
                new_status=next_status,
                reason=note or None,
            )
        except Exception:
            pass

        return Response({
            "success": True,
            "order": _serialize_delivery_order(order),
        })


class RestaurantDeliverySettleCODAPIView(BusinessAPIView):
    """
    POST /api/operations/restaurant/deliveries/settle-cod/
    Body: { "rider_id": <id> } OR { "order_ids": [<id>, ...] }
    Marks delivered, unsettled COD orders as settled and returns totals.
    """

    required_business_permission = None

    def post(self, request):
        company = self.company
        rider_id = request.data.get("rider_id")
        order_ids = request.data.get("order_ids")

        qs = Order.objects.filter(
            company=company,
            order_type=Order.ORDER_TYPE_DELIVERY,
            status=Order.STATUS_DELIVERED,
            cod_collected=True,
            cod_settled=False,
        )

        if rider_id is not None and str(rider_id).strip() != "":
            rider = get_object_or_404(User, pk=rider_id, company=company)
            qs = qs.filter(assigned_rider=rider)
        elif isinstance(order_ids, list) and order_ids:
            qs = qs.filter(id__in=order_ids)
        else:
            return Response({"detail": "Provide rider_id or order_ids to settle COD cash."}, status=400)

        orders = list(qs)
        if not orders:
            return Response({
                "success": True,
                "settled_count": 0,
                "settled_amount": 0.0,
                "settled_at": None,
                "rider_id": int(rider_id) if rider_id is not None and str(rider_id).strip() != "" else None,
                "message": "No unsettled COD orders found.",
            })

        now_ts = timezone.now()
        settled_amount = sum((o.total or Decimal("0.00")) for o in orders)
        settled_ids = [o.id for o in orders]

        Order.objects.filter(id__in=settled_ids, company=company).update(
            cod_settled=True,
            cod_settled_at=now_ts,
            updated_at=now_ts,
        )

        events = [
            OrderEvent(
                company=company,
                order_id=o.id,
                actor=request.user,
                event_type="cod_settled",
                from_status=o.status,
                to_status=o.status,
                note=f"COD settled: Rs. {o.total}",
                metadata={"rider_id": o.assigned_rider_id, "amount": str(o.total)},
            )
            for o in orders
        ]
        OrderEvent.objects.bulk_create(events)

        return Response({
            "success": True,
            "settled_count": len(orders),
            "settled_amount": float(settled_amount),
            "settled_at": now_ts.isoformat(),
            "rider_id": int(rider_id) if rider_id is not None and str(rider_id).strip() != "" else None,
            "order_ids": settled_ids,
        })


class RestaurantDeliverySettingsAPIView(BusinessAPIView):
    """
    PATCH /api/operations/restaurant/deliveries/settings/
    Body: { "auto_dispatch_enabled": true | false }
    """

    required_business_permission = None

    def patch(self, request):
        company = self.company
        if "auto_dispatch_enabled" not in request.data:
            return Response({"detail": "Provide 'auto_dispatch_enabled' boolean."}, status=400)
        raw = request.data.get("auto_dispatch_enabled")
        if isinstance(raw, bool):
            enabled = raw
        elif isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
            enabled = raw.strip().lower() == "true"
        else:
            return Response({"detail": "'auto_dispatch_enabled' must be a boolean."}, status=400)

        company.auto_dispatch_enabled = enabled
        company.save(update_fields=["auto_dispatch_enabled"])
        return Response({
            "success": True,
            "auto_dispatch_enabled": company.auto_dispatch_enabled,
        })
