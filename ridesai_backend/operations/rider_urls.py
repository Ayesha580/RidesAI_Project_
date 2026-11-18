from django.urls import path
from .kitchen_rider_views import RiderOrdersAPIView, RiderOrderStatusAPIView

urlpatterns = [
    path("orders/", RiderOrdersAPIView.as_view(), name="rider-orders"),
    path("orders/<int:order_id>/status/", RiderOrderStatusAPIView.as_view(), name="rider-order-status"),
]
