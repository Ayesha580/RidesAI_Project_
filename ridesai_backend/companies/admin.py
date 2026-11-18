from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    # Yeh fields aapko dashboard ke bahir list mein hi nazar aa jayengi
    list_display = ('id', 'name', 'subscription_status', 'is_manual_override', 'is_calling_enabled', 'trial_ends_at', 'manual_override_expires_at')
    list_filter = ('subscription_status', 'is_manual_override', 'is_calling_enabled')