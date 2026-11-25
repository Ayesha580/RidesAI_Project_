"""
Restaurant Modifiers Helper & Live Kitchen Display System (KDS) APIs.
Strictly multi-tenant (scoped to `request.user.company`) and PostgreSQL 16 compatible.

Endpoints:
- GET  /api/operations/restaurant/kds/?station=all|general|grill|fryer|drinks|dessert
- POST /api/operations/restaurant/kds/<order_id>/bump/
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import DeliveryAssignment, Order, OrderEvent

KDS_ACTIVE_STATUSES = [
    Order.STATUS_NEW,
    Order.STATUS_PENDING,
    Order.STATUS_CONFIRMED,
    Order.STATUS_PREPARING,
    Order.STATUS_READY,
]

VALID_STATIONS = {"all", "general", "grill", "fryer", "drinks", "dessert"}


def _to_decimal(val: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return default


def normalize_selected_modifiers(
    catalog_item,
    raw_modifiers: Any,
    fallback_text: str = "",
) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Normalizes `selected_modifiers` against `catalog_item.modifiers_schema` (when available)
    and computes the per-unit modifier price delta.

    Also performs deterministic fallback scanning on `fallback_text` (e.g., item_notes,
    special_instructions, order notes, or requested item_name) against every option in
    `catalog_item.modifiers_schema` so paid add-ons/sizes can NEVER be undercharged.

    Accepts:
      - list of dicts: [{"group": "Add-ons", "name": "Extra Cheese", "price": 100}]
      - list of strings: ["Extra Cheese", "Large"] (matched case-insensitively to schema)
    Returns:
      (normalized_list, per_unit_delta_decimal)
    """
    import re

    schema_lookup: Dict[str, Dict[str, Any]] = {}
    schema = getattr(catalog_item, "modifiers_schema", None) or []
    if isinstance(schema, list):
        for grp in schema:
            if not isinstance(grp, dict):
                continue
            grp_name = str(grp.get("group") or grp.get("name") or "").strip()
            for opt in grp.get("options") or []:
                if not isinstance(opt, dict):
                    continue
                opt_name = str(opt.get("name") or "").strip()
                if opt_name:
                    schema_lookup[opt_name.lower()] = {
                        "group": grp_name,
                        "name": opt_name,
                        "price": round(float(_to_decimal(opt.get("price"), Decimal("0.00"))), 2),
                    }

    normalized: List[Dict[str, Any]] = []
    seen_keys = set()
    total_delta = Decimal("0.00")

    if raw_modifiers and isinstance(raw_modifiers, list):
        for entry in raw_modifiers:
            if isinstance(entry, str):
                key = entry.strip().lower()
                if not key or key in seen_keys:
                    continue
                matched = schema_lookup.get(key)
                if matched:
                    seen_keys.add(key)
                    normalized.append(dict(matched))
                    total_delta += _to_decimal(matched["price"])
                else:
                    seen_keys.add(key)
                    normalized.append({"group": "", "name": entry.strip(), "price": 0.0})
            elif isinstance(entry, dict):
                name = str(entry.get("name") or entry.get("option") or "").strip()
                if not name:
                    continue
                key = name.lower()
                if key in seen_keys:
                    continue
                matched = schema_lookup.get(key)
                if matched:
                    price_dec = _to_decimal(matched["price"])
                    grp_name = str(entry.get("group") or matched["group"] or "").strip()
                else:
                    price_dec = max(Decimal("0.00"), _to_decimal(entry.get("price"), Decimal("0.00")))
                    grp_name = str(entry.get("group") or "").strip()
                seen_keys.add(key)
                normalized.append({
                    "group": grp_name,
                    "name": matched["name"] if matched else name,
                    "price": round(float(price_dec), 2),
                })
                total_delta += price_dec

    # Deterministic fallback: scan fallback_text (item_notes / special_notes / item_name)
    # for any modifier option defined in catalog_item.modifiers_schema
    if fallback_text and schema_lookup:
        haystack = str(fallback_text).lower()
        for opt_key, opt_meta in schema_lookup.items():
            if opt_key in seen_keys:
                continue
            # Match whole word/phrase (case-insensitive)
            pattern = r"(?<!\w)" + re.escape(opt_key) + r"(?!\w)"
            if re.search(pattern, haystack):
                seen_keys.add(opt_key)
                normalized.append(dict(opt_meta))
                total_delta += _to_decimal(opt_meta["price"])

    return normalized, total_delta


