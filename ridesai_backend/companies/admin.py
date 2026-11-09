from django.contrib import admin, messages

from billing.services import approve_company
from .models import Company, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "billing_cycle", "price", "currency", "polar_product_id", "is_active")
    list_editable = ("price", "currency", "polar_product_id", "is_active")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "plan", "is_approved", "payment_status", "message_limit", "messages_used", "access_expires_at")
    list_filter = ("is_approved", "payment_status", "status", "business_email_setup_status")
    search_fields = ("name", "email", "cnic", "business_email_address")
    list_editable = ("message_limit",)
    fieldsets = (
        ("Business", {"fields": ("name", "business_type", "address", "is_registered", "registration_number", "cnic", "email", "phone")}),
        ("Documents", {"fields": ("business_registration_document", "cnic_front", "cnic_back", "passport_size_photo")}),
        ("Approval", {"fields": ("plan", "status", "is_approved", "approved_at", "trial_ends_at")}),
        ("Manual access & usage", {"fields": ("payment_status", "initial_access_started_at", "access_expires_at", "renewal_due_at", "grace_ends_at", "message_limit", "messages_used", "message_period_started_at")}),
        ("Business email", {"fields": ("business_email_address", "business_email_domain", "business_email_setup_status")}),
    )
    actions = ["approve_selected"]

    @admin.action(description="Approve selected companies (starts one-month initial access)")
    def approve_selected(self, request, queryset):
        for company in queryset:
            approve_company(company)
        self.message_user(request, f"{queryset.count()} company approved.", messages.SUCCESS)