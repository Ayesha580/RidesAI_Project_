"""
Clinic & Hospital Platform API Views: Doctors, Patients & Appointments.

Strictly multi-tenant isolated to request.user.company.
Protected by IsAuthenticated.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import Doctor, Patient, Appointment
from operations.notifications import send_status_notification

logger = logging.getLogger("operations.clinic")


def _get_request_company(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "company", None)
    return None


ALLOWED_APPOINTMENT_TRANSITIONS = {
    Appointment.STATUS_PENDING: {Appointment.STATUS_CONFIRMED, Appointment.STATUS_CANCELLED},
    Appointment.STATUS_CONFIRMED: {
        Appointment.STATUS_CHECKED_IN,
        Appointment.STATUS_COMPLETED,
        Appointment.STATUS_CANCELLED,
        Appointment.STATUS_NO_SHOW,
    },
    Appointment.STATUS_CHECKED_IN: {
        Appointment.STATUS_COMPLETED,
        Appointment.STATUS_CANCELLED,
    },
    Appointment.STATUS_COMPLETED: set(),
    Appointment.STATUS_CANCELLED: set(),
    Appointment.STATUS_NO_SHOW: set(),
}


def _serialize_doctor(doc: Doctor) -> dict:
    return {
        "id": doc.id,
        "name": doc.name,
        "specialty": doc.specialty,
        "qualification": doc.qualification,
        "consultation_fee": str(doc.consultation_fee),
        "available_days": doc.available_days,
        "available_hours": doc.available_hours,
        "is_active": doc.is_active,
        "total_appointments": getattr(doc, "total_appointments", 0),
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


def _serialize_patient(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "name": patient.name,
        "phone": patient.phone,
        "age": patient.age,
        "gender": patient.gender,
        "notes": patient.notes,
        "total_appointments": getattr(patient, "total_appointments", 0),
        "created_at": patient.created_at.isoformat(),
        "updated_at": patient.updated_at.isoformat(),
    }


def _serialize_appointment(apt: Appointment) -> dict:
    return {
        "id": apt.id,
        "appointment_number": apt.appointment_number,
        "doctor_id": apt.doctor_id,
        "doctor_name": apt.doctor.name if apt.doctor else "Unassigned",
        "doctor_specialty": apt.doctor.specialty if apt.doctor else "",
        "doctor_fee": str(apt.doctor.consultation_fee) if apt.doctor else "0.00",
        "patient_id": apt.patient_id,
        "patient_name": apt.patient_name,
        "patient_phone": apt.patient_phone,
        "appointment_date": (
            apt.appointment_date.isoformat()
            if hasattr(apt.appointment_date, "isoformat")
            else (str(apt.appointment_date) if apt.appointment_date else None)
        ),
        "appointment_time": apt.appointment_time,
        "reason": apt.reason,
        "status": apt.status,
        "status_display": apt.get_status_display(),
        "staff_notes": apt.staff_notes,
        "source": apt.source,
        "created_at": apt.created_at.isoformat(),
        "formatted_date": apt.created_at.strftime("%b %d, %Y %I:%M %p"),
        "updated_at": apt.updated_at.isoformat(),
    }


# ============================================================================
# Doctors API
# ============================================================================

class ClinicDoctorsAPIView(APIView):
    """
    GET /api/clinic/doctors/
    POST /api/clinic/doctors/
    Tenant-scoped list & creation for clinic doctors directory.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Doctor.objects.filter(company=company).annotate(total_appointments=Count("appointments"))

        is_active_param = request.query_params.get("is_active")
        if is_active_param is not None and is_active_param != "":
            qs = qs.filter(is_active=is_active_param.lower() in ("true", "1"))

        specialty = request.query_params.get("specialty", "").strip()
        if specialty:
            qs = qs.filter(specialty__iexact=specialty)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(specialty__icontains=search)
                | Q(qualification__icontains=search)
            )

        doctors = list(qs)
        summary = {
            "total_doctors": Doctor.objects.filter(company=company).count(),
            "active_doctors": Doctor.objects.filter(company=company, is_active=True).count(),
            "specialties_count": Doctor.objects.filter(company=company, is_active=True).values("specialty").distinct().count(),
        }

        return Response({
            "summary": summary,
            "doctors": [_serialize_doctor(d) for d in doctors],
        })

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        name = (data.get("name") or "").strip()
        specialty = (data.get("specialty") or "").strip()

        if not name:
            return Response({"error": "Doctor name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not specialty:
            return Response({"error": "Doctor specialty is required."}, status=status.HTTP_400_BAD_REQUEST)

        fee_raw = data.get("consultation_fee", 0)
        try:
            consultation_fee = Decimal(str(fee_raw) if fee_raw != "" else "0")
            if consultation_fee < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            return Response({"error": "Invalid consultation fee."}, status=status.HTTP_400_BAD_REQUEST)

        doctor = Doctor.objects.create(
            company=company,
            name=name,
            specialty=specialty,
            qualification=(data.get("qualification") or "").strip(),
            consultation_fee=consultation_fee,
            available_days=(data.get("available_days") or "Mon-Sat").strip(),
            available_hours=(data.get("available_hours") or "10:00 AM - 06:00 PM").strip(),
            is_active=bool(data.get("is_active", True)),
        )

        return Response(_serialize_doctor(doctor), status=status.HTTP_201_CREATED)


class ClinicDoctorDetailAPIView(APIView):
    """
    PATCH /api/clinic/doctors/<id>/
    DELETE /api/clinic/doctors/<id>/
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        doctor = get_object_or_404(Doctor, id=pk, company=company)
        data = request.data

        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return Response({"error": "Doctor name cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
            doctor.name = name

        if "specialty" in data:
            specialty = (data["specialty"] or "").strip()
            if not specialty:
                return Response({"error": "Specialty cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
            doctor.specialty = specialty

        if "qualification" in data:
            doctor.qualification = (data["qualification"] or "").strip()

        if "consultation_fee" in data:
            fee_raw = data["consultation_fee"]
            try:
                doctor.consultation_fee = Decimal(str(fee_raw) if fee_raw != "" else "0")
            except (InvalidOperation, ValueError):
                return Response({"error": "Invalid consultation fee."}, status=status.HTTP_400_BAD_REQUEST)

        if "available_days" in data:
            doctor.available_days = (data["available_days"] or "Mon-Sat").strip()

        if "available_hours" in data:
            doctor.available_hours = (data["available_hours"] or "10:00 AM - 06:00 PM").strip()

        if "is_active" in data:
            doctor.is_active = bool(data["is_active"])

        doctor.save()
        return Response(_serialize_doctor(doctor), status=status.HTTP_200_OK)

    def delete(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        doctor = get_object_or_404(Doctor, id=pk, company=company)
        doctor.delete()
        return Response({"message": "Doctor removed successfully."}, status=status.HTTP_200_OK)


# ============================================================================
# Patients API
# ============================================================================

class ClinicPatientsAPIView(APIView):
    """
    GET /api/clinic/patients/
    POST /api/clinic/patients/
    Tenant-scoped list & creation for clinic patients directory.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Patient.objects.filter(company=company).annotate(total_appointments=Count("appointments"))

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(notes__icontains=search)
            )

        patients = list(qs)
        summary = {
            "total_patients": Patient.objects.filter(company=company).count(),
        }

        return Response({
            "summary": summary,
            "patients": [_serialize_patient(p) for p in patients],
        })

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()

        if not name:
            return Response({"error": "Patient name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not phone:
            return Response({"error": "Patient phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        age = data.get("age")
        if age in ("", None):
            age = None
        else:
            try:
                age = int(age)
            except ValueError:
                return Response({"error": "Age must be a valid integer."}, status=status.HTTP_400_BAD_REQUEST)

        patient, created = Patient.objects.get_or_create(
            company=company,
            phone=phone,
            defaults={
                "name": name,
                "age": age,
                "gender": (data.get("gender") or "").strip(),
                "notes": (data.get("notes") or "").strip(),
            }
        )
        if not created:
            patient.name = name
            if age is not None:
                patient.age = age
            if "gender" in data:
                patient.gender = (data.get("gender") or "").strip()
            if "notes" in data:
                patient.notes = (data.get("notes") or "").strip()
            patient.save()

        return Response(_serialize_patient(patient), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ClinicPatientDetailAPIView(APIView):
    """
    PATCH /api/clinic/patients/<id>/
    DELETE /api/clinic/patients/<id>/
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        patient = get_object_or_404(Patient, id=pk, company=company)
        data = request.data

        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return Response({"error": "Patient name cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
            patient.name = name

        if "phone" in data:
            phone = (data["phone"] or "").strip()
            if not phone:
                return Response({"error": "Phone number cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
            # Check unique per company
            if Patient.objects.filter(company=company, phone=phone).exclude(id=patient.id).exists():
                return Response({"error": "Another patient with this phone number already exists."}, status=status.HTTP_400_BAD_REQUEST)
            patient.phone = phone

        if "age" in data:
            age = data["age"]
            if age in ("", None):
                patient.age = None
            else:
                try:
                    patient.age = int(age)
                except ValueError:
                    return Response({"error": "Age must be a valid integer."}, status=status.HTTP_400_BAD_REQUEST)

        if "gender" in data:
            patient.gender = (data["gender"] or "").strip()

        if "notes" in data:
            patient.notes = (data["notes"] or "").strip()

        patient.save()
        return Response(_serialize_patient(patient), status=status.HTTP_200_OK)

    def delete(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        patient = get_object_or_404(Patient, id=pk, company=company)
        patient.delete()
        return Response({"message": "Patient deleted successfully."}, status=status.HTTP_200_OK)


# ============================================================================
# Appointments API
# ============================================================================

class ClinicAppointmentsAPIView(APIView):
    """
    GET /api/clinic/appointments/
    POST /api/clinic/appointments/
    Tenant-scoped list & creation for clinic appointments.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        qs = Appointment.objects.filter(company=company).select_related("doctor", "patient")

        status_param = request.query_params.get("status", "").strip().lower()
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)

        doctor_id = request.query_params.get("doctor_id")
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        date_param = request.query_params.get("date")
        if date_param:
            qs = qs.filter(appointment_date=date_param)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(appointment_number__icontains=search)
                | Q(patient_name__icontains=search)
                | Q(patient_phone__icontains=search)
                | Q(doctor__name__icontains=search)
                | Q(doctor__specialty__icontains=search)
            )

        appointments = list(qs)
        all_company_apts = Appointment.objects.filter(company=company)
        summary = {
            "total": all_company_apts.count(),
            "pending": all_company_apts.filter(status=Appointment.STATUS_PENDING).count(),
            "confirmed": all_company_apts.filter(status=Appointment.STATUS_CONFIRMED).count(),
            "checked_in": all_company_apts.filter(status=Appointment.STATUS_CHECKED_IN).count(),
            "completed": all_company_apts.filter(status=Appointment.STATUS_COMPLETED).count(),
            "cancelled": all_company_apts.filter(status=Appointment.STATUS_CANCELLED).count(),
            "no_show": all_company_apts.filter(status=Appointment.STATUS_NO_SHOW).count(),
        }

        return Response({
            "summary": summary,
            "appointments": [_serialize_appointment(apt) for apt in appointments],
        })

    def post(self, request):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        patient_name = (data.get("patient_name") or "").strip()
        patient_phone = (data.get("patient_phone") or "").strip()

        if not patient_name:
            return Response({"error": "Patient name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not patient_phone:
            return Response({"error": "Patient phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        doctor = None
        doctor_id = data.get("doctor_id")
        if doctor_id:
            doctor = get_object_or_404(Doctor, id=doctor_id, company=company)

        # Get or create patient record
        patient = None
        patient_id = data.get("patient_id")
        if patient_id:
            patient = Patient.objects.filter(id=patient_id, company=company).first()
        if not patient:
            patient, _ = Patient.objects.get_or_create(
                company=company,
                phone=patient_phone,
                defaults={"name": patient_name}
            )

        appointment_date = data.get("appointment_date") or None
        appointment_time = (data.get("appointment_time") or "").strip()
        reason = (data.get("reason") or "").strip()
        staff_notes = (data.get("staff_notes") or "").strip()
        source = (data.get("source") or "dashboard").strip()

        apt = Appointment.objects.create(
            company=company,
            doctor=doctor,
            patient=patient,
            patient_name=patient_name,
            patient_phone=patient_phone,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status=Appointment.STATUS_PENDING,
            staff_notes=staff_notes,
            source=source,
        )

        return Response(_serialize_appointment(apt), status=status.HTTP_201_CREATED)


class ClinicAppointmentStatusAPIView(APIView):
    """
    PATCH /api/clinic/appointments/<id>/status/
    Strict forward-only state machine transition & automated WhatsApp notifications.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company = _get_request_company(request)
        if not company:
            return Response({"detail": "User has no associated company."}, status=status.HTTP_403_FORBIDDEN)

        apt = get_object_or_404(Appointment, id=pk, company=company)
        data = request.data
        new_status = (data.get("status") or "").strip().lower()
        staff_notes = (data.get("staff_notes") or "").strip()
        reason = (data.get("reason") or "").strip()

        if not new_status:
            return Response({"error": "New status is required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_choices = [c[0] for c in Appointment.STATUS_CHOICES]
        if new_status not in valid_choices:
            return Response(
                {"error": f"Invalid status '{new_status}'. Choices: {', '.join(valid_choices)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        current_status = apt.status
        if current_status == new_status:
            return Response(_serialize_appointment(apt), status=status.HTTP_200_OK)

        allowed = ALLOWED_APPOINTMENT_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            return Response(
                {
                    "error": (
                        f"Invalid appointment transition from '{current_status}' to '{new_status}'. "
                        f"Allowed next states: {list(allowed) or 'terminal state'}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        apt.status = new_status
        if staff_notes:
            apt.staff_notes = staff_notes
        apt.save()

        # Automated WhatsApp notification for confirmed, completed, cancelled
        if new_status in (Appointment.STATUS_CONFIRMED, Appointment.STATUS_COMPLETED, Appointment.STATUS_CANCELLED):
            try:
                send_status_notification(
                    company=company,
                    customer_phone=apt.patient_phone,
                    entity_type="appointment",
                    reference_id=apt.appointment_number,
                    new_status=new_status,
                    reason=reason or staff_notes or apt.reason or "",
                    previous_status=current_status,
                )
            except Exception as e:
                logger.error("[Clinic Notification ERROR] Failed to dispatch WhatsApp notification for appointment %s: %s", apt.appointment_number, e)

        return Response(_serialize_appointment(apt), status=status.HTTP_200_OK)
