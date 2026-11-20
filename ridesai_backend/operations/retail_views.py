"""
Retail / Store Platform API Views: Fulfillment (Packing & Dispatch), Returns & Exchanges, and Inventory Alerts.

Strictly multi-tenant isolated to request.user.company.
Protected by IsAuthenticated.
"""

import logging
from decimal import Decimal
from typing import Optional

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import CatalogItem, Inventory
from operations.models import Order, OrderItem, ReturnRequest
from operations.order_state import is_valid_order_transition, get_allowed_next_statuses
from operations.notifications import send_status_notification

logger = logging.getLogger("operations.retail")


def _get_request_company(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


ALLOWED_RETURN_TRANSITIONS = {
    ReturnRequest.STATUS_PENDING: {
        ReturnRequest.STATUS_APPROVED,
        ReturnRequest.STATUS_REJECTED,
    },
    ReturnRequest.STATUS_APPROVED: {
        ReturnRequest.STATUS_COMPLETED,
    },
    ReturnRequest.STATUS_REJECTED: set(),
    ReturnRequest.STATUS_COMPLETED: set(),
}


STAGE_STATUS_MAP = {
    "to_pack": [Order.STATUS_NEW, Order.STATUS_PENDING, Order.STATUS_CONFIRMED],
    "packing": [Order.STATUS_PREPARING],
    "ready": [Order.STATUS_PREPARED, Order.STATUS_READY],
    "dispatched": [
        Order.STATUS_ASSIGNED,
        Order.STATUS_PICKED_UP,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_OUT_FOR_DELIVERY,
    ],
    "delivered": [Order.STATUS_DELIVERED],
    "cancelled": [Order.STATUS_CANCELLED],
}


def _get_order_stage(order_status: str) -> str:
    st = (order_status or "").strip().lower()
    for stage, statuses in STAGE_STATUS_MAP.items():
        if st in statuses:
            return stage
    return "other"


def _serialize_fulfillment_order(order: Order) -> dict:
    items = [
        {
            "id": oi.id,
            "item_id": oi.item_id,
            "item_name": oi.item_name,
            "quantity": float(oi.quantity),
            "unit_price": str(oi.unit_price),
            "line_total": str(oi.line_total),
        }
        for oi in order.items.all()
    ]
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_email": order.customer_email,
        "delivery_address": order.delivery_address,
        "status": order.status,
        "stage": _get_order_stage(order.status),
        "allowed_next_statuses": list(get_allowed_next_statuses(order.status)),
        "subtotal": str(order.subtotal),
        "delivery_fee": str(order.delivery_fee),
        "total": str(order.total),
        "notes": order.notes,
        "source": order.source,
        "assigned_to": order.assigned_to.email if order.assigned_to else None,
        "assigned_rider": order.assigned_rider.email if order.assigned_rider else None,
        "is_exchange": bool("EXCHANGE SWAP" in (order.notes or "") or order.exchange_requests.exists()),
        "items": items,
        "items_count": len(items),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def _serialize_return_request(ret: ReturnRequest) -> dict:
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "order_id": ret.order_id,
        "order_number": ret.order_number or (ret.order.order_number if ret.order else ""),
        "customer_name": ret.customer_name,
        "customer_phone": ret.customer_phone,
        "item_summary": ret.item_summary,
        "reason": ret.reason,
        "request_type": ret.request_type,
        "status": ret.status,
        "staff_notes": ret.staff_notes,
        "replacement_order_id": ret.replacement_order_id,
        "replacement_order_number": ret.replacement_order.order_number if ret.replacement_order else None,
        "allowed_next_statuses": list(ALLOWED_RETURN_TRANSITIONS.get(ret.status, set())),
        "created_at": ret.created_at.isoformat(),
        "updated_at": ret.updated_at.isoformat(),
    }


