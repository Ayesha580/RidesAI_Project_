from django.urls import path
from .views import (OrderCatalogAPIView, OrderListCreateAPIView, OrderStatusAPIView, RiderDeliveryAPIView,
                    DeliveryAssignAPIView, DeliveryListAPIView, DeliveryRiderListAPIView, AgentSettingsAPIView, AgentChatAPIView,
                    AgentConversationListAPIView, OrderAssignAPIView, PublicAgentChatAPIView, PublicAgentCatalogAPIView, PublicAgentConversationAPIView)

urlpatterns = [
    path("orders/catalog/", OrderCatalogAPIView.as_view(), name="order-catalog"),
    path("orders/", OrderListCreateAPIView.as_view(), name="orders"),
    path("orders/<int:order_id>/status/", OrderStatusAPIView.as_view(), name="order-status"),
    path("orders/<int:order_id>/assign/", OrderAssignAPIView.as_view(), name="order-assign"),
    path("deliveries/my/", RiderDeliveryAPIView.as_view(), name="my-deliveries"),
    path("deliveries/", DeliveryListAPIView.as_view(), name="deliveries"),
    path("deliveries/assign/", DeliveryAssignAPIView.as_view(), name="assign-delivery"),
    path("deliveries/riders/", DeliveryRiderListAPIView.as_view(), name="delivery-riders"),
    path("agent/settings/", AgentSettingsAPIView.as_view(), name="agent-settings"),
    path("agent/chat/", AgentChatAPIView.as_view(), name="agent-chat"),
    path("public/agent/<uuid:public_id>/catalog/", PublicAgentCatalogAPIView.as_view(), name="public-agent-catalog"),
    path("public/agent/<uuid:public_id>/conversation/<uuid:conversation_id>/", PublicAgentConversationAPIView.as_view(), name="public-agent-conversation"),
    path("public/agent/<uuid:public_id>/chat/", PublicAgentChatAPIView.as_view(), name="public-agent-chat"),
    path("agent/conversations/", AgentConversationListAPIView.as_view(), name="agent-conversations"),
]
