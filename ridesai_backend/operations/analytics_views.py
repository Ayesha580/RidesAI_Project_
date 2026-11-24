"""
Advanced Time-Series Analytics & Exportable Operational Reports (CSV).
Strictly multi-tenant isolated: every query and export filters by `company=request.user.company`.
Optimized for PostgreSQL aggregations (`TruncDate`, `TruncWeek`, `Sum`, `Count`).
"""

import csv
import io
import re
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import (
    AgentConversation,
    AgentMessage,
    Appointment,
    LabTestBooking,
    Order,
    OrderItem,
)

CHANNEL_LABELS = {
    "public_web": "Public Voice Link",
    "widget": "Website Widget",
    "whatsapp": "WhatsApp",
    "manual": "Manual / Dashboard",
}


def _normalize_channel(source_val: str) -> str:
    raw = (source_val or "").strip().lower()
    if "whatsapp" in raw or raw == "wa":
        return "whatsapp"
    if "widget" in raw or "embed" in raw:
        return "widget"
    if raw in ("agent", "public_web", "public", "web", "voice", "ai"):
        return "public_web"
    return "manual"


def _resolve_date_window(request):
    """Parses range=7d|30d|90d|custom (+ start_date, end_date) into timezone-aware bounds."""
    today = timezone.localdate()
    range_key = (request.query_params.get("range") or "30d").strip().lower()

    if range_key == "7d":
        start_date = today - timedelta(days=6)
        end_date = today
    elif range_key == "90d":
        start_date = today - timedelta(days=89)
        end_date = today
    elif range_key == "custom":
        s_raw = (request.query_params.get("start_date") or "").strip()
        e_raw = (request.query_params.get("end_date") or "").strip()
        try:
            start_date = datetime.strptime(s_raw[:10], "%Y-%m-%d").date() if s_raw else today - timedelta(days=29)
            end_date = datetime.strptime(e_raw[:10], "%Y-%m-%d").date() if e_raw else today
        except ValueError:
            start_date = today - timedelta(days=29)
            end_date = today
        if start_date > end_date:
            start_date, end_date = end_date, start_date
    else:
        range_key = "30d"
        start_date = today - timedelta(days=29)
        end_date = today

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
    use_weekly = (end_date - start_date).days > 45
    return range_key, start_dt, end_dt, start_date, end_date, use_weekly