def complete_linked_exchanges_on_delivery(order: Order, company=None) -> list:
    """
    When an order transitions to 'delivered', check if it is linked as a replacement_order
    to any ReturnRequest(s) with request_type='exchange' and status='approved'.
    Automatically update their status to 'completed' and send WhatsApp completion notification.
    """
    if not order or (order.status or "").strip().lower() != Order.STATUS_DELIVERED:
        return []

    comp = company or getattr(order, "company", None)
    linked_requests = ReturnRequest.objects.filter(
        replacement_order=order,
        status=ReturnRequest.STATUS_APPROVED,
    )
    if comp:
        linked_requests = linked_requests.filter(company=comp)

    completed = []
    for ret in linked_requests:
        old_status = ret.status
        ret.status = ReturnRequest.STATUS_COMPLETED
        auto_note = f"Auto-completed upon delivery of replacement order #{order.order_number}."
        if ret.staff_notes:
            ret.staff_notes = f"{ret.staff_notes} | {auto_note}"
        else:
            ret.staff_notes = auto_note
        ret.save(update_fields=["status", "staff_notes", "updated_at"])
        completed.append(ret)

        if ret.customer_phone:
            try:
                send_status_notification(
                    company=comp or ret.company,
                    customer_phone=ret.customer_phone,
                    entity_type="exchange",
                    reference_id=ret.return_number,
                    new_status=ReturnRequest.STATUS_COMPLETED,
                    reason="Doorstep swap delivery completed",
                    previous_status=old_status,
                )
            except Exception as e:
                logger.warning(
                    "Failed to dispatch WhatsApp completion notification for exchange %s: %s",
                    ret.return_number, e
                )

    return completed


