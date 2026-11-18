from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'subscription_status', 'is_manual_override', 'is_calling_enabled', 'printer_name', 'currency_symbol', 'auto_print_kot', 'auto_print_invoice', 'trial_ends_at', 'manual_override_expires_at')
    list_filter = ('subscription_status', 'is_manual_override', 'is_calling_enabled', 'auto_print_kot', 'auto_print_invoice')