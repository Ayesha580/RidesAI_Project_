from django.urls import path
from operations.clinic_views import (
    ClinicDoctorsAPIView,
    ClinicDoctorDetailAPIView,
    ClinicPatientsAPIView,
    ClinicPatientDetailAPIView,
    ClinicAppointmentsAPIView,
    ClinicAppointmentStatusAPIView,
)

urlpatterns = [
    # Doctors
    path("doctors/", ClinicDoctorsAPIView.as_view(), name="clinic-doctors"),
    path("doctors/<int:pk>/", ClinicDoctorDetailAPIView.as_view(), name="clinic-doctor-detail"),
    # Patients
    path("patients/", ClinicPatientsAPIView.as_view(), name="clinic-patients"),
    path("patients/<int:pk>/", ClinicPatientDetailAPIView.as_view(), name="clinic-patient-detail"),
    # Appointments
    path("appointments/", ClinicAppointmentsAPIView.as_view(), name="clinic-appointments"),
    path("appointments/<int:pk>/status/", ClinicAppointmentStatusAPIView.as_view(), name="clinic-appointment-status"),
]
