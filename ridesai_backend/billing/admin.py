from django.contrib import admin
from .models import CheckoutSession, PaymentTransaction, WebhookEvent, ManualPayment
from .services import approve_manual_payment

@admin.register(ManualPayment)
class ManualPaymentAdmin(admin.ModelAdmin):
    list_display = ("company", "amount", "currency", "payment_reference", "status", "created_at", "reviewed_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("company__name", "company__email", "payment_reference")
    readonly_fields = ("submitted_by", "created_at", "reviewed_at", "reviewed_by")
    actions = ("approve_selected",)

    @admin.action(description="Approve selected manual payments and renew access for 30 days")
    def approve_selected(self, request, queryset):
        for payment in queryset.filter(status="pending"):
            approve_manual_payment(payment, request.user)

admin.site.register(CheckoutSession)
admin.site.register(PaymentTransaction)
admin.site.register(WebhookEvent)
