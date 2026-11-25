"""
Restaurant Interactive Floor Plan & Smart Reservations APIs.
Strictly multi-tenant (scoped to `request.user.company`) and PostgreSQL 16 compatible.

Endpoints:
- GET  /api/operations/restaurant/floor-plan/
- POST /api/operations/restaurant/tables/<table_id>/status/
- GET / POST   /api/operations/restaurant/reservations/
- PATCH / DEL  /api/operations/restaurant/reservations/<pk>/
- POST /api/operations/restaurant/reservations/<pk>/seat/
- POST /api/operations/restaurant/reservations/<pk>/complete/
"""

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.customer_recall_views import upsert_guest_customer
from operations.models import Order, RestaurantTable, TableReservation

ACTIVE_RESERVATION_STATUSES = [
    TableReservation.STATUS_PENDING,
    TableReservation.STATUS_CONFIRMED,
    TableReservation.STATUS_SEATED,
]

ACTIVE_ORDER_STATUSES = [
    Order.STATUS_NEW,
    Order.STATUS_PENDING,
    Order.STATUS_CONFIRMED,
    Order.STATUS_PREPARING,
    Order.STATUS_PREPARED,
    Order.STATUS_READY,
]

CONFLICT_WINDOW_MINUTES = 90


def parse_reservation_datetime(raw_date: Any, raw_time: Any) -> Tuple[date, time, datetime]:
    """
    Parses YYYY-MM-DD and HH:MM[:SS] (or 12h like '7:30 PM') into (date, time, aware datetime).
    Raises ValueError on invalid input.
    """
    if isinstance(raw_date, date) and not isinstance(raw_date, datetime):
        d = raw_date
    else:
        s_date = str(raw_date or "").strip()
        if not s_date:
            raise ValueError("Reservation date (YYYY-MM-DD) is required.")
        try:
            d = date.fromisoformat(s_date[:10])
        except ValueError:
            raise ValueError("Invalid reservation_date format. Expected YYYY-MM-DD.")

    if isinstance(raw_time, time):
        t = raw_time
    else:
        s_time = str(raw_time or "").strip().upper()
        if not s_time:
            raise ValueError("Reservation time (HH:MM) is required.")
        t = None
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
            try:
                t = datetime.strptime(s_time, fmt).time()
                break
            except ValueError:
                continue
        if t is None:
            raise ValueError("Invalid reservation_time format. Expected HH:MM (e.g. 19:30 or 7:30 PM).")

    tz = timezone.get_current_timezone()
    naive_dt = datetime.combine(d, t)
    aware_dt = timezone.make_aware(naive_dt, tz)
    return d, t, aware_dt