class RetailFulfillmentAPIView(APIView):
    """
    GET /api/retail/fulfillment/
    Lists orders for the retail packing & dispatch fulfillment board.
    Supports filtering by stage, status, or search query.
    Returns KPI counts across fulfillment stages.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Order.objects.filter(company=company).prefetch_related("items").select_related("assigned_to", "assigned_rider")

        # KPI counts across all company orders
        all_orders = list(qs)
        kpi_counts = {
            "total": len(all_orders),
            "to_pack": 0,
            "packing": 0,
            "ready": 0,
            "dispatched": 0,
            "delivered": 0,
            "cancelled": 0,
        }
        for o in all_orders:
            stage = _get_order_stage(o.status)
            if stage in kpi_counts:
                kpi_counts[stage] += 1

        # Apply filters
        stage_filter = request.query_params.get("stage", "").strip().lower()
        status_filter = request.query_params.get("status", "").strip().lower()
        search_query = request.query_params.get("search", "").strip()

        filtered_qs = qs
        if stage_filter and stage_filter in STAGE_STATUS_MAP:
            filtered_qs = filtered_qs.filter(status__in=STAGE_STATUS_MAP[stage_filter])
        elif status_filter:
            filtered_qs = filtered_qs.filter(status=status_filter)

        if search_query:
            filtered_qs = filtered_qs.filter(
                Q(order_number__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(delivery_address__icontains=search_query)
            )

        results = [_serialize_fulfillment_order(o) for o in filtered_qs]
        return Response({
            "kpis": kpi_counts,
            "count": len(results),
            "results": results,
        }, status=status.HTTP_200_OK)


class RetailFulfillmentStatusAPIView(APIView):
    """
    PATCH /api/retail/fulfillment/<order_id>/status/
    Updates an order's status enforcing the strict forward-only order state machine.
    Fires automated WhatsApp status notifications.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, pk=order_id, company=company)
        new_status = (request.data.get("status") or "").strip().lower()
        if not new_status:
            return Response({"detail": "Field 'status' is required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_choices = {c[0] for c in Order.STATUS_CHOICES}
        if new_status not in valid_choices:
            return Response({
                "detail": f"Invalid status '{new_status}'. Allowed: {sorted(list(valid_choices))}"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Enforce forward-only transition
        if not is_valid_order_transition(order.status, new_status):
            return Response({
                "detail": (
                    f"Invalid status transition from '{order.status}' to '{new_status}'. "
                    f"Allowed next: {list(get_allowed_next_statuses(order.status))}"
                )
            }, status=status.HTTP_400_BAD_REQUEST)

        old_status = order.status
        order.status = new_status

        # Optional notes or assignment updates
        if "notes" in request.data:
            order.notes = str(request.data.get("notes") or "").strip()

        order.save()

        # Fire automated WhatsApp notification
        notification_result = None
        if old_status != new_status and order.customer_phone:
            try:
                notification_result = send_status_notification(
                    company=company,
                    customer_phone=order.customer_phone,
                    entity_type="order",
                    reference_id=order.order_number,
                    new_status=new_status,
                    reason=order.notes,
                    previous_status=old_status,
                )
            except Exception as e:
                logger.warning("Failed to dispatch WhatsApp notification for order %s: %s", order.order_number, e)

        # Auto-complete linked exchange requests if delivered
        if new_status == Order.STATUS_DELIVERED:
            complete_linked_exchanges_on_delivery(order, company=company)

        return Response({
            "detail": f"Order status updated from {old_status} to {new_status}.",
            "order": _serialize_fulfillment_order(order),
            "notification_sent": bool(notification_result),
        }, status=status.HTTP_200_OK)


class RetailReturnsAPIView(APIView):
    """
    GET /api/retail/returns/
    Lists returns and exchanges with KPI counts and status/type/search filtering.

    POST /api/retail/returns/
    Creates a new return or exchange request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = ReturnRequest.objects.filter(company=company).select_related("order")

        # KPI counts
        all_reqs = list(qs)
        kpi_counts = {
            "total": len(all_reqs),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "return_type": 0,
            "exchange_type": 0,
        }
        for r in all_reqs:
            if r.status in kpi_counts:
                kpi_counts[r.status] += 1
            if r.request_type == ReturnRequest.TYPE_RETURN:
                kpi_counts["return_type"] += 1
            elif r.request_type == ReturnRequest.TYPE_EXCHANGE:
                kpi_counts["exchange_type"] += 1

        # Apply filters
        status_filter = request.query_params.get("status", "").strip().lower()
        type_filter = request.query_params.get("request_type", "").strip().lower()
        search_query = request.query_params.get("search", "").strip()

        filtered_qs = qs
        if status_filter:
            filtered_qs = filtered_qs.filter(status=status_filter)
        if type_filter:
            filtered_qs = filtered_qs.filter(request_type=type_filter)
        if search_query:
            filtered_qs = filtered_qs.filter(
                Q(return_number__icontains=search_query) |
                Q(order_number__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(item_summary__icontains=search_query) |
                Q(reason__icontains=search_query)
            )

        results = [_serialize_return_request(r) for r in filtered_qs]
        return Response({
            "kpis": kpi_counts,
            "count": len(results),
            "results": results,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        customer_phone = str(data.get("customer_phone") or "").strip()
        reason = str(data.get("reason") or "").strip()

        if not customer_phone:
            return Response({"detail": "Field 'customer_phone' is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not reason:
            return Response({"detail": "Field 'reason' is required."}, status=status.HTTP_400_BAD_REQUEST)

        customer_name = str(data.get("customer_name") or "").strip()
        order_number = str(data.get("order_number") or "").strip()
        item_summary = str(data.get("item_summary") or "").strip()
        request_type = str(data.get("request_type") or ReturnRequest.TYPE_RETURN).strip().lower()
        staff_notes = str(data.get("staff_notes") or "").strip()

        if request_type not in (ReturnRequest.TYPE_RETURN, ReturnRequest.TYPE_EXCHANGE):
            request_type = ReturnRequest.TYPE_RETURN

        # Match existing order if order_number provided
        matched_order = None
        if order_number:
            matched_order = Order.objects.filter(company=company, order_number__iexact=order_number).first()
            if matched_order and not customer_name:
                customer_name = matched_order.customer_name

        ret = ReturnRequest.objects.create(
            company=company,
            order=matched_order,
            order_number=order_number,
            customer_name=customer_name,
            customer_phone=customer_phone,
            item_summary=item_summary,
            reason=reason,
            request_type=request_type,
            status=ReturnRequest.STATUS_PENDING,
            staff_notes=staff_notes,
        )

        return Response({
            "detail": f"{request_type.title()} request {ret.return_number} created successfully.",
            "return_request": _serialize_return_request(ret),
        }, status=status.HTTP_201_CREATED)


class RetailReturnStatusAPIView(APIView):
    """
    PATCH /api/retail/returns/<id>/status/
    Transitions return/exchange status forward:
      pending -> approved | rejected
      approved -> completed
    Sends automated WhatsApp notification to customer.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        ret = get_object_or_404(ReturnRequest, pk=pk, company=company)
        new_status = (request.data.get("status") or "").strip().lower()
        if not new_status:
            return Response({"detail": "Field 'status' is required."}, status=status.HTTP_400_BAD_REQUEST)

        allowed_next = ALLOWED_RETURN_TRANSITIONS.get(ret.status, set())
        if new_status not in allowed_next:
            return Response({
                "detail": (
                    f"Invalid status transition from '{ret.status}' to '{new_status}'. "
                    f"Allowed next: {list(allowed_next)}"
                )
            }, status=status.HTTP_400_BAD_REQUEST)

        old_status = ret.status
        ret.status = new_status

        reason_text = ""
        if "staff_notes" in request.data:
            ret.staff_notes = str(request.data.get("staff_notes") or "").strip()
            reason_text = ret.staff_notes
        if "reason" in request.data and not reason_text:
            reason_text = str(request.data.get("reason") or "").strip()

        # Auto-create Replacement Order on Exchange Approval
        if (
            ret.request_type == ReturnRequest.TYPE_EXCHANGE
            and new_status == ReturnRequest.STATUS_APPROVED
            and not ret.replacement_order
        ):
            delivery_addr = ""
            if ret.order and ret.order.delivery_address:
                delivery_addr = ret.order.delivery_address
            if not delivery_addr:
                delivery_addr = "Customer address (confirm via phone)"

            notes_msg = (
                f"🔄 EXCHANGE SWAP ({ret.return_number}): Deliver replacement item(s) "
                f"[{ret.item_summary or 'replacement item'}] and collect original/damaged item from customer."
            )

            replacement_order = Order.objects.create(
                company=company,
                status=Order.STATUS_CONFIRMED,
                customer_name=ret.customer_name or (ret.order.customer_name if ret.order else "Valued Customer"),
                customer_phone=ret.customer_phone or (ret.order.customer_phone if ret.order else ""),
                customer_email=ret.order.customer_email if ret.order else "",
                delivery_address=delivery_addr,
                subtotal=Decimal("0.00"),
                delivery_fee=Decimal("0.00"),
                total=Decimal("0.00"),
                notes=notes_msg,
                source="dashboard",
            )

            # Copy line items if available or create line item
            copied_items = False
            if ret.order and ret.order.items.exists():
                matching_items = []
                summary_lower = (ret.item_summary or "").lower()
                for oi in ret.order.items.all():
                    if summary_lower and (oi.item_name.lower() in summary_lower or summary_lower in oi.item_name.lower()):
                        matching_items.append(oi)
                target_items = matching_items if matching_items else list(ret.order.items.all())
                for oi in target_items:
                    OrderItem.objects.create(
                        order=replacement_order,
                        item=oi.item,
                        item_name=oi.item_name,
                        quantity=oi.quantity,
                        unit_price=Decimal("0.00"),
                        line_total=Decimal("0.00"),
                    )
                    copied_items = True

            if not copied_items:
                OrderItem.objects.create(
                    order=replacement_order,
                    item=None,
                    item_name=ret.item_summary or "Exchange Replacement Item",
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("0.00"),
                    line_total=Decimal("0.00"),
                )

            ret.replacement_order = replacement_order

        ret.save()

        # Fire WhatsApp notification
        notification_result = None
        if ret.customer_phone:
            try:
                notification_result = send_status_notification(
                    company=company,
                    customer_phone=ret.customer_phone,
                    entity_type=ret.request_type,
                    reference_id=ret.return_number,
                    new_status=new_status,
                    reason=reason_text or ret.reason,
                    previous_status=old_status,
                    replacement_order_number=(
                        ret.replacement_order.order_number if ret.replacement_order else None
                    ),
                )
            except Exception as e:
                logger.warning("Failed to dispatch WhatsApp notification for return %s: %s", ret.return_number, e)

        return Response({
            "detail": f"Return request status updated from {old_status} to {new_status}.",
            "return_request": _serialize_return_request(ret),
            "replacement_order_number": ret.replacement_order.order_number if ret.replacement_order else None,
            "notification_sent": bool(notification_result),
        }, status=status.HTTP_200_OK)


class RetailInventoryAlertsAPIView(APIView):
    """
    GET /api/retail/inventory-alerts/
    Returns items with low stock (<= 10 or <= low_stock_threshold) and out of stock (<= 0).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        items = CatalogItem.objects.filter(company=company).select_related("inventory", "category")

        low_stock_items = []
        out_of_stock_items = []

        for item in items:
            inv = getattr(item, "inventory", None)
            if inv is None:
                # If no inventory record, check is_available
                if not item.is_available:
                    out_of_stock_items.append({
                        "id": item.id,
                        "name": item.name,
                        "sku": item.sku,
                        "brand": item.brand,
                        "category": item.category.name if item.category else "",
                        "price": str(item.price),
                        "stock_quantity": 0,
                        "threshold": 5,
                        "is_available": item.is_available,
                    })
                continue

            if inv.is_unlimited:
                continue

            qty = float(inv.quantity)
            threshold = float(inv.low_stock_threshold or 10)

            item_data = {
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "brand": item.brand,
                "category": item.category.name if item.category else "",
                "price": str(item.price),
                "stock_quantity": qty,
                "threshold": threshold,
                "is_available": item.is_available,
            }

            if qty <= 0 or not item.is_available:
                out_of_stock_items.append(item_data)
            elif qty <= threshold or qty <= 10:
                low_stock_items.append(item_data)

        total_alerts = len(low_stock_items) + len(out_of_stock_items)
        return Response({
            "kpis": {
                "total_alerts": total_alerts,
                "low_stock_count": len(low_stock_items),
                "out_of_stock_count": len(out_of_stock_items),
            },
            "low_stock": low_stock_items,
            "out_of_stock": out_of_stock_items,
        }, status=status.HTTP_200_OK)
