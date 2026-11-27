"""
Hospital Vertical DRF Views (Strictly Multi-Tenant Isolated).
Provides CRUD endpoints for Hospital Departments & Ward Bed Availability,
Lab / Diagnostic Test Bookings, and real-time Hospital Operations Summary.
"""

from datetime import datetime
from decimal import Decimal
import math

from django.db import IntegrityError, transaction
from django.db.models import Max, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.models import (
    AgentConversation,
    Appointment,
    Doctor,
    HospitalAdmission,
    HospitalAppointment,
    HospitalBed,
    HospitalDepartment,
    HospitalDoctor,
    HospitalDoctorSchedule,
    HospitalWard,
    LabTestBooking,
    Patient,
)


def _parse_date(val):
    if not val:
        return None
    if hasattr(val, "year"):
        return val
    try:
        return datetime.strptime(str(val).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(val):
    if not val:
        return None
    if hasattr(val, "hour") and hasattr(val, "minute"):
        return val
    raw = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def _serialize_department(dept: HospitalDepartment) -> dict:
    return {
        "id": dept.id,
        "name": dept.name,
        "code": dept.code or "",
        "ward_type": dept.ward_type,
        "ward_type_label": dept.get_ward_type_display(),
        "floor_or_location": dept.floor_or_location,
        "floor_location": dept.floor_or_location,
        "total_beds": dept.total_beds,
        "available_beds": dept.available_beds,
        "occupied_beds": max(0, dept.total_beds - dept.available_beds),
        "is_24_7": dept.is_24_7,
        "head_of_department": dept.head_of_department or (dept.head_doctor.name if dept.head_doctor else ""),
        "head_doctor_id": dept.head_doctor_id,
        "head_doctor_name": dept.head_doctor.name if dept.head_doctor else (dept.head_of_department or None),
        "phone_extension": dept.phone_extension,
        "phone_ext": dept.phone_extension,
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
            code=str(request.data.get("code") or "").strip().upper()[:24],
            ward_type=ward_type,
            floor_or_location=str(
                request.data.get("floor_location") or request.data.get("floor_or_location") or ""
            ).strip()[:120],
            total_beds=total_beds,
            available_beds=min(available_beds, total_beds),
            is_24_7=bool(request.data.get("is_24_7", ward_type in ("emergency", "icu"))),
            head_of_department=str(request.data.get("head_of_department") or "").strip()[:160],
            head_doctor=head_doctor,
            phone_extension=str(
                request.data.get("phone_ext") or request.data.get("phone_extension") or ""
            ).strip()[:32],
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
        if "code" in request.data:
            dept.code = str(request.data["code"] or "").strip()[:24]
        if "head_of_department" in request.data:
            dept.head_of_department = str(request.data["head_of_department"] or "").strip()[:150]
        if "ward_type" in request.data:
            wt = str(request.data["ward_type"]).strip()
            if wt in {c[0] for c in HospitalDepartment.WARD_TYPE_CHOICES}:
                dept.ward_type = wt
        if "floor_location" in request.data or "floor_or_location" in request.data:
            fl = request.data["floor_location"] if "floor_location" in request.data else request.data["floor_or_location"]
            dept.floor_or_location = str(fl or "").strip()[:120]
        if "total_beds" in request.data:
            dept.total_beds = max(0, int(request.data["total_beds"] or 0))
        if "available_beds" in request.data:
            dept.available_beds = max(0, int(request.data["available_beds"] or 0))
        if "is_24_7" in request.data:
            dept.is_24_7 = bool(request.data["is_24_7"])
        if "phone_ext" in request.data or "phone_extension" in request.data:
            pe = request.data["phone_ext"] if "phone_ext" in request.data else request.data["phone_extension"]
            dept.phone_extension = str(pe or "").strip()[:32]
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


# ============================================================================
# Hospital Module 1: Executive Dashboard, Wards, Live Bed Map & IPD Admissions
# ============================================================================

def _serialize_bed(bed: HospitalBed) -> dict:
    return {
        "id": bed.id,
        "ward_id": bed.ward_id,
        "ward_name": bed.ward.name if bed.ward else "",
        "ward_type": bed.ward.ward_type if bed.ward else "",
        "daily_bed_rate": float(bed.ward.daily_bed_rate) if bed.ward else 0.0,
        "bed_number": bed.bed_number,
        "status": bed.status,
        "status_label": bed.get_status_display(),
        "current_patient_name": bed.current_patient_name or "",
        "current_patient_phone": bed.current_patient_phone or "",
        "admitted_at": bed.admitted_at.isoformat() if bed.admitted_at else None,
        "attending_doctor": bed.attending_doctor or "",
        "admission_notes": bed.admission_notes or "",
    }


def _serialize_ward(ward: HospitalWard, include_beds: bool = True) -> dict:
    beds_list = list(ward.beds.all())
    total_beds = len(beds_list)
    available_beds = sum(1 for b in beds_list if b.status == HospitalBed.STATUS_AVAILABLE)
    occupied_beds = sum(1 for b in beds_list if b.status == HospitalBed.STATUS_OCCUPIED)
    cleaning_beds = sum(1 for b in beds_list if b.status == HospitalBed.STATUS_CLEANING)
    maintenance_beds = sum(1 for b in beds_list if b.status == HospitalBed.STATUS_MAINTENANCE)
    occ_pct = round((occupied_beds / total_beds) * 100.0, 1) if total_beds > 0 else 0.0

    data = {
        "id": ward.id,
        "name": ward.name,
        "department_id": ward.department_id,
        "department_name": ward.department.name if ward.department else "",
        "ward_type": ward.ward_type,
        "ward_type_label": ward.get_ward_type_display(),
        "daily_bed_rate": float(ward.daily_bed_rate or 0),
        "floor": ward.floor or "",
        "is_active": bool(ward.is_active),
        "total_beds": total_beds,
        "available_beds": available_beds,
        "occupied_beds": occupied_beds,
        "cleaning_beds": cleaning_beds,
        "maintenance_beds": maintenance_beds,
        "occupancy_pct": occ_pct,
    }
    if include_beds:
        data["beds"] = [_serialize_bed(b) for b in beds_list]
    return data


def _serialize_admission(adm: HospitalAdmission) -> dict:
    return {
        "id": adm.id,
        "bed_id": adm.bed_id,
        "bed_number": adm.bed.bed_number if adm.bed else "",
        "ward_name": adm.bed.ward.name if (adm.bed and adm.bed.ward) else "",
        "patient_name": adm.patient_name,
        "patient_phone": adm.patient_phone or "",
        "attending_doctor": adm.attending_doctor or "",
        "diagnosis": adm.diagnosis or "",
        "admitted_at": adm.admitted_at.isoformat() if adm.admitted_at else None,
        "discharged_at": adm.discharged_at.isoformat() if adm.discharged_at else None,
        "status": adm.status,
        "daily_rate": float(adm.daily_rate or 0),
        "total_bed_charges": float(adm.total_bed_charges or 0),
        "notes": adm.notes or "",
    }


class HospitalDashboardAPIView(HospitalBaseAPIView):
    """GET /api/operations/hospital/dashboard/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        today = timezone.localdate()
        total_departments = HospitalDepartment.objects.filter(company=company, is_active=True).count()
        wards_qs = (
            HospitalWard.objects.filter(company=company, is_active=True)
            .select_related("department")
            .prefetch_related("beds")
            .order_by("name")
        )
        wards = list(wards_qs)
        total_wards = len(wards)

        ward_summary = [_serialize_ward(w, include_beds=False) for w in wards]
        total_beds = sum(w["total_beds"] for w in ward_summary)
        available_beds = sum(w["available_beds"] for w in ward_summary)
        occupied_beds = sum(w["occupied_beds"] for w in ward_summary)
        cleaning_beds = sum(w["cleaning_beds"] for w in ward_summary)
        maintenance_beds = sum(w["maintenance_beds"] for w in ward_summary)
        bed_occupancy_pct = round((occupied_beds / total_beds) * 100.0, 1) if total_beds > 0 else 0.0

        admissions_qs = HospitalAdmission.objects.filter(company=company).select_related("bed__ward")
        active_admissions_count = admissions_qs.filter(status=HospitalAdmission.STATUS_ADMITTED).count()
        admissions_today = admissions_qs.filter(admitted_at__date=today).count()
        discharges_today = admissions_qs.filter(
            status=HospitalAdmission.STATUS_DISCHARGED,
            discharged_at__date=today,
        ).count()
        recent_admissions = [_serialize_admission(a) for a in admissions_qs.order_by("-admitted_at")[:8]]

        hosp_appts_today = HospitalAppointment.objects.filter(company=company, appointment_date=today)
        today_appointments = hosp_appts_today.exclude(status=HospitalAppointment.STATUS_CANCELLED).count()
        waiting_in_opd = hosp_appts_today.filter(
            status__in=[HospitalAppointment.STATUS_BOOKED, HospitalAppointment.STATUS_CHECKED_IN]
        ).count()
        today_opd_revenue = float(
            hosp_appts_today.filter(payment_status=HospitalAppointment.PAYMENT_PAID)
            .exclude(status=HospitalAppointment.STATUS_CANCELLED)
            .aggregate(total=Sum("consultation_fee"))
            .get("total")
            or Decimal("0.00")
        )
        appointments_today = today_appointments
        if appointments_today == 0:
            try:
                appointments_today = Appointment.objects.filter(company=company, appointment_date=today).count()
            except Exception:
                appointments_today = 0

        active_ai_conversations = 0
        try:
            active_ai_conversations = AgentConversation.objects.filter(company=company).exclude(status="closed").count()
        except Exception:
            active_ai_conversations = 0

        docs_qs = HospitalDoctor.objects.filter(company=company, is_active=True)
        total_doctors = docs_qs.count()
        doctors_available_today = docs_qs.filter(
            availability_status__in=[HospitalDoctor.STATUS_AVAILABLE, HospitalDoctor.STATUS_IN_OPD]
        ).count()

        return Response({
            "kpis": {
                "total_departments": total_departments,
                "total_wards": total_wards,
                "total_beds": total_beds,
                "available_beds": available_beds,
                "occupied_beds": occupied_beds,
                "cleaning_beds": cleaning_beds,
                "maintenance_beds": maintenance_beds,
                "bed_occupancy_pct": bed_occupancy_pct,
                "active_admissions_count": active_admissions_count,
                "admissions_today": admissions_today,
                "discharges_today": discharges_today,
                "appointments_today": appointments_today,
                "today_appointments": today_appointments,
                "waiting_in_opd": waiting_in_opd,
                "today_opd_revenue": today_opd_revenue,
                "active_ai_conversations": active_ai_conversations,
                "total_doctors": total_doctors,
                "doctors_available_today": doctors_available_today,
            },
            "ward_occupancy_summary": ward_summary,
            "recent_admissions": recent_admissions,
        }, status=200)


class HospitalWardsAPIView(HospitalBaseAPIView):
    """GET / POST /api/operations/hospital/wards/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        qs = (
            HospitalWard.objects.filter(company=company)
            .select_related("department")
            .prefetch_related("beds")
            .order_by("name")
        )
        return Response([_serialize_ward(w, include_beds=True) for w in qs], status=200)

    def post(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        name = str(request.data.get("name") or "").strip()[:160]
        if not name:
            return Response({"name": "Ward name is required."}, status=400)

        ward_type = str(request.data.get("ward_type") or HospitalWard.WARD_GENERAL).strip().lower()
        valid_types = {c[0] for c in HospitalWard.WARD_TYPE_CHOICES}
        if ward_type not in valid_types:
            ward_type = HospitalWard.WARD_GENERAL

        try:
            daily_rate = max(Decimal("0.00"), Decimal(str(request.data.get("daily_bed_rate", "0.00") or "0.00")))
        except Exception:
            daily_rate = Decimal("0.00")

        dept = None
        dept_id = request.data.get("department_id")
        if dept_id is not None and str(dept_id).strip() != "":
            dept = get_object_or_404(HospitalDepartment, pk=dept_id, company=company)

        try:
            auto_create_beds = max(0, min(200, int(request.data.get("auto_create_beds") or 0)))
        except (TypeError, ValueError):
            auto_create_beds = 0

        raw_prefix = str(request.data.get("bed_prefix") or "").strip().upper()
        if not raw_prefix:
            raw_prefix = "".join(ch for ch in name.upper() if ch.isalnum())[:3] or "BED"

        with transaction.atomic():
            ward = HospitalWard.objects.create(
                company=company,
                department=dept,
                name=name,
                ward_type=ward_type,
                daily_bed_rate=daily_rate,
                floor=str(request.data.get("floor") or "").strip()[:80],
                is_active=bool(request.data.get("is_active", True)),
            )
            if auto_create_beds > 0:
                beds_to_create = [
                    HospitalBed(
                        company=company,
                        ward=ward,
                        bed_number=f"{raw_prefix}-{i:02d}",
                        status=HospitalBed.STATUS_AVAILABLE,
                    )
                    for i in range(1, auto_create_beds + 1)
                ]
                HospitalBed.objects.bulk_create(beds_to_create)

        ward = HospitalWard.objects.select_related("department").prefetch_related("beds").get(pk=ward.pk)
        return Response(_serialize_ward(ward, include_beds=True), status=201)


class HospitalWardDetailAPIView(HospitalBaseAPIView):
    """PATCH / DELETE /api/operations/hospital/wards/<pk>/"""

    def patch(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        ward = get_object_or_404(HospitalWard, pk=pk, company=company)
        if "name" in request.data and str(request.data["name"]).strip():
            ward.name = str(request.data["name"]).strip()[:160]
        if "ward_type" in request.data:
            wt = str(request.data["ward_type"]).strip().lower()
            if wt in {c[0] for c in HospitalWard.WARD_TYPE_CHOICES}:
                ward.ward_type = wt
        if "daily_bed_rate" in request.data:
            try:
                ward.daily_bed_rate = max(Decimal("0.00"), Decimal(str(request.data["daily_bed_rate"] or "0.00")))
            except Exception:
                pass
        if "floor" in request.data:
            ward.floor = str(request.data["floor"] or "").strip()[:80]
        if "department_id" in request.data:
            did = request.data.get("department_id")
            ward.department = get_object_or_404(HospitalDepartment, pk=did, company=company) if did else None
        if "is_active" in request.data:
            ward.is_active = bool(request.data["is_active"])
        ward.save()
        ward = HospitalWard.objects.select_related("department").prefetch_related("beds").get(pk=ward.pk)
        return Response(_serialize_ward(ward, include_beds=True), status=200)

    def delete(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        ward = get_object_or_404(HospitalWard, pk=pk, company=company)
        ward.delete()
        return Response(status=204)


class HospitalWardBedsAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/wards/<ward_id>/beds/"""

    def post(self, request, ward_id: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        ward = get_object_or_404(HospitalWard, pk=ward_id, company=company)
        bed_number = str(request.data.get("bed_number") or "").strip()[:40]
        if not bed_number:
            return Response({"bed_number": "Bed number is required."}, status=400)
        try:
            bed = HospitalBed.objects.create(
                company=company,
                ward=ward,
                bed_number=bed_number,
                status=HospitalBed.STATUS_AVAILABLE,
            )
        except IntegrityError:
            return Response({"bed_number": f"Bed '{bed_number}' already exists in this ward."}, status=400)
        return Response(_serialize_bed(bed), status=201)


class HospitalBedDetailAPIView(HospitalBaseAPIView):
    """PATCH / DELETE /api/operations/hospital/beds/<bed_id>/"""

    def patch(self, request, bed_id: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        bed = get_object_or_404(HospitalBed.objects.select_related("ward"), pk=bed_id, company=company)
        if "status" in request.data:
            new_st = str(request.data["status"] or "").strip().lower()
            valid = {c[0] for c in HospitalBed.STATUS_CHOICES}
            if new_st not in valid:
                return Response({"status": f"Invalid bed status '{new_st}'."}, status=400)
            if bed.status == HospitalBed.STATUS_OCCUPIED and new_st != HospitalBed.STATUS_OCCUPIED:
                return Response({"detail": "Discharge the patient before changing an occupied bed's status."}, status=409)
            bed.status = new_st
        if "bed_number" in request.data and str(request.data["bed_number"]).strip():
            bed.bed_number = str(request.data["bed_number"]).strip()[:40]
        bed.save()
        return Response(_serialize_bed(bed), status=200)

    def delete(self, request, bed_id: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        bed = get_object_or_404(HospitalBed, pk=bed_id, company=company)
        if bed.status == HospitalBed.STATUS_OCCUPIED:
            return Response({"detail": "Cannot delete an occupied bed. Discharge the patient first."}, status=409)
        bed.delete()
        return Response(status=204)


class HospitalBedAdmitAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/beds/<bed_id>/admit/ — Atomic IPD Admission"""

    def post(self, request, bed_id: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        patient_name = str(request.data.get("patient_name") or "").strip()[:160]
        if not patient_name:
            return Response({"patient_name": "Patient name is required."}, status=400)

        patient_phone = str(request.data.get("patient_phone") or "").strip()[:40]
        attending_doctor = str(request.data.get("attending_doctor") or "").strip()[:160]
        diagnosis = str(request.data.get("diagnosis") or "").strip()
        notes = str(request.data.get("notes") or request.data.get("admission_notes") or "").strip()

        with transaction.atomic():
            bed = get_object_or_404(
                HospitalBed.objects.select_for_update().select_related("ward"),
                pk=bed_id,
                company=company,
            )
            if bed.status != HospitalBed.STATUS_AVAILABLE:
                return Response(
                    {"detail": f"Bed {bed.bed_number} is currently '{bed.status}' and cannot be admitted."},
                    status=409,
                )
            now_ts = timezone.now()
            bed.status = HospitalBed.STATUS_OCCUPIED
            bed.current_patient_name = patient_name
            bed.current_patient_phone = patient_phone
            bed.attending_doctor = attending_doctor
            bed.admission_notes = notes or diagnosis
            bed.admitted_at = now_ts
            bed.save(
                update_fields=[
                    "status",
                    "current_patient_name",
                    "current_patient_phone",
                    "attending_doctor",
                    "admission_notes",
                    "admitted_at",
                    "updated_at",
                ]
            )
            admission = HospitalAdmission.objects.create(
                company=company,
                bed=bed,
                patient_name=patient_name,
                patient_phone=patient_phone,
                attending_doctor=attending_doctor,
                diagnosis=diagnosis,
                status=HospitalAdmission.STATUS_ADMITTED,
                daily_rate=bed.ward.daily_bed_rate if bed.ward else Decimal("0.00"),
                notes=notes,
            )

        return Response(
            {
                "bed": _serialize_bed(bed),
                "admission": _serialize_admission(admission),
            },
            status=201,
        )


class HospitalBedDischargeAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/beds/<bed_id>/discharge/ — Atomic IPD Discharge & Bed Billing"""

    def post(self, request, bed_id: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        discharge_notes = str(request.data.get("notes") or "").strip()

        with transaction.atomic():
            bed = get_object_or_404(
                HospitalBed.objects.select_for_update().select_related("ward"),
                pk=bed_id,
                company=company,
            )
            if bed.status != HospitalBed.STATUS_OCCUPIED:
                return Response(
                    {"detail": f"Bed {bed.bed_number} is not currently occupied."},
                    status=409,
                )

            now_ts = timezone.now()
            admission = (
                HospitalAdmission.objects.filter(
                    company=company,
                    bed=bed,
                    status=HospitalAdmission.STATUS_ADMITTED,
                )
                .order_by("-admitted_at")
                .first()
            )
            daily_rate = (
                admission.daily_rate
                if admission and admission.daily_rate is not None
                else (bed.ward.daily_bed_rate if bed.ward else Decimal("0.00"))
            )
            start_ts = (admission.admitted_at if admission else bed.admitted_at) or now_ts
            elapsed_seconds = max(0.0, (now_ts - start_ts).total_seconds())
            stay_days = max(1, math.ceil(elapsed_seconds / 86400.0)) if elapsed_seconds > 0 else 1
            total_charges = (Decimal(stay_days) * daily_rate).quantize(Decimal("0.01"))

            if admission:
                admission.status = HospitalAdmission.STATUS_DISCHARGED
                admission.discharged_at = now_ts
                admission.total_bed_charges = total_charges
                if discharge_notes:
                    admission.notes = (
                        f"{admission.notes} | Discharge: {discharge_notes}"
                        if admission.notes
                        else f"Discharge: {discharge_notes}"
                    )
                admission.save(update_fields=["status", "discharged_at", "total_bed_charges", "notes"])
            else:
                admission = HospitalAdmission.objects.create(
                    company=company,
                    bed=bed,
                    patient_name=bed.current_patient_name or "Patient",
                    patient_phone=bed.current_patient_phone or "",
                    attending_doctor=bed.attending_doctor or "",
                    status=HospitalAdmission.STATUS_DISCHARGED,
                    discharged_at=now_ts,
                    daily_rate=daily_rate,
                    total_bed_charges=total_charges,
                    notes=discharge_notes,
                )

            bed.status = HospitalBed.STATUS_CLEANING
            bed.current_patient_name = ""
            bed.current_patient_phone = ""
            bed.attending_doctor = ""
            bed.admission_notes = ""
            bed.admitted_at = None
            bed.save(
                update_fields=[
                    "status",
                    "current_patient_name",
                    "current_patient_phone",
                    "attending_doctor",
                    "admission_notes",
                    "admitted_at",
                    "updated_at",
                ]
            )

        return Response(
            {
                "bed": _serialize_bed(bed),
                "admission": _serialize_admission(admission),
                "stay_days": stay_days,
                "total_bed_charges": float(total_charges),
            },
            status=200,
        )


# ============================================================================
# Hospital Module 2: Doctors Directory & Weekly OPD Schedules
# ============================================================================

DAY_ORDER = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DAY_LABELS = dict(HospitalDoctorSchedule.DAY_CHOICES)


def _parse_time_str(val):
    if not val:
        return None
    if hasattr(val, "hour"):
        return val
    s = str(val).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _serialize_doctor(doc: HospitalDoctor) -> dict:
    scheds = sorted(
        list(doc.schedules.filter(is_active=True)),
        key=lambda s: (DAY_ORDER.get(s.day_of_week, 9), s.start_time),
    )
    return {
        "id": doc.id,
        "department_id": doc.department_id,
        "department_name": doc.department.name if doc.department else "",
        "full_name": doc.full_name,
        "specialization": doc.specialization or "",
        "qualification": doc.qualification or "",
        "license_number": doc.license_number or "",
        "pmdc_number": doc.license_number or "",
        "phone": doc.phone or "",
        "email": doc.email or "",
        "consultation_fee": float(doc.consultation_fee or 0),
        "follow_up_fee": float(doc.follow_up_fee or 0),
        "slot_duration_minutes": int(doc.slot_duration_minutes or 15),
        "availability_status": doc.availability_status,
        "availability_label": doc.get_availability_status_display(),
        "room_number": doc.room_number or "",
        "bio": doc.bio or "",
        "is_active": bool(doc.is_active),
        "schedules": [
            {
                "id": s.id,
                "day_of_week": s.day_of_week,
                "day_label": DAY_LABELS.get(s.day_of_week, s.day_of_week.title()),
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                "max_patients": int(s.max_patients or 20),
                "is_active": bool(s.is_active),
            }
            for s in scheds
        ],
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def _sync_doctor_schedules(company, doctor: HospitalDoctor, schedules_payload):
    if not isinstance(schedules_payload, list):
        return
    valid_days = set(DAY_ORDER.keys())
    doctor.schedules.all().delete()
    seen = set()
    to_create = []
    for row in schedules_payload:
        if not isinstance(row, dict):
            continue
        day = str(row.get("day_of_week") or "").strip().lower()[:3]
        if day not in valid_days:
            continue
        start_t = _parse_time_str(row.get("start_time"))
        end_t = _parse_time_str(row.get("end_time"))
        if not start_t or not end_t:
            continue
        key = (day, start_t)
        if key in seen:
            continue
        seen.add(key)
        try:
            max_p = max(1, int(row.get("max_patients") or 20))
        except (TypeError, ValueError):
            max_p = 20
        to_create.append(
            HospitalDoctorSchedule(
                company=company,
                doctor=doctor,
                day_of_week=day,
                start_time=start_t,
                end_time=end_t,
                max_patients=max_p,
                is_active=bool(row.get("is_active", True)),
            )
        )
    if to_create:
        HospitalDoctorSchedule.objects.bulk_create(to_create)


class HospitalDoctorsAPIView(HospitalBaseAPIView):
    """GET / POST /api/operations/hospital/doctors/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        qs = (
            HospitalDoctor.objects.filter(company=company, is_active=True)
            .select_related("department")
            .prefetch_related("schedules")
            .order_by("full_name")
        )
        dept_id = request.query_params.get("department_id")
        if dept_id and str(dept_id).strip().isdigit():
            qs = qs.filter(department_id=int(dept_id))
        avail = str(request.query_params.get("availability_status") or "").strip().lower()
        if avail and avail != "all":
            qs = qs.filter(availability_status=avail)
        search = str(request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search)
                | Q(specialization__icontains=search)
                | Q(qualification__icontains=search)
                | Q(room_number__icontains=search)
            )
        return Response([_serialize_doctor(d) for d in qs], status=200)

    def post(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        full_name = str(request.data.get("full_name") or "").strip()[:160]
        if not full_name:
            return Response({"full_name": "Doctor full name is required."}, status=400)

        dept = None
        dept_id = request.data.get("department_id")
        if dept_id is not None and str(dept_id).strip() != "":
            dept = get_object_or_404(HospitalDepartment, pk=dept_id, company=company)

        avail = str(request.data.get("availability_status") or HospitalDoctor.STATUS_AVAILABLE).strip().lower()
        if avail not in {c[0] for c in HospitalDoctor.AVAILABILITY_CHOICES}:
            avail = HospitalDoctor.STATUS_AVAILABLE

        try:
            fee = max(Decimal("0.00"), Decimal(str(request.data.get("consultation_fee", "0.00") or "0.00")))
        except Exception:
            fee = Decimal("0.00")
        try:
            f_fee = max(Decimal("0.00"), Decimal(str(request.data.get("follow_up_fee", "0.00") or "0.00")))
        except Exception:
            f_fee = Decimal("0.00")
        try:
            slot_min = max(5, min(120, int(request.data.get("slot_duration_minutes") or 15)))
        except (TypeError, ValueError):
            slot_min = 15

        with transaction.atomic():
            doc = HospitalDoctor.objects.create(
                company=company,
                department=dept,
                full_name=full_name,
                specialization=str(request.data.get("specialization") or "").strip()[:160],
                qualification=str(request.data.get("qualification") or "").strip()[:200],
                license_number=str(
                    request.data.get("license_number") or request.data.get("pmdc_number") or ""
                ).strip()[:80],
                phone=str(request.data.get("phone") or "").strip()[:40],
                email=str(request.data.get("email") or "").strip()[:254],
                consultation_fee=fee,
                follow_up_fee=f_fee,
                slot_duration_minutes=slot_min,
                availability_status=avail,
                room_number=str(request.data.get("room_number") or "").strip()[:60],
                bio=str(request.data.get("bio") or "").strip(),
                is_active=True,
            )
            if "schedules" in request.data:
                _sync_doctor_schedules(company, doc, request.data.get("schedules"))

        doc = HospitalDoctor.objects.select_related("department").prefetch_related("schedules").get(pk=doc.pk)
        return Response(_serialize_doctor(doc), status=201)


class HospitalDoctorDetailAPIView(HospitalBaseAPIView):
    """PATCH / DELETE /api/operations/hospital/doctors/<pk>/"""

    def patch(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        doc = get_object_or_404(HospitalDoctor, pk=pk, company=company)

        with transaction.atomic():
            if "full_name" in request.data and str(request.data["full_name"]).strip():
                doc.full_name = str(request.data["full_name"]).strip()[:160]
            if "department_id" in request.data:
                did = request.data.get("department_id")
                doc.department = get_object_or_404(HospitalDepartment, pk=did, company=company) if did else None
            for field, max_len in [
                ("specialization", 160),
                ("qualification", 200),
                ("phone", 40),
                ("email", 254),
                ("room_number", 60),
            ]:
                if field in request.data:
                    setattr(doc, field, str(request.data.get(field) or "").strip()[:max_len])
            if "license_number" in request.data or "pmdc_number" in request.data:
                doc.license_number = str(
                    request.data.get("license_number") or request.data.get("pmdc_number") or ""
                ).strip()[:80]
            if "bio" in request.data:
                doc.bio = str(request.data.get("bio") or "").strip()
            if "consultation_fee" in request.data:
                try:
                    doc.consultation_fee = max(Decimal("0.00"), Decimal(str(request.data["consultation_fee"] or "0.00")))
                except Exception:
                    pass
            if "follow_up_fee" in request.data:
                try:
                    doc.follow_up_fee = max(Decimal("0.00"), Decimal(str(request.data["follow_up_fee"] or "0.00")))
                except Exception:
                    pass
            if "slot_duration_minutes" in request.data:
                try:
                    doc.slot_duration_minutes = max(5, min(120, int(request.data["slot_duration_minutes"] or 15)))
                except (TypeError, ValueError):
                    pass
            if "availability_status" in request.data:
                av = str(request.data["availability_status"] or "").strip().lower()
                if av in {c[0] for c in HospitalDoctor.AVAILABILITY_CHOICES}:
                    doc.availability_status = av
            if "is_active" in request.data:
                doc.is_active = bool(request.data["is_active"])
            doc.save()

            if "schedules" in request.data:
                _sync_doctor_schedules(company, doc, request.data.get("schedules"))

        doc = HospitalDoctor.objects.select_related("department").prefetch_related("schedules").get(pk=doc.pk)
        return Response(_serialize_doctor(doc), status=200)


    def delete(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        appt = get_object_or_404(HospitalAppointment, pk=pk, company=company)
        appt.delete()
        return Response(status=204)


class HospitalAppointmentStatusAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/appointments/<pk>/status/"""

    def post(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        appt = get_object_or_404(HospitalAppointment, pk=pk, company=company)
        next_status = str(request.data.get("status") or "").strip().lower()
        valid_statuses = {c[0] for c in HospitalAppointment.STATUS_CHOICES}

        update_fields = ["updated_at"]
        if next_status:
            if next_status not in valid_statuses:
                return Response(
                    {"status": f"Invalid status. Choose from: {', '.join(sorted(valid_statuses))}."},
                    status=400,
                )
            appt.status = next_status
            update_fields.append("status")

        if "payment_status" in request.data:
            ps = str(request.data.get("payment_status") or "").strip().lower()
            if ps in {c[0] for c in HospitalAppointment.PAYMENT_STATUS_CHOICES}:
                appt.payment_status = ps
                update_fields.append("payment_status")

        if len(update_fields) == 1:
            return Response({"detail": "Provide status or payment_status to update."}, status=400)

        appt.save(update_fields=update_fields)
        appt = HospitalAppointment.objects.select_related("doctor", "doctor__department", "department").get(pk=appt.pk)
        return Response(_serialize_appointment(appt), status=200)


class HospitalOpdQueueAPIView(HospitalBaseAPIView):
    """GET /api/operations/hospital/opd-queue/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        target_date = _parse_date(request.query_params.get("date")) or timezone.localdate()
        doctor_id = request.query_params.get("doctor_id")

        doctors_qs = HospitalDoctor.objects.filter(company=company, is_active=True).select_related("department").order_by("full_name")
        if doctor_id:
            doctors_qs = doctors_qs.filter(pk=doctor_id)
        doctors = list(doctors_qs)

        appts_qs = (
            HospitalAppointment.objects.filter(company=company, appointment_date=target_date)
            .select_related("doctor", "doctor__department", "department")
            .order_by("token_number", "id")
        )
        if doctor_id:
            appts_qs = appts_qs.filter(doctor_id=doctor_id)
        all_appts = list(appts_qs)

        by_doc = {}
        for a in all_appts:
            by_doc.setdefault(a.doctor_id, []).append(a)

        queues = []
        for doc in doctors:
            doc_appts = by_doc.get(doc.id, [])
            in_consult = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_IN_CONSULTATION]
            checked_in = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_CHECKED_IN]
            booked = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_BOOKED]
            completed = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_COMPLETED]

            current_appt = in_consult[0] if in_consult else None
            next_appt = checked_in[0] if checked_in else (booked[0] if booked else None)

            queues.append({
                "doctor_id": doc.id,
                "doctor_name": doc.full_name,
                "specialization": doc.specialization or "",
                "department_name": doc.department.name if doc.department else "",
                "room_number": doc.room_number or "",
                "availability_status": doc.availability_status,
                "consultation_fee": float(doc.consultation_fee or 0),
                "current_token": current_appt.token_number if current_appt else None,
                "current_appointment": _serialize_appointment(current_appt) if current_appt else None,
                "next_token": next_appt.token_number if next_appt else None,
                "next_appointment": _serialize_appointment(next_appt) if next_appt else None,
                "waiting_count": len(checked_in) + len(booked),
                "completed_count": len(completed),
                "total_count": len([a for a in doc_appts if a.status != HospitalAppointment.STATUS_CANCELLED]),
                "queue": [_serialize_appointment(a) for a in doc_appts],
            })

        # Sort doctors with active appointments first
        queues.sort(key=lambda q: (-q["total_count"], q["doctor_name"]))

        active_non_cancelled = [a for a in all_appts if a.status != HospitalAppointment.STATUS_CANCELLED]
        summary = {
            "today_appointments": len(active_non_cancelled),
            "waiting_in_opd": sum(
                1 for a in all_appts
                if a.status in (HospitalAppointment.STATUS_BOOKED, HospitalAppointment.STATUS_CHECKED_IN)
            ),
            "in_consultation": sum(
                1 for a in all_appts if a.status == HospitalAppointment.STATUS_IN_CONSULTATION
            ),
            "completed": sum(
                1 for a in all_appts if a.status == HospitalAppointment.STATUS_COMPLETED
            ),
            "today_opd_revenue": float(
                sum(
                    (a.consultation_fee or Decimal("0.00"))
                    for a in active_non_cancelled
                    if a.payment_status == HospitalAppointment.PAYMENT_PAID
                )
            ),
        }

        return Response({
            "date": target_date.isoformat(),
            "summary": summary,
            "queues": queues,
        }, status=200)

    def delete(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        doc = get_object_or_404(HospitalDoctor, pk=pk, company=company)
        doc.delete()
        return Response(status=204)


class HospitalDoctorStatusAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/doctors/<pk>/status/"""

    def post(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        doc = get_object_or_404(HospitalDoctor, pk=pk, company=company)
        next_status = str(request.data.get("availability_status") or request.data.get("status") or "").strip().lower()
        valid = {c[0] for c in HospitalDoctor.AVAILABILITY_CHOICES}
        if next_status not in valid:
            return Response(
                {"availability_status": f"Invalid status. Choose from: {', '.join(sorted(valid))}."},
                status=400,
            )
        doc.availability_status = next_status
        doc.save(update_fields=["availability_status", "updated_at"])
        doc = HospitalDoctor.objects.select_related("department").prefetch_related("schedules").get(pk=doc.pk)
        return Response(_serialize_doctor(doc), status=200)


# ============================================================================
# Hospital Module 3: OPD Appointments & Live Token Queue APIs
# ============================================================================

def _serialize_appointment(appt: HospitalAppointment) -> dict:
    return {
        "id": appt.id,
        "doctor_id": appt.doctor_id,
        "doctor_name": appt.doctor.full_name if appt.doctor else "",
        "doctor_specialization": appt.doctor.specialization if appt.doctor else "",
        "doctor_room": appt.doctor.room_number if appt.doctor else "",
        "department_id": appt.department_id,
        "department_name": appt.department.name if appt.department else (
            appt.doctor.department.name if (appt.doctor and appt.doctor.department) else ""
        ),
        "patient_name": appt.patient_name,
        "patient_phone": appt.patient_phone,
        "patient_age": appt.patient_age,
        "patient_gender": appt.patient_gender or "",
        "appointment_date": appt.appointment_date.isoformat() if appt.appointment_date else None,
        "appointment_time": appt.appointment_time.strftime("%H:%M") if appt.appointment_time else "",
        "token_number": appt.token_number,
        "token_display": f"#{appt.token_number:02d}",
        "visit_type": appt.visit_type,
        "visit_type_label": appt.get_visit_type_display(),
        "status": appt.status,
        "status_label": appt.get_status_display(),
        "consultation_fee": float(appt.consultation_fee or 0),
        "payment_status": appt.payment_status,
        "payment_status_label": appt.get_payment_status_display(),
        "booking_source": appt.booking_source,
        "booking_source_label": appt.get_booking_source_display(),
        "chief_complaint": appt.chief_complaint or "",
        "notes": appt.notes or "",
        "created_at": appt.created_at.isoformat() if appt.created_at else None,
        "updated_at": appt.updated_at.isoformat() if appt.updated_at else None,
    }


def create_hospital_appointment_atomic(
    *,
    company,
    doctor: HospitalDoctor,
    patient_name: str,
    patient_phone: str,
    appointment_date,
    appointment_time=None,
    department=None,
    patient_age=None,
    patient_gender: str = "",
    visit_type: str = HospitalAppointment.VISIT_NEW,
    consultation_fee=None,
    payment_status: str = HospitalAppointment.PAYMENT_UNPAID,
    booking_source: str = HospitalAppointment.SOURCE_WALK_IN,
    chief_complaint: str = "",
    notes: str = "",
) -> HospitalAppointment:
    """
    Atomically assigns the next sequential daily token_number for (company, doctor, appointment_date)
    by locking the parent HospitalDoctor row inside transaction.atomic().
    """
    valid_visit = {c[0] for c in HospitalAppointment.VISIT_TYPE_CHOICES}
    vt = visit_type if visit_type in valid_visit else HospitalAppointment.VISIT_NEW

    valid_pay = {c[0] for c in HospitalAppointment.PAYMENT_STATUS_CHOICES}
    ps = payment_status if payment_status in valid_pay else HospitalAppointment.PAYMENT_UNPAID

    valid_src = {c[0] for c in HospitalAppointment.BOOKING_SOURCE_CHOICES}
    src = booking_source if booking_source in valid_src else HospitalAppointment.SOURCE_WALK_IN

    with transaction.atomic():
        locked_doc = HospitalDoctor.objects.select_for_update().get(
            pk=doctor.pk, company=company
        )
        max_token = (
            HospitalAppointment.objects.filter(
                company=company,
                doctor=locked_doc,
                appointment_date=appointment_date,
            )
            .aggregate(max_tok=Max("token_number"))
            .get("max_tok")
            or 0
        )
        next_token = int(max_token) + 1

        resolved_dept = department if department is not None else locked_doc.department

        if consultation_fee is not None and str(consultation_fee).strip() != "":
            try:
                resolved_fee = max(Decimal("0.00"), Decimal(str(consultation_fee)))
            except Exception:
                resolved_fee = locked_doc.consultation_fee or Decimal("0.00")
        else:
            if vt == HospitalAppointment.VISIT_FOLLOW_UP and (locked_doc.follow_up_fee or Decimal("0.00")) > 0:
                resolved_fee = locked_doc.follow_up_fee
            else:
                resolved_fee = locked_doc.consultation_fee or Decimal("0.00")

        appt = HospitalAppointment.objects.create(
            company=company,
            doctor=locked_doc,
            department=resolved_dept,
            patient_name=str(patient_name).strip()[:255],
            patient_phone=str(patient_phone or "").strip()[:50],
            patient_age=patient_age,
            patient_gender=str(patient_gender or "").strip()[:20],
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            token_number=next_token,
            visit_type=vt,
            status=HospitalAppointment.STATUS_BOOKED,
            consultation_fee=resolved_fee,
            payment_status=ps,
            booking_source=src,
            chief_complaint=str(chief_complaint or "").strip(),
            notes=str(notes or "").strip(),
        )
    return HospitalAppointment.objects.select_related("doctor", "doctor__department", "department").get(pk=appt.pk)


class HospitalAppointmentsAPIView(HospitalBaseAPIView):
    """GET / POST /api/operations/hospital/appointments/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        today = timezone.localdate()
        qs = HospitalAppointment.objects.filter(company=company).select_related(
            "doctor", "doctor__department", "department"
        )

        date_param = request.query_params.get("date")
        today_only = str(request.query_params.get("today_only") or "").strip().lower() in ("1", "true", "yes")
        if date_param:
            parsed_dt = _parse_date(date_param)
            if parsed_dt:
                qs = qs.filter(appointment_date=parsed_dt)
        elif today_only:
            qs = qs.filter(appointment_date=today)

        doctor_id = request.query_params.get("doctor_id")
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        dept_id = request.query_params.get("department_id")
        if dept_id:
            qs = qs.filter(Q(department_id=dept_id) | Q(doctor__department_id=dept_id))

        status_param = str(request.query_params.get("status") or "").strip().lower()
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)

        search = str(request.query_params.get("search") or "").strip()
        if search:
            q_filter = (
                Q(patient_name__icontains=search)
                | Q(patient_phone__icontains=search)
                | Q(doctor__full_name__icontains=search)
                | Q(chief_complaint__icontains=search)
            )
            digits = search.lstrip("#").strip()
            if digits.isdigit():
                q_filter |= Q(token_number=int(digits))
            qs = qs.filter(q_filter)

        qs = qs.order_by("-appointment_date", "token_number", "id")
        items = [_serialize_appointment(a) for a in qs[:300]]

        # Today's KPI summary scoped to company
        today_qs = HospitalAppointment.objects.filter(company=company, appointment_date=today)
        summary = {
            "today_appointments": today_qs.exclude(status=HospitalAppointment.STATUS_CANCELLED).count(),
            "waiting_in_opd": today_qs.filter(
                status__in=[HospitalAppointment.STATUS_BOOKED, HospitalAppointment.STATUS_CHECKED_IN]
            ).count(),
            "in_consultation": today_qs.filter(status=HospitalAppointment.STATUS_IN_CONSULTATION).count(),
            "completed": today_qs.filter(status=HospitalAppointment.STATUS_COMPLETED).count(),
            "today_opd_revenue": float(
                today_qs.filter(payment_status=HospitalAppointment.PAYMENT_PAID)
                .exclude(status=HospitalAppointment.STATUS_CANCELLED)
                .aggregate(total=Sum("consultation_fee"))
                .get("total")
                or Decimal("0.00")
            ),
        }

        return Response({"count": len(items), "summary": summary, "results": items}, status=200)

    def post(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        doctor_id = request.data.get("doctor_id") or request.data.get("doctor")
        if not doctor_id:
            return Response({"doctor_id": "Please select a doctor."}, status=400)

        doctor = HospitalDoctor.objects.filter(company=company, pk=doctor_id).first()
        if not doctor:
            return Response({"doctor_id": "Doctor not found in your hospital."}, status=404)

        patient_name = str(request.data.get("patient_name") or "").strip()
        if not patient_name:
            return Response({"patient_name": "Patient name is required."}, status=400)

        patient_phone = str(request.data.get("patient_phone") or "").strip()
        appt_date = _parse_date(request.data.get("appointment_date")) or timezone.localdate()
        appt_time = _parse_time(request.data.get("appointment_time"))

        dept = None
        dept_id = request.data.get("department_id") or request.data.get("department")
        if dept_id:
            dept = HospitalDepartment.objects.filter(company=company, pk=dept_id).first()

        age_val = request.data.get("patient_age")
        patient_age = None
        if age_val not in (None, ""):
            try:
                patient_age = max(0, min(150, int(age_val)))
            except (TypeError, ValueError):
                patient_age = None

        appt = create_hospital_appointment_atomic(
            company=company,
            doctor=doctor,
            patient_name=patient_name,
            patient_phone=patient_phone,
            appointment_date=appt_date,
            appointment_time=appt_time,
            department=dept,
            patient_age=patient_age,
            patient_gender=str(request.data.get("patient_gender") or "").strip(),
            visit_type=str(request.data.get("visit_type") or HospitalAppointment.VISIT_NEW).strip().lower(),
            consultation_fee=request.data.get("consultation_fee"),
            payment_status=str(request.data.get("payment_status") or HospitalAppointment.PAYMENT_UNPAID).strip().lower(),
            booking_source=str(request.data.get("booking_source") or HospitalAppointment.SOURCE_WALK_IN).strip().lower(),
            chief_complaint=str(request.data.get("chief_complaint") or "").strip(),
            notes=str(request.data.get("notes") or "").strip(),
        )
        return Response(_serialize_appointment(appt), status=201)


class HospitalAppointmentDetailAPIView(HospitalBaseAPIView):
    """PATCH / DELETE /api/operations/hospital/appointments/<pk>/"""

    def patch(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        appt = get_object_or_404(HospitalAppointment, pk=pk, company=company)

        if "patient_name" in request.data and str(request.data["patient_name"]).strip():
            appt.patient_name = str(request.data["patient_name"]).strip()[:255]
        if "patient_phone" in request.data:
            appt.patient_phone = str(request.data["patient_phone"] or "").strip()[:50]
        if "patient_age" in request.data:
            raw_age = request.data["patient_age"]
            if raw_age in (None, ""):
                appt.patient_age = None
            else:
                try:
                    appt.patient_age = max(0, min(150, int(raw_age)))
                except (TypeError, ValueError):
                    pass
        if "patient_gender" in request.data:
            appt.patient_gender = str(request.data["patient_gender"] or "").strip()[:20]
        if "appointment_time" in request.data:
            appt.appointment_time = _parse_time(request.data["appointment_time"])
        if "visit_type" in request.data:
            vt = str(request.data["visit_type"] or "").strip().lower()
            if vt in {c[0] for c in HospitalAppointment.VISIT_TYPE_CHOICES}:
                appt.visit_type = vt
        if "status" in request.data:
            st = str(request.data["status"] or "").strip().lower()
            if st in {c[0] for c in HospitalAppointment.STATUS_CHOICES}:
                appt.status = st
        if "consultation_fee" in request.data and request.data["consultation_fee"] not in (None, ""):
            try:
                appt.consultation_fee = max(Decimal("0.00"), Decimal(str(request.data["consultation_fee"])))
            except Exception:
                pass
        if "payment_status" in request.data:
            ps = str(request.data["payment_status"] or "").strip().lower()
            if ps in {c[0] for c in HospitalAppointment.PAYMENT_STATUS_CHOICES}:
                appt.payment_status = ps
        if "chief_complaint" in request.data:
            appt.chief_complaint = str(request.data["chief_complaint"] or "").strip()
        if "notes" in request.data:
            appt.notes = str(request.data["notes"] or "").strip()
        if "department_id" in request.data:
            d_id = request.data.get("department_id")
            appt.department = (
                HospitalDepartment.objects.filter(company=company, pk=d_id).first() if d_id else None
            )

        appt.save()
        appt = HospitalAppointment.objects.select_related("doctor", "doctor__department", "department").get(pk=appt.pk)
        return Response(_serialize_appointment(appt), status=200)

    def delete(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)
        appt = get_object_or_404(HospitalAppointment, pk=pk, company=company)
        appt.delete()
        return Response(status=204)


class HospitalAppointmentStatusAPIView(HospitalBaseAPIView):
    """POST /api/operations/hospital/appointments/<pk>/status/"""

    def post(self, request, pk: int):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        appt = get_object_or_404(HospitalAppointment, pk=pk, company=company)
        next_status = str(request.data.get("status") or "").strip().lower()
        valid_statuses = {c[0] for c in HospitalAppointment.STATUS_CHOICES}

        update_fields = ["updated_at"]
        if next_status:
            if next_status not in valid_statuses:
                return Response(
                    {"status": f"Invalid status. Choose from: {', '.join(sorted(valid_statuses))}."},
                    status=400,
                )
            appt.status = next_status
            update_fields.append("status")

        if "payment_status" in request.data:
            ps = str(request.data.get("payment_status") or "").strip().lower()
            if ps in {c[0] for c in HospitalAppointment.PAYMENT_STATUS_CHOICES}:
                appt.payment_status = ps
                update_fields.append("payment_status")

        if len(update_fields) == 1:
            return Response({"detail": "Provide status or payment_status to update."}, status=400)

        appt.save(update_fields=update_fields)
        appt = HospitalAppointment.objects.select_related("doctor", "doctor__department", "department").get(pk=appt.pk)
        return Response(_serialize_appointment(appt), status=200)


class HospitalOpdQueueAPIView(HospitalBaseAPIView):
    """GET /api/operations/hospital/opd-queue/"""

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return Response({"detail": "No company associated with this account."}, status=403)

        target_date = _parse_date(request.query_params.get("date")) or timezone.localdate()
        doctor_id = request.query_params.get("doctor_id")

        doctors_qs = HospitalDoctor.objects.filter(company=company, is_active=True).select_related("department").order_by("full_name")
        if doctor_id:
            doctors_qs = doctors_qs.filter(pk=doctor_id)
        doctors = list(doctors_qs)

        appts_qs = (
            HospitalAppointment.objects.filter(company=company, appointment_date=target_date)
            .select_related("doctor", "doctor__department", "department")
            .order_by("token_number", "id")
        )
        if doctor_id:
            appts_qs = appts_qs.filter(doctor_id=doctor_id)
        all_appts = list(appts_qs)

        by_doc = {}
        for a in all_appts:
            by_doc.setdefault(a.doctor_id, []).append(a)

        queues = []
        for doc in doctors:
            doc_appts = by_doc.get(doc.id, [])
            in_consult = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_IN_CONSULTATION]
            checked_in = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_CHECKED_IN]
            booked = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_BOOKED]
            completed = [a for a in doc_appts if a.status == HospitalAppointment.STATUS_COMPLETED]

            current_appt = in_consult[0] if in_consult else None
            next_appt = checked_in[0] if checked_in else (booked[0] if booked else None)

            queues.append({
                "doctor_id": doc.id,
                "doctor_name": doc.full_name,
                "specialization": doc.specialization or "",
                "department_name": doc.department.name if doc.department else "",
                "room_number": doc.room_number or "",
                "availability_status": doc.availability_status,
                "consultation_fee": float(doc.consultation_fee or 0),
                "current_token": current_appt.token_number if current_appt else None,
                "current_appointment": _serialize_appointment(current_appt) if current_appt else None,
                "next_token": next_appt.token_number if next_appt else None,
                "next_appointment": _serialize_appointment(next_appt) if next_appt else None,
                "waiting_count": len(checked_in) + len(booked),
                "completed_count": len(completed),
                "total_count": len([a for a in doc_appts if a.status != HospitalAppointment.STATUS_CANCELLED]),
                "queue": [_serialize_appointment(a) for a in doc_appts],
            })

        # Sort doctors with active appointments first
        queues.sort(key=lambda q: (-q["total_count"], q["doctor_name"]))

        active_non_cancelled = [a for a in all_appts if a.status != HospitalAppointment.STATUS_CANCELLED]
        summary = {
            "today_appointments": len(active_non_cancelled),
            "waiting_in_opd": sum(
                1 for a in all_appts
                if a.status in (HospitalAppointment.STATUS_BOOKED, HospitalAppointment.STATUS_CHECKED_IN)
            ),
            "in_consultation": sum(
                1 for a in all_appts if a.status == HospitalAppointment.STATUS_IN_CONSULTATION
            ),
            "completed": sum(
                1 for a in all_appts if a.status == HospitalAppointment.STATUS_COMPLETED
            ),
            "today_opd_revenue": float(
                sum(
                    (a.consultation_fee or Decimal("0.00"))
                    for a in active_non_cancelled
                    if a.payment_status == HospitalAppointment.PAYMENT_PAID
                )
            ),
        }

        return Response({
            "date": target_date.isoformat(),
            "summary": summary,
            "queues": queues,
        }, status=200)
