"""
Restaurant Customers CRM, Guest Profiles, Segmentation & AI Personalization APIs.

Strictly scoped to request.user.company and PostgreSQL 16 compatible.
"""

from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone
from rest_framework.response import Response

from .customer_recall_views import PLACEHOLDER_NAMES, _normalize_phone_key
from .models import Order, RestaurantGuestProfile, TableReservation
from .views import BusinessAPIView

VIP_ORDER_THRESHOLD = 5
VIP_SPEND_THRESHOLD = Decimal("5000.00")
AT_RISK_DAYS = 30


def _clean_name(name: Optional[str]) -> str:
    val = (name or "").strip()
    if val.lower() in PLACEHOLDER_NAMES:
        return ""
    return val


def _compute_segment(
    total_orders: int,
    total_spend: Decimal,
    last_order_at,
    is_vip_override: bool,
    now_ts=None,
) -> str:
    now_ts = now_ts or timezone.now()
    if is_vip_override or total_orders >= VIP_ORDER_THRESHOLD or total_spend >= VIP_SPEND_THRESHOLD:
        return "vip"
    if total_orders >= 1 and last_order_at and (now_ts - last_order_at) > timedelta(days=AT_RISK_DAYS):
        return "at_risk"
    if total_orders >= 2:
        return "repeat"
    return "new"


