"""
Hospital Vertical DRF Views (Strictly Multi-Tenant Isolated).
Provides CRUD endpoints for Hospital Departments & Ward Bed Availability,
Lab / Diagnostic Test Bookings, and real-time Hospital Operations Summary.
"""

from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.models import Appointment, Doctor, HospitalDepartment, LabTestBooking, Patient


def _parse_date(val):
    if not val:
        return None
    if hasattr(val, "year"):
        return val
    try:
        return datetime.strptime(str(val).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _serialize_department(dept: HospitalDepartment) -> dict:
    return {
        "id": dept.id,
        "name": dept.name,
        "ward_type": dept.ward_type,
        "ward_type_label": dept.get_ward_type_display(),
        "floor_or_location": dept.floor_or_location,
        "total_beds": dept.total_beds,
        "available_beds": dept.available_beds,
        "occupied_beds": max(0, dept.total_beds - dept.available_beds),
        "is_24_7": dept.is_24_7,
        "head_doctor_id": dept.head_doctor_id,
        "head_doctor_name": dept.head_doctor.name if dept.head_doctor else None,
        "phone_extension": dept.phone_extension,
        "is_active": dept.is_active,
        "updated_at": dept.updated_at.isoformat() if dept.updated_at else None,
    }


def _serialize_lab_booking(b: LabTestBooking) -> dict:
    return {
        "id": b.id,
        "booking_number": b.booking_number,
        "patient_id": b.patient_id,
        "department_id": b.department_id,
        "department_name": b.department.name if b.department else None,
        "patient_name": b.patient_name,
        "patient_phone": b.patient_phone,
        "test_name": b.test_name,
        "price": str(b.price),
        "scheduled_date": b.scheduled_date.isoformat() if b.scheduled_date else None,
        "scheduled_time": b.scheduled_time,
        "status": b.status,
        "notes": b.notes,
        "source": b.source,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


class HospitalBaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_company(self, request):
        return getattr(request.user, "company", None)


class HospitalSummaryAPIView(HospitalBaseAPIView):
    """GET /api/operations/hospital/summary/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        today = timezone.localdate()
        depts = HospitalDepartment.objects.filter(company=company, is_active=True).select_related("head_doctor")
        bed_agg = depts.aggregate(total=Sum("total_beds"), available=Sum("available_beds"))
        total_beds = int(bed_agg.get("total") or 0)
        available_beds = int(bed_agg.get("available") or 0)

        doctors_count = Doctor.objects.filter(company=company, is_active=True).count()
        today_appointments = Appointment.objects.filter(company=company, appointment_date=today).count()
        pending_appointments = Appointment.objects.filter(
            company=company,
            status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_SCHEDULED, Appointment.STATUS_CONFIRMED],
        ).count()
        scheduled_labs = LabTestBooking.objects.filter(
            company=company,
            status__in=[LabTestBooking.STATUS_SCHEDULED, LabTestBooking.STATUS_CHECKED_IN],
        ).count()
        lab_revenue_today = (
            LabTestBooking.objects.filter(company=company, created_at__date=today)
            .exclude(status=LabTestBooking.STATUS_CANCELLED)
            .aggregate(total=Sum("price"))
            .get("total")
            or Decimal("0.00")
        )

        return Response({
            "departments_count": depts.count(),
            "total_beds": total_beds,
            "available_beds": available_beds,
            "occupied_beds": max(0, total_beds - available_beds),
            "doctors_on_duty": doctors_count,
            "today_opd_appointments": today_appointments,
            "pending_opd_appointments": pending_appointments,
            "scheduled_lab_bookings": scheduled_labs,
            "lab_revenue_today": float(lab_revenue_today),
            "departments": [_serialize_department(d) for d in depts[:50]],
        })


class HospitalDepartmentsAPIView(HospitalBaseAPIView):
    """GET / POST /api/operations/hospital/departments/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = HospitalDepartment.objects.filter(company=company).select_related("head_doctor")
        ward_type = request.query_params.get("ward_type")
        if ward_type:
            qs = qs.filter(ward_type=ward_type)
        return Response([_serialize_department(d) for d in qs])

    def post(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        name = str(request.data.get("name") or "").strip()
        if not name:
            return Response({"name": "Department name is required."}, status=400)

        ward_type = str(request.data.get("ward_type") or HospitalDepartment.WARD_OPD).strip()
        valid_ward_types = {c[0] for c in HospitalDepartment.WARD_TYPE_CHOICES}
        if ward_type not in valid_ward_types:
            return Response({"ward_type": "Invalid ward_type."}, status=400)

        try:
            total_beds = max(0, int(request.data.get("total_beds", 0) or 0))
            available_beds = max(0, int(request.data.get("available_beds", total_beds) if request.data.get("available_beds") is not None else total_beds))
        except (TypeError, ValueError):
            return Response({"detail": "Bed counts must be non-negative integers."}, status=400)

        head_doctor = None
        if request.data.get("head_doctor_id"):
            head_doctor = Doctor.objects.filter(company=company, pk=request.data["head_doctor_id"]).first()

        if HospitalDepartment.objects.filter(company=company, name__iexact=name).exists():
            return Response({"name": f"Department '{name}' already exists for this hospital."}, status=400)

        dept = HospitalDepartment.objects.create(
            company=company,
            name=name,
            ward_type=ward_type,
            floor_or_location=str(request.data.get("floor_or_location") or "").strip()[:120],
            total_beds=total_beds,
            available_beds=min(available_beds, total_beds),
            is_24_7=bool(request.data.get("is_24_7", ward_type in ("emergency", "icu"))),
            head_doctor=head_doctor,
            phone_extension=str(request.data.get("phone_extension") or "").strip()[:32],
            is_active=bool(request.data.get("is_active", True)),
        )
        return Response(_serialize_department(dept), status=201)


class HospitalDepartmentDetailAPIView(HospitalBaseAPIView):
    """PATCH / DELETE /api/operations/hospital/departments/<pk>/"""

    def patch(self, request, pk):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        dept = get_object_or_404(HospitalDepartment, pk=pk, company=company)

        if "name" in request.data and str(request.data["name"]).strip():
            dept.name = str(request.data["name"]).strip()[:150]
        if "ward_type" in request.data:
            wt = str(request.data["ward_type"]).strip()
            if wt in {c[0] for c in HospitalDepartment.WARD_TYPE_CHOICES}:
                dept.ward_type = wt
        if "floor_or_location" in request.data:
            dept.floor_or_location = str(request.data["floor_or_location"] or "").strip()[:120]
        if "total_beds" in request.data:
            dept.total_beds = max(0, int(request.data["total_beds"] or 0))
        if "available_beds" in request.data:
            dept.available_beds = max(0, int(request.data["available_beds"] or 0))
        if "is_24_7" in request.data:
            dept.is_24_7 = bool(request.data["is_24_7"])
        if "phone_extension" in request.data:
            dept.phone_extension = str(request.data["phone_extension"] or "").strip()[:32]
        if "is_active" in request.data:
            dept.is_active = bool(request.data["is_active"])
        if "head_doctor_id" in request.data:
            hd_id = request.data.get("head_doctor_id")
            dept.head_doctor = Doctor.objects.filter(company=company, pk=hd_id).first() if hd_id else None

        dept.save()
        return Response(_serialize_department(dept), status=200)

    def delete(self, request, pk):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        dept = get_object_or_404(HospitalDepartment, pk=pk, company=company)
        dept.delete()
        return Response(status=204)


class HospitalLabBookingsAPIView(HospitalBaseAPIView):
    """GET / POST /api/operations/hospital/lab-bookings/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = LabTestBooking.objects.filter(company=company).select_related("department", "patient")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response([_serialize_lab_booking(b) for b in qs[:100]])

    def post(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        patient_name = str(request.data.get("patient_name") or "").strip()
        patient_phone = str(request.data.get("patient_phone") or "").strip()
        test_name = str(request.data.get("test_name") or "").strip()

        if not patient_name or not test_name:
            return Response({"detail": "patient_name and test_name are required."}, status=400)

        patient = None
        if patient_phone:
            patient, _ = Patient.objects.get_or_create(
                company=company,
                phone=patient_phone,
                defaults={"name": patient_name},
            )

        department = None
        if request.data.get("department_id"):
            department = HospitalDepartment.objects.filter(company=company, pk=request.data["department_id"]).first()

        try:
            price = Decimal(str(request.data.get("price", "0.00") or "0.00"))
        except Exception:
            price = Decimal("0.00")

        booking = LabTestBooking.objects.create(
            company=company,
            patient=patient,
            department=department,
            patient_name=patient_name,
            patient_phone=patient_phone,
            test_name=test_name,
            price=max(Decimal("0.00"), price),
            scheduled_date=_parse_date(request.data.get("scheduled_date")) or timezone.localdate(),
            scheduled_time=str(request.data.get("scheduled_time") or "").strip()[:50],
            status=LabTestBooking.STATUS_SCHEDULED,
            notes=str(request.data.get("notes") or "").strip(),
            source="dashboard",
        )
        return Response(_serialize_lab_booking(booking), status=201)


class HospitalLabBookingStatusAPIView(HospitalBaseAPIView):
    """PATCH /api/operations/hospital/lab-bookings/<pk>/status/"""

    def patch(self, request, pk):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        booking = get_object_or_404(LabTestBooking, pk=pk, company=company)
        new_status = str(request.data.get("status") or "").strip().lower()
        valid = {c[0] for c in LabTestBooking.STATUS_CHOICES}
        if new_status not in valid:
            return Response({"status": f"Invalid status. Choose from: {', '.join(sorted(valid))}."}, status=400)

        booking.status = new_status
        if "notes" in request.data:
            booking.notes = str(request.data.get("notes") or "").strip()
        booking.save(update_fields=["status", "notes", "updated_at"])
        return Response(_serialize_lab_booking(booking), status=200)
