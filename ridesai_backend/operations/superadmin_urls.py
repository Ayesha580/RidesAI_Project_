"""Platform Owner / Super Admin URL Configuration (/api/superadmin/)."""

from django.urls import path
from operations.superadmin_views import (
    SuperAdminOverviewAPIView,
    SuperAdminCompaniesAPIView,
    SuperAdminCompanyStatusAPIView,
    SuperAdminAuditLogsAPIView,
)

urlpatterns = [
    path("overview/", SuperAdminOverviewAPIView.as_view(), name="superadmin-overview"),
    path("companies/", SuperAdminCompaniesAPIView.as_view(), name="superadmin-companies"),
    path("companies/<int:pk>/status/", SuperAdminCompanyStatusAPIView.as_view(), name="superadmin-company-status"),
    path("audit-logs/", SuperAdminAuditLogsAPIView.as_view(), name="superadmin-audit-logs"),
]