def _build_analytics_payload(company, range_key, start_dt, end_dt, start_date, end_date, use_weekly):
    trunc_fn = TruncWeek("created_at") if use_weekly else TruncDate("created_at")

    # 1. Orders (strictly scoped to company)
    orders_qs = Order.objects.filter(company=company, created_at__gte=start_dt, created_at__lte=end_dt)
    non_cancelled_orders = orders_qs.exclude(status__in=["cancelled", "rejected"])

    orders_agg = non_cancelled_orders.aggregate(rev=Sum("total"), cnt=Count("id"))
    orders_rev = Decimal(str(orders_agg.get("rev") or "0.00"))
    total_orders_count = orders_qs.count()

    # 2. Healthcare bookings (LabTestBooking & Appointments) strictly scoped to company
    labs_qs = LabTestBooking.objects.filter(company=company, created_at__gte=start_dt, created_at__lte=end_dt)
    labs_rev = Decimal(
        str(
            labs_qs.exclude(status=LabTestBooking.STATUS_CANCELLED)
            .aggregate(rev=Sum("price"))
            .get("rev")
            or "0.00"
        )
    )
    labs_count = labs_qs.count()

    appts_qs = Appointment.objects.filter(company=company, created_at__gte=start_dt, created_at__lte=end_dt).select_related("doctor")
    appts_count = appts_qs.count()
    appts_rev = Decimal("0.00")
    for appt in appts_qs.exclude(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_NO_SHOW]):
        if appt.doctor and appt.doctor.consultation_fee:
            appts_rev += Decimal(str(appt.doctor.consultation_fee))

    total_revenue = orders_rev + labs_rev + appts_rev
    total_records = total_orders_count + labs_count + appts_count

    completed_orders = orders_qs.filter(status__in=["delivered", "completed"]).count()
    cancelled_orders = orders_qs.filter(status__in=["cancelled", "rejected"]).count()
    completed_labs = labs_qs.filter(status=LabTestBooking.STATUS_COMPLETED).count()
    cancelled_labs = labs_qs.filter(status=LabTestBooking.STATUS_CANCELLED).count()
    completed_appts = appts_qs.filter(status=Appointment.STATUS_COMPLETED).count()
    cancelled_appts = appts_qs.filter(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_NO_SHOW]).count()

    completed_total = completed_orders + completed_labs + completed_appts
    cancelled_total = cancelled_orders + cancelled_labs + cancelled_appts
    active_non_cancelled = max(0, total_records - cancelled_total)
    aov = float(total_revenue / active_non_cancelled) if active_non_cancelled > 0 else 0.0
    completion_rate = round((completed_total / total_records) * 100.0, 1) if total_records > 0 else 0.0

    # 3. AI Conversations & Voice Turns (strictly scoped to company)
    convs_qs = AgentConversation.objects.filter(company=company, created_at__gte=start_dt, created_at__lte=end_dt)
    active_ai_conversations = convs_qs.count()
    ai_voice_turns = AgentMessage.objects.filter(
        conversation__company=company,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    ).count()

    # 4. Time-Series Trend (PostgreSQL TruncDate / TruncWeek)
    bucket_map = defaultdict(lambda: {"revenue": Decimal("0.00"), "orders_count": 0, "ai_conversations": 0})

    for row in (
        orders_qs.annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(cnt=Count("id"))
    ):
        b = row["bucket"]
        if b:
            key = b.date().isoformat() if hasattr(b, "date") else str(b)[:10]
            bucket_map[key]["orders_count"] += int(row["cnt"] or 0)

    for row in (
        non_cancelled_orders.annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(rev=Sum("total"))
    ):
        b = row["bucket"]
        if b:
            key = b.date().isoformat() if hasattr(b, "date") else str(b)[:10]
            bucket_map[key]["revenue"] += Decimal(str(row["rev"] or "0.00"))

    for row in (
        labs_qs.annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(cnt=Count("id"))
    ):
        b = row["bucket"]
        if b:
            key = b.date().isoformat() if hasattr(b, "date") else str(b)[:10]
            bucket_map[key]["orders_count"] += int(row["cnt"] or 0)

    for row in (
        labs_qs.exclude(status=LabTestBooking.STATUS_CANCELLED)
        .annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(rev=Sum("price"))
    ):
        b = row["bucket"]
        if b:
            key = b.date().isoformat() if hasattr(b, "date") else str(b)[:10]
            bucket_map[key]["revenue"] += Decimal(str(row["rev"] or "0.00"))

    for row in (
        convs_qs.annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(cnt=Count("id"))
    ):
        b = row["bucket"]
        if b:
            key = b.date().isoformat() if hasattr(b, "date") else str(b)[:10]
            bucket_map[key]["ai_conversations"] += int(row["cnt"] or 0)

    # Gap-fill continuous timeline
    time_series = []
    if use_weekly:
        cursor = start_date - timedelta(days=start_date.weekday())
        while cursor <= end_date:
            key = cursor.isoformat()
            entry = bucket_map.get(key, {"revenue": Decimal("0.00"), "orders_count": 0, "ai_conversations": 0})
            time_series.append({
                "date": key,
                "label": cursor.strftime("%d %b"),
                "revenue": round(float(entry["revenue"]), 2),
                "orders_count": entry["orders_count"],
                "ai_conversations": entry["ai_conversations"],
            })
            cursor += timedelta(days=7)
    else:
        cursor = start_date
        while cursor <= end_date:
            key = cursor.isoformat()
            entry = bucket_map.get(key, {"revenue": Decimal("0.00"), "orders_count": 0, "ai_conversations": 0})
            time_series.append({
                "date": key,
                "label": cursor.strftime("%d %b"),
                "revenue": round(float(entry["revenue"]), 2),
                "orders_count": entry["orders_count"],
                "ai_conversations": entry["ai_conversations"],
            })
            cursor += timedelta(days=1)

    # 5. Status & Channel Breakdown
    status_counts = defaultdict(int)
    for row in orders_qs.values("status").annotate(cnt=Count("id")):
        status_counts[row["status"]] += row["cnt"]
    for row in labs_qs.values("status").annotate(cnt=Count("id")):
        status_counts[row["status"]] += row["cnt"]
    for row in appts_qs.values("status").annotate(cnt=Count("id")):
        status_counts[row["status"]] += row["cnt"]

    status_breakdown = [
        {"status": st, "label": st.replace("_", " ").title(), "count": cnt}
        for st, cnt in sorted(status_counts.items(), key=lambda x: -x[1])
    ]

    channel_counts = {"public_web": 0, "widget": 0, "whatsapp": 0, "manual": 0}
    for row in orders_qs.values("source").annotate(cnt=Count("id")):
        channel_counts[_normalize_channel(row["source"])] += row["cnt"]
    for row in labs_qs.values("source").annotate(cnt=Count("id")):
        channel_counts[_normalize_channel(row["source"])] += row["cnt"]
    for row in appts_qs.values("source").annotate(cnt=Count("id")):
        channel_counts[_normalize_channel(row["source"])] += row["cnt"]

    channel_breakdown = [
        {"channel": ch, "label": CHANNEL_LABELS[ch], "count": cnt}
        for ch, cnt in channel_counts.items()
    ]

    # 6. Top 5 Selling Items / Services
    top_map = defaultdict(lambda: {"quantity": Decimal("0"), "revenue": Decimal("0.00")})
    for row in (
        OrderItem.objects.filter(
            order__company=company,
            order__created_at__gte=start_dt,
            order__created_at__lte=end_dt,
        )
        .exclude(order__status__in=["cancelled", "rejected"])
        .values("item_name")
        .annotate(qty=Sum("quantity"), rev=Sum("line_total"))
    ):
        name = (row["item_name"] or "Item").strip()
        top_map[name]["quantity"] += Decimal(str(row["qty"] or "0"))
        top_map[name]["revenue"] += Decimal(str(row["rev"] or "0.00"))

    for row in (
        labs_qs.exclude(status=LabTestBooking.STATUS_CANCELLED)
        .values("test_name")
        .annotate(cnt=Count("id"), rev=Sum("price"))
    ):
        name = (row["test_name"] or "Lab Test").strip()
        top_map[name]["quantity"] += Decimal(str(row["cnt"] or "0"))
        top_map[name]["revenue"] += Decimal(str(row["rev"] or "0.00"))

    top_items = [
        {
            "name": name,
            "quantity": float(vals["quantity"]),
            "revenue": round(float(vals["revenue"]), 2),
        }
        for name, vals in sorted(top_map.items(), key=lambda kv: (-kv[1]["revenue"], -kv[1]["quantity"]))[:5]
    ]

    # 7. Itemized recent rows (for CSV & Printable PDF report)
    itemized_rows = []
    for o in orders_qs.prefetch_related("items").order_by("-created_at")[:200]:
        items_desc = ", ".join(f"{int(it.quantity) if it.quantity == int(it.quantity) else it.quantity}x {it.item_name}" for it in o.items.all())
        itemized_rows.append({
            "id": o.order_number,
            "date": timezone.localtime(o.created_at).strftime("%Y-%m-%d %H:%M"),
            "customer": o.customer_name or o.customer_phone or "Customer",
            "items": items_desc or "Order",
            "status": o.status,
            "channel": CHANNEL_LABELS[_normalize_channel(o.source)],
            "total": round(float(o.total or 0), 2),
        })
    for lb in labs_qs.order_by("-created_at")[:100]:
        itemized_rows.append({
            "id": lb.booking_number,
            "date": timezone.localtime(lb.created_at).strftime("%Y-%m-%d %H:%M"),
            "customer": lb.patient_name or lb.patient_phone or "Patient",
            "items": f"Lab: {lb.test_name}",
            "status": lb.status,
            "channel": CHANNEL_LABELS[_normalize_channel(lb.source)],
            "total": round(float(lb.price or 0), 2),
        })
    for ap in appts_qs.order_by("-created_at")[:100]:
        fee = float(ap.doctor.consultation_fee) if (ap.doctor and ap.doctor.consultation_fee) else 0.0
        doc_label = f"OPD: {ap.doctor.name} ({ap.doctor.specialty})" if ap.doctor else "OPD Appointment"
        itemized_rows.append({
            "id": ap.appointment_number,
            "date": timezone.localtime(ap.created_at).strftime("%Y-%m-%d %H:%M"),
            "customer": ap.patient_name or ap.patient_phone or "Patient",
            "items": doc_label,
            "status": ap.status,
            "channel": CHANNEL_LABELS[_normalize_channel(ap.source)],
            "total": round(fee, 2),
        })
    itemized_rows.sort(key=lambda r: r["date"], reverse=True)

    return {
        "company_name": company.name,
        "business_type": company.business_type or "general",
        "range": range_key,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "granularity": "weekly" if use_weekly else "daily",
        "kpis": {
            "total_revenue": round(float(total_revenue), 2),
            "total_orders": total_records,
            "average_order_value": round(aov, 2),
            "completed_count": completed_total,
            "cancelled_count": cancelled_total,
            "completion_rate": completion_rate,
            "active_ai_conversations": active_ai_conversations,
            "ai_voice_turns": ai_voice_turns,
            "messages_used": int(company.messages_used or 0),
            "message_limit": int(company.message_limit or 0),
        },
        "time_series": time_series,
        "status_breakdown": status_breakdown,
        "channel_breakdown": channel_breakdown,
        "top_items": top_items,
        "recent_records": itemized_rows[:100],
    }


