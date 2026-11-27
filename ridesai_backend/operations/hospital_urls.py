"""Hospital Vertical URL Configuration."""

from django.urls import path
from operations.hospital_views import (
    HospitalSummaryAPIView,
    HospitalDashboardAPIView,
    HospitalDepartmentsAPIView,
    HospitalDepartmentDetailAPIView,
    HospitalWardsAPIView,
    HospitalWardDetailAPIView,
    HospitalWardBedsAPIView,
    HospitalBedDetailAPIView,
    HospitalBedAdmitAPIView,
    HospitalBedDischargeAPIView,
    HospitalLabBookingsAPIView,
    HospitalLabBookingStatusAPIView,
)

urlpatterns = [
    path("summary/", HospitalSummaryAPIView.as_view(), name="hospital-summary"),
    path("dashboard/", HospitalDashboardAPIView.as_view(), name="hospital-dashboard"),
    path("departments/", HospitalDepartmentsAPIView.as_view(), name="hospital-departments"),
    path("departments/<int:pk>/", HospitalDepartmentDetailAPIView.as_view(), name="hospital-department-detail"),
    path("wards/", HospitalWardsAPIView.as_view(), name="hospital-wards"),
    path("wards/<int:pk>/", HospitalWardDetailAPIView.as_view(), name="hospital-ward-detail"),
    path("wards/<int:ward_id>/beds/", HospitalWardBedsAPIView.as_view(), name="hospital-ward-beds"),
    path("beds/<int:bed_id>/", HospitalBedDetailAPIView.as_view(), name="hospital-bed-detail"),
    path("beds/<int:bed_id>/admit/", HospitalBedAdmitAPIView.as_view(), name="hospital-bed-admit"),
    path("beds/<int:bed_id>/discharge/", HospitalBedDischargeAPIView.as_view(), name="hospital-bed-discharge"),
    path("lab-bookings/", HospitalLabBookingsAPIView.as_view(), name="hospital-lab-bookings"),
    path("lab-bookings/<int:pk>/status/", HospitalLabBookingStatusAPIView.as_view(), name="hospital-lab-booking-status"),
]
