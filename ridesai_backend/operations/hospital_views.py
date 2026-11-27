"""
Hospital Vertical DRF Views (Strictly Multi-Tenant Isolated).
Provides CRUD endpoints for Hospital Departments & Ward Bed Availability,
Lab / Diagnostic Test Bookings, and real-time Hospital Operations Summary.
"""

from datetime import datetime
from decimal import Decimal
import math

from django.db import IntegrityError, transaction
from django.db.models import Sum
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
    HospitalBed,
    HospitalDepartment,
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

        appointments_today = 0
        try:
            appointments_today = Appointment.objects.filter(company=company, appointment_date=today).count()
        except Exception:
            appointments_today = 0

        active_ai_conversations = 0
        try:
            active_ai_conversations = AgentConversation.objects.filter(company=company).exclude(status="closed").count()
        except Exception:
            active_ai_conversations = 0

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
                "active_ai_conversations": active_ai_conversations,
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