def _aggregate_company_guests(company) -> Dict[str, Dict[str, Any]]:
    """
    Aggregates unique restaurant guests for `company` by normalized phone key
    across RestaurantGuestProfile, non-cancelled Orders, and TableReservations.
    """
    now_ts = timezone.now()
    guests: Dict[str, Dict[str, Any]] = {}

    def _ensure_bucket(norm_phone: str, raw_phone: str = "") -> Dict[str, Any]:
        if norm_phone not in guests:
            guests[norm_phone] = {
                "phone": norm_phone,
                "display_phone": (raw_phone or norm_phone).strip(),
                "name": "",
                "dietary_notes": "",
                "tags": [],
                "is_vip_override": False,
                "profile_id": None,
                "total_orders": 0,
                "total_spend": Decimal("0.00"),
                "last_order_at": None,
                "dish_counts": Counter(),
                "order_type_counts": Counter(),
                "reservations_count": 0,
                "last_reservation_at": None,
            }
        elif raw_phone and not guests[norm_phone]["display_phone"]:
            guests[norm_phone]["display_phone"] = raw_phone.strip()
        return guests[norm_phone]

    # 1. Saved guest profiles
    for prof in RestaurantGuestProfile.objects.filter(company=company):
        norm = _normalize_phone_key(prof.phone)
        if not norm:
            continue
        b = _ensure_bucket(norm, prof.display_phone or prof.phone)
        b["profile_id"] = prof.id
        if _clean_name(prof.name):
            b["name"] = prof.name.strip()
        if prof.display_phone:
            b["display_phone"] = prof.display_phone.strip()
        b["dietary_notes"] = prof.dietary_notes or ""
        b["tags"] = list(prof.tags) if isinstance(prof.tags, list) else []
        b["is_vip_override"] = bool(prof.is_vip_override)

    # 2. Orders (excluding cancelled for spend/order metrics)
    orders_qs = (
        Order.objects.filter(company=company)
        .exclude(status=Order.STATUS_CANCELLED)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    for order in orders_qs:
        norm = _normalize_phone_key(order.customer_phone)
        if not norm:
            continue
        b = _ensure_bucket(norm, order.customer_phone)
        if not b["name"]:
            cname = _clean_name(order.customer_name)
            if cname:
                b["name"] = cname
        b["total_orders"] += 1
        b["total_spend"] += order.total or Decimal("0.00")
        if order.created_at and (b["last_order_at"] is None or order.created_at > b["last_order_at"]):
            b["last_order_at"] = order.created_at
        if order.order_type:
            b["order_type_counts"][order.order_type] += 1
        for item in order.items.all():
            iname = (item.item_name or "").strip()
            if iname:
                qty = int(item.quantity) if item.quantity and item.quantity >= 1 else 1
                b["dish_counts"][iname] += qty

    # 3. Table Reservations
    for res in TableReservation.objects.filter(company=company).order_by("-reserved_at"):
        norm = _normalize_phone_key(res.customer_phone)
        if not norm:
            continue
        b = _ensure_bucket(norm, res.customer_phone)
        if not b["name"]:
            cname = _clean_name(res.customer_name)
            if cname:
                b["name"] = cname
        b["reservations_count"] += 1
        if res.reserved_at and (b["last_reservation_at"] is None or res.reserved_at > b["last_reservation_at"]):
            b["last_reservation_at"] = res.reserved_at

    # 4. Finalize computed fields
    result: Dict[str, Dict[str, Any]] = {}
    for norm, b in guests.items():
        total_orders = b["total_orders"]
        total_spend = b["total_spend"]
        avg_val = round(float(total_spend) / total_orders, 2) if total_orders > 0 else 0.0
        top_dishes = [
            {"name": dish_name, "count": count}
            for dish_name, count in b["dish_counts"].most_common(3)
        ]
        favorite_dish = top_dishes[0]["name"] if top_dishes else ""
        pref_type = (
            b["order_type_counts"].most_common(1)[0][0]
            if b["order_type_counts"]
            else ""
        )
        segment = _compute_segment(
            total_orders=total_orders,
            total_spend=total_spend,
            last_order_at=b["last_order_at"],
            is_vip_override=b["is_vip_override"],
            now_ts=now_ts,
        )
        result[norm] = {
            "phone": norm,
            "display_phone": b["display_phone"] or norm,
            "name": b["name"] or "Guest",
            "dietary_notes": b["dietary_notes"],
            "tags": b["tags"],
            "is_vip_override": b["is_vip_override"],
            "segment": segment,
            "total_orders": total_orders,
            "total_spend": round(float(total_spend), 2),
            "avg_order_value": avg_val,
            "last_order_at": b["last_order_at"].isoformat() if b["last_order_at"] else None,
            "favorite_dish": favorite_dish,
            "top_dishes": top_dishes,
            "preferred_order_type": pref_type,
            "reservations_count": b["reservations_count"],
            "last_reservation_at": (
                b["last_reservation_at"].isoformat() if b["last_reservation_at"] else None
            ),
        }
    return result


def build_returning_guest_ai_context(company, sender_phone: str) -> Optional[Dict[str, Any]]:
    """
    Lightweight lookup used by WhatsApp AI Agent to personalize replies for returning
    restaurant guests (favorite dish, past orders count, VIP status, dietary notes).
    Strictly scoped to `company`.
    """
    if not company or not sender_phone:
        return None
    norm = _normalize_phone_key(sender_phone)
    if not norm:
        return None

    profile = RestaurantGuestProfile.objects.filter(company=company, phone=norm).first()

    # Match non-cancelled orders whose normalized phone equals `norm`
    dish_counts: Counter = Counter()
    order_type_counts: Counter = Counter()
    total_orders = 0
    total_spend = Decimal("0.00")
    latest_name = ""
    last_order_at = None

    orders_qs = (
        Order.objects.filter(company=company)
        .exclude(status=Order.STATUS_CANCELLED)
        .exclude(customer_phone="")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    for order in orders_qs:
        if _normalize_phone_key(order.customer_phone) != norm:
            continue
        total_orders += 1
        total_spend += order.total or Decimal("0.00")
        if last_order_at is None:
            last_order_at = order.created_at
        if order.order_type:
            order_type_counts[order.order_type] += 1
        if not latest_name:
            cname = _clean_name(order.customer_name)
            if cname:
                latest_name = cname
        for item in order.items.all():
            iname = (item.item_name or "").strip()
            if iname:
                qty = int(item.quantity) if item.quantity and item.quantity >= 1 else 1
                dish_counts[iname] += qty

    dietary_notes = (profile.dietary_notes or "").strip() if profile else ""
    is_vip_override = bool(profile.is_vip_override) if profile else False
    tags = list(profile.tags) if (profile and isinstance(profile.tags, list)) else []
    guest_name = (_clean_name(profile.name) if profile else "") or latest_name

    if total_orders == 0 and not dietary_notes and not is_vip_override and not tags:
        return None

    favorite_dish = dish_counts.most_common(1)[0][0] if dish_counts else ""
    preferred_order_type = (
        order_type_counts.most_common(1)[0][0] if order_type_counts else ""
    )
    segment = _compute_segment(
        total_orders=total_orders,
        total_spend=total_spend,
        last_order_at=last_order_at,
        is_vip_override=is_vip_override,
    )
    return {
        "name": guest_name,
        "phone": norm,
        "total_orders": total_orders,
        "favorite_dish": favorite_dish,
        "dietary_notes": dietary_notes,
        "preferred_order_type": preferred_order_type,
        "tags": tags,
        "is_vip": segment == "vip",
        "segment": segment,
    }


def merge_guest_dietary_notes(company, customer_phone: str, existing_notes: str = "") -> str:
    """
    Looks up saved `dietary_notes` in `RestaurantGuestProfile` for `(company, normalized_phone)`.
    If non-empty and not already present (case-insensitive) in `existing_notes`, appends it cleanly
    so kitchen staff & KOT receipts always see the guest's dietary preferences.
    """
    base = (existing_notes or "").strip()
    if not company or not (customer_phone or "").strip():
        return base
    norm = _normalize_phone_key(customer_phone)
    if not norm:
        return base
    profile = RestaurantGuestProfile.objects.filter(company=company, phone=norm).only("dietary_notes").first()
    dietary = (profile.dietary_notes or "").strip() if profile else ""
    if not dietary:
        return base
    if dietary.lower() in base.lower():
        return base
    pref_tag = f"Guest Preference: {dietary}"
    return f"{base} | {pref_tag}" if base else pref_tag


def _build_guest_detail_payload(company, norm_phone: str) -> Optional[Dict[str, Any]]:
    guests = _aggregate_company_guests(company)
    summary = guests.get(norm_phone)
    if not summary:
        return None

    # Recent orders matching this normalized phone
    recent_orders = []
    for order in (
        Order.objects.filter(company=company)
        .exclude(customer_phone="")
        .prefetch_related("items")
        .order_by("-created_at")
    ):
        if _normalize_phone_key(order.customer_phone) != norm_phone:
            continue
        recent_orders.append({
            "id": order.id,
            "order_number": order.order_number,
            "order_type": order.order_type,
            "status": order.status,
            "subtotal": str(order.subtotal),
            "delivery_fee": str(order.delivery_fee),
            "total": str(order.total),
            "total_amount": float(order.total or 0),
            "delivery_address": order.delivery_address or "",
            "notes": order.notes or "",
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "items": [
                {
                    "id": it.id,
                    "item_name": it.item_name,
                    "quantity": float(it.quantity),
                    "unit_price": str(it.unit_price),
                    "line_total": str(it.line_total),
                    "selected_modifiers": it.selected_modifiers or [],
                }
                for it in order.items.all()
            ],
        })
        if len(recent_orders) >= 30:
            break

    # Recent table reservations matching this normalized phone
    recent_reservations = []
    for res in (
        TableReservation.objects.filter(company=company)
        .exclude(customer_phone="")
        .select_related("table")
        .order_by("-reserved_at")
    ):
        if _normalize_phone_key(res.customer_phone) != norm_phone:
            continue
        recent_reservations.append({
            "id": res.id,
            "customer_name": res.customer_name,
            "party_size": res.party_size,
            "reservation_date": res.reservation_date.isoformat() if res.reservation_date else None,
            "reservation_time": res.reservation_time.strftime("%H:%M") if res.reservation_time else "",
            "reserved_at": res.reserved_at.isoformat() if res.reserved_at else None,
            "status": res.status,
            "table_number": res.table.table_number if res.table else "",
            "special_requests": res.special_requests or "",
        })
        if len(recent_reservations) >= 20:
            break

    return {
        **summary,
        "orders": recent_orders,
        "reservations": recent_reservations,
    }


class RestaurantCustomersListAPIView(BusinessAPIView):
    """
    GET /api/operations/restaurant/customers/?segment=all|vip|repeat|new|at_risk&search=...
    """

    required_business_permission = None

    def get(self, request):
        company = self.company
        segment_filter = str(request.query_params.get("segment", "all")).strip().lower()
        search_q = str(request.query_params.get("search", "")).strip().lower()

        all_guests = list(_aggregate_company_guests(company).values())

        # KPI summary across all company guests
        total_guests = len(all_guests)
        vip_count = sum(1 for g in all_guests if g["segment"] == "vip")
        repeat_count = sum(1 for g in all_guests if g["segment"] == "repeat")
        at_risk_count = sum(1 for g in all_guests if g["segment"] == "at_risk")
        new_count = sum(1 for g in all_guests if g["segment"] == "new")
        avg_ltv = (
            round(sum(g["total_spend"] for g in all_guests) / total_guests, 2)
            if total_guests > 0
            else 0.0
        )

        # Apply segment + search filters
        filtered = all_guests
        if segment_filter in ("vip", "repeat", "new", "at_risk"):
            filtered = [g for g in filtered if g["segment"] == segment_filter]

        if search_q:
            filtered = [
                g
                for g in filtered
                if search_q in g["name"].lower()
                or search_q in g["phone"].lower()
                or search_q in g["display_phone"].lower()
                or search_q in g["favorite_dish"].lower()
                or search_q in g["dietary_notes"].lower()
                or any(search_q in str(t).lower() for t in (g["tags"] or []))
            ]

        # Sort by total_spend desc, then last_order_at desc
        filtered.sort(
            key=lambda g: (
                g["total_spend"],
                g["total_orders"],
                g["last_order_at"] or "",
            ),
            reverse=True,
        )

        return Response({
            "kpis": {
                "total_guests": total_guests,
                "vip_count": vip_count,
                "repeat_count": repeat_count,
                "at_risk_count": at_risk_count,
                "new_count": new_count,
                "avg_lifetime_value": avg_ltv,
            },
            "customers": filtered[:250],
        })


class RestaurantCustomerDetailAPIView(BusinessAPIView):
    """
    GET /api/operations/restaurant/customers/<phone>/
    PATCH /api/operations/restaurant/customers/<phone>/
    """

    required_business_permission = None

    def get(self, request, phone):
        norm = _normalize_phone_key(phone)
        if not norm:
            return Response({"detail": "Invalid phone number."}, status=400)
        detail = _build_guest_detail_payload(self.company, norm)
        if not detail:
            return Response({"detail": "Guest not found."}, status=404)
        return Response(detail)

    def patch(self, request, phone):
        norm = _normalize_phone_key(phone)
        if not norm:
            return Response({"detail": "Invalid phone number."}, status=400)

        profile, _ = RestaurantGuestProfile.objects.get_or_create(
            company=self.company,
            phone=norm,
            defaults={"display_phone": str(phone).strip()},
        )

        update_fields = ["updated_at"]
        if "name" in request.data:
            profile.name = str(request.data.get("name") or "").strip()[:160]
            update_fields.append("name")
        if "dietary_notes" in request.data:
            profile.dietary_notes = str(request.data.get("dietary_notes") or "").strip()
            update_fields.append("dietary_notes")
        if "tags" in request.data:
            raw_tags = request.data.get("tags")
            if isinstance(raw_tags, list):
                profile.tags = [str(t).strip()[:40] for t in raw_tags if str(t).strip()][:15]
            elif isinstance(raw_tags, str):
                profile.tags = [t.strip()[:40] for t in raw_tags.split(",") if t.strip()][:15]
            else:
                profile.tags = []
            update_fields.append("tags")
        if "is_vip_override" in request.data:
            raw_vip = request.data.get("is_vip_override")
            if isinstance(raw_vip, bool):
                profile.is_vip_override = raw_vip
            elif isinstance(raw_vip, str):
                profile.is_vip_override = raw_vip.strip().lower() == "true"
            else:
                profile.is_vip_override = bool(raw_vip)
            update_fields.append("is_vip_override")
        if not profile.display_phone:
            profile.display_phone = str(phone).strip()
            update_fields.append("display_phone")

        profile.save(update_fields=update_fields)
        detail = _build_guest_detail_payload(self.company, norm)
        return Response(detail)
