from django.urls import path
from .views import (OrderCatalogAPIView, OrderListCreateAPIView, OrderStatusAPIView, RiderDeliveryAPIView,
                    DeliveryAssignAPIView, DeliveryListAPIView, DeliveryRiderListAPIView, AgentSettingsAPIView,
                    AgentTogglePauseAPIView, AgentChatAPIView, AgentConversationListAPIView, OrderAssignAPIView,
                    OrderAutoAssignRiderAPIView,
                    PublicAgentChatAPIView, PublicAgentCatalogAPIView, PublicAgentConversationAPIView,
                    PublicAgentWidgetScriptAPIView, WhatsAppWebhookAPIView, WhatsAppSettingsAPIView)
from .calling_views import IncomingAICallWebhookView
from .evolution_views import ConnectWhatsAppView, EvolutionWebhookView

urlpatterns = [
    path("orders/catalog/", OrderCatalogAPIView.as_view(), name="order-catalog"),
    path("orders/", OrderListCreateAPIView.as_view(), name="orders"),
    path("orders/<int:order_id>/status/", OrderStatusAPIView.as_view(), name="order-status"),
    path("orders/<int:order_id>/assign/", OrderAssignAPIView.as_view(), name="order-assign"),
    path("orders/<int:order_id>/auto-assign-rider/", OrderAutoAssignRiderAPIView.as_view(), name="order-auto-assign-rider"),
    path("deliveries/my/", RiderDeliveryAPIView.as_view(), name="my-deliveries"),
    path("deliveries/", DeliveryListAPIView.as_view(), name="deliveries"),
    path("deliveries/assign/", DeliveryAssignAPIView.as_view(), name="assign-delivery"),
    path("deliveries/riders/", DeliveryRiderListAPIView.as_view(), name="delivery-riders"),
    path("agent/settings/", AgentSettingsAPIView.as_view(), name="agent-settings"),
    path("agent/toggle-pause/", AgentTogglePauseAPIView.as_view(), name="agent-toggle-pause"),
    path("agent/whatsapp-settings/", WhatsAppSettingsAPIView.as_view(), name="agent-whatsapp-settings"),
    path("agent/whatsapp_settings/", WhatsAppSettingsAPIView.as_view(), name="agent-whatsapp-settings-alt"),
    path("agent/chat/", AgentChatAPIView.as_view(), name="agent-chat"),
    path("whatsapp/webhook/", WhatsAppWebhookAPIView.as_view(), name="whatsapp-webhook"),
    path("whatsapp/connect/", ConnectWhatsAppView.as_view(), name="whatsapp-connect"),
    path("whatsapp/evolution-webhook/", EvolutionWebhookView.as_view(), name="evolution-webhook"),
    path("calling/webhook/", IncomingAICallWebhookView.as_view(), name="incoming-call-webhook"),
    path("calls/incoming/", IncomingAICallWebhookView.as_view(), name="incoming-call-twiml"),
    path("public/agent/<uuid:public_id>/catalog/", PublicAgentCatalogAPIView.as_view(), name="public-agent-catalog"),
    path("public/agent/<uuid:public_id>/conversation/<uuid:conversation_id>/", PublicAgentConversationAPIView.as_view(), name="public-agent-conversation"),
    path("public/agent/<uuid:public_id>/chat/", PublicAgentChatAPIView.as_view(), name="public-agent-chat"),
    path("widget/<uuid:public_id>.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js"),
    path("widget/<str:public_id>.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js-str"),
    path("public/agent/<uuid:public_id>/widget.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js-alt"),
    path("agent/conversations/", AgentConversationListAPIView.as_view(), name="agent-conversations"),
]
