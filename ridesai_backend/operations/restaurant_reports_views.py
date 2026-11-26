"""
Restaurant Reports, Recipe-Based Profitability Analytics & CSV Export APIs.

Strictly scoped to request.user.company and PostgreSQL 16 compatible.
"""

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response

from .models import MenuItemRecipe, Order, RestaurantExpense, RestaurantSupplier
from .views import BusinessAPIView


def _parse_iso_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except (ValueError, TypeError):
        return None


def _resolve_date_window(request) -> Tuple[str, Optional[date], Optional[date]]:
    """Resolves (range_key, start_date, end_date) from query params."""
    range_key = str(request.query_params.get("range", "30d")).strip().lower()
    if range_key not in ("today", "7d", "30d", "all"):
        range_key = "30d"

    start_d = _parse_iso_date(request.query_params.get("start_date"))
    end_d = _parse_iso_date(request.query_params.get("end_date"))
    today = timezone.localdate()

    if start_d or end_d:
        return "custom", start_d, end_d

    if range_key == "today":
        return "today", today, today
    if range_key == "7d":
        return "7d", today - timedelta(days=6), today
    if range_key == "30d":
        return "30d", today - timedelta(days=29), today
    return "all", None, None


def _build_recipe_unit_cost_map(company) -> Dict[int, Decimal]:
    """
    Returns { catalog_item_id: unit_cogs_decimal } from Module 4 MenuItemRecipe
    & RestaurantIngredient.cost_per_unit.
    """
    cost_map: Dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    recipes = (
        MenuItemRecipe.objects.filter(company=company)
        .select_related("ingredient")
        .only("catalog_item_id", "quantity_required", "ingredient__cost_per_unit")
    )
    for rec in recipes:
        unit_cost = getattr(rec.ingredient, "cost_per_unit", Decimal("0.00")) or Decimal("0.00")
        qty_req = rec.quantity_required or Decimal("0.00")
        cost_map[rec.catalog_item_id] += qty_req * unit_cost
    return dict(cost_map)


def _classify_channel(order: Order) -> str:
    src = str(order.source or "").strip().lower()
    if src in ("dashboard", "pos", "counter"):
        return "POS"
    if src in ("web_voice", "website_voice", "voice", "web", "api"):
        return "Website Voice AI"
    return "WhatsApp AI"


def _compute_order_cogs(order: Order, recipe_cost_map: Dict[int, Decimal]) -> Decimal:
    total_cogs = Decimal("0.00")
    for item in order.items.all():
        if item.item_id and item.item_id in recipe_cost_map:
            qty = item.quantity or Decimal("0")
            total_cogs += recipe_cost_map[item.item_id] * qty
    return total_cogs


def _filtered_orders_queryset(company, start_d: Optional[date], end_d: Optional[date]):
    qs = (
        Order.objects.filter(company=company)
        .prefetch_related("items")
        .order_by("created_at")
    )
    if start_d:
        qs = qs.filter(created_at__date__gte=start_d)
    if end_d:
        qs = qs.filter(created_at__date__lte=end_d)
    return qs


