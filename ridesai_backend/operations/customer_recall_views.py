"""
POS Returning Customer Auto-Recall & Guest Memory API.
Strictly multi-tenant (scoped to `request.user.company`) and PostgreSQL 16 compatible.

Provides:
- upsert_guest_customer(): Auto-remembers guests on POS and AI order creation.
- GET /api/operations/customers/lookup/?q=<name_or_phone>: Fast deduplicated lookup across
  both Customer records and historical Order records (up to 8 matches).
"""

import logging
import re
from typing import Dict, List, Optional

from django.db.models import Count, Max, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import Customer, Order

logger = logging.getLogger("operations.customers")

PLACEHOLDER_NAMES = {
    "",
    "walk-in",
    "walk-in guest",
    "walk-in customer",
    "guest",
    "customer",
    "valued customer",
    "unknown",
}


def _normalize_phone_key(raw_phone: Optional[str]) -> str:
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return ""
    # Normalize Pakistani 03xx vs 923xx so both dedupe to the same customer
    if digits.startswith("0092"):
        digits = "92" + digits[4:]
    elif digits.startswith("03") and len(digits) == 11:
        digits = "92" + digits[1:]
    return digits


def upsert_guest_customer(
    company,
    name: str = "",
    phone: str = "",
    delivery_address: str = "",
) -> Optional[Customer]:
    """
    Automatically creates or updates a tenant's Customer record whenever an order
    is placed (POS or AI Agent) with a phone number.
    Fault-tolerant: never raises exceptions that could break order creation.
    """
    if not company:
        return None
    clean_phone = (phone or "").strip()
    clean_name = (name or "").strip()
    clean_addr = (delivery_address or "").strip()

    if not clean_phone:
        return None

    try:
        customer, created = Customer.objects.get_or_create(
            company=company,
            phone=clean_phone,
            defaults={
                "name": clean_name if clean_name.lower() not in PLACEHOLDER_NAMES else "",
                "delivery_address": clean_addr,
            },
        )
        if not created:
            update_fields = []
            if clean_name and clean_name.lower() not in PLACEHOLDER_NAMES and customer.name != clean_name:
                customer.name = clean_name
                update_fields.append("name")
            if clean_addr and customer.delivery_address != clean_addr:
                customer.delivery_address = clean_addr
                update_fields.append("delivery_address")
            if update_fields:
                update_fields.append("updated_at")
                customer.save(update_fields=update_fields)
        return customer
    except Exception as exc:
        logger.warning("[CustomerRecall] Failed to upsert guest customer for company %s: %s", company.id, exc)
        return None


class CustomerLookupAPIView(APIView):
    """
    GET /api/operations/customers/lookup/?q=<name_or_phone>
    Returns up to 8 deduplicated returning customer matches strictly scoped to `request.user.company`.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response([], status=200)

        # Build phone-digit variant so searching "0300" matches "+92300..." too
        q_digits = re.sub(r"\D", "", q)
        alt_digits = ""
        if q_digits.startswith("03") and len(q_digits) >= 4:
            alt_digits = "92" + q_digits[1:]
        elif q_digits.startswith("923") and len(q_digits) >= 5:
            alt_digits = "0" + q_digits[2:]

        cust_filter = Q(name__icontains=q) | Q(phone__icontains=q)
        order_filter = Q(customer_name__icontains=q) | Q(customer_phone__icontains=q)
        if alt_digits:
            cust_filter |= Q(phone__icontains=alt_digits)
            order_filter |= Q(customer_phone__icontains=alt_digits)

        # 1. Pre-aggregate order stats for matching orders in this company
        matching_orders = list(
            Order.objects.filter(company=company)
            .filter(order_filter)
            .order_by("-created_at")
            .values("id", "customer_name", "customer_phone", "delivery_address", "created_at")[:120]
        )

        # Build merged deduplicated map keyed by normalized phone (or lowercased name if phone empty)
        merged: Dict[str, Dict] = {}

        # First ingest Customer records
        matching_customers = list(
            Customer.objects.filter(company=company).filter(cust_filter).order_by("-updated_at")[:40]
        )
        for c in matching_customers:
            key = _normalize_phone_key(c.phone) or f"name:{(c.name or '').strip().lower()}"
            if not key or key == "name:":
                continue
            merged[key] = {
                "id": c.id,
                "name": (c.name or "").strip(),
                "phone": (c.phone or "").strip(),
                "delivery_address": (c.delivery_address or "").strip(),
                "total_orders": 0,
                "last_order_at": None,
                "_last_dt": None,
            }

        # Aggregate order counts & latest address across all matching orders
        for o in matching_orders:
            o_phone = (o.get("customer_phone") or "").strip()
            o_name = (o.get("customer_name") or "").strip()
            o_addr = (o.get("delivery_address") or "").strip()
            o_dt = o.get("created_at")

            key = _normalize_phone_key(o_phone) or f"name:{o_name.lower()}"
            if not key or key == "name:" or (not o_phone and o_name.lower() in PLACEHOLDER_NAMES):
                continue

            if key not in merged:
                merged[key] = {
                    "id": None,
                    "name": o_name,
                    "phone": o_phone,
                    "delivery_address": o_addr,
                    "total_orders": 0,
                    "last_order_at": None,
                    "_last_dt": None,
                }

            entry = merged[key]
            entry["total_orders"] += 1
            if not entry["name"] and o_name:
                entry["name"] = o_name
            if not entry["phone"] and o_phone:
                entry["phone"] = o_phone
            if not entry["delivery_address"] and o_addr:
                entry["delivery_address"] = o_addr
            if o_dt and (entry["_last_dt"] is None or o_dt > entry["_last_dt"]):
                entry["_last_dt"] = o_dt
                entry["last_order_at"] = o_dt.isoformat()
                if o_addr:
                    entry["delivery_address"] = o_addr

        # Backfill accurate total_orders for Customer-only hits whose orders didn't match name query directly
        cust_phones = [e["phone"] for e in merged.values() if e["phone"] and e["total_orders"] == 0]
        if cust_phones:
            stats = (
                Order.objects.filter(company=company, customer_phone__in=cust_phones)
                .values("customer_phone")
                .annotate(cnt=Count("id"), last_dt=Max("created_at"))
            )
            for row in stats:
                k = _normalize_phone_key(row["customer_phone"])
                if k in merged:
                    merged[k]["total_orders"] = row["cnt"]
                    if row["last_dt"]:
                        merged[k]["_last_dt"] = row["last_dt"]
                        merged[k]["last_order_at"] = row["last_dt"].isoformat()

        results: List[Dict] = sorted(
            merged.values(),
            key=lambda r: (r["total_orders"], r["last_order_at"] or ""),
            reverse=True,
        )[:8]

        for r in results:
            r.pop("_last_dt", None)

        return Response(results, status=200)
