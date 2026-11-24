"""Hospital Vertical URL Configuration."""

from django.urls import path
from operations.hospital_views import (
    HospitalSummaryAPIView,
    HospitalDepartmentsAPIView,
    HospitalDepartmentDetailAPIView,
    HospitalLabBookingsAPIView,
    HospitalLabBookingStatusAPIView,
)

urlpatterns = [
    path("summary/", HospitalSummaryAPIView.as_view(), name="hospital-summary"),
    path("departments/", HospitalDepartmentsAPIView.as_view(), name="hospital-departments"),
    path("departments/<int:pk>/", HospitalDepartmentDetailAPIView.as_view(), name="hospital-department-detail"),
    path("lab-bookings/", HospitalLabBookingsAPIView.as_view(), name="hospital-lab-bookings"),
    path("lab-bookings/<int:pk>/status/", HospitalLabBookingStatusAPIView.as_view(), name="hospital-lab-booking-status"),
]
