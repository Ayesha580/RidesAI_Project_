"""
Staff Attendance & Suppliers Management DRF APIs (PRD §3 / §9).
Strictly multi-tenant isolated by `company=request.user.company`.
"""

from datetime import datetime

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.models import StaffAttendance, Supplier


def _parse_date(raw_val):
    if not raw_val:
        return timezone.localdate()
    try:
        return datetime.strptime(str(raw_val).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


def _parse_time(raw_val):
    if raw_val is None or str(raw_val).strip() == "":
        return None
    s = str(raw_val).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s[:8], fmt).time()
        except ValueError:
            continue
    return None


def _serialize_supplier(s: Supplier) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "contact_person": s.contact_person,
        "phone": s.phone,
        "email": s.email,
        "category": s.category,
        "address": s.address,
        "payment_terms": s.payment_terms,
        "is_active": s.is_active,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


class StaffAttendanceAPIView(APIView):
    """GET / POST /api/operations/attendance/?date=YYYY-MM-DD"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        target_date = _parse_date(request.query_params.get("date"))
        staff_qs = (
            User.objects.filter(company=company, is_active=True)
            .exclude(is_superuser=True)
            .select_related("staff_role")
            .order_by("first_name", "username")
        )
        records = {
            r.staff_user_id: r
            for r in StaffAttendance.objects.filter(company=company, date=target_date)
        }

        summary = {"present": 0, "late": 0, "absent": 0, "half_day": 0, "on_leave": 0, "unmarked": 0}
        rows = []
        for u in staff_qs:
            rec = records.get(u.id)
            st = rec.status if rec else None
            if st in summary:
                summary[st] += 1
            else:
                summary["unmarked"] += 1

            role_label = (u.staff_role.name if u.staff_role else (u.role or "Staff")).title()
            rows.append({
                "staff_user_id": u.id,
                "name": u.get_full_name().strip() or u.username,
                "email": u.email,
                "role": role_label,
                "date": target_date.isoformat(),
                "status": st or "unmarked",
                "check_in_time": rec.check_in_time.strftime("%H:%M") if (rec and rec.check_in_time) else "",
                "check_out_time": rec.check_out_time.strftime("%H:%M") if (rec and rec.check_out_time) else "",
                "notes": rec.notes if rec else "",
                "updated_at": rec.updated_at.isoformat() if (rec and rec.updated_at) else None,
            })

        return Response({
            "date": target_date.isoformat(),
            "summary": summary,
            "staff": rows,
        }, status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        staff_user_id = request.data.get("staff_user_id")
        if not staff_user_id:
            return Response({"staff_user_id": "staff_user_id is required."}, status=400)

        # Strictly enforce that staff_user belongs to request.user.company
        staff_user = get_object_or_404(User, pk=staff_user_id, company=company)
        target_date = _parse_date(request.data.get("date"))

        st = str(request.data.get("status") or StaffAttendance.STATUS_PRESENT).strip().lower()
        valid_statuses = {c[0] for c in StaffAttendance.STATUS_CHOICES}
        if st not in valid_statuses:
            return Response({"status": f"Invalid status. Choose from: {', '.join(sorted(valid_statuses))}."}, status=400)

        check_in = _parse_time(request.data.get("check_in_time"))
        check_out = _parse_time(request.data.get("check_out_time"))
        notes = str(request.data.get("notes") or "").strip()[:255]

        rec, _ = StaffAttendance.objects.update_or_create(
            company=company,
            staff_user=staff_user,
            date=target_date,
            defaults={
                "status": st,
                "check_in_time": check_in,
                "check_out_time": check_out,
                "notes": notes,
            },
        )
        return Response({
            "id": rec.id,
            "staff_user_id": rec.staff_user_id,
            "date": rec.date.isoformat(),
            "status": rec.status,
            "check_in_time": rec.check_in_time.strftime("%H:%M") if rec.check_in_time else "",
            "check_out_time": rec.check_out_time.strftime("%H:%M") if rec.check_out_time else "",
            "notes": rec.notes,
        }, status=200)


class SupplierListCreateAPIView(APIView):
    """GET / POST /api/operations/suppliers/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = Supplier.objects.filter(company=company).order_by("name")
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(phone__icontains=search)
                | Q(category__icontains=search)
            )
        category = (request.query_params.get("category") or "").strip()
        if category and category.lower() != "all":
            qs = qs.filter(category__iexact=category)

        return Response([_serialize_supplier(s) for s in qs], status=200)

    def post(self, request):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        name = str(request.data.get("name") or "").strip()[:200]
        if not name:
            return Response({"name": "Supplier name is required."}, status=400)

        supplier = Supplier.objects.create(
            company=company,
            name=name,
            contact_person=str(request.data.get("contact_person") or "").strip()[:160],
            phone=str(request.data.get("phone") or "").strip()[:40],
            email=str(request.data.get("email") or "").strip()[:254],
            category=str(request.data.get("category") or "").strip()[:100],
            address=str(request.data.get("address") or "").strip(),
            payment_terms=str(request.data.get("payment_terms") or "").strip()[:80],
            is_active=bool(request.data.get("is_active", True)),
            notes=str(request.data.get("notes") or "").strip(),
        )
        return Response(_serialize_supplier(supplier), status=201)


class SupplierDetailAPIView(APIView):
    """PATCH / DELETE /api/operations/suppliers/<int:pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        supplier = get_object_or_404(Supplier, pk=pk, company=company)
        for field, maxlen in [
            ("name", 200),
            ("contact_person", 160),
            ("phone", 40),
            ("email", 254),
            ("category", 100),
            ("payment_terms", 80),
        ]:
            if field in request.data:
                val = str(request.data.get(field) or "").strip()[:maxlen]
                if field == "name" and not val:
                    continue
                setattr(supplier, field, val)
        if "address" in request.data:
            supplier.address = str(request.data.get("address") or "").strip()
        if "notes" in request.data:
            supplier.notes = str(request.data.get("notes") or "").strip()
        if "is_active" in request.data:
            supplier.is_active = bool(request.data["is_active"])

        supplier.save()
        return Response(_serialize_supplier(supplier), status=200)

    def delete(self, request, pk):
        company = getattr(request.user, "company", None)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        supplier = get_object_or_404(Supplier, pk=pk, company=company)
        supplier.delete()
        return Response(status=204)
