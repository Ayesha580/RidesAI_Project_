"""
Restaurant Visual Floor-Plan Table Management API.
Strictly multi-tenant isolated by `company=request.user.company`.
"""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import Order, RestaurantTable


def _serialize_table(t: RestaurantTable) -> dict:
    return {
        "id": t.id,
        "table_number": t.table_number,
        "capacity": t.capacity,
        "status": t.status,
        "status_label": t.get_status_display(),
        "section": t.section or RestaurantTable.SECTION_INDOOR,
        "zone": t.zone,
        "shape": t.shape,
        "pos_x": t.pos_x,
        "pos_y": t.pos_y,
        "guest_name": t.guest_name,
        "guest_phone": t.guest_phone,
        "reservation_time": t.reservation_time,
        "active_order_id": t.active_order_id,
        "active_order_number": t.active_order.order_number if t.active_order else None,
        "notes": t.notes,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


class RestaurantTableListCreateAPIView(APIView):
    """GET / POST /api/operations/tables/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = RestaurantTable.objects.filter(company=company).select_related("active_order")
        zone = (request.query_params.get("zone") or "").strip()
        if zone:
            qs = qs.filter(zone__iexact=zone)
        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response([_serialize_table(t) for t in qs], status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        table_number = str(request.data.get("table_number") or "").strip()[:40]
        if not table_number:
            return Response({"table_number": "Table number/label is required."}, status=400)

        if RestaurantTable.objects.filter(company=company, table_number__iexact=table_number).exists():
            return Response({"table_number": f"Table '{table_number}' already exists."}, status=400)

        shape = str(request.data.get("shape") or RestaurantTable.SHAPE_SQUARE).strip().lower()
        if shape not in {c[0] for c in RestaurantTable.SHAPE_CHOICES}:
            shape = RestaurantTable.SHAPE_SQUARE

        status_val = str(request.data.get("status") or RestaurantTable.STATUS_AVAILABLE).strip().lower()
        if status_val not in {c[0] for c in RestaurantTable.STATUS_CHOICES}:
            status_val = RestaurantTable.STATUS_AVAILABLE

        count = RestaurantTable.objects.filter(company=company).count()
        default_x = 40 + (count % 4) * 165
        default_y = 40 + (count // 4) * 140

        section_val = str(request.data.get("section") or RestaurantTable.SECTION_INDOOR).strip().lower()
        if section_val not in {c[0] for c in RestaurantTable.SECTION_CHOICES}:
            section_val = RestaurantTable.SECTION_INDOOR

        table = RestaurantTable.objects.create(
            company=company,
            table_number=table_number,
            capacity=max(1, int(request.data.get("capacity", 4) or 4)),
            status=status_val,
            section=section_val,
            zone=str(request.data.get("zone") or section_val.title()).strip()[:60] or "Main Hall",
            shape=shape,
            pos_x=max(0, int(request.data.get("pos_x", default_x) if request.data.get("pos_x") is not None else default_x)),
            pos_y=max(0, int(request.data.get("pos_y", default_y) if request.data.get("pos_y") is not None else default_y)),
            guest_name=str(request.data.get("guest_name") or "").strip()[:160],
            guest_phone=str(request.data.get("guest_phone") or "").strip()[:40],
            reservation_time=str(request.data.get("reservation_time") or "").strip()[:60],
            notes=str(request.data.get("notes") or "").strip(),
        )
        return Response(_serialize_table(table), status=201)


class RestaurantTableDetailAPIView(APIView):
    """PATCH / DELETE /api/operations/tables/<int:pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        table = get_object_or_404(RestaurantTable, pk=pk, company=company)

        if "table_number" in request.data and str(request.data["table_number"]).strip():
            table.table_number = str(request.data["table_number"]).strip()[:40]
        if "capacity" in request.data:
            table.capacity = max(1, int(request.data["capacity"] or 1))
        if "status" in request.data:
            st = str(request.data["status"]).strip().lower()
            if st in {c[0] for c in RestaurantTable.STATUS_CHOICES}:
                table.status = st
                if st == RestaurantTable.STATUS_AVAILABLE and "guest_name" not in request.data:
                    table.guest_name = ""
                    table.guest_phone = ""
                    table.reservation_time = ""
                    table.active_order = None
        if "section" in request.data and str(request.data["section"]).strip():
            sec = str(request.data["section"]).strip().lower()
            if sec in {c[0] for c in RestaurantTable.SECTION_CHOICES}:
                table.section = sec
        if "zone" in request.data and str(request.data["zone"]).strip():
            table.zone = str(request.data["zone"]).strip()[:60]
        if "shape" in request.data:
            sh = str(request.data["shape"]).strip().lower()
            if sh in {c[0] for c in RestaurantTable.SHAPE_CHOICES}:
                table.shape = sh
        if "pos_x" in request.data and request.data["pos_x"] is not None:
            table.pos_x = max(0, int(request.data["pos_x"]))
        if "pos_y" in request.data and request.data["pos_y"] is not None:
            table.pos_y = max(0, int(request.data["pos_y"]))
        if "guest_name" in request.data:
            table.guest_name = str(request.data["guest_name"] or "").strip()[:160]
        if "guest_phone" in request.data:
            table.guest_phone = str(request.data["guest_phone"] or "").strip()[:40]
        if "reservation_time" in request.data:
            table.reservation_time = str(request.data["reservation_time"] or "").strip()[:60]
        if "notes" in request.data:
            table.notes = str(request.data["notes"] or "").strip()
        if "active_order_id" in request.data:
            oid = request.data.get("active_order_id")
            table.active_order = Order.objects.filter(company=company, pk=oid).first() if oid else None

        table.save()
        return Response(_serialize_table(table), status=200)

    def delete(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        table = get_object_or_404(RestaurantTable, pk=pk, company=company)
        table.delete()
        return Response(status=204)
