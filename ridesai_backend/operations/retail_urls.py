"""
Retail / Store Platform URL Configuration.
"""

from django.urls import path
from operations.retail_views import (
    RetailFulfillmentAPIView,
    RetailFulfillmentStatusAPIView,
    RetailReturnsAPIView,
    RetailReturnStatusAPIView,
    RetailInventoryAlertsAPIView,
)

urlpatterns = [
    path("fulfillment/", RetailFulfillmentAPIView.as_view(), name="retail_fulfillment"),
    path("fulfillment/<int:order_id>/status/", RetailFulfillmentStatusAPIView.as_view(), name="retail_fulfillment_status"),
    path("returns/", RetailReturnsAPIView.as_view(), name="retail_returns"),
    path("returns/<int:pk>/status/", RetailReturnStatusAPIView.as_view(), name="retail_return_status"),
    path("inventory-alerts/", RetailInventoryAlertsAPIView.as_view(), name="retail_inventory_alerts"),
]
