"""
URL Routing for Dashboard Endpoints (Phase 4).

Base URL: /api/dashboard/
"""

from django.urls import path
from .dashboard_views import (
    DashboardConversationsAPIView,
    DashboardConversationDetailAPIView,
    DashboardConversationReplyAPIView,
    DashboardOrdersAPIView,
    DashboardOrderStatusAPIView,
    DashboardOrderAutoAssignRiderAPIView,
    DashboardCallsAPIView,
    DashboardCallEventsAPIView,
    DashboardOrderReceiptAPIView,
    DashboardOrderPrintAPIView,
)

urlpatterns = [
    path("conversations/", DashboardConversationsAPIView.as_view(), name="dashboard-conversations"),
    path("conversations/<uuid:conversation_key>/", DashboardConversationDetailAPIView.as_view(), name="dashboard-conversation-detail"),
    path("conversations/<uuid:conversation_key>/reply/", DashboardConversationReplyAPIView.as_view(), name="dashboard-conversation-reply"),
    path("orders/", DashboardOrdersAPIView.as_view(), name="dashboard-orders"),
    path("orders/<int:order_id>/status/", DashboardOrderStatusAPIView.as_view(), name="dashboard-order-status"),
    path("orders/<int:order_pk>/auto-assign-rider/", DashboardOrderAutoAssignRiderAPIView.as_view(), name="dashboard-order-auto-assign-rider"),
    path("orders/<int:order_pk>/receipt/", DashboardOrderReceiptAPIView.as_view(), name="dashboard-order-receipt"),
    path("orders/<int:order_pk>/print/", DashboardOrderPrintAPIView.as_view(), name="dashboard-order-print"),
    path("calls/", DashboardCallsAPIView.as_view(), name="dashboard-calls"),
    path("calls/<int:call_pk>/events/", DashboardCallEventsAPIView.as_view(), name="dashboard-call-events"),
]