def has_table_conflict(
    company,
    table: RestaurantTable,
    reserved_at: datetime,
    exclude_id: Optional[int] = None,
) -> bool:
    """
    Returns True if `table` already has an active reservation (pending/confirmed/seated)
    within a ±90-minute window around `reserved_at`.
    """
    if not company or not table:
        return False
    window_start = reserved_at - timedelta(minutes=CONFLICT_WINDOW_MINUTES)
    window_end = reserved_at + timedelta(minutes=CONFLICT_WINDOW_MINUTES)
    qs = TableReservation.objects.filter(
        company=company,
        table=table,
        status__in=ACTIVE_RESERVATION_STATUSES,
        reserved_at__gt=window_start,
        reserved_at__lt=window_end,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def find_available_table_for_party(
    company,
    party_size: int,
    reserved_at: datetime,
    preferred_section: Optional[str] = None,
) -> Optional[RestaurantTable]:
    """
    Finds the best-fit (smallest capacity >= party_size) table in `company` with no
    90-minute reservation conflict at `reserved_at`.
    """
    qs = RestaurantTable.objects.filter(company=company, capacity__gte=max(1, party_size)).order_by("capacity", "table_number")
    if preferred_section:
        sec_qs = qs.filter(section__iexact=preferred_section.strip())
        for tbl in sec_qs:
            if not has_table_conflict(company, tbl, reserved_at):
                return tbl
    for tbl in qs:
        if not has_table_conflict(company, tbl, reserved_at):
            return tbl
    return None


def serialize_reservation(r: TableReservation) -> Dict[str, Any]:
    return {
        "id": r.id,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "party_size": r.party_size,
        "reservation_date": r.reservation_date.isoformat() if r.reservation_date else None,
        "reservation_time": r.reservation_time.strftime("%H:%M") if r.reservation_time else None,
        "reserved_at": r.reserved_at.isoformat() if r.reserved_at else None,
        "table_id": r.table_id,
        "table_number": r.table.table_number if r.table else "",
        "table_section": r.table.section if r.table else "",
        "table_capacity": r.table.capacity if r.table else None,
        "status": r.status,
        "status_label": r.get_status_display(),
        "special_requests": r.special_requests or "",
        "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class RestaurantFloorPlanAPIView(APIView):
    """GET /api/operations/restaurant/floor-plan/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        now = timezone.now()
        today = timezone.localdate()

        tables = list(
            RestaurantTable.objects.filter(company=company)
            .select_related("active_order")
            .order_by("section", "table_number")
        )

        # Fetch active dine-in orders for this company to attach live order context to tables
        active_dine_in_orders = list(
            Order.objects.filter(
                company=company,
                order_type=Order.ORDER_TYPE_DINE_IN,
                status__in=ACTIVE_ORDER_STATUSES,
            )
            .order_by("-created_at")
        )
        order_by_table_id: Dict[int, Order] = {}
        order_by_table_num: Dict[str, Order] = {}
        for o in active_dine_in_orders:
            if o.table_id and o.table_id not in order_by_table_id:
                order_by_table_id[o.table_id] = o
            t_key = (o.table_number or "").strip().lower()
            if t_key and t_key not in order_by_table_num:
                order_by_table_num[t_key] = o

        # Fetch today's upcoming active reservations
        todays_reservations = list(
            TableReservation.objects.filter(
                company=company,
                reservation_date=today,
                status__in=[TableReservation.STATUS_PENDING, TableReservation.STATUS_CONFIRMED],
                reserved_at__gte=now - timedelta(minutes=30),
            )
            .select_related("table")
            .order_by("reserved_at")
        )
        next_res_by_table: Dict[int, TableReservation] = {}
        for res in todays_reservations:
            if res.table_id and res.table_id not in next_res_by_table:
                next_res_by_table[res.table_id] = res

        by_status = {
            RestaurantTable.STATUS_AVAILABLE: 0,
            RestaurantTable.STATUS_OCCUPIED: 0,
            RestaurantTable.STATUS_RESERVED: 0,
            RestaurantTable.STATUS_CLEANING: 0,
        }
        by_section = {
            RestaurantTable.SECTION_INDOOR: 0,
            RestaurantTable.SECTION_OUTDOOR: 0,
            RestaurantTable.SECTION_VIP: 0,
            RestaurantTable.SECTION_ROOFTOP: 0,
        }

        serialized_tables = []
        for tbl in tables:
            st = tbl.status or RestaurantTable.STATUS_AVAILABLE
            sec = tbl.section or RestaurantTable.SECTION_INDOOR
            by_status[st] = by_status.get(st, 0) + 1
            by_section[sec] = by_section.get(sec, 0) + 1

            # Resolve live active order (either explicit FK or latest active dine-in order on this table)
            live_order = tbl.active_order
            if live_order and live_order.status not in ACTIVE_ORDER_STATUSES:
                live_order = None
            if not live_order:
                live_order = order_by_table_id.get(tbl.id) or order_by_table_num.get(tbl.table_number.strip().lower())

            active_order_summary = None
            if live_order:
                elapsed_min = max(0, int((now - live_order.created_at).total_seconds()) // 60) if live_order.created_at else 0
                active_order_summary = {
                    "order_id": live_order.id,
                    "reference": live_order.order_number,
                    "total": round(float(live_order.total or 0), 2),
                    "status": live_order.status,
                    "elapsed_minutes": elapsed_min,
                    "customer_name": live_order.customer_name,
                }

            next_res = next_res_by_table.get(tbl.id)
            next_res_summary = None
            if next_res:
                next_res_summary = {
                    "id": next_res.id,
                    "customer_name": next_res.customer_name,
                    "customer_phone": next_res.customer_phone,
                    "party_size": next_res.party_size,
                    "reservation_time": next_res.reservation_time.strftime("%H:%M"),
                    "status": next_res.status,
                }

            serialized_tables.append({
                "id": tbl.id,
                "table_number": tbl.table_number,
                "capacity": tbl.capacity,
                "section": sec,
                "zone": tbl.zone,
                "status": st,
                "guest_name": tbl.guest_name,
                "guest_phone": tbl.guest_phone,
                "active_order": active_order_summary,
                "next_reservation": next_res_summary,
                "notes": tbl.notes,
            })

        return Response({
            "tables": serialized_tables,
            "summary": {
                "total": len(serialized_tables),
                "by_status": by_status,
                "by_section": by_section,
            },
        }, status=200)


class RestaurantTableStatusAPIView(APIView):
    """POST /api/operations/restaurant/tables/<table_id>/status/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, table_id: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        table = get_object_or_404(RestaurantTable, pk=table_id, company=company)
        new_status = str(request.data.get("status") or "").strip().lower()
        valid_statuses = {c[0] for c in RestaurantTable.STATUS_CHOICES}
        if new_status not in valid_statuses:
            return Response(
                {"status": f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}."},
                status=400,
            )

        table.status = new_status
        if new_status in (RestaurantTable.STATUS_AVAILABLE, RestaurantTable.STATUS_CLEANING):
            table.guest_name = ""
            table.guest_phone = ""
            table.reservation_time = ""
            table.active_order = None
        table.save()

        return Response({
            "id": table.id,
            "table_number": table.table_number,
            "status": table.status,
            "section": table.section,
            "capacity": table.capacity,
        }, status=200)


class RestaurantReservationListCreateAPIView(APIView):
    """GET / POST /api/operations/restaurant/reservations/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = TableReservation.objects.filter(company=company).select_related("table")

        date_param = (request.query_params.get("date") or "upcoming").strip().lower()
        today = timezone.localdate()
        if date_param == "today":
            qs = qs.filter(reservation_date=today)
        elif date_param == "tomorrow":
            qs = qs.filter(reservation_date=today + timedelta(days=1))
        elif date_param == "upcoming":
            qs = qs.filter(reservation_date__gte=today)
        elif date_param != "all":
            try:
                parsed_d = date.fromisoformat(date_param[:10])
                qs = qs.filter(reservation_date=parsed_d)
            except ValueError:
                pass

        status_param = (request.query_params.get("status") or "").strip().lower()
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)

        return Response([serialize_reservation(r) for r in qs[:150]], status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        customer_name = str(request.data.get("customer_name") or "").strip()
        if not customer_name:
            return Response({"customer_name": "Customer name is required."}, status=400)

        customer_phone = str(request.data.get("customer_phone") or "").strip()
        try:
            party_size = max(1, int(request.data.get("party_size") or 2))
        except (TypeError, ValueError):
            return Response({"party_size": "Party size must be a positive integer."}, status=400)

        try:
            res_date, res_time, reserved_at = parse_reservation_datetime(
                request.data.get("reservation_date"),
                request.data.get("reservation_time"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        table_obj = None
        raw_table_id = request.data.get("table_id") or request.data.get("table")
        if raw_table_id:
            table_obj = get_object_or_404(RestaurantTable, pk=raw_table_id, company=company)
            if has_table_conflict(company, table_obj, reserved_at):
                return Response(
                    {
                        "detail": (
                            f"Table {table_obj.table_number} is already booked within 90 minutes "
                            f"of {res_time.strftime('%H:%M')} on {res_date.isoformat()}. Please choose another table or time."
                        )
                    },
                    status=409,
                )
        else:
            table_obj = find_available_table_for_party(company, party_size, reserved_at)

        status_val = str(request.data.get("status") or TableReservation.STATUS_CONFIRMED).strip().lower()
        if status_val not in {c[0] for c in TableReservation.STATUS_CHOICES}:
            status_val = TableReservation.STATUS_CONFIRMED

        reservation = TableReservation.objects.create(
            company=company,
            table=table_obj,
            customer_name=customer_name,
            customer_phone=customer_phone,
            party_size=party_size,
            reservation_date=res_date,
            reservation_time=res_time,
            reserved_at=reserved_at,
            status=status_val,
            special_requests=str(request.data.get("special_requests") or "").strip(),
            source=str(request.data.get("source") or "dashboard").strip().lower()[:20],
        )

        # Auto-remember guest customer
        upsert_guest_customer(company=company, name=customer_name, phone=customer_phone)

        return Response(serialize_reservation(reservation), status=201)


class RestaurantReservationDetailAPIView(APIView):
    """PATCH / DELETE /api/operations/restaurant/reservations/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        reservation = get_object_or_404(TableReservation.objects.select_related("table"), pk=pk, company=company)

        new_date = request.data.get("reservation_date", reservation.reservation_date)
        new_time = request.data.get("reservation_time", reservation.reservation_time)
        try:
            res_date, res_time, reserved_at = parse_reservation_datetime(new_date, new_time)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        new_table = reservation.table
        if "table_id" in request.data or "table" in request.data:
            raw_tid = request.data.get("table_id", request.data.get("table"))
            new_table = get_object_or_404(RestaurantTable, pk=raw_tid, company=company) if raw_tid else None

        new_status = str(request.data.get("status") or reservation.status).strip().lower()
        if new_status not in {c[0] for c in TableReservation.STATUS_CHOICES}:
            new_status = reservation.status

        if new_status in ACTIVE_RESERVATION_STATUSES and new_table:
            if has_table_conflict(company, new_table, reserved_at, exclude_id=reservation.id):
                return Response(
                    {"detail": f"Table {new_table.table_number} has a conflicting reservation within 90 minutes."},
                    status=409,
                )

        if "customer_name" in request.data and str(request.data["customer_name"]).strip():
            reservation.customer_name = str(request.data["customer_name"]).strip()
        if "customer_phone" in request.data:
            reservation.customer_phone = str(request.data["customer_phone"] or "").strip()
        if "party_size" in request.data:
            reservation.party_size = max(1, int(request.data["party_size"] or 1))
        if "special_requests" in request.data:
            reservation.special_requests = str(request.data["special_requests"] or "").strip()

        reservation.reservation_date = res_date
        reservation.reservation_time = res_time
        reservation.reserved_at = reserved_at
        reservation.table = new_table
        reservation.status = new_status
        reservation.save()

        return Response(serialize_reservation(reservation), status=200)

    def delete(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        reservation = get_object_or_404(TableReservation, pk=pk, company=company)
        reservation.delete()
        return Response(status=204)


class RestaurantReservationSeatAPIView(APIView):
    """
    POST /api/operations/restaurant/reservations/<pk>/seat/
    1-click Seat Guest: marks reservation 'seated' AND sets assigned table to 'occupied'.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        reservation = get_object_or_404(TableReservation.objects.select_related("table"), pk=pk, company=company)

        # Allow optional table assignment at seat time if none was assigned yet
        raw_tid = request.data.get("table_id")
        if raw_tid:
            reservation.table = get_object_or_404(RestaurantTable, pk=raw_tid, company=company)

        reservation.status = TableReservation.STATUS_SEATED
        reservation.save(update_fields=["status", "table", "updated_at"])

        if reservation.table:
            tbl = reservation.table
            tbl.status = RestaurantTable.STATUS_OCCUPIED
            tbl.guest_name = reservation.customer_name
            tbl.guest_phone = reservation.customer_phone
            tbl.reservation_time = reservation.reservation_time.strftime("%H:%M")
            tbl.save(update_fields=["status", "guest_name", "guest_phone", "reservation_time", "updated_at"])

        return Response(serialize_reservation(reservation), status=200)


class RestaurantReservationCompleteAPIView(APIView):
    """
    POST /api/operations/restaurant/reservations/<pk>/complete/
    Marks reservation 'completed' AND frees the assigned table ('available' or 'cleaning').
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        reservation = get_object_or_404(TableReservation.objects.select_related("table"), pk=pk, company=company)
        reservation.status = TableReservation.STATUS_COMPLETED
        reservation.save(update_fields=["status", "updated_at"])

        next_table_status = str(request.data.get("table_status") or RestaurantTable.STATUS_AVAILABLE).strip().lower()
        if next_table_status not in (RestaurantTable.STATUS_AVAILABLE, RestaurantTable.STATUS_CLEANING):
            next_table_status = RestaurantTable.STATUS_AVAILABLE

        if reservation.table:
            tbl = reservation.table
            tbl.status = next_table_status
            tbl.guest_name = ""
            tbl.guest_phone = ""
            tbl.reservation_time = ""
            tbl.active_order = None
            tbl.save(update_fields=["status", "guest_name", "guest_phone", "reservation_time", "active_order", "updated_at"])

        return Response(serialize_reservation(reservation), status=200)