class RestaurantReportsSummaryAPIView(BusinessAPIView):
    """
    GET /api/operations/restaurant/reports/?range=today|7d|30d|all&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """

    required_business_permission = None

    def get(self, request):
        company = self.company
        range_key, start_d, end_d = _resolve_date_window(request)
        orders = list(_filtered_orders_queryset(company, start_d, end_d))
        recipe_cost_map = _build_recipe_unit_cost_map(company)

        net_revenue = Decimal("0.00")
        delivery_fees_total = Decimal("0.00")
        estimated_cogs = Decimal("0.00")
        unsettled_cod_total = Decimal("0.00")
        total_orders = 0
        cancelled_orders = 0

        order_type_stats: Dict[str, Dict[str, Any]] = {
            "dine_in": {"key": "dine_in", "label": "Dine-In", "orders": 0, "revenue": Decimal("0.00")},
            "takeaway": {"key": "takeaway", "label": "Takeaway", "orders": 0, "revenue": Decimal("0.00")},
            "delivery": {"key": "delivery", "label": "Delivery", "orders": 0, "revenue": Decimal("0.00")},
        }
        channel_stats: Dict[str, Dict[str, Any]] = {
            "POS": {"channel": "POS", "orders": 0, "revenue": Decimal("0.00")},
            "WhatsApp AI": {"channel": "WhatsApp AI", "orders": 0, "revenue": Decimal("0.00")},
            "Website Voice AI": {"channel": "Website Voice AI", "orders": 0, "revenue": Decimal("0.00")},
        }
        daily_map: Dict[str, Dict[str, Any]] = {}
        dish_map: Dict[str, Dict[str, Any]] = {}
        hourly_stats = [
            {"hour": h, "label": f"{h:02d}:00", "orders": 0, "revenue": Decimal("0.00")}
            for h in range(24)
        ]

        for order in orders:
            if order.status == Order.STATUS_CANCELLED:
                cancelled_orders += 1
                continue

            total_orders += 1
            order_total = order.total or Decimal("0.00")
            order_fee = order.delivery_fee or Decimal("0.00")
            order_cogs = _compute_order_cogs(order, recipe_cost_map)
            order_profit = order_total - order_cogs

            net_revenue += order_total
            delivery_fees_total += order_fee
            estimated_cogs += order_cogs

            if (
                order.order_type == Order.ORDER_TYPE_DELIVERY
                and order.status == Order.STATUS_DELIVERED
                and order.cod_collected
                and not order.cod_settled
            ):
                unsettled_cod_total += order_total

            # Order Type split
            otype = order.order_type if order.order_type in order_type_stats else "delivery"
            order_type_stats[otype]["orders"] += 1
            order_type_stats[otype]["revenue"] += order_total

            # Channel split
            ch = _classify_channel(order)
            channel_stats[ch]["orders"] += 1
            channel_stats[ch]["revenue"] += order_total

            # Local timestamp for daily trend & peak hours
            local_dt = timezone.localtime(order.created_at) if order.created_at else timezone.localtime()
            day_str = local_dt.date().isoformat()
            if day_str not in daily_map:
                daily_map[day_str] = {
                    "date": day_str,
                    "orders": 0,
                    "revenue": Decimal("0.00"),
                    "estimated_cogs": Decimal("0.00"),
                    "estimated_profit": Decimal("0.00"),
                }
            daily_map[day_str]["orders"] += 1
            daily_map[day_str]["revenue"] += order_total
            daily_map[day_str]["estimated_cogs"] += order_cogs
            daily_map[day_str]["estimated_profit"] += order_profit

            # Peak hours
            hr = local_dt.hour
            hourly_stats[hr]["orders"] += 1
            hourly_stats[hr]["revenue"] += order_total

            # Per-dish revenue & margin
            for item in order.items.all():
                dname = (item.item_name or "Unknown Dish").strip()
                qty = item.quantity or Decimal("0")
                line_rev = item.line_total or Decimal("0.00")
                item_cogs = (
                    recipe_cost_map[item.item_id] * qty
                    if item.item_id and item.item_id in recipe_cost_map
                    else Decimal("0.00")
                )
                if dname not in dish_map:
                    dish_map[dname] = {
                        "dish_name": dname,
                        "qty_sold": Decimal("0"),
                        "revenue": Decimal("0.00"),
                        "estimated_cogs": Decimal("0.00"),
                    }
                dish_map[dname]["qty_sold"] += qty
                dish_map[dname]["revenue"] += line_rev
                dish_map[dname]["estimated_cogs"] += item_cogs

        gross_profit = net_revenue - estimated_cogs
        gross_margin_pct = (
            round(float(gross_profit) / float(net_revenue) * 100.0, 1)
            if net_revenue > 0
            else 0.0
        )

        # Operating Expenses in the same date window
        exp_qs = RestaurantExpense.objects.filter(company=company).select_related("supplier")
        if start_d:
            exp_qs = exp_qs.filter(expense_date__gte=start_d)
        if end_d:
            exp_qs = exp_qs.filter(expense_date__lte=end_d)
        expenses_list = list(exp_qs.order_by("-expense_date", "-created_at"))
        total_expenses = sum((e.amount or Decimal("0.00")) for e in expenses_list)
        net_profit = gross_profit - total_expenses
        net_margin_pct = (
            round(float(net_profit) / float(net_revenue) * 100.0, 1)
            if net_revenue > 0
            else 0.0
        )

        cat_labels = dict(RestaurantExpense.CATEGORY_CHOICES)
        exp_cat_map: Dict[str, Dict[str, Any]] = {}
        for exp in expenses_list:
            ck = exp.category or RestaurantExpense.CAT_OTHER
            if ck not in exp_cat_map:
                exp_cat_map[ck] = {
                    "category": ck,
                    "label": cat_labels.get(ck, ck.replace("_", " ").title()),
                    "amount": Decimal("0.00"),
                    "count": 0,
                }
            exp_cat_map[ck]["amount"] += exp.amount or Decimal("0.00")
            exp_cat_map[ck]["count"] += 1
        expenses_by_category = [
            {
                "category": v["category"],
                "label": v["label"],
                "amount": round(float(v["amount"]), 2),
                "count": v["count"],
            }
            for v in sorted(exp_cat_map.values(), key=lambda x: x["amount"], reverse=True)
        ]

        avg_order_value = (
            round(float(net_revenue) / total_orders, 2) if total_orders > 0 else 0.0
        )

        # Format order type breakdown
        order_type_breakdown = []
        for entry in order_type_stats.values():
            rev_f = float(entry["revenue"])
            share = round(rev_f / float(net_revenue) * 100.0, 1) if net_revenue > 0 else 0.0
            order_type_breakdown.append({
                "key": entry["key"],
                "label": entry["label"],
                "orders": entry["orders"],
                "revenue": round(rev_f, 2),
                "share_pct": share,
            })

        # Format channel breakdown
        channel_breakdown = []
        for entry in channel_stats.values():
            rev_f = float(entry["revenue"])
            share = round(rev_f / float(net_revenue) * 100.0, 1) if net_revenue > 0 else 0.0
            channel_breakdown.append({
                "channel": entry["channel"],
                "orders": entry["orders"],
                "revenue": round(rev_f, 2),
                "share_pct": share,
            })

        # Daily revenue trend (sorted ascending by date)
        daily_trend = [
            {
                "date": d["date"],
                "orders": d["orders"],
                "revenue": round(float(d["revenue"]), 2),
                "estimated_cogs": round(float(d["estimated_cogs"]), 2),
                "estimated_profit": round(float(d["estimated_profit"]), 2),
            }
            for _, d in sorted(daily_map.items(), key=lambda kv: kv[0])
        ]

        # Top 15 dishes by revenue
        top_dishes_raw = sorted(
            dish_map.values(), key=lambda x: x["revenue"], reverse=True
        )[:15]
        top_dishes = []
        for d in top_dishes_raw:
            rev_f = float(d["revenue"])
            cogs_f = float(d["estimated_cogs"])
            gp_f = rev_f - cogs_f
            margin = round((gp_f / rev_f) * 100.0, 1) if rev_f > 0 else 0.0
            top_dishes.append({
                "dish_name": d["dish_name"],
                "qty_sold": float(d["qty_sold"]),
                "revenue": round(rev_f, 2),
                "estimated_cogs": round(cogs_f, 2),
                "gross_profit": round(gp_f, 2),
                "margin_pct": margin,
            })

        # Peak hours
        max_hr_orders = max((h["orders"] for h in hourly_stats), default=0)
        peak_hour_label = ""
        peak_hours = []
        for h in hourly_stats:
            is_peak = max_hr_orders > 0 and h["orders"] == max_hr_orders
            if is_peak and not peak_hour_label:
                peak_hour_label = h["label"]
            peak_hours.append({
                "hour": h["hour"],
                "label": h["label"],
                "orders": h["orders"],
                "revenue": round(float(h["revenue"]), 2),
                "is_peak": is_peak,
            })

        return Response({
            "range": range_key,
            "start_date": start_d.isoformat() if start_d else None,
            "end_date": end_d.isoformat() if end_d else None,
            "kpis": {
                "net_revenue": round(float(net_revenue), 2),
                "total_orders": total_orders,
                "cancelled_orders": cancelled_orders,
                "avg_order_value": avg_order_value,
                "delivery_fees_total": round(float(delivery_fees_total), 2),
                "estimated_cogs": round(float(estimated_cogs), 2),
                "gross_profit": round(float(gross_profit), 2),
                "gross_margin_pct": gross_margin_pct,
                "total_expenses": round(float(total_expenses), 2),
                "net_profit": round(float(net_profit), 2),
                "net_margin_pct": net_margin_pct,
                "unsettled_cod_total": round(float(unsettled_cod_total), 2),
            },
            "expenses_by_category": expenses_by_category,
            "order_type_breakdown": order_type_breakdown,
            "channel_breakdown": channel_breakdown,
            "daily_trend": daily_trend,
            "top_dishes": top_dishes,
            "peak_hours": peak_hours,
            "peak_hour_label": peak_hour_label,
        })


