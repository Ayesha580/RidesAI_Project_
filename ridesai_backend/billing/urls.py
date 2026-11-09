from django.urls import path

from .views import (
    BillingOverviewAPIView,
    CancelSubscriptionAPIView,
    CompleteRenewalAPIView,
    CustomerSessionAPIView,
    PolarWebhookAPIView,
    PublicPlansAPIView,
    ManualPaymentSubmitAPIView, BusinessEmailSettingsAPIView, ManualPaymentAdminAPIView, ConsumeMessageAPIView,
    ResumeSubscriptionAPIView,SelectPlanAPIView
)

urlpatterns = [
    path("plans/", PublicPlansAPIView.as_view()),
    path("manual-payment/", ManualPaymentSubmitAPIView.as_view()),
    path("business-email/", BusinessEmailSettingsAPIView.as_view()),
    path("messages/consume/", ConsumeMessageAPIView.as_view()),
    path("admin/manual-payments/", ManualPaymentAdminAPIView.as_view()),
    path("admin/manual-payments/<int:payment_id>/", ManualPaymentAdminAPIView.as_view()),
    path("overview/", BillingOverviewAPIView.as_view()),
    path("customer-session/", CustomerSessionAPIView.as_view()),
    path("complete-renewal/", CompleteRenewalAPIView.as_view()),
    path("cancel/", CancelSubscriptionAPIView.as_view()),
    path("resume/", ResumeSubscriptionAPIView.as_view()),
    path("webhook/", PolarWebhookAPIView.as_view()),
    path("select-plan/", SelectPlanAPIView.as_view()),
]