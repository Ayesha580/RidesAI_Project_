from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    # Yeh fields aapko dashboard ke bahir list mein hi nazar aa jayengi
    list_display = ('id', 'subscription_status', 'is_manual_override', 'trial_ends_at', 'manual_override_expires_at')
    list_filter = ('subscription_status', 'is_manual_override')