class RestaurantReportsExportCSVAPIView(BusinessAPIView):
    """
    GET /api/operations/restaurant/reports/export/?range=today|7d|30d|all&start_date=...&end_date=...
    Returns downloadable text/csv financial report.
    """

    required_business_permission = None

    def get(self, request):
        company = self.company
        range_key, start_d, end_d = _resolve_date_window(request)
        orders = list(_filtered_orders_queryset(company, start_d, end_d))
        recipe_cost_map = _build_recipe_unit_cost_map(company)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Order Ref",
            "Date/Time",
            "Customer",
            "Order Type",
            "Channel",
            "Status",
            "Subtotal",
            "Delivery Fee",
            "Total",
            "Est. COGS",
            "Est. Profit",
            "COD Settled",
        ])

        total_net_rev = Decimal("0.00")
        total_cogs = Decimal("0.00")
        for order in orders:
            local_dt = timezone.localtime(order.created_at) if order.created_at else None
            dt_str = local_dt.strftime("%Y-%m-%d %H:%M") if local_dt else ""
            is_cancelled = order.status == Order.STATUS_CANCELLED
            order_total = order.total or Decimal("0.00")
            cogs = Decimal("0.00") if is_cancelled else _compute_order_cogs(order, recipe_cost_map)
            profit = Decimal("0.00") if is_cancelled else (order_total - cogs)
            if not is_cancelled:
                total_net_rev += order_total
                total_cogs += cogs
            cod_label = (
                "Yes"
                if order.cod_settled
                else ("Pending" if order.cod_collected else "N/A")
            )
            writer.writerow([
                order.order_number,
                dt_str,
                order.customer_name or "Guest",
                (order.order_type or "delivery").replace("_", " ").title(),
                _classify_channel(order),
                (order.status or "").replace("_", " ").title(),
                f"{float(order.subtotal or 0):.2f}",
                f"{float(order.delivery_fee or 0):.2f}",
                f"{float(order_total):.2f}",
                f"{float(cogs):.2f}",
                f"{float(profit):.2f}",
                cod_label,
            ])

        exp_qs = RestaurantExpense.objects.filter(company=company)
        if start_d:
            exp_qs = exp_qs.filter(expense_date__gte=start_d)
        if end_d:
            exp_qs = exp_qs.filter(expense_date__lte=end_d)
        total_expenses = sum((e.amount or Decimal("0.00")) for e in exp_qs)
        gross_profit = total_net_rev - total_cogs
        net_profit = gross_profit - total_expenses

        writer.writerow([])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", "Net Revenue", "Est. COGS", "Operating Expenses", "Net Profit"])
        writer.writerow([
            "TOTALS", "", "", "", "", "", "", "",
            f"{float(total_net_rev):.2f}",
            f"{float(total_cogs):.2f}",
            f"{float(total_expenses):.2f}",
            f"{float(net_profit):.2f}",
        ])

        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="restaurant_financial_report_{range_key}.csv"'
        )
        return response


