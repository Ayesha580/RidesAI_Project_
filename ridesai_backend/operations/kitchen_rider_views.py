"""
Kitchen Display System (KDS) & Delivery Rider Dashboard APIs.
Enforces role-based permissions and strict multi-tenant isolation.
"""

import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, OrderEvent
from .printing.receipt_formatter import build_receipt_payload
from .services.dispatch_service import assign_best_rider

logger = logging.getLogger("operations.kds_rider")


def _get_user_company(request):
    """Extracts company from authenticated user, with dev fallback if needed."""
    if request.user and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


def _serialize_order_items(order):
    return [
        {
            "id": it.id,
            "name": it.item_name,
            "quantity": float(it.quantity),
            "unit_price": float(it.unit_price),
            "line_total": float(it.line_total),
        }
        for it in order.items.all()
    ]


class KitchenOrdersAPIView(APIView):
    """
    GET /api/kitchen/orders/
    Returns active kitchen orders for request.user.company in pending/new/confirmed/preparing status.
    Ordered by oldest first for FIFO kitchen preparation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_user_company(request)
        if not company:
            return Response({"detail": "User is not associated with an active company."}, status=status.HTTP_403_FORBIDDEN)

        # Active kitchen statuses
        kitchen_statuses = [
            Order.STATUS_NEW,
            Order.STATUS_PENDING,
            Order.STATUS_CONFIRMED,
            Order.STATUS_PREPARING,
        ]

        orders = (
            Order.objects.filter(company=company, status__in=kitchen_statuses)
            .select_related("assigned_rider")
            .prefetch_related("items")
            .order_by("created_at")
        )

        now = timezone.now()
        results = []
        for o in orders:
            elapsed_seconds = max(0, int((now - o.created_at).total_seconds()))
            elapsed_minutes = int(elapsed_seconds // 60)

            results.append({
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "status_display": o.get_status_display(),
                "created_at": o.created_at.isoformat(),
                "elapsed_minutes": elapsed_minutes,
                "source": o.source,
                "customer_name": o.customer_name or "Walk-in Customer",
                "customer_phone": o.customer_phone or "",
                "notes": o.notes or "",
                "has_notes": bool(o.notes and o.notes.strip()),
                "items": _serialize_order_items(o),
                "total": float(o.total or 0),
                "assigned_rider": {
                    "id": o.assigned_rider.id,
                    "name": o.assigned_rider.get_full_name() or o.assigned_rider.username,
                    "phone": o.assigned_rider.phone or "",
                } if o.assigned_rider else None,
            })

        return Response({
            "count": len(results),
            "company_name": company.name,
            "orders": results,
        })


class KitchenOrderStatusAPIView(APIView):
    """
    PATCH /api/kitchen/orders/<int:order_id>/status/
    Updates order preparation status (e.g. 'preparing' -> 'prepared').
    When status becomes 'prepared', automatically invokes auto-assignment.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        company = _get_user_company(request)
        if not company:
            return Response({"detail": "User is not associated with an active company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, pk=order_id, company=company)
        new_status = request.data.get("status", "").strip().lower()

        allowed_transitions = {
            Order.STATUS_PREPARING: "Preparing",
            Order.STATUS_PREPARED: "Prepared",
            Order.STATUS_READY: "Ready",
            Order.STATUS_CANCELLED: "Cancelled",
        }

        if new_status not in allowed_transitions:
            return Response(
                {"detail": f"Invalid kitchen status '{new_status}'. Allowed: {list(allowed_transitions.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = order.status
        from operations.order_state import is_valid_order_transition
        if not is_valid_order_transition(previous_status, new_status):
            return Response(
                {"error": f"Invalid status transition from '{previous_status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Audit event
        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=request.user,
            event_type="kitchen_status_updated",
            from_status=previous_status,
            to_status=new_status,
            note=f"Kitchen staff {request.user.username} updated status from {previous_status} to {new_status}",
        )

        # Trigger auto-assignment if marked prepared and unassigned
        assigned_rider = order.assigned_rider
        if new_status in (Order.STATUS_PREPARED, Order.STATUS_READY) and not assigned_rider:
            assigned_rider = assign_best_rider(order)

        # Dispatch automated customer WhatsApp notification
        from operations.notifications import send_order_status_notification
        send_order_status_notification(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            reason=request.data.get("reason") or request.data.get("note"),
        )

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_display": order.get_status_display(),
            "assigned_rider": {
                "id": assigned_rider.id,
                "name": assigned_rider.get_full_name() or assigned_rider.username,
                "phone": assigned_rider.phone or "",
            } if assigned_rider else None,
        })


class RiderOrdersAPIView(APIView):
    """
    GET /api/rider/orders/
    Returns active deliveries assigned to request.user (assigned_rider=request.user).
    Excludes delivered and cancelled orders.
    Includes customer address/phone and thermal receipt KOT data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_user_company(request)
        if not company:
            return Response({"detail": "User is not associated with an active company."}, status=status.HTTP_403_FORBIDDEN)

        # Exclude completed / cancelled deliveries
        excluded_statuses = [Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]

        orders = (
            Order.objects.filter(company=company, assigned_rider=request.user)
            .exclude(status__in=excluded_statuses)
            .prefetch_related("items")
            .order_by("-created_at")
        )

        results = []
        for o in orders:
            # Build thermal KOT payload for rider's digital slip
            kot_payload = build_receipt_payload(o, company=company, slip_type="kot")

            results.append({
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "status_display": o.get_status_display(),
                "created_at": o.created_at.isoformat(),
                "formatted_date": o.created_at.strftime("%b %d, %I:%M %p"),
                "customer_name": o.customer_name or "Customer",
                "customer_phone": o.customer_phone or "",
                "delivery_address": o.delivery_address or "Store Pickup",
                "total": float(o.total or 0),
                "notes": o.notes or "",
                "items": _serialize_order_items(o),
                "kot_data": kot_payload,
            })

        return Response({
            "count": len(results),
            "rider": {
                "id": request.user.id,
                "name": request.user.get_full_name() or request.user.username,
            },
            "orders": results,
        })


class RiderOrderStatusAPIView(APIView):
    """
    PATCH /api/rider/orders/<int:order_id>/status/
    Allows rider to update delivery status:
    - 'out_for_delivery' (or 'picked_up', 'on_the_way')
    - 'delivered'
    Strictly restricted to the order's assigned rider.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        company = _get_user_company(request)
        if not company:
            return Response({"detail": "User is not associated with an active company."}, status=status.HTTP_403_FORBIDDEN)

        # Rider can only update orders assigned to THEM
        order = get_object_or_404(Order, pk=order_id, company=company, assigned_rider=request.user)
        new_status = request.data.get("status", "").strip().lower()

        allowed_rider_statuses = {
            Order.STATUS_OUT_FOR_DELIVERY: "Out for Delivery",
            Order.STATUS_ON_THE_WAY: "Out for Delivery",
            Order.STATUS_PICKED_UP: "Picked Up",
            Order.STATUS_DELIVERED: "Delivered",
        }

        if new_status not in allowed_rider_statuses:
            return Response(
                {"detail": f"Invalid rider delivery status '{new_status}'. Allowed: {list(allowed_rider_statuses.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = order.status
        from operations.order_state import is_valid_order_transition
        if not is_valid_order_transition(previous_status, new_status):
            return Response(
                {"error": f"Invalid status transition from '{previous_status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Audit event
        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=request.user,
            event_type="rider_status_updated",
            from_status=previous_status,
            to_status=new_status,
            note=f"Rider {request.user.username} updated delivery status to {new_status}",
        )

        # Dispatch automated customer WhatsApp notification
        from operations.notifications import send_order_status_notification
        send_order_status_notification(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            reason=request.data.get("reason") or request.data.get("note"),
        )

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_display": order.get_status_display(),
        })
