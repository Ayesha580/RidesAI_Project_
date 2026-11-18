from django.urls import path
from .kitchen_rider_views import KitchenOrdersAPIView, KitchenOrderStatusAPIView

urlpatterns = [
    path("orders/", KitchenOrdersAPIView.as_view(), name="kitchen-orders"),
    path("orders/<int:order_id>/status/", KitchenOrderStatusAPIView.as_view(), name="kitchen-order-status"),
]