def _serialize_expense(exp: RestaurantExpense) -> Dict[str, Any]:
    return {
        "id": exp.id,
        "title": exp.title,
        "category": exp.category,
        "category_label": exp.get_category_display(),
        "amount": round(float(exp.amount or 0), 2),
        "expense_date": exp.expense_date.isoformat() if exp.expense_date else None,
        "supplier_id": exp.supplier_id,
        "supplier_name": exp.supplier.name if exp.supplier else "",
        "notes": exp.notes or "",
        "recorded_by": (
            (exp.recorded_by.get_full_name() or exp.recorded_by.username)
            if exp.recorded_by
            else ""
        ),
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
    }


class RestaurantExpenseListCreateAPIView(BusinessAPIView):
    """GET / POST /api/operations/restaurant/expenses/"""

    required_business_permission = None

    def get(self, request):
        company = self.company
        _, start_d, end_d = _resolve_date_window(request)
        category = str(request.query_params.get("category") or "").strip().lower()

        qs = RestaurantExpense.objects.filter(company=company).select_related("supplier", "recorded_by")
        if start_d:
            qs = qs.filter(expense_date__gte=start_d)
        if end_d:
            qs = qs.filter(expense_date__lte=end_d)
        if category and category != "all":
            qs = qs.filter(category=category)

        rows = list(qs.order_by("-expense_date", "-created_at")[:300])
        total_amount = sum((e.amount or Decimal("0.00")) for e in rows)
        return Response({
            "total_expenses": round(float(total_amount), 2),
            "categories": [
                {"key": k, "label": lbl} for k, lbl in RestaurantExpense.CATEGORY_CHOICES
            ],
            "expenses": [_serialize_expense(e) for e in rows],
        })

    def post(self, request):
        company = self.company
        title = str(request.data.get("title") or "").strip()[:200]
        if not title:
            return Response({"title": "Expense title is required."}, status=400)

        category = str(request.data.get("category") or RestaurantExpense.CAT_OTHER).strip().lower()
        valid_cats = {k for k, _ in RestaurantExpense.CATEGORY_CHOICES}
        if category not in valid_cats:
            category = RestaurantExpense.CAT_OTHER

        try:
            amount = Decimal(str(request.data.get("amount", "0")))
        except Exception:
            return Response({"amount": "Invalid amount."}, status=400)
        if amount <= 0:
            return Response({"amount": "Amount must be greater than 0."}, status=400)

        exp_date = _parse_iso_date(request.data.get("expense_date")) or timezone.localdate()

        supplier_obj = None
        raw_sid = request.data.get("supplier_id")
        if raw_sid is not None and str(raw_sid).strip() != "":
            supplier_obj = get_object_or_404(RestaurantSupplier, pk=raw_sid, company=company)

        exp = RestaurantExpense.objects.create(
            company=company,
            title=title,
            category=category,
            amount=amount,
            expense_date=exp_date,
            supplier=supplier_obj,
            notes=str(request.data.get("notes") or "").strip(),
            recorded_by=request.user,
        )
        return Response(_serialize_expense(exp), status=201)


class RestaurantExpenseDetailAPIView(BusinessAPIView):
    """DELETE /api/operations/restaurant/expenses/<pk>/"""

    required_business_permission = None

    def delete(self, request, pk: int):
        exp = get_object_or_404(RestaurantExpense, pk=pk, company=self.company)
        exp.delete()
        return Response(status=204)
