"""
Executive Bird's-Eye Restaurant Owner Dashboard Summary API.
Single efficient PostgreSQL query set strictly scoped to `request.user.company`.
Endpoint: GET /api/operations/restaurant/dashboard-summary/?period=today|7d|30d
"""

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Inventory
from operations.models import (
    AgentConversation,
    Order,
    OrderItem,
    RestaurantIngredient,
    RestaurantTable,
    SuggestedFAQ,
)

ACTIVE_ORDER_STATUSES = [
    Order.STATUS_NEW,
    "pending",
    Order.STATUS_CONFIRMED,
    Order.STATUS_PREPARING,
    "in_kitchen",
    Order.STATUS_PREPARED,
    Order.STATUS_READY,
    Order.STATUS_ASSIGNED,
    Order.STATUS_PICKED_UP,
    Order.STATUS_ON_THE_WAY,
    "out_for_delivery",
    "dispatched",
]
COMPLETED_ORDER_STATUSES = [Order.STATUS_DELIVERED, "completed"]
CANCELLED_ORDER_STATUSES = [Order.STATUS_CANCELLED, "rejected"]


def _normalize_restaurant_channel(source_val: str) -> str:
    raw = (source_val or "").strip().lower()
    if "whatsapp" in raw or raw == "wa":
        return "whatsapp"
    if "widget" in raw or "embed" in raw:
        return "widget"
    if raw in ("agent", "public_web", "public", "web", "voice", "ai"):
        return "public_web"
    return "dashboard"