def _serialize_kds_ticket(order: Order, now) -> Dict[str, Any]:
    elapsed_sec = max(0, int((now - order.created_at).total_seconds())) if order.created_at else 0
    elapsed_minutes = elapsed_sec // 60

    items_payload = []
    stations_set = set()
    for oi in order.items.all():
        station = (getattr(oi.item, "kitchen_station", None) or "general").strip().lower()
        stations_set.add(station)
        items_payload.append({
            "id": oi.id,
            "item_id": oi.item_id,
            "name": oi.item_name,
            "quantity": float(oi.quantity),
            "unit_price": round(float(oi.unit_price), 2),
            "line_total": round(float(oi.line_total), 2),
            "kitchen_station": station,
            "prep_time_minutes": getattr(oi.item, "prep_time_minutes", 15) if oi.item else 15,
            "selected_modifiers": oi.selected_modifiers or [],
            "item_notes": oi.item_notes or "",
        })

    if not stations_set:
        stations_set.add("general")

    table_num = order.table_number or (order.table.table_number if order.table else "")

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "order_type": order.order_type or Order.ORDER_TYPE_DELIVERY,
        "table_number": table_num,
        "table_id": order.table_id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "notes": order.notes or "",
        "total": round(float(order.total or 0), 2),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "prep_started_at": order.prep_started_at.isoformat() if order.prep_started_at else None,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
        "elapsed_minutes": elapsed_minutes,
        "stations": sorted(stations_set),
        "items": items_payload,
    }


class RestaurantKDSListAPIView(APIView):
    """GET /api/operations/restaurant/kds/?station=all|general|grill|fryer|drinks|dessert"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        station = (request.query_params.get("station") or "all").strip().lower()
        if station not in VALID_STATIONS:
            station = "all"

        now = timezone.now()
        active_orders = (
            Order.objects.filter(company=company, status__in=KDS_ACTIVE_STATUSES)
            .select_related("table")
            .prefetch_related("items__item")
            .order_by("created_at")
        )

        all_tickets = [_serialize_kds_ticket(o, now) for o in active_orders]

        station_counts = {
            "all": len(all_tickets),
            "general": 0,
            "grill": 0,
            "fryer": 0,
            "drinks": 0,
            "dessert": 0,
        }
        for t in all_tickets:
            for st in t["stations"]:
                if st in station_counts:
                    station_counts[st] += 1

        if station == "all":
            filtered_tickets = all_tickets
        else:
            filtered_tickets = [t for t in all_tickets if station in t["stations"]]

        return Response({
            "station": station,
            "station_counts": station_counts,
            "tickets": filtered_tickets,
        }, status=200)


class RestaurantKDSBumpAPIView(APIView):
    """
    POST /api/operations/restaurant/kds/<order_id>/bump/
    1-click kitchen status progression:
      - new / pending / confirmed -> preparing (sets prep_started_at)
      - preparing -> ready (sets ready_at)
      - ready -> out_for_delivery (delivery) OR delivered (dine_in / takeaway)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        order = get_object_or_404(
            Order.objects.select_related("table").prefetch_related("items__item"),
            pk=order_id,
            company=company,
        )
        previous = (order.status or "").strip().lower()
        now = timezone.now()

        if previous in (Order.STATUS_NEW, Order.STATUS_PENDING, Order.STATUS_CONFIRMED):
            next_status = Order.STATUS_PREPARING
            if not order.prep_started_at:
                order.prep_started_at = now
        elif previous == Order.STATUS_PREPARING:
            next_status = Order.STATUS_READY
            if not order.prep_started_at:
                order.prep_started_at = now
            if not order.ready_at:
                order.ready_at = now
        elif previous in (Order.STATUS_READY, Order.STATUS_PREPARED):
            if (order.order_type or Order.ORDER_TYPE_DELIVERY) in (
                Order.ORDER_TYPE_DINE_IN,
                Order.ORDER_TYPE_TAKEAWAY,
            ):
                next_status = Order.STATUS_DELIVERED
            else:
                next_status = Order.STATUS_OUT_FOR_DELIVERY
        else:
            return Response(
                {"detail": f"Order is already '{order.status}' and cannot be bumped further on KDS."},
                status=400,
            )

        order.status = next_status
        order.save(update_fields=["status", "prep_started_at", "ready_at", "updated_at"])
        DeliveryAssignment.objects.filter(order=order).update(status=next_status)
        OrderEvent.objects.create(
            company=company,
            order=order,
            actor=request.user,
            event_type="kds_bumped",
            from_status=previous,
            to_status=next_status,
            note="Bumped from Kitchen Display System",
        )

        # Trigger existing WhatsApp / email order status notification pipeline
        from operations.notifications import send_order_status_notification
        send_order_status_notification(
            order=order,
            previous_status=previous,
            new_status=next_status,
        )

        # Auto-free dine-in table when bumped to delivered/cancelled
        if next_status in (Order.STATUS_DELIVERED, Order.STATUS_CANCELLED):
            from operations.views import release_table_if_idle
            release_table_if_idle(order)

        return Response(_serialize_kds_ticket(order, now), status=200)
