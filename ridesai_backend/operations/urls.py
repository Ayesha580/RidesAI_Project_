from django.urls import include, path
from .views import (OrderCatalogAPIView, OrderListCreateAPIView, OrderStatusAPIView, RiderDeliveryAPIView,
                    DeliveryAssignAPIView, DeliveryListAPIView, DeliveryRiderListAPIView, AgentSettingsAPIView,
                    AgentTogglePauseAPIView, AgentChatAPIView, AgentConversationListAPIView, OrderAssignAPIView,
                    OrderAutoAssignRiderAPIView, OwnerBusinessAssistantAPIView,
                    PublicAgentChatAPIView, PublicAgentCatalogAPIView, PublicAgentConversationAPIView,
                    PublicAgentWidgetScriptAPIView, WhatsAppWebhookAPIView, WhatsAppSettingsAPIView)
from .calling_views import IncomingAICallWebhookView
from .evolution_views import (
    ConnectWhatsAppView,
    ReconnectWhatsAppView,
    DisconnectWhatsAppView,
    EvolutionWebhookView,
)
from .analytics_views import AnalyticsOverviewAPIView, AnalyticsExportCSVAPIView
from .notification_views import (
    NotificationTemplateListAPIView,
    NotificationTemplateDetailAPIView,
    NotificationTemplateResetAPIView,
)
from .faq_views import (
    SuggestedFAQListAPIView,
    SuggestedFAQApproveAPIView,
    SuggestedFAQDismissAPIView,
    ApprovedFAQListCreateAPIView,
    ApprovedFAQDetailAPIView,
)
from .table_views import RestaurantTableListCreateAPIView, RestaurantTableDetailAPIView
from .privacy_views import (
    DataRetentionPolicyAPIView,
    DataRetentionRunPurgeAPIView,
    CustomerConsentListCreateAPIView,
    CustomerEraseAPIView,
)
from .staff_supplier_views import (
    StaffAttendanceAPIView,
    SupplierListCreateAPIView,
    SupplierDetailAPIView,
)
from .restaurant_dashboard_views import RestaurantDashboardSummaryAPIView
from .restaurant_kds_views import RestaurantKDSListAPIView, RestaurantKDSBumpAPIView
from .customer_recall_views import CustomerLookupAPIView
from .restaurant_floor_views import (
    RestaurantFloorPlanAPIView,
    RestaurantTableStatusAPIView,
    RestaurantReservationListCreateAPIView,
    RestaurantReservationDetailAPIView,
    RestaurantReservationSeatAPIView,
    RestaurantReservationCompleteAPIView,
)

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
    path("whatsapp/reconnect/", ReconnectWhatsAppView.as_view(), name="whatsapp-reconnect"),
    path("whatsapp/disconnect/", DisconnectWhatsAppView.as_view(), name="whatsapp-disconnect"),
    path("whatsapp/evolution-webhook/", EvolutionWebhookView.as_view(), name="evolution-webhook"),
    path("whatsapp/evolution-webhook", EvolutionWebhookView.as_view(), name="evolution-webhook-noslash"),
    path("whatsapp/evolution-webhook/<path:event_slug>", EvolutionWebhookView.as_view(), name="evolution-webhook-event"),
    path("calling/webhook/", IncomingAICallWebhookView.as_view(), name="incoming-call-webhook"),
    path("calls/incoming/", IncomingAICallWebhookView.as_view(), name="incoming-call-twiml"),
    path("public/agent/<uuid:public_id>/catalog/", PublicAgentCatalogAPIView.as_view(), name="public-agent-catalog"),
    path("public/agent/<uuid:public_id>/conversation/<uuid:conversation_id>/", PublicAgentConversationAPIView.as_view(), name="public-agent-conversation"),
    path("public/agent/<uuid:public_id>/chat/", PublicAgentChatAPIView.as_view(), name="public-agent-chat"),
    path("widget/<uuid:public_id>.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js"),
    path("widget/<str:public_id>.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js-str"),
    path("public/agent/<uuid:public_id>/widget.js", PublicAgentWidgetScriptAPIView.as_view(), name="public-agent-widget-js-alt"),
    path("agent/conversations/", AgentConversationListAPIView.as_view(), name="agent-conversations"),
    path("owner/assistant/", OwnerBusinessAssistantAPIView.as_view(), name="owner-business-assistant"),
    path("analytics/overview/", AnalyticsOverviewAPIView.as_view(), name="analytics-overview"),
    path("analytics/export/csv/", AnalyticsExportCSVAPIView.as_view(), name="analytics-export-csv"),
    path("notifications/templates/", NotificationTemplateListAPIView.as_view(), name="notification-templates-list"),
    path("notifications/templates/<str:event_type>/", NotificationTemplateDetailAPIView.as_view(), name="notification-templates-detail"),
    path("notifications/templates/<str:event_type>/reset/", NotificationTemplateResetAPIView.as_view(), name="notification-templates-reset"),
    path("faqs/suggestions/", SuggestedFAQListAPIView.as_view(), name="faq-suggestions-list"),
    path("faqs/suggestions/<int:pk>/approve/", SuggestedFAQApproveAPIView.as_view(), name="faq-suggestions-approve"),
    path("faqs/suggestions/<int:pk>/dismiss/", SuggestedFAQDismissAPIView.as_view(), name="faq-suggestions-dismiss"),
    path("faqs/", ApprovedFAQListCreateAPIView.as_view(), name="approved-faqs-list"),
    path("faqs/<int:pk>/", ApprovedFAQDetailAPIView.as_view(), name="approved-faqs-detail"),
    path("tables/", RestaurantTableListCreateAPIView.as_view(), name="restaurant-tables-list"),
    path("tables/<int:pk>/", RestaurantTableDetailAPIView.as_view(), name="restaurant-tables-detail"),
    path("privacy/retention/", DataRetentionPolicyAPIView.as_view(), name="privacy-retention-policy"),
    path("privacy/retention/run-purge/", DataRetentionRunPurgeAPIView.as_view(), name="privacy-retention-run-purge"),
    path("privacy/consents/", CustomerConsentListCreateAPIView.as_view(), name="privacy-consents-list"),
    path("privacy/erase-customer/", CustomerEraseAPIView.as_view(), name="privacy-erase-customer"),
    path("attendance/", StaffAttendanceAPIView.as_view(), name="staff-attendance"),
    path("suppliers/", SupplierListCreateAPIView.as_view(), name="suppliers-list-create"),
    path("suppliers/<int:pk>/", SupplierDetailAPIView.as_view(), name="suppliers-detail"),
    path("restaurant/dashboard-summary/", RestaurantDashboardSummaryAPIView.as_view(), name="restaurant-dashboard-summary"),
    path("restaurant/kds/", RestaurantKDSListAPIView.as_view(), name="restaurant-kds-list"),
    path("restaurant/kds/<int:order_id>/bump/", RestaurantKDSBumpAPIView.as_view(), name="restaurant-kds-bump"),
    path("restaurant/floor-plan/", RestaurantFloorPlanAPIView.as_view(), name="restaurant-floor-plan"),
    path("restaurant/tables/<int:table_id>/status/", RestaurantTableStatusAPIView.as_view(), name="restaurant-table-status"),
    path("restaurant/reservations/", RestaurantReservationListCreateAPIView.as_view(), name="restaurant-reservations-list"),
    path("restaurant/reservations/<int:pk>/", RestaurantReservationDetailAPIView.as_view(), name="restaurant-reservations-detail"),
    path("restaurant/reservations/<int:pk>/seat/", RestaurantReservationSeatAPIView.as_view(), name="restaurant-reservations-seat"),
    path("restaurant/reservations/<int:pk>/complete/", RestaurantReservationCompleteAPIView.as_view(), name="restaurant-reservations-complete"),
    path("customers/lookup/", CustomerLookupAPIView.as_view(), name="customers-lookup"),
    path("hospital/", include("operations.hospital_urls")),
]