class AnalyticsOverviewAPIView(APIView):
    """GET /api/operations/analytics/overview/?range=7d|30d|90d|custom"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        range_key, start_dt, end_dt, start_date, end_date, use_weekly = _resolve_date_window(request)
        payload = _build_analytics_payload(company, range_key, start_dt, end_dt, start_date, end_date, use_weekly)
        return Response(payload, status=200)


class AnalyticsExportCSVAPIView(APIView):
    """GET /api/operations/analytics/export/csv/?range=7d|30d|90d|custom"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        range_key, start_dt, end_dt, start_date, end_date, use_weekly = _resolve_date_window(request)
        payload = _build_analytics_payload(company, range_key, start_dt, end_dt, start_date, end_date, use_weekly)

        buf = io.StringIO()
        # UTF-8 BOM for clean Excel rendering of Urdu / Roman Urdu
        buf.write("\ufeff")
        writer = csv.writer(buf)

        kpis = payload["kpis"]
        writer.writerow(["RidesAI Operational Report — Owned by Rides Technologies"])
        writer.writerow(["Business", company.name])
        writer.writerow(["Date Range", f"{payload['start_date']} to {payload['end_date']} ({range_key})"])
        writer.writerow(["Total Revenue (Rs.)", f"{kpis['total_revenue']:.2f}"])
        writer.writerow(["Total Orders / Bookings", kpis["total_orders"]])
        writer.writerow(["Average Order Value (Rs.)", f"{kpis['average_order_value']:.2f}"])
        writer.writerow(["Completed", kpis["completed_count"], "Cancelled", kpis["cancelled_count"]])
        writer.writerow(["AI Conversations", kpis["active_ai_conversations"], "Monthly Voice Usage", f"{kpis['messages_used']} / {kpis['message_limit']}"])
        writer.writerow([])
        writer.writerow(["ID", "Date", "Customer", "Items / Service", "Status", "Channel", "Total (Rs.)"])

        for row in payload["recent_records"]:
            writer.writerow([
                row["id"],
                row["date"],
                row["customer"],
                row["items"],
                row["status"],
                row["channel"],
                f"{row['total']:.2f}",
            ])

        safe_slug = re.sub(r"[^a-z0-9]+", "-", (company.name or "business").lower()).strip("-") or "business"
        filename = f"ridesai-report-{safe_slug}-{range_key}.csv"
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