class RestaurantDashboardSummaryAPIView(APIView):
    """GET /api/operations/restaurant/dashboard-summary/?period=today|7d|30d"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        period = (request.query_params.get("period") or "today").strip().lower()
        if period not in ("today", "7d", "30d"):
            period = "today"

        today = timezone.localdate()
        tz = timezone.get_current_timezone()

        if period == "today":
            start_date = today
        elif period == "7d":
            start_date = today - timedelta(days=6)
        else:
            start_date = today - timedelta(days=29)

        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(today, time.max), tz)

        # 1. Period Orders & KPIs (strictly scoped to company)
        orders_qs = Order.objects.filter(company=company, created_at__gte=start_dt, created_at__lte=end_dt)
        non_cancelled = orders_qs.exclude(status__in=CANCELLED_ORDER_STATUSES)

        rev_agg = non_cancelled.aggregate(rev=Sum("total"), cnt=Count("id"))
        revenue = Decimal(str(rev_agg.get("rev") or "0.00"))
        non_cancelled_cnt = int(rev_agg.get("cnt") or 0)
        avg_order_value = float(revenue / non_cancelled_cnt) if non_cancelled_cnt > 0 else 0.0

        total_orders = orders_qs.count()
        active_orders = orders_qs.filter(status__in=ACTIVE_ORDER_STATUSES).count()
        completed_orders = orders_qs.filter(status__in=COMPLETED_ORDER_STATUSES).count()
        cancelled_orders = orders_qs.filter(status__in=CANCELLED_ORDER_STATUSES).count()

        ai_conversations_count = AgentConversation.objects.filter(
            company=company, created_at__gte=start_dt, created_at__lte=end_dt
        ).count()
        ai_orders_count = orders_qs.exclude(source__in=["dashboard", "manual"]).count()

        # 2. Live Tables & Floor Snapshot
        tables_qs = RestaurantTable.objects.filter(company=company)
        table_counts = defaultdict(int)
        for row in tables_qs.values("status").annotate(cnt=Count("id")):
            table_counts[row["status"]] = row["cnt"]
        tables_total = sum(table_counts.values())

        # 3. Actionable Alerts (live across company)
        unassigned_orders_count = Order.objects.filter(company=company).filter(
            Q(status__in=[Order.STATUS_NEW, "pending", Order.STATUS_CONFIRMED])
            | Q(status__in=[Order.STATUS_PREPARED, Order.STATUS_READY], assigned_rider__isnull=True)
        ).count()

        catalog_low_stock = Inventory.objects.filter(
            company=company,
            is_unlimited=False,
            quantity__lte=F("low_stock_threshold"),
        ).count()
        ingredient_low_stock = RestaurantIngredient.objects.filter(
            company=company,
            current_stock__lte=F("low_stock_threshold"),
        ).count()
        low_stock_items_count = catalog_low_stock + ingredient_low_stock

        pending_faq_suggestions_count = SuggestedFAQ.objects.filter(
            company=company,
            status=SuggestedFAQ.STATUS_PENDING,
        ).count()

        # 4. Time-Series Trend (hourly for today, daily for 7d/30d)
        trend = []
        if period == "today":
            hour_map = defaultdict(lambda: {"revenue": Decimal("0.00"), "orders_count": 0})
            for row in orders_qs.annotate(hr=TruncHour("created_at", tzinfo=tz)).values("hr").annotate(cnt=Count("id")):
                if row["hr"]:
                    hour_map[row["hr"].hour]["orders_count"] += int(row["cnt"] or 0)
            for row in non_cancelled.annotate(hr=TruncHour("created_at", tzinfo=tz)).values("hr").annotate(rev=Sum("total")):
                if row["hr"]:
                    hour_map[row["hr"].hour]["revenue"] += Decimal(str(row["rev"] or "0.00"))
            for h in range(24):
                entry = hour_map[h]
                trend.append({
                    "key": f"{h:02d}:00",
                    "label": f"{h:02d}:00",
                    "revenue": round(float(entry["revenue"]), 2),
                    "orders_count": entry["orders_count"],
                })
        else:
            day_map = defaultdict(lambda: {"revenue": Decimal("0.00"), "orders_count": 0})
            for row in orders_qs.annotate(d=TruncDate("created_at", tzinfo=tz)).values("d").annotate(cnt=Count("id")):
                if row["d"]:
                    day_map[row["d"].isoformat()]["orders_count"] += int(row["cnt"] or 0)
            for row in non_cancelled.annotate(d=TruncDate("created_at", tzinfo=tz)).values("d").annotate(rev=Sum("total")):
                if row["d"]:
                    day_map[row["d"].isoformat()]["revenue"] += Decimal(str(row["rev"] or "0.00"))
            cursor = start_date
            while cursor <= today:
                k = cursor.isoformat()
                entry = day_map[k]
                trend.append({
                    "key": k,
                    "label": cursor.strftime("%d %b"),
                    "revenue": round(float(entry["revenue"]), 2),
                    "orders_count": entry["orders_count"],
                })
                cursor += timedelta(days=1)

        # 5. Top Selling Items (Top 5)
        top_items_qs = (
            OrderItem.objects.filter(
                order__company=company,
                order__created_at__gte=start_dt,
                order__created_at__lte=end_dt,
            )
            .exclude(order__status__in=CANCELLED_ORDER_STATUSES)
            .values("item_name")
            .annotate(qty=Sum("quantity"), rev=Sum("line_total"))
            .order_by("-rev", "-qty")[:5]
        )
        top_items = [
            {
                "name": (r["item_name"] or "Item").strip(),
                "quantity": float(r["qty"] or 0),
                "revenue": round(float(r["rev"] or 0), 2),
            }
            for r in top_items_qs
        ]

        # 6. Channel Breakdown
        channel_breakdown = {"whatsapp": 0, "public_web": 0, "widget": 0, "dashboard": 0}
        for row in orders_qs.values("source").annotate(cnt=Count("id")):
            channel_breakdown[_normalize_restaurant_channel(row["source"])] += int(row["cnt"] or 0)

        # 7. Recent Orders (Top 5)
        recent_orders = [
            {
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name or o.customer_phone or "Customer",
                "total_amount": round(float(o.total or 0), 2),
                "status": o.status,
                "channel": _normalize_restaurant_channel(o.source),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in Order.objects.filter(company=company).order_by("-created_at")[:5]
        ]

        return Response({
            "period": period,
            "company_name": company.name,
            "kpis": {
                "revenue": round(float(revenue), 2),
                "avg_order_value": round(avg_order_value, 2),
                "total_orders": total_orders,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "cancelled_orders": cancelled_orders,
                "ai_conversations_count": ai_conversations_count,
                "ai_orders_count": ai_orders_count,
            },
            "tables": {
                "tables_total": tables_total,
                "tables_available": table_counts.get(RestaurantTable.STATUS_AVAILABLE, 0),
                "tables_occupied": table_counts.get(RestaurantTable.STATUS_OCCUPIED, 0),
                "tables_reserved": table_counts.get(RestaurantTable.STATUS_RESERVED, 0),
            },
            "alerts": {
                "unassigned_orders_count": unassigned_orders_count,
                "low_stock_items_count": low_stock_items_count,
                "pending_faq_suggestions_count": pending_faq_suggestions_count,
            },
            "trend": trend,
            "top_items": top_items,
            "channel_breakdown": channel_breakdown,
            "recent_orders": recent_orders,
        }, status=200)
