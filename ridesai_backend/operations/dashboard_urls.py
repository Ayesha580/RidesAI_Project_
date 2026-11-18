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
)

urlpatterns = [
    path("conversations/", DashboardConversationsAPIView.as_view(), name="dashboard-conversations"),
    path("conversations/<uuid:conversation_key>/", DashboardConversationDetailAPIView.as_view(), name="dashboard-conversation-detail"),
    path("conversations/<uuid:conversation_key>/reply/", DashboardConversationReplyAPIView.as_view(), name="dashboard-conversation-reply"),
    path("orders/", DashboardOrdersAPIView.as_view(), name="dashboard-orders"),
    path("orders/<int:order_id>/status/", DashboardOrderStatusAPIView.as_view(), name="dashboard-order-status"),
]